"""
reddit_fullbacktest.py -- Full Reddit mention-momentum backtest on all collected data.

Signal: mention velocity spike (>=2x 20-day rolling avg AND >=5 mentions/day).
Short-ticker false-positive control: the task spec requires a `$TICKER` prefix for
tickers <=3 chars (e.g. $GME) to avoid LOW/AMP/ALL English-word collisions. The
stored DB (reddit_mentions.db) aggregates `$TICKER` and bare `TICKER` into a single
`mention_count` with NO way to separate them post-hoc. The faithful substitute is a
curated hard-exclusion list of dictionary-word <=3-char tickers (documented below).
We report results BOTH with and without this filter so the impact is fully visible.

Entry: next-day OPEN. Exit: CLOSE on day N (holds 1,3,5,10). Cost: 2bps one-way.
Benchmark: SPY buy-and-hold on same dates.
"""

import sys
import os
import sqlite3
import argparse
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

# --- Parameters (per task spec) ---
COST_BPS = 2          # one-way (2bps stocks); round-trip = 2*COST_BPS
MAX_POSITIONS = 10
VELOCITY_THRESHOLD = 2.0
MIN_MENTIONS = 5
LOOKBACK_DAYS = 20
HOLDS = [1, 3, 5, 10]

# --- Short-ticker (<=3 char) English-word collisions to EXCLUDE ---
# These dominate the raw mention counts as dictionary words, not tickers:
#   ALL (16.9k mentions, 100% of days), AMP (& / ampere), LOW ("buy the low"),
#   AI (the concept), APP (mobile app), NET (net worth), ES (futures/"es"),
#   FIX, DOC, ARM, GEN, ICE, MO, PM, GL, ED, FDS.
# Substitute for the spec's "$TICKER-only for <=3 char" rule (DB can't separate $-prefix).
# Real <=3 char tickers (SPY, AMD, GME, AMC, BB, BA, NOK, QQQ, ...) are KEPT.
SHORT_TICKER_EXCLUDE = {
    "ALL", "AMP", "LOW", "AI", "APP", "NET", "ES", "FIX", "DOC",
    "ARM", "GEN", "ICE", "MO", "PM", "GL", "ED", "FDS",
}

GME_AMC_WINDOW = [("2021-01-15", "2021-03-31")]
OOS_START = "2022-01-01"   # post-2022 out-of-sample gate window


def load_prices_opens(tickers, start, end):
    prices, opens, failed = {}, {}, []
    spy = get_daily("SPY")
    prices["SPY"] = pd.Series(
        {r["date"]: r["adjclose"] for r in spy if start <= r["date"] <= end}
    )
    opens["SPY"] = pd.Series(
        {r["date"]: r["open"] for r in spy if start <= r["date"] <= end}
    )
    for i, ticker in enumerate(tickers):
        if ticker == "SPY":
            continue
        try:
            bars = get_daily(ticker)
            if not bars:
                failed.append(ticker)
                continue
            p = pd.Series({r["date"]: r["adjclose"] for r in bars})
            o = pd.Series({r["date"]: r["open"] for r in bars})
            p = p[(p.index >= start) & (p.index <= end)]
            o = o[(o.index >= start) & (o.index <= end)]
            if len(p) >= 3:
                prices[ticker] = p
                opens[ticker] = o
        except Exception:
            failed.append(ticker)
    return prices, opens, failed


def build_signals(db_path, start, end, apply_short_filter=True):
    conn = sqlite3.connect(str(db_path))
    ls = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=40)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        "SELECT date,ticker,mention_count FROM mentions WHERE date>=? AND date<=?",
        conn, params=(ls, end)
    )
    conn.close()
    if df.empty:
        return pd.DataFrame()
    # Short-ticker English-word filter (spec: $TICKER-only for <=3 char)
    if apply_short_filter:
        mask = df["ticker"].str.len().le(3) & df["ticker"].isin(SHORT_TICKER_EXCLUDE)
        df = df[~mask]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    results = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index()
        rm = grp["mention_count"].shift(1).rolling(LOOKBACK_DAYS, min_periods=5).mean()
        grp["roll_mean"] = rm
        grp["velocity"] = grp["mention_count"] / (rm + 0.1)
        grp["ticker"] = ticker
        results.append(grp.reset_index())
    sdf = pd.concat(results, ignore_index=True)
    sdf = sdf[sdf["date"] >= pd.to_datetime(start)]
    sdf["signal"] = (
        (sdf["velocity"] >= VELOCITY_THRESHOLD) & (sdf["mention_count"] >= MIN_MENTIONS)
    )
    return sdf


def run_backtest(sdf, prices, opens, hold_days, start, end, excl=None):
    sigs = sdf[sdf["signal"]].copy()
    if excl:
        for es, ee in excl:
            m = (sigs["date"] >= pd.to_datetime(es)) & (sigs["date"] <= pd.to_datetime(ee))
            sigs = sigs[~m]
    all_dates = sorted({
        str(d)[:10] for d in prices["SPY"].index if start <= str(d)[:10] <= end
    })
    sig_by_date = defaultdict(list)
    # Rank same-day signals by velocity (strongest first) for slot allocation
    for _, row in sigs.sort_values("velocity", ascending=False).iterrows():
        sig_by_date[str(row["date"])[:10]].append(row["ticker"])
    trades_list, open_pos = [], {}
    for idx, date in enumerate(all_dates):
        to_exit = [t for t, pos in open_pos.items() if pos["exit_date"] == date]
        for ticker in to_exit:
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
            ret = (close_px / pos["entry_price"] - 1) - 2 * COST_BPS / 10000
            trades_list.append({
                "ticker": ticker, "signal_date": pos["signal_date"],
                "entry_date": pos["entry_date"], "exit_date": date,
                "entry_price": pos["entry_price"], "exit_price": close_px, "return": ret,
            })
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
    for ticker, pos in list(open_pos.items()):
        if ticker in prices:
            avail = prices[ticker].dropna()
            if len(avail) == 0:
                continue
            close_px = float(avail.iloc[-1])
            if pos["entry_price"] > 0:
                ret = (close_px / pos["entry_price"] - 1) - 2 * COST_BPS / 10000
                trades_list.append({
                    "ticker": ticker, "signal_date": pos["signal_date"],
                    "entry_date": pos["entry_date"], "exit_date": end,
                    "entry_price": pos["entry_price"], "exit_price": close_px, "return": ret,
                })
    return {"trades": trades_list, "n_signals": len(sigs)}


def compute_metrics(trades_list, spy_prices, start, end, hold_days):
    if not trades_list:
        return {"error": "no trades"}
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
        return {"error": "empty"}
    final_eq = eq_vals[-1]
    years = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days / 365.25
    cagr = float((final_eq ** (1 / years) - 1)) if years > 0 and final_eq > 0 else float("nan")
    eq_s = pd.Series(eq_vals, index=eq_dates)
    rm = eq_s.cummax()
    max_dd = float(((eq_s - rm) / rm).min())
    spy_ds = [str(d)[:10] for d in spy_prices.index]
    spy_r = spy_prices.pct_change().dropna()
    spy_map = dict(zip(spy_ds[1:], spy_r.values))
    tr, sr = [], []
    for _, row in trades.iterrows():
        ed = str(row["exit_date"])[:10]
        if ed in spy_map:
            tr.append(row["return"])
            sr.append(spy_map[ed])
    if len(tr) > 20:
        cov = np.cov(tr, sr)
        beta = float(cov[0, 1] / (np.var(sr) + 1e-10))
    else:
        beta = float("nan")
    ticker_pnl = trades.groupby("ticker").agg(
        total_return=("return", "sum"),
        n_trades=("return", "count"),
        avg_return=("return", "mean"),
        win_rate_=("return", lambda x: float((x > 0).mean())),
    ).sort_values("total_return", ascending=False)
    return {
        "n_trades": n_trades, "win_rate": win_rate, "avg_return": avg_return,
        "sharpe": sharpe, "cagr": cagr, "max_dd": max_dd, "beta": beta,
        "final_equity": final_eq, "ticker_pnl": ticker_pnl,
    }


def spy_benchmark(spy_prices, start, end):
    f = spy_prices[(spy_prices.index >= start) & (spy_prices.index <= end)]
    if f.empty:
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
    print("Use reddit_fullbacktest_run.py to drive this module.")
