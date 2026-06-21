"""
reddit_altsignals_run.py -- driver for H1-H4 alternative Reddit signal backtests.

Runs each hypothesis across: full period, ex-GME/AMC mania, OOS (post-2022).
Year-by-year breakdown for the best long hypothesis. Dumps JSON + prints a digest.
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import reddit_altsignals as R

WORKSPACE = Path(__file__).parent
OUT_JSON = WORKSPACE / "_reddit_altsignals_result.json"


def union_tickers(*sdfs):
    ts = set()
    for sdf in sdfs:
        if sdf is not None and not sdf.empty:
            ts |= set(sdf[sdf["signal"]]["ticker"].unique())
    return sorted(ts)


def fmt(m):
    if not m or m.get("error") or m.get("n_trades", 0) == 0:
        return {"n_trades": m.get("n_trades", 0) if m else 0, "note": (m or {}).get("error", "no trades")}
    return {
        "n_trades": m["n_trades"],
        "win_rate": round(m["win_rate"], 4),
        "avg_return": round(m["avg_return"], 4),
        "sharpe": round(m["sharpe"], 3) if m["sharpe"] == m["sharpe"] else None,
        "cagr": round(m["cagr"], 4) if m["cagr"] == m["cagr"] else None,
        "max_dd": round(m["max_dd"], 4),
        "beta": round(m["beta"], 3) if m.get("beta") == m.get("beta") else None,
    }


def run_one(name, build_fn, hold, side, start, end, prices, opens):
    sdf = build_fn(start, end)
    if sdf is None or sdf.empty or not sdf["signal"].any():
        return {"name": name, "hold": hold, "side": side, "full": {"n_trades": 0, "note": "no signals"}}
    res_full = R.run_backtest(sdf, prices, opens, hold, start, end, side=side)
    m_full = R.compute_metrics(res_full["trades"], prices["SPY"], start, end, hold)

    res_exm = R.run_backtest(sdf, prices, opens, hold, start, end, side=side, excl=R.GME_AMC_WINDOW)
    m_exm = R.compute_metrics(res_exm["trades"], prices["SPY"], start, end, hold)

    # OOS: restrict signals to >= OOS_START
    oos_start = R.OOS_START
    res_oos = R.run_backtest(sdf, prices, opens, hold, oos_start, end, side=side)
    m_oos = R.compute_metrics(res_oos["trades"], prices["SPY"], oos_start, end, hold)

    return {
        "name": name, "hold": hold, "side": side,
        "n_signals_full": res_full["n_signals"],
        "full": fmt(m_full),
        "ex_mania": fmt(m_exm),
        "oos_post2022": fmt(m_oos),
        "_trades_full": res_full["trades"],   # kept for year-by-year of best
        "_sdf_name": name,
    }


def year_by_year(build_fn, hold, side, start, end, prices, opens):
    sdf = build_fn(start, end)
    res = R.run_backtest(sdf, prices, opens, hold, start, end, side=side)
    trades = pd.DataFrame(res["trades"])
    if trades.empty:
        return {}
    trades["year"] = trades["exit_date"].astype(str).str[:4]
    out = {}
    spy = prices["SPY"]
    for yr, grp in trades.groupby("year"):
        ys, ye = f"{yr}-01-01", f"{yr}-12-31"
        m = R.compute_metrics(grp.to_dict("records"), spy, ys, ye, hold)
        spb = R.spy_benchmark(spy, ys, ye)
        out[yr] = {
            "n_trades": int(len(grp)),
            "win_rate": round(float((grp["return"] > 0).mean()), 4),
            "sharpe": round(m["sharpe"], 3) if m.get("sharpe") == m.get("sharpe") else None,
            "cagr": round(m["cagr"], 4) if m.get("cagr") == m.get("cagr") else None,
            "spy_sharpe": round(spb.get("sharpe", float("nan")), 3) if spb else None,
            "spy_cagr": round(spb.get("cagr", float("nan")), 4) if spb else None,
        }
    return out


def top_tickers(trades, n=12):
    if not trades:
        return []
    df = pd.DataFrame(trades)
    agg = df.groupby("ticker").agg(
        total_return=("return", "sum"),
        n=("return", "count"),
        avg_return=("return", "mean"),
        win_rate=("return", lambda x: float((x > 0).mean())),
    ).sort_values("total_return", ascending=False)
    rows = []
    for tk, r in agg.head(n).iterrows():
        rows.append({"ticker": tk, "total_return": round(float(r["total_return"]), 4),
                     "n": int(r["n"]), "avg_return": round(float(r["avg_return"]), 4),
                     "win_rate": round(float(r["win_rate"]), 4)})
    return rows


def main():
    # full data window
    conn = sqlite3.connect(str(R.DB_PATH))
    row = conn.execute("SELECT MIN(date), MAX(date) FROM mentions").fetchone()
    conn.close()
    start, end = row[0], row[1]
    print(f"[run] data window {start} -> {end}", flush=True)

    # Build all signal sets once to collect ticker universe for price loading
    print("[run] building signals to collect ticker universe...", flush=True)
    sdf_h1 = R.build_h1(start, end)
    sdf_h2 = R.build_h2(start, end)
    sdf_h3 = R.build_h3(start, end)
    sdf_h4 = R.build_h4(start, end)
    tickers = union_tickers(sdf_h1, sdf_h2, sdf_h3, sdf_h4)
    print(f"[run] {len(tickers)} unique signalling tickers; loading prices (cached)...", flush=True)
    prices, opens, failed = R.load_prices_opens(tickers, start, end)
    print(f"[run] prices loaded for {len(prices)} symbols; {len(failed)} failed/missing", flush=True)
    if failed:
        print(f"[run] missing (no price): {failed[:40]}{'...' if len(failed)>40 else ''}", flush=True)

    spb_full = R.spy_benchmark(prices["SPY"], start, end)
    spb_oos = R.spy_benchmark(prices["SPY"], R.OOS_START, end)

    results = {}
    print("[run] H1 high-score...", flush=True)
    results["H1"] = run_one("H1_highscore", R.build_h1, R.H1_HOLD, "long", start, end, prices, opens)
    print("[run] H2 contrarian short...", flush=True)
    results["H2"] = run_one("H2_contrarian_short", R.build_h2, R.H2_HOLD, "short", start, end, prices, opens)
    print("[run] H3 sustained attention...", flush=True)
    results["H3"] = run_one("H3_sustained", R.build_h3, R.H3_HOLD, "long", start, end, prices, opens)
    print("[run] H4 sentiment-filtered velocity...", flush=True)
    results["H4"] = run_one("H4_sentfilter", R.build_h4, R.H4_HOLD, "long", start, end, prices, opens)

    # pick best LONG hypothesis by full-period Sharpe for year-by-year
    long_hyps = {k: v for k, v in results.items() if v["side"] == "long"}
    def sh(v):
        s = v.get("full", {}).get("sharpe")
        return s if isinstance(s, (int, float)) else -99
    best_key = max(long_hyps, key=lambda k: sh(long_hyps[k]))
    build_map = {"H1": R.build_h1, "H3": R.build_h3, "H4": R.build_h4, "H2": R.build_h2}
    hold_map = {"H1": R.H1_HOLD, "H2": R.H2_HOLD, "H3": R.H3_HOLD, "H4": R.H4_HOLD}
    side_map = {"H1": "long", "H2": "short", "H3": "long", "H4": "long"}
    print(f"[run] best long hyp = {best_key}; running year-by-year...", flush=True)
    yby = year_by_year(build_map[best_key], hold_map[best_key], side_map[best_key], start, end, prices, opens)

    # also year-by-year for H2 short (interesting flag) regardless
    yby_h2 = year_by_year(R.build_h2, R.H2_HOLD, "short", start, end, prices, opens)

    # top tickers for best + H2
    tt_best = top_tickers(results[best_key].pop("_trades_full", []))
    tt_h2 = top_tickers(results["H2"].get("_trades_full", []))
    # also worst (tail) for H2
    h2_trades = results["H2"].get("_trades_full", [])
    bottom_h2 = []
    if h2_trades:
        dfh = pd.DataFrame(h2_trades).groupby("ticker").agg(
            total_return=("return", "sum"), n=("return", "count"),
            avg_return=("return", "mean"),
            win_rate=("return", lambda x: float((x > 0).mean()))).sort_values("total_return")
        for tk, r in dfh.head(10).iterrows():
            bottom_h2.append({"ticker": tk, "total_return": round(float(r["total_return"]),4),
                              "n": int(r["n"]), "avg_return": round(float(r["avg_return"]),4),
                              "win_rate": round(float(r["win_rate"]),4)})

    # strip internal trade lists before dump
    for v in results.values():
        v.pop("_trades_full", None)
        v.pop("_sdf_name", None)

    out = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "data_window": {"start": start, "end": end},
        "cost_bps_oneway": R.COST_BPS,
        "spy_benchmark_full": {k: round(v, 4) for k, v in spb_full.items()} if spb_full else {},
        "spy_benchmark_oos": {k: round(v, 4) for k, v in spb_oos.items()} if spb_oos else {},
        "n_prices_loaded": len(prices),
        "n_prices_failed": len(failed),
        "results": results,
        "best_long_hyp": best_key,
        "year_by_year_best": yby,
        "year_by_year_H2_short": yby_h2,
        "top_tickers_best": tt_best,
        "top_tickers_H2_short": tt_h2,
        "bottom_tickers_H2_short": bottom_h2,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, default=str))
    print("\n==== DIGEST ====", flush=True)
    print(f"SPY full: {out['spy_benchmark_full']}", flush=True)
    print(f"SPY oos : {out['spy_benchmark_oos']}", flush=True)
    for k in ["H1", "H2", "H3", "H4"]:
        v = results[k]
        print(f"\n{k} ({v['name']}, hold={v['hold']}d, side={v['side']}):", flush=True)
        print(f"  full     : {v.get('full')}", flush=True)
        print(f"  ex_mania : {v.get('ex_mania')}", flush=True)
        print(f"  oos      : {v.get('oos_post2022')}", flush=True)
    print(f"\nbest long hyp: {best_key}", flush=True)
    print(f"year-by-year ({best_key}): {json.dumps(yby, default=str)}", flush=True)
    print(f"\nH2 short year-by-year: {json.dumps(yby_h2, default=str)}", flush=True)
    print(f"\nJSON -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
