"""Driver: pre-registered clean short-signal backtest. Runs all cuts + writes JSON."""
import sys
import json
import sqlite3
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reddit_short_cleantest as R


def summ(m):
    if not m or m.get("error"):
        return {"n_trades": (m or {}).get("n_trades", 0), "error": (m or {}).get("error")}
    def r(x, n=3):
        return round(x, n) if (x == x) else None  # NaN guard
    return {
        "n_trades": m["n_trades"], "win_rate": r(m["win_rate"], 4),
        "avg_return": r(m["avg_return"], 4), "sharpe": r(m["sharpe"]),
        "tstat": r(m["tstat"], 2), "cagr": r(m["cagr"], 4),
        "max_dd": r(m["max_dd"], 4), "final_equity": r(m["final_equity"], 2),
    }


def main():
    print("Building velocity-spike signals (full period)...", file=sys.stderr)
    sdf_full = R.build_signals(R.FULL_START, R.FULL_END)
    print(f"  raw velocity-spike signals: {len(sdf_full)} "
          f"({sdf_full['ticker'].nunique()} tickers), "
          f"range {str(sdf_full['date'].min())[:10]}..{str(sdf_full['date'].max())[:10]}",
          file=sys.stderr)

    result = {
        "params": {
            "velocity_threshold": R.VELOCITY_THRESHOLD, "min_mentions": R.MIN_MENTIONS,
            "lookback_days": R.LOOKBACK_DAYS, "min_price": R.MIN_PRICE,
            "min_adv_notional": R.MIN_ADV_NOTIONAL, "adv_window": R.ADV_WINDOW,
            "min_market_cap": R.MIN_MARKET_CAP, "rvol_window": R.RVOL_WINDOW,
            "max_realized_vol": R.MAX_REALIZED_VOL, "cost_bps_oneway": R.COST_BPS_ONEWAY,
            "borrow_bps_per_yr": R.BORROW_BPS_PER_YR, "max_positions": R.MAX_POSITIONS,
        },
        "raw_signals": int(len(sdf_full)),
        "full_filtered": {}, "full_unfiltered": {}, "oos_filtered": {}, "oos_unfiltered": {},
        "by_year_filtered": {}, "filter_stats": None, "top_shorts": [], "worst_shorts": [],
    }

    # ---- Full period, filtered + unfiltered, all holds ----
    fs_captured = None
    for h in R.HOLDS:
        bt_f = R.run_backtest(sdf_full, h, R.FULL_START, R.FULL_END,
                              apply_filter=True, collect_filter_stats=(h == 3))
        result["full_filtered"][h] = summ(R.compute_metrics(bt_f["trades"], R.FULL_START, R.FULL_END, h))
        if h == 3:
            fs_captured = bt_f.get("filter_stats")
            result["full_filtered"][h]["n_passed_signals"] = bt_f["n_passed_signals"]
        bt_u = R.run_backtest(sdf_full, h, R.FULL_START, R.FULL_END, apply_filter=False)
        result["full_unfiltered"][h] = summ(R.compute_metrics(bt_u["trades"], R.FULL_START, R.FULL_END, h))
        print(f"  hold={h}d FILTERED {result['full_filtered'][h]}", file=sys.stderr)
        print(f"  hold={h}d UNFILT   {result['full_unfiltered'][h]}", file=sys.stderr)
    result["filter_stats"] = fs_captured

    # ---- OOS (2023-01-01+), filtered + unfiltered ----
    sdf_oos = R.build_signals(R.OOS_START, R.FULL_END)
    print(f"  OOS raw signals: {len(sdf_oos)}", file=sys.stderr)
    for h in R.HOLDS:
        bt_f = R.run_backtest(sdf_oos, h, R.OOS_START, R.FULL_END, apply_filter=True)
        result["oos_filtered"][h] = summ(R.compute_metrics(bt_f["trades"], R.OOS_START, R.FULL_END, h))
        bt_u = R.run_backtest(sdf_oos, h, R.OOS_START, R.FULL_END, apply_filter=False)
        result["oos_unfiltered"][h] = summ(R.compute_metrics(bt_u["trades"], R.OOS_START, R.FULL_END, h))
        print(f"  OOS hold={h}d FILTERED {result['oos_filtered'][h]}", file=sys.stderr)

    # ---- Year-by-year (hold=3, the canonical short hold), filtered ----
    for yr in [2020, 2021, 2022, 2023, 2024]:
        ys, ye = f"{yr}-01-01", f"{yr}-12-31"
        sdf_y = R.build_signals(ys, ye)
        if sdf_y.empty:
            result["by_year_filtered"][yr] = {"n_trades": 0}
            continue
        bt = R.run_backtest(sdf_y, 3, ys, ye, apply_filter=True)
        result["by_year_filtered"][yr] = summ(R.compute_metrics(bt["trades"], ys, ye, 3))
        print(f"  year={yr} hold=3d {result['by_year_filtered'][yr]}", file=sys.stderr)

    # ---- Ticker contribution (hold=3, full, filtered) ----
    bt3 = R.run_backtest(sdf_full, 3, R.FULL_START, R.FULL_END, apply_filter=True)
    import pandas as pd
    if bt3["trades"]:
        tdf = pd.DataFrame(bt3["trades"])
        agg = tdf.groupby("ticker").agg(
            total_return=("return", "sum"), n_trades=("return", "count"),
            avg_return=("return", "mean"),
            win_rate=("return", lambda x: float((x > 0).mean())),
        ).sort_values("total_return", ascending=False)
        for tk, row in agg.head(15).iterrows():
            result["top_shorts"].append({
                "ticker": tk, "total_return": round(row["total_return"], 4),
                "n_trades": int(row["n_trades"]), "avg_return": round(row["avg_return"], 4),
                "win_rate": round(row["win_rate"], 3)})
        for tk, row in agg.tail(8).iterrows():
            result["worst_shorts"].append({
                "ticker": tk, "total_return": round(row["total_return"], 4),
                "n_trades": int(row["n_trades"]), "avg_return": round(row["avg_return"], 4),
                "win_rate": round(row["win_rate"], 3)})

    # ---- Universe pass-rate vs hand-picked exclusion (overlap analysis) ----
    # Reproduce the OLD hand-picked exclusion set used by H2' for comparison.
    OLD_EXCLUDE = {
        "ALL","AMP","LOW","AI","APP","NET","ES","FIX","DOC","ARM","GEN","ICE",
        "MO","PM","GL","ED","FDS","TECH","FAST","BILL","AM","GO","ON","OR","BE",
        "SO","AN","IT","AR","EX","BY","OUT","NOW","PAY","CAT","TAP","DD",
        # plus the squeeze names H2' hand-excluded via the GME/AMC date window
        # + the "meme/squeeze" prose exclusion (GME,AMC,BB,TSLA,BBBY,CLOV,SPCE,MVIS):
        "GME","AMC","BB","TSLA","BBBY","CLOV","SPCE","MVIS",
    }
    raw_tickers_on_sig = set(sdf_full["ticker"].unique())
    mech_pass_tickers = set(r["ticker"] for r in bt3.get("passed_rows", []))
    # signals removed by mechanical filter
    n_raw = len(sdf_full)
    n_mech_pass = len(bt3.get("passed_rows", []))
    # how the OLD hand-picked list would have filtered the SAME raw signals
    sdf_old = sdf_full[~sdf_full["ticker"].isin(OLD_EXCLUDE)]
    n_old_pass = len(sdf_old)
    result["universe_compare"] = {
        "raw_signals": n_raw,
        "mechanical_pass": n_mech_pass,
        "mechanical_pass_pct": round(100 * n_mech_pass / max(n_raw, 1), 1),
        "handpicked_pass": n_old_pass,
        "handpicked_pass_pct": round(100 * n_old_pass / max(n_raw, 1), 1),
        "tickers_kept_by_mech_only": sorted(mech_pass_tickers - (raw_tickers_on_sig - OLD_EXCLUDE)),
        "tickers_kept_by_handpick_only": sorted((raw_tickers_on_sig - OLD_EXCLUDE) - mech_pass_tickers)[:40],
        "mech_pass_tickers": sorted(mech_pass_tickers),
    }

    out = R.WORKSPACE / "_reddit_short_cleantest_result.json"
    out.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWROTE {out}", file=sys.stderr)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
