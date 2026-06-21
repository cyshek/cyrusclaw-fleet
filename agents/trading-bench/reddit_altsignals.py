"""
reddit_altsignals.py -- Alternative Reddit signal constructions (H1-H4).

The naive "mention-velocity -> buy" signal was NEGATIVE (Sharpe -0.67 full period,
-0.88 OOS) -- see reports/REDDIT_FULLBACKTEST_20260621.md. This module tests whether
DIFFERENT signal constructions from the SAME mention data show edge.

Hypotheses
----------
H1  High-score (community endorsement): avg_score > 90th pct (that ticker's history)
    AND mention_count >= 3. Long, entry next-day OPEN, hold 5d.
H2  Contrarian/reversal (flip the original): velocity spike (>=2x 20d avg, >=5 mentions),
    SHORT next-day OPEN, hold 3d. Short simulated as negative of long return (paper can't
    short -- flag only).
H3  Sustained attention: ticker mentioned on >=10 of the last 14 days. Long, entry
    next-day OPEN after the 14th day, hold 10d.
H4  Negative-sentiment filter: velocity spike (same as original) BUT only take trades
    where avg_score >= that ticker's MEDIAN (community receptive, not downvoting).
    Long, entry next-day OPEN, hold 5d (matches original hold for apples-to-apples).

Shared conventions (match reddit_fullbacktest.py exactly)
---------------------------------------------------------
- Entry: NEXT trading day OPEN (lookahead-free; signal computed on data through day D,
  position entered at D+1 open).
- Exit: CLOSE on day (entry_idx + hold_days).
- Cost: 2 bps one-way -> 2*COST_BPS/10000 round-trip subtracted from each trade return.
- Sizing: equal weight, max 10 concurrent, same-day signals ranked (H1 by avg_score,
  H2/H4 by velocity, H3 by mention_count), best-first for slot allocation.
- Prices: runner.daily_bars_cache.get_daily -> Yahoo v8 adjclose (split+div adj) + open.
- Sharpe: per-exit-date mean PnL series, annualized by sqrt(252/hold_days).
- Benchmark: SPY buy & hold on the same window.
- Short-ticker English-word collisions excluded (same curated list as full backtest).
"""

import sys
import sqlite3
import math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import numpy as np
from runner.daily_bars_cache import get_daily

WORKSPACE = Path(__file__).parent
DB_PATH = WORKSPACE / "reddit_mentions.db"

# --- Shared params ---
COST_BPS = 2            # one-way; round-trip = 2*COST_BPS
MAX_POSITIONS = 10
LOOKBACK_DAYS = 20      # velocity rolling window (H2/H4)
VELOCITY_THRESHOLD = 2.0
MIN_MENTIONS_VELOCITY = 5

# H1 params
H1_SCORE_PCTILE = 0.90
H1_MIN_MENTIONS = 3
H1_HOLD = 5

# H2 params (short)
H2_HOLD = 3

# H3 params
H3_WINDOW = 14
H3_MIN_DAYS = 10
H3_HOLD = 10

# H4 params
H4_HOLD = 5

# Short-ticker (<=3 char) English-word collisions to EXCLUDE (same as full backtest).
SHORT_TICKER_EXCLUDE = {
    "ALL", "AMP", "LOW", "AI", "APP", "NET", "ES", "FIX", "DOC",
    "ARM", "GEN", "ICE", "MO", "PM", "GL", "ED", "FDS",
    # extras observed as dictionary words / non-tradable in this DB:
    "TECH", "FAST", "BILL", "AM", "GO", "ON", "OR", "BE", "SO", "AN",
    "IT", "AR", "EX", "BY", "OUT", "NOW", "PAY", "CAT", "TAP", "DD",
}

GME_AMC_WINDOW = [("2021-01-15", "2021-03-31")]
OOS_START = "2022-01-01"


# ---------------------------------------------------------------------------
# Price loading (reuses cached Yahoo bars; no re-download for cached names)
# ---------------------------------------------------------------------------
def load_prices_opens(tickers, start, end):
    prices, opens, failed = {}, {}, []
    needed = set(tickers) | {"SPY"}
    for ticker in sorted(needed):
        try:
            bars = get_daily(ticker)
            if not bars:
                failed.append(ticker)
                continue
            p = pd.Series({r["date"]: r["adjclose"] for r in bars
                           if r.get("adjclose") is not None})
            o = pd.Series({r["date"]: r["open"] for r in bars
                           if r.get("open") is not None})
            p = p[(p.index >= start) & (p.index <= end)]
            o = o[(o.index >= start) & (o.index <= end)]
            if len(p) >= 3:
                prices[ticker] = p
                opens[ticker] = o
            else:
                failed.append(ticker)
        except Exception:
            failed.append(ticker)
    return prices, opens, failed


def _load_mentions(start, end, lookback_pad=60):
    """Load mentions with a lookback pad so rolling stats are warm at `start`."""
    conn = sqlite3.connect(str(DB_PATH))
    ls = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=lookback_pad)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        "SELECT date,ticker,mention_count,avg_score,post_count FROM mentions "
        "WHERE date>=? AND date<=?",
        conn, params=(ls, end),
    )
    conn.close()
    if df.empty:
        return df
    mask = df["ticker"].str.len().le(3) & df["ticker"].isin(SHORT_TICKER_EXCLUDE)
    # also drop the longer dictionary-word names in the exclude set
    mask = mask | df["ticker"].isin(SHORT_TICKER_EXCLUDE)
    df = df[~mask]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Signal builders -- each returns a DataFrame with columns:
#   date (Timestamp), ticker (str), signal (bool), rank_val (float, higher=better)
# ---------------------------------------------------------------------------
def build_h1(start, end):
    """High-score: avg_score > 90th pct of that ticker's *trailing* history AND mc>=3.

    Uses an EXPANDING trailing percentile (shifted 1 day) so the threshold at day D
    uses only data through D-1 -> no lookahead. min_periods=20 days of history.
    """
    df = _load_mentions(start, end)
    if df.empty:
        return df
    out = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index().copy()
        # trailing 90th percentile of avg_score using history strictly before D
        sc = grp["avg_score"]
        thr = sc.shift(1).expanding(min_periods=20).quantile(H1_SCORE_PCTILE)
        grp["thr"] = thr
        grp["ticker"] = ticker
        grp["signal"] = (grp["avg_score"] > thr) & (grp["mention_count"] >= H1_MIN_MENTIONS) & thr.notna()
        grp["rank_val"] = grp["avg_score"]
        out.append(grp.reset_index())
    sdf = pd.concat(out, ignore_index=True)
    return sdf[sdf["date"] >= pd.to_datetime(start)].reset_index(drop=True)


def build_velocity(start, end):
    """Shared velocity-spike base for H2 and H4."""
    df = _load_mentions(start, end)
    if df.empty:
        return df
    out = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index().copy()
        rm = grp["mention_count"].shift(1).rolling(LOOKBACK_DAYS, min_periods=5).mean()
        grp["roll_mean"] = rm
        grp["velocity"] = grp["mention_count"] / (rm + 0.1)
        # trailing median avg_score (strictly-prior) for H4 filter
        grp["score_median"] = grp["avg_score"].shift(1).expanding(min_periods=10).median()
        grp["ticker"] = ticker
        grp["base_signal"] = (grp["velocity"] >= VELOCITY_THRESHOLD) & (grp["mention_count"] >= MIN_MENTIONS_VELOCITY)
        out.append(grp.reset_index())
    sdf = pd.concat(out, ignore_index=True)
    return sdf[sdf["date"] >= pd.to_datetime(start)].reset_index(drop=True)


def build_h2(start, end):
    """Contrarian: velocity spike -> SHORT. signal=base_signal; rank by velocity."""
    sdf = build_velocity(start, end)
    if sdf.empty:
        return sdf
    sdf = sdf.copy()
    sdf["signal"] = sdf["base_signal"]
    sdf["rank_val"] = sdf["velocity"]
    return sdf


def build_h3(start, end):
    """Sustained attention: mentioned on >=10 of last 14 calendar-present days.

    Counts days (rows) present in the last H3_WINDOW *trading-data* days for that ticker
    where mention_count>0. Signal fires on the day the 14-window threshold is met; entry
    is next-day open. Rank by recent mention sum.
    """
    df = _load_mentions(start, end)
    if df.empty:
        return df
    out = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index().copy()
        present = (grp["mention_count"] > 0).astype(int)
        # rolling over the last H3_WINDOW rows (data days), inclusive of D
        days_present = present.rolling(H3_WINDOW, min_periods=H3_WINDOW).sum()
        grp["days_present"] = days_present
        grp["recent_sum"] = grp["mention_count"].rolling(H3_WINDOW, min_periods=H3_WINDOW).sum()
        grp["ticker"] = ticker
        grp["signal"] = days_present >= H3_MIN_DAYS
        grp["rank_val"] = grp["recent_sum"]
        out.append(grp.reset_index())
    sdf = pd.concat(out, ignore_index=True)
    return sdf[sdf["date"] >= pd.to_datetime(start)].reset_index(drop=True)


def build_h4(start, end):
    """Negative-sentiment filter: velocity spike AND avg_score >= trailing median."""
    sdf = build_velocity(start, end)
    if sdf.empty:
        return sdf
    sdf = sdf.copy()
    sdf["signal"] = sdf["base_signal"] & (sdf["avg_score"] >= sdf["score_median"]) & sdf["score_median"].notna()
    sdf["rank_val"] = sdf["velocity"]
    return sdf


# ---------------------------------------------------------------------------
# Backtest engine (long or short)
# ---------------------------------------------------------------------------
def run_backtest(sdf, prices, opens, hold_days, start, end, side="long", excl=None):
    """side: 'long' or 'short'. Short return = -(long pnl) - costs."""
    sigs = sdf[sdf["signal"]].copy()
    if excl:
        for es, ee in excl:
            m = (sigs["date"] >= pd.to_datetime(es)) & (sigs["date"] <= pd.to_datetime(ee))
            sigs = sigs[~m]
    if sigs.empty:
        return {"trades": [], "n_signals": 0}

    all_dates = sorted({str(d)[:10] for d in prices["SPY"].index if start <= str(d)[:10] <= end})
    didx = {d: i for i, d in enumerate(all_dates)}

    sig_by_date = defaultdict(list)
    for _, row in sigs.sort_values("rank_val", ascending=False).iterrows():
        d = str(row["date"])[:10]
        if d in didx:
            sig_by_date[d].append(row["ticker"])

    sign = 1.0 if side == "long" else -1.0
    trades, open_pos = [], {}
    for idx, date in enumerate(all_dates):
        # exits
        for ticker in [t for t, p in open_pos.items() if p["exit_date"] == date]:
            pos = open_pos.pop(ticker)
            if ticker not in prices:
                continue
            close_px = prices[ticker].get(date)
            if close_px is None or pd.isna(close_px):
                for back in range(1, 6):
                    if idx >= back:
                        px = prices[ticker].get(all_dates[idx - back])
                        if px and not pd.isna(px):
                            close_px = px
                            break
            if close_px is None or pd.isna(close_px):
                continue
            raw = (close_px / pos["entry_price"] - 1)
            ret = sign * raw - 2 * COST_BPS / 10000
            trades.append({
                "ticker": ticker, "signal_date": pos["signal_date"],
                "entry_date": pos["entry_date"], "exit_date": date,
                "entry_price": pos["entry_price"], "exit_price": close_px,
                "raw_return": raw, "return": ret,
            })
        # entries (next-day open)
        if date in sig_by_date and idx + 1 < len(all_dates):
            slots = MAX_POSITIONS - len(open_pos)
            if slots > 0:
                cands = [t for t in sig_by_date[date]
                         if t not in open_pos and t in opens and t in prices]
                for ticker in cands[:slots]:
                    edate = all_dates[idx + 1]
                    epx = opens[ticker].get(edate)
                    if epx is None or pd.isna(epx) or epx <= 0:
                        continue
                    xidx = min(idx + 1 + hold_days, len(all_dates) - 1)
                    open_pos[ticker] = {
                        "signal_date": date, "entry_date": edate,
                        "entry_price": epx, "exit_date": all_dates[xidx],
                    }
    # force-close survivors at last available price
    for ticker, pos in list(open_pos.items()):
        if ticker in prices:
            avail = prices[ticker].dropna()
            if len(avail) == 0:
                continue
            close_px = float(avail.iloc[-1])
            if pos["entry_price"] > 0:
                raw = (close_px / pos["entry_price"] - 1)
                ret = sign * raw - 2 * COST_BPS / 10000
                trades.append({
                    "ticker": ticker, "signal_date": pos["signal_date"],
                    "entry_date": pos["entry_date"], "exit_date": end,
                    "entry_price": pos["entry_price"], "exit_price": close_px,
                    "raw_return": raw, "return": ret,
                })
    return {"trades": trades, "n_signals": len(sigs)}


def compute_metrics(trades_list, spy_prices, start, end, hold_days):
    if not trades_list:
        return {"error": "no trades", "n_trades": 0}
    trades = pd.DataFrame(trades_list)
    n_trades = len(trades)
    win_rate = float((trades["return"] > 0).mean())
    avg_return = float(trades["return"].mean())
    daily_pnl = trades.groupby("exit_date")["return"].mean().sort_index()
    ppy = 252 / max(hold_days, 1)
    if len(daily_pnl) >= 5:
        mu, sd = float(daily_pnl.mean()), float(daily_pnl.std())
        sharpe = float((mu / (sd + 1e-8)) * math.sqrt(ppy))
    else:
        sharpe = float("nan")
    equity, eq_vals, eq_dates = 1.0, [], []
    for d, r in daily_pnl.items():
        equity *= (1 + r)
        eq_vals.append(equity)
        eq_dates.append(d)
    if not eq_vals:
        return {"error": "empty", "n_trades": n_trades}
    final_eq = eq_vals[-1]
    years = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days / 365.25
    cagr = float((final_eq ** (1 / years) - 1)) if years > 0 and final_eq > 0 else float("nan")
    eq_s = pd.Series(eq_vals, index=eq_dates)
    rm = eq_s.cummax()
    max_dd = float(((eq_s - rm) / rm).min())
    # beta vs SPY
    spy_ds = [str(d)[:10] for d in spy_prices.index]
    spy_r = spy_prices.pct_change().dropna()
    spy_map = dict(zip(spy_ds[1:], spy_r.values))
    tr, sr = [], []
    for _, row in trades.iterrows():
        ed = str(row["exit_date"])[:10]
        if ed in spy_map:
            tr.append(row["return"])
            sr.append(spy_map[ed])
    beta = float(np.cov(tr, sr)[0, 1] / (np.var(sr) + 1e-10)) if len(tr) > 20 else float("nan")
    return {
        "n_trades": n_trades, "win_rate": win_rate, "avg_return": avg_return,
        "sharpe": sharpe, "cagr": cagr, "max_dd": max_dd, "beta": beta,
        "final_equity": final_eq,
    }


def spy_benchmark(spy_prices, start, end):
    f = spy_prices[(spy_prices.index >= start) & (spy_prices.index <= end)]
    if f.empty or len(f) < 2:
        return {}
    r = f.pct_change().dropna()
    mu, sd = float(r.mean()), float(r.std())
    sharpe = (mu / (sd + 1e-8)) * math.sqrt(252)
    total_ret = float(f.iloc[-1] / f.iloc[0] - 1)
    years = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days / 365.25
    cagr = float((1 + total_ret) ** (1 / years) - 1) if years > 0 else float("nan")
    rm = f.cummax()
    max_dd = float(((f - rm) / rm).min())
    return {"sharpe": sharpe, "cagr": cagr, "max_dd": max_dd, "total_ret": total_ret}


if __name__ == "__main__":
    print("Use reddit_altsignals_run.py to drive this module.")
