"""
reddit_short_cleantest.py -- PRE-REGISTERED clean short-signal backtest.

PURPOSE
-------
The H2' result ("short liquid large-caps on WSB velocity spike": Sharpe 4.0 /
OOS 2.8 / 74% WR) used a HAND-PICKED exclusion list (SHORT_TICKER_EXCLUDE +
a GME/AMC date window) chosen AFTER seeing which names blew up. That is
in-sample selection and the Sharpe is not trustworthy.

This module re-runs the SAME signal/short mechanics with ZERO hand-picked
name exclusions. The ONLY universe filter is a mechanical rule defined a-priori
(below), applied blindly to every (ticker, signal-day):

================== PRE-REGISTERED MECHANICAL UNIVERSE FILTER ==================
Evaluated on each signal day D using ONLY data through D (no lookahead):
  1. Price on signal day  >= $10            (filters penny / low-float)
  2. 30-day ADV notional   >= $50M          (ADV = mean(close*volume) over the
                                             30 trading days ending at D)
  3. Market cap            >= $5B           (shares_outstanding * price via SEC
                                             EDGAR PIT; if shares unavailable,
                                             FALL BACK to the price+ADV proxy --
                                             i.e. rule 1&2 stand in for mcap, per
                                             task spec. Pass-rate impact of this
                                             fallback is reported explicitly.)
  4. NOT squeeze-prone:    30d realized vol  < 100% annualized
                           (realized vol = std(daily log returns, 30d) *
                            sqrt(252). This MECHANICALLY removes the meme/squeeze
                            names -- GME/AMC/BBBY/etc. run far above 100% annual
                            vol during their spikes -- WITHOUT naming any ticker.)
==============================================================================

SIGNAL (unchanged from H2'):
  velocity = mention_count / (20d trailing mean of mention_count)
  fire if velocity >= 2.0 AND mention_count >= 5.
ENTRY:  SHORT at next-day OPEN.
EXIT:   CLOSE on day (entry_idx + hold).  Hold sweep: 1,3,5,10.
COST:   4 bps one-way (8 bps round-trip) + borrow: 50 bps/yr accrued over the
        hold (hold/252 * 0.005 subtracted from the short return).
SIZING: equal weight, max 10 concurrent shorts. Same-day overflow -> take the
        highest velocity (mention_count / 20d_avg).

SHORT RETURN: short pnl = (entry_open / exit_close - 1)   [+ if price falls]
              net = short_pnl - roundtrip_cost - borrow.

Prices: runner.daily_bars_cache (Yahoo v8 adjclose split+div adj, + raw open).
  NOTE on adj vs raw: we hold 1-10 trading days. To keep entry(open)/exit(close)
  on the SAME price basis we use each bar's *adjclose* for the exit and the
  *adjusted open* (raw open scaled by adjclose/close) for entry, so a split or
  dividend inside the (tiny) hold window cannot fabricate PnL. For the 30d ADV /
  realized-vol / price filters we use adjclose-consistent fields too.

No hand-picked ticker list anywhere in this file. The ONLY way a name leaves the
universe is by failing a numeric, pre-registered threshold above.
"""

from __future__ import annotations

import sys
import sqlite3
import math
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import numpy as np
from runner.daily_bars_cache import get_daily

WORKSPACE = Path(__file__).parent
DB_PATH = WORKSPACE / "reddit_mentions.db"

# ---- Signal params (frozen, == H2') ----
VELOCITY_THRESHOLD = 2.0
MIN_MENTIONS = 5
LOOKBACK_DAYS = 20

# ---- Pre-registered mechanical filter thresholds (frozen) ----
MIN_PRICE = 10.0
MIN_ADV_NOTIONAL = 50_000_000.0      # $50M
ADV_WINDOW = 30                      # trading days
MIN_MARKET_CAP = 5_000_000_000.0     # $5B
RVOL_WINDOW = 30                     # trading days
MAX_REALIZED_VOL = 1.00              # 100% annualized

# ---- Execution params (frozen) ----
COST_BPS_ONEWAY = 4.0
BORROW_BPS_PER_YR = 50.0
MAX_POSITIONS = 10
HOLDS = [1, 3, 5, 10]

# Cuts
FULL_START, FULL_END = "2020-01-01", "2024-12-31"
OOS_START = "2023-01-01"   # task: cleanest OOS (collection was 2023H1)


# ---------------------------------------------------------------------------
# Price frame: per ticker, an aligned DataFrame indexed by ISO date with
# columns: open_adj, close_adj, dollar_vol, logret. Built once, memoized.
# ---------------------------------------------------------------------------
_PX_MEMO: dict = {}


def get_px_frame(ticker: str):
    if ticker in _PX_MEMO:
        return _PX_MEMO[ticker]
    try:
        bars = get_daily(ticker)
    except Exception:
        _PX_MEMO[ticker] = None
        return None
    if not bars:
        _PX_MEMO[ticker] = None
        return None
    rows = []
    for b in bars:
        ac = b.get("adjclose")
        cl = b.get("close")
        op = b.get("open")
        vol = b.get("volume")
        if ac is None or cl is None or cl == 0:
            continue
        adj_factor = ac / cl  # split+div factor applied to that day's close
        open_adj = (op * adj_factor) if (op is not None) else None
        # dollar volume on raw basis (shares*price) is split-neutral in notional
        dollar_vol = (cl * vol) if (vol is not None) else None
        rows.append({
            "date": b["date"],
            "open_adj": open_adj,
            "close_adj": ac,
            "raw_close": cl,
            "dollar_vol": dollar_vol,
        })
    if len(rows) < RVOL_WINDOW + 2:
        _PX_MEMO[ticker] = None
        return None
    df = pd.DataFrame(rows).set_index("date").sort_index()
    df["logret"] = np.log(df["close_adj"]).diff()
    # rolling stats computed on data THROUGH each date (inclusive of D)
    df["adv30"] = df["dollar_vol"].rolling(ADV_WINDOW, min_periods=20).mean()
    df["rvol30"] = df["logret"].rolling(RVOL_WINDOW, min_periods=20).std() * math.sqrt(252)
    _PX_MEMO[ticker] = df
    return df


# ---------------------------------------------------------------------------
# EDGAR shares-outstanding (point-in-time) for the market-cap rule.
# Free, works from this VM with a declared User-Agent (per TOOLS.md). Best-effort:
# if a ticker has no CIK / no shares concept, we record None and the backtest
# falls back to the price+ADV proxy for that name (and reports the count).
# ---------------------------------------------------------------------------
import urllib.request
import urllib.error

_EDGAR_UA = "trading-bench-research azureuser@example.com"
_CIK_MAP = None
_SHARES_MEMO: dict = {}
EDGAR_CACHE = WORKSPACE / "data_cache" / "edgar_shares"


def _load_cik_map():
    global _CIK_MAP
    if _CIK_MAP is not None:
        return _CIK_MAP
    EDGAR_CACHE.mkdir(parents=True, exist_ok=True)
    cache = EDGAR_CACHE / "ticker_cik.json"
    data = None
    if cache.exists() and cache.stat().st_size > 100:
        try:
            data = json.loads(cache.read_text())
        except Exception:
            data = None
    if data is None:
        url = "https://www.sec.gov/files/company_tickers.json"
        req = urllib.request.Request(url, headers={"User-Agent": _EDGAR_UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            cache.write_text(json.dumps(data))
        except Exception as e:
            print(f"[edgar] cik map fetch failed: {e}", file=sys.stderr)
            data = {}
    m = {}
    if isinstance(data, dict):
        for _, row in data.items():
            try:
                m[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
            except Exception:
                continue
    _CIK_MAP = m
    return m


def _fetch_shares_series(ticker: str):
    """Return ascending list of (filed_date, shares) for a ticker, or [].

    Uses EDGAR companyconcept dei/EntityCommonStockSharesOutstanding. Each fact
    carries an 'end' (period) and 'filed' date -> native point-in-time.
    """
    if ticker in _SHARES_MEMO:
        return _SHARES_MEMO[ticker]
    cikmap = _load_cik_map()
    cik = cikmap.get(ticker.upper())
    if not cik:
        _SHARES_MEMO[ticker] = []
        return []
    EDGAR_CACHE.mkdir(parents=True, exist_ok=True)
    cache = EDGAR_CACHE / f"{ticker.upper()}_shares.json"
    facts = None
    if cache.exists() and cache.stat().st_size > 2:
        try:
            facts = json.loads(cache.read_text())
        except Exception:
            facts = None
    if facts is None:
        url = (f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/"
               f"dei/EntityCommonStockSharesOutstanding.json")
        req = urllib.request.Request(url, headers={"User-Agent": _EDGAR_UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode("utf-8", "replace"))
            facts = payload.get("units", {}).get("shares", [])
            cache.write_text(json.dumps(facts))
        except urllib.error.HTTPError as e:
            facts = [] if e.code == 404 else None
            if facts is None:
                facts = []
            cache.write_text(json.dumps(facts))
        except Exception as e:
            print(f"[edgar] {ticker} shares fetch failed: {e}", file=sys.stderr)
            facts = []
    # Build ascending (filed, val). 'filed' is when it became public knowledge.
    rows = []
    for f in (facts or []):
        filed = f.get("filed")
        val = f.get("val")
        if filed and val:
            rows.append((filed, float(val)))
    rows.sort()
    _SHARES_MEMO[ticker] = rows
    return rows


def shares_asof(ticker: str, date_iso: str):
    """Most-recent shares-outstanding value FILED on/before `date_iso` (PIT)."""
    rows = _fetch_shares_series(ticker)
    if not rows:
        return None
    val = None
    for filed, v in rows:
        if filed <= date_iso:
            val = v
        else:
            break
    return val


# ---------------------------------------------------------------------------
# Signals (velocity spike), with per-(ticker,day) mechanical-filter evaluation.
# ---------------------------------------------------------------------------
def build_signals(start, end):
    conn = sqlite3.connect(str(DB_PATH))
    ls = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        "SELECT date,ticker,mention_count FROM mentions WHERE date>=? AND date<=?",
        conn, params=(ls, end),
    )
    conn.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    out = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index().copy()
        rm = grp["mention_count"].shift(1).rolling(LOOKBACK_DAYS, min_periods=5).mean()
        grp["roll_mean"] = rm
        grp["velocity"] = grp["mention_count"] / (rm + 0.1)
        grp["ticker"] = ticker
        grp["signal"] = (grp["velocity"] >= VELOCITY_THRESHOLD) & (grp["mention_count"] >= MIN_MENTIONS)
        out.append(grp.reset_index())
    sdf = pd.concat(out, ignore_index=True)
    sdf = sdf[(sdf["date"] >= pd.to_datetime(start)) & sdf["signal"]].reset_index(drop=True)
    return sdf


def evaluate_filter(ticker, date_iso):
    """Return (passes_all, detail dict) for the mechanical filter on signal day.

    detail flags: price_ok, adv_ok, mcap_ok, rvol_ok, mcap_method ('edgar'|'proxy'),
    and the raw values. Uses ONLY data through date_iso.
    """
    px = get_px_frame(ticker)
    detail = {"price_ok": False, "adv_ok": False, "mcap_ok": False,
              "rvol_ok": False, "mcap_method": None, "have_px": px is not None}
    if px is None or date_iso not in px.index:
        # try most-recent prior trading row (signal day might be a non-trading cal day)
        if px is not None:
            prior = px.index[px.index <= date_iso]
            if len(prior) == 0:
                return False, detail
            date_iso = prior[-1]
        else:
            return False, detail
    row = px.loc[date_iso]
    price = float(row["close_adj"]) if pd.notna(row["close_adj"]) else None
    # price filter uses the *raw* close (actual tradable price, not adj) -- a
    # $10 floor is about real share price / low-float, so use raw_close.
    raw_price = float(row["raw_close"]) if pd.notna(row["raw_close"]) else None
    adv = float(row["adv30"]) if pd.notna(row["adv30"]) else None
    rvol = float(row["rvol30"]) if pd.notna(row["rvol30"]) else None

    detail["raw_price"] = raw_price
    detail["adv30"] = adv
    detail["rvol30"] = rvol

    detail["price_ok"] = (raw_price is not None and raw_price >= MIN_PRICE)
    detail["adv_ok"] = (adv is not None and adv >= MIN_ADV_NOTIONAL)
    detail["rvol_ok"] = (rvol is not None and rvol < MAX_REALIZED_VOL)

    # market cap: EDGAR shares PIT * raw price; fallback to proxy (price&adv).
    sh = shares_asof(ticker, date_iso)
    if sh is not None and raw_price is not None:
        mcap = sh * raw_price
        detail["mcap"] = mcap
        detail["mcap_method"] = "edgar"
        detail["mcap_ok"] = (mcap >= MIN_MARKET_CAP)
    else:
        # Proxy per task spec: if shares unavailable, price+ADV stand in for mcap.
        # We treat mcap_ok as satisfied iff price>=$10 AND adv>=$50M already hold
        # (a $50M/day ADV at >$10 is a deep, large-cap-like name). This makes the
        # proxy NON-additive (it never rejects beyond rules 1&2) -- documented.
        detail["mcap_method"] = "proxy"
        detail["mcap"] = None
        detail["mcap_ok"] = detail["price_ok"] and detail["adv_ok"]

    passes = (detail["price_ok"] and detail["adv_ok"]
              and detail["mcap_ok"] and detail["rvol_ok"])
    return passes, detail


# ---------------------------------------------------------------------------
# Backtest engine (SHORT only, mechanical filter applied at signal time)
# ---------------------------------------------------------------------------
def run_backtest(sdf, hold_days, start, end, apply_filter=True, collect_filter_stats=False):
    # SPY axis as the trading calendar
    spy = get_px_frame("SPY")
    all_dates = sorted([d for d in spy.index if start <= d <= end])
    didx = {d: i for i, d in enumerate(all_dates)}

    # Evaluate filter per signal (cache results), rank same-day by velocity.
    sig_by_date = defaultdict(list)
    filt_stats = {"total": 0, "pass": 0, "fail_price": 0, "fail_adv": 0,
                  "fail_mcap": 0, "fail_rvol": 0, "no_px": 0,
                  "mcap_edgar": 0, "mcap_proxy": 0}
    passed_rows = []
    for _, row in sdf.sort_values("velocity", ascending=False).iterrows():
        d = str(row["date"])[:10]
        if d not in didx:
            # snap to most-recent trading day <= d (entry will be next open)
            prior = [x for x in all_dates if x <= d]
            if not prior:
                continue
            d = prior[-1]
        tk = row["ticker"]
        if apply_filter or collect_filter_stats:
            passes, det = evaluate_filter(tk, d)
            if collect_filter_stats:
                filt_stats["total"] += 1
                if not det["have_px"]:
                    filt_stats["no_px"] += 1
                if det["mcap_method"] == "edgar":
                    filt_stats["mcap_edgar"] += 1
                elif det["mcap_method"] == "proxy":
                    filt_stats["mcap_proxy"] += 1
                if passes:
                    filt_stats["pass"] += 1
                else:
                    if not det["price_ok"]:
                        filt_stats["fail_price"] += 1
                    if not det["adv_ok"]:
                        filt_stats["fail_adv"] += 1
                    if not det["mcap_ok"]:
                        filt_stats["fail_mcap"] += 1
                    if not det["rvol_ok"]:
                        filt_stats["fail_rvol"] += 1
            if apply_filter and not passes:
                continue
        sig_by_date[d].append((tk, float(row["velocity"])))
        passed_rows.append({"date": d, "ticker": tk, "velocity": float(row["velocity"])})

    # ranking by velocity already from sort; keep order within day
    trades, open_pos = [], {}
    roundtrip_cost = 2 * COST_BPS_ONEWAY / 10000.0
    borrow = (hold_days / 252.0) * (BORROW_BPS_PER_YR / 10000.0)

    for idx, date in enumerate(all_dates):
        # exits
        for ticker in [t for t, p in open_pos.items() if p["exit_date"] == date]:
            pos = open_pos.pop(ticker)
            px = get_px_frame(ticker)
            if px is None:
                continue
            exit_px = _price_on_or_before(px, date, "close_adj", idx, all_dates)
            if exit_px is None:
                continue
            short_pnl = (pos["entry_price"] / exit_px - 1.0)   # + if price fell
            net = short_pnl - roundtrip_cost - borrow
            trades.append({
                "ticker": ticker, "signal_date": pos["signal_date"],
                "entry_date": pos["entry_date"], "exit_date": date,
                "entry_price": pos["entry_price"], "exit_price": exit_px,
                "short_pnl": short_pnl, "return": net,
            })
        # entries at next-day open
        if date in sig_by_date and idx + 1 < len(all_dates):
            slots = MAX_POSITIONS - len(open_pos)
            if slots > 0:
                for ticker, _vel in sig_by_date[date]:
                    if slots <= 0:
                        break
                    if ticker in open_pos:
                        continue
                    px = get_px_frame(ticker)
                    if px is None:
                        continue
                    edate = all_dates[idx + 1]
                    if edate not in px.index:
                        continue
                    epx = px.loc[edate, "open_adj"]
                    if epx is None or pd.isna(epx) or epx <= 0:
                        continue
                    xidx = min(idx + 1 + hold_days, len(all_dates) - 1)
                    open_pos[ticker] = {
                        "signal_date": date, "entry_date": edate,
                        "entry_price": float(epx), "exit_date": all_dates[xidx],
                    }
                    slots -= 1
    # force-close survivors
    for ticker, pos in list(open_pos.items()):
        px = get_px_frame(ticker)
        if px is None:
            continue
        avail = px["close_adj"].dropna()
        if len(avail) == 0:
            continue
        exit_px = float(avail.iloc[-1])
        short_pnl = (pos["entry_price"] / exit_px - 1.0)
        net = short_pnl - roundtrip_cost - borrow
        trades.append({
            "ticker": ticker, "signal_date": pos["signal_date"],
            "entry_date": pos["entry_date"], "exit_date": end,
            "entry_price": pos["entry_price"], "exit_price": exit_px,
            "short_pnl": short_pnl, "return": net,
        })

    result = {"trades": trades, "n_passed_signals": len(passed_rows),
             "passed_rows": passed_rows}
    if collect_filter_stats:
        result["filter_stats"] = filt_stats
    return result


def _price_on_or_before(px, date, col, idx, all_dates):
    """Value of `col` at `date`, else most-recent prior trading day (<=5 back)."""
    if date in px.index:
        v = px.loc[date, col]
        if v is not None and not pd.isna(v):
            return float(v)
    for back in range(1, 6):
        if idx >= back:
            d2 = all_dates[idx - back]
            if d2 in px.index:
                v = px.loc[d2, col]
                if v is not None and not pd.isna(v):
                    return float(v)
    return None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_metrics(trades_list, start, end, hold_days):
    if not trades_list:
        return {"error": "no trades", "n_trades": 0}
    trades = pd.DataFrame(trades_list)
    n_trades = len(trades)
    win_rate = float((trades["return"] > 0).mean())
    avg_return = float(trades["return"].mean())
    # per-exit-date mean PnL (equal-weight book), annualize by sqrt(252/hold)
    daily_pnl = trades.groupby("exit_date")["return"].mean().sort_index()
    ppy = 252 / max(hold_days, 1)
    if len(daily_pnl) >= 5:
        mu, sd = float(daily_pnl.mean()), float(daily_pnl.std())
        sharpe = float((mu / (sd + 1e-9)) * math.sqrt(ppy))
    else:
        sharpe = float("nan")
    # per-trade t-stat (independent-trade approximation)
    if n_trades >= 5:
        tr_mu, tr_sd = float(trades["return"].mean()), float(trades["return"].std())
        tstat = float(tr_mu / (tr_sd / math.sqrt(n_trades) + 1e-12))
    else:
        tstat = float("nan")
    # equity curve (sequential per-exit-date)
    equity, eq_vals, eq_dates = 1.0, [], []
    for d, r in daily_pnl.items():
        equity *= (1 + r)
        eq_vals.append(equity)
        eq_dates.append(d)
    final_eq = eq_vals[-1] if eq_vals else float("nan")
    years = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days / 365.25
    cagr = float((final_eq ** (1 / years) - 1)) if (years > 0 and final_eq > 0) else float("nan")
    if eq_vals:
        eq_s = pd.Series(eq_vals, index=eq_dates)
        rm = eq_s.cummax()
        max_dd = float(((eq_s - rm) / rm).min())
    else:
        max_dd = float("nan")
    return {
        "n_trades": n_trades, "win_rate": win_rate, "avg_return": avg_return,
        "sharpe": sharpe, "tstat": tstat, "cagr": cagr, "max_dd": max_dd,
        "final_equity": final_eq,
    }


if __name__ == "__main__":
    print("Use reddit_short_cleantest_run.py to drive this module.")