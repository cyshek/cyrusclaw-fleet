"""Driver for the full Reddit mention-momentum backtest. Runs all cuts, prints JSON-ish summary."""
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
import reddit_fullbacktest as R

DB = sys.argv[1] if len(sys.argv) > 1 else str(R.DB_PATH)
START = "2020-01-01"
END = "2024-12-31"


def summarize(m):
    if not m or m.get("error"):
        return None
    return {
        "n_trades": m["n_trades"], "win_rate": round(m["win_rate"], 4),
        "avg_return": round(m["avg_return"], 4), "sharpe": round(m["sharpe"], 3) if m["sharpe"] == m["sharpe"] else None,
        "cagr": round(m["cagr"], 4) if m["cagr"] == m["cagr"] else None,
        "max_dd": round(m["max_dd"], 4) if m["max_dd"] == m["max_dd"] else None,
        "beta": round(m["beta"], 3) if m["beta"] == m["beta"] else None,
    }


def run_all(apply_filter):
    print(f"\n{'='*70}\nBUILDING SIGNALS (short_filter={apply_filter})\n{'='*70}", file=sys.stderr)
    sdf = R.build_signals(DB, START, END, apply_short_filter=apply_filter)
    if sdf.empty:
        return {"error": "no signals"}
    n_sig = int(sdf["signal"].sum())
    sig_tickers = sorted(sdf[sdf["signal"]]["ticker"].unique().tolist())
    n_tickers = len(sig_tickers)
    drange = f"{str(sdf['date'].min())[:10]} to {str(sdf['date'].max())[:10]}"
    print(f"  Signals: {n_sig}, tickers: {n_tickers}, range: {drange}", file=sys.stderr)
    print(f"  Loading prices for {n_tickers} tickers...", file=sys.stderr)
    prices, opens, failed = R.load_prices_opens(sig_tickers, START, END)
    print(f"  Prices: {len(prices)} loaded, {len(failed)} failed", file=sys.stderr)
    spy = prices.get("SPY")
    spy_bench = R.spy_benchmark(spy, START, END)

    out = {
        "n_signals": n_sig, "n_signal_tickers": n_tickers, "signal_range": drange,
        "spy_benchmark": {k: round(v, 4) for k, v in spy_bench.items()},
        "full": {}, "ex_gme": {}, "oos_post2022": {}, "by_year": {},
        "ticker_pnl_5d": [], "failed_tickers": failed[:50],
    }

    for h in R.HOLDS:
        bt = R.run_backtest(sdf, prices, opens, h, START, END)
        out["full"][h] = summarize(R.compute_metrics(bt["trades"], spy, START, END, h))
        btx = R.run_backtest(sdf, prices, opens, h, START, END, excl=R.GME_AMC_WINDOW)
        out["ex_gme"][h] = summarize(R.compute_metrics(btx["trades"], spy, START, END, h))
        bto = R.run_backtest(sdf, prices, opens, h, R.OOS_START, END)
        out["oos_post2022"][h] = summarize(R.compute_metrics(bto["trades"], spy, R.OOS_START, END, h))
        print(f"  hold={h}d full={out['full'][h]} oos={out['oos_post2022'][h]}", file=sys.stderr)

    # Year-by-year (5-day hold, the canonical hold)
    for yr in [2020, 2021, 2022, 2023, 2024]:
        ys, ye = f"{yr}-01-01", f"{yr}-12-31"
        bt = R.run_backtest(sdf, prices, opens, 5, ys, ye)
        m = R.compute_metrics(bt["trades"], spy, ys, ye, 5)
        out["by_year"][yr] = summarize(m)
        sb = R.spy_benchmark(spy, ys, ye)
        if out["by_year"][yr]:
            out["by_year"][yr]["spy_sharpe"] = round(sb.get("sharpe", float("nan")), 3) if sb else None

    # Ticker contribution (5d hold, full period)
    bt5 = R.run_backtest(sdf, prices, opens, 5, START, END)
    m5 = R.compute_metrics(bt5["trades"], spy, START, END, 5)
    if m5 and "ticker_pnl" in m5:
        tp = m5["ticker_pnl"]
        for tk, row in tp.head(15).iterrows():
            out["ticker_pnl_5d"].append({
                "ticker": tk, "total_return": round(row["total_return"], 4),
                "n_trades": int(row["n_trades"]), "avg_return": round(row["avg_return"], 4),
                "win_rate": round(row["win_rate_"], 3),
            })
        out["ticker_pnl_5d_worst"] = []
        for tk, row in tp.tail(8).iterrows():
            out["ticker_pnl_5d_worst"].append({
                "ticker": tk, "total_return": round(row["total_return"], 4),
                "n_trades": int(row["n_trades"]), "avg_return": round(row["avg_return"], 4),
                "win_rate": round(row["win_rate_"], 3),
            })
    return out


result = {"filtered": run_all(True), "unfiltered": run_all(False)}

# DB coverage stats
conn = sqlite3.connect(DB)
cov = {}
cov["total_rows"] = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]
cov["earliest"] = conn.execute("SELECT MIN(date) FROM mentions").fetchone()[0]
cov["latest"] = conn.execute("SELECT MAX(date) FROM mentions").fetchone()[0]
cov["days"] = conn.execute("SELECT COUNT(DISTINCT date) FROM mentions").fetchone()[0]
cov["tickers"] = conn.execute("SELECT COUNT(DISTINCT ticker) FROM mentions").fetchone()[0]
cov["by_year"] = {}
for yr, days, rows in conn.execute(
        "SELECT substr(date,1,4), COUNT(DISTINCT date), COUNT(*) FROM mentions GROUP BY substr(date,1,4)"):
    cov["by_year"][yr] = {"days": days, "rows": rows}
try:
    cov["total_posts"] = conn.execute("SELECT SUM(sub_count+comment_count) FROM fetch_log").fetchone()[0]
    cov["fetch_days"] = conn.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
except Exception:
    pass
conn.close()
result["coverage"] = cov

out_path = R.WORKSPACE / "_reddit_fullbt_result.json"
out_path.write_text(json.dumps(result, indent=2, default=str))
print(f"\nWROTE {out_path}", file=sys.stderr)
print(json.dumps(result, indent=2, default=str))
