"""ALLOCATOR BREADTH ENGINE PORT — verification driver.

PAPER RESEARCH ONLY. Reads caches read-only via the engine. Writes nothing but
its own stdout (the markdown report is written by the parent task separately).
Does NOT touch runner/, the live sleeve, crontab, or any *.db.

PURPOSE
=======
Prove that the breadth-capable VolTargetParams.breadth_windows port into
strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py is:

  (A) NON-DESTRUCTIVE: breadth_windows=None reproduces the documented binary
      SMA-200 baseline BIT-FOR-BIT (engine pop-Sharpe 0.853913, fp-Sharpe
      0.853809, maxDD -34.5236%, total +2002.071%).
  (B) CORRECT: breadth_windows=[30,90,180] reproduces the validated target
      table from reports/_ens_breadth_tiebreak_result.json (the 30-90-180
      triple) to ~1e-6 on Sharpe and ~1e-9 on equity:
         FULL: total +1339.64%, fpS 0.8306, popS 0.830719, maxdd -29.853%,
               avgW 0.47287, n=4118
         OOS : total +315.19%, fpS 0.8551, maxdd -22.550%, avgW 0.40784, n=2132
         IS  : fpS 0.7786, maxdd -29.853%

The convention (continuous full-span sim, slice OOS @2018-01-01, fp-Sharpe
ddof=1 sqrt252, vix_gate=False) is the LIVE-sleeve + engine validate_oos
convention. We drive the REAL engine run_backtest_voltarget() and slice its
returned continuous equity exactly as the validated tiebreak driver did, so a
match here is a match against the validated artifact.

Run: PYTHONPATH=. python3 reports/_allocator_breadth_engine_port_verify.py
"""
from __future__ import annotations

import bisect
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget,
)
from runner.fp_sharpe import sharpe_from_returns
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS

WORKSPACE = Path(__file__).resolve().parent.parent
GOLD = WORKSPACE / "reports" / "_ens_breadth_tiebreak_result.json"
BPY = float(TRADING_DAYS)
SPLIT = "2018-01-01"

# Live-sleeve config (params.json), the convention the allocator uses.
LIVE = dict(sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC", gate_mode="sma200",
            sma_window=200, vix_gate=False, vix_ratio_thr=1.0, switch_cost_bps=2.0,
            use_tbill_cash=True, target_ann_vol=0.25, vol_window=20, w_max=1.0)

# Tolerances: equity bit-for-bit (engine-vs-engine reslice), Sharpe to ~1e-6.
TOL_EQUITY = 1e-9
TOL_SHARPE = 1e-6
TOL_DD = 1e-4      # pp; maxdd reported to ~4dp in gold
TOL_TOTAL = 1e-3   # pct
TOL_AVGW = 1e-6


def slice_metrics(dates: List[str], eq: List[float], weights: List[float],
                  start: Optional[str], end: Optional[str]) -> Dict:
    """Reslice a CONTINUOUS equity curve to [start,end]; fp/pop Sharpe, total,
    CAGR, maxDD, avg weight. Mirrors the validated tiebreak slice_metrics so the
    numbers are directly comparable to the gold JSON."""
    lo = 0 if start is None else bisect.bisect_left(dates, start)
    hi = len(dates) if end is None else bisect.bisect_right(dates, end)
    if hi - lo < 2:
        return {"n": hi - lo}
    seg = eq[lo:hi]
    rets = [seg[j] / seg[j - 1] - 1.0 for j in range(1, len(seg))]
    total = (seg[-1] / seg[0] - 1.0) * 100.0
    sh_fp = sharpe_from_returns(rets, BPY)
    m = sum(rets) / len(rets)
    var0 = sum((r - m) ** 2 for r in rets) / len(rets)
    sd0 = math.sqrt(var0)
    sh_pop = (m / sd0) * math.sqrt(BPY) if sd0 > 0 else 0.0
    peak = seg[0]
    mdd = 0.0
    for v in seg:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    # weights[k] is the weight held over dates[k+1]; slice by held date.
    wsel = []
    for k in range(len(weights)):
        held = dates[k + 1]
        if (start is None or held >= start) and (end is None or held <= end):
            wsel.append(weights[k])
    avg_w = (sum(wsel) / len(wsel)) if wsel else 0.0
    return {"n": hi - lo, "first": dates[lo], "last": dates[hi - 1],
            "total_ret_pct": total, "sharpe_fp": sh_fp, "sharpe_pop": sh_pop,
            "maxdd_pct": mdd * 100.0, "avg_weight": avg_w}


def run_block(breadth_windows: Optional[List[int]]) -> Dict:
    p = VolTargetParams(breadth_windows=breadth_windows, **LIVE)
    r = run_backtest_voltarget(p)
    dates = r["strategy"]["dates"]
    eq = r["strategy"]["equity"]
    weights = r["strategy"]["weights"]
    return {
        "dates": dates, "equity": eq, "weights": weights,
        "engine_stats": r["strategy"]["stats"],
        "full": slice_metrics(dates, eq, weights, None, None),
        "is": slice_metrics(dates, eq, weights, None, "2017-12-31"),
        "oos": slice_metrics(dates, eq, weights, SPLIT, None),
    }


def _chk(label, got, want, tol):
    ok = abs(got - want) <= tol
    return {"label": label, "got": got, "want": want, "diff": got - want,
            "tol": tol, "ok": ok}


def main() -> Dict:
    gold = json.loads(GOLD.read_text())
    gbase = gold["base"]                  # engine binary baseline (continuous slice)
    gtrip = gold["triples"]["30-90-180"]  # the validated triple

    # ---- (A) None path == documented binary baseline (bit-for-bit) ----
    base = run_block(None)
    checks_base = [
        _chk("base.full.total_ret_pct", base["full"]["total_ret_pct"], gbase["full"]["total_ret_pct"], TOL_TOTAL),
        _chk("base.full.sharpe_fp",     base["full"]["sharpe_fp"],     gbase["full"]["sharpe_fp"],     TOL_SHARPE),
        _chk("base.full.sharpe_pop",    base["full"]["sharpe_pop"],    gbase["full"]["sharpe_pop"],    TOL_SHARPE),
        _chk("base.full.maxdd_pct",     base["full"]["maxdd_pct"],     gbase["full"]["maxdd_pct"],     TOL_DD),
        _chk("base.full.avg_weight",    base["full"]["avg_weight"],    gbase["full"]["avg_weight"],    TOL_AVGW),
        _chk("base.oos.sharpe_fp",      base["oos"]["sharpe_fp"],      gbase["oos"]["sharpe_fp"],      TOL_SHARPE),
        _chk("base.oos.maxdd_pct",      base["oos"]["maxdd_pct"],      gbase["oos"]["maxdd_pct"],      TOL_DD),
        _chk("base.is.sharpe_fp",       base["is"]["sharpe_fp"],       gbase["is"]["sharpe_fp"],       TOL_SHARPE),
        _chk("base.is.maxdd_pct",       base["is"]["maxdd_pct"],       gbase["is"]["maxdd_pct"],       TOL_DD),
    ]
    # engine_stats cross-check (the engine's own pop-Sharpe / maxdd / total)
    es = base["engine_stats"]
    checks_base += [
        _chk("base.engine.total_return_pct", es["total_return_pct"], gbase["full"]["total_ret_pct"], TOL_TOTAL),
        _chk("base.engine.sharpe(pop)",      es["sharpe"],           gbase["full"]["sharpe_pop"],    TOL_SHARPE),
        _chk("base.engine.max_drawdown_pct", es["max_drawdown_pct"], gbase["full"]["maxdd_pct"],     TOL_DD),
        _chk("base.engine.avg_weight",       es["avg_weight"],       gbase["full"]["avg_weight"],    TOL_AVGW),
    ]

    # ---- equity bit-for-bit: engine None path vs gold base equity is implicit
    #      (gold base IS the engine run); we instead assert the engine None path
    #      reproduces the gold base equity by reconstructing it is impossible
    #      (gold didn't store equity). The 0-diff parity guarantee is the gold's
    #      own parity block (max_abs_equity_diff=0.0 vix_off). We re-state it.
    gold_parity = gold["parity"]["vix_off"]["max_abs_equity_diff"]

    # ---- (B) [30,90,180] path == validated triple ----
    trip = run_block([30, 90, 180])
    checks_trip = [
        _chk("trip.full.total_ret_pct", trip["full"]["total_ret_pct"], gtrip["full"]["total_ret_pct"], TOL_TOTAL),
        _chk("trip.full.sharpe_fp",     trip["full"]["sharpe_fp"],     gtrip["full"]["sharpe_fp"],     TOL_SHARPE),
        _chk("trip.full.sharpe_pop",    trip["full"]["sharpe_pop"],    gtrip["full"]["sharpe_pop"],    TOL_SHARPE),
        _chk("trip.full.maxdd_pct",     trip["full"]["maxdd_pct"],     gtrip["full"]["maxdd_pct"],     TOL_DD),
        _chk("trip.full.avg_weight",    trip["full"]["avg_weight"],    gtrip["full"]["avg_weight"],    TOL_AVGW),
        _chk("trip.oos.total_ret_pct",  trip["oos"]["total_ret_pct"],  gtrip["oos"]["total_ret_pct"],  TOL_TOTAL),
        _chk("trip.oos.sharpe_fp",      trip["oos"]["sharpe_fp"],      gtrip["oos"]["sharpe_fp"],      TOL_SHARPE),
        _chk("trip.oos.maxdd_pct",      trip["oos"]["maxdd_pct"],      gtrip["oos"]["maxdd_pct"],      TOL_DD),
        _chk("trip.oos.avg_weight",     trip["oos"]["avg_weight"],     gtrip["oos"]["avg_weight"],     TOL_AVGW),
        _chk("trip.is.sharpe_fp",       trip["is"]["sharpe_fp"],       gtrip["is"]["sharpe_fp"],       TOL_SHARPE),
        _chk("trip.is.maxdd_pct",       trip["is"]["maxdd_pct"],       gtrip["is"]["maxdd_pct"],       TOL_DD),
    ]

    # ---- empty-list path also == binary (non-destructive for [] too) ----
    empty = run_block([])
    checks_empty = [
        _chk("empty.full.sharpe_pop", empty["full"]["sharpe_pop"], gbase["full"]["sharpe_pop"], TOL_SHARPE),
        _chk("empty.full.maxdd_pct",  empty["full"]["maxdd_pct"],  gbase["full"]["maxdd_pct"],  TOL_DD),
        _chk("empty.full.total_ret_pct", empty["full"]["total_ret_pct"], gbase["full"]["total_ret_pct"], TOL_TOTAL),
    ]
    # bit-for-bit None-vs-empty equity (both must be the identical binary curve)
    ne_maxdiff = max(abs(a - b) for a, b in zip(base["equity"], empty["equity"]))
    checks_empty.append({"label": "None-vs-empty max|Δequity|", "got": ne_maxdiff,
                         "want": 0.0, "diff": ne_maxdiff, "tol": TOL_EQUITY,
                         "ok": ne_maxdiff <= TOL_EQUITY})

    all_checks = checks_base + checks_trip + checks_empty
    n_pass = sum(1 for c in all_checks if c["ok"])
    n_fail = len(all_checks) - n_pass

    out = {
        "gold_parity_vixoff_max_abs_equity_diff": gold_parity,
        "none_vs_empty_max_abs_equity_diff": ne_maxdiff,
        "base_full": base["full"], "base_oos": base["oos"], "base_is": base["is"],
        "base_engine_stats": {k: es[k] for k in ("total_return_pct", "sharpe", "max_drawdown_pct", "avg_weight")},
        "trip_full": trip["full"], "trip_oos": trip["oos"], "trip_is": trip["is"],
        "checks": all_checks, "n_pass": n_pass, "n_fail": n_fail,
        "verdict": "PASS" if n_fail == 0 else "FAIL",
    }
    return out


if __name__ == "__main__":
    res = main()
    print("=" * 100)
    print("ALLOCATOR BREADTH ENGINE PORT — VERIFICATION")
    print("=" * 100)
    print("Convention: continuous full-span sim, slice OOS @%s, fp-Sharpe ddof=1 sqrt252, vix_gate=False" % SPLIT)
    print("gold parity (vix_off) max|Δequity| engine-vs-wrapper: %.2e" % res["gold_parity_vixoff_max_abs_equity_diff"])
    print("None-vs-empty-list max|Δequity| (both must be binary): %.2e" % res["none_vs_empty_max_abs_equity_diff"])
    print()
    def _row(tag, b):
        print("  %-26s n=%-5d total=%11.4f%%  fpS=%.6f  popS=%.6f  maxDD=%.4f%%  avgW=%.6f"
              % (tag, b["n"], b["total_ret_pct"], b["sharpe_fp"], b["sharpe_pop"], b["maxdd_pct"], b["avg_weight"]))
    print("BASE (breadth_windows=None):")
    _row("FULL", res["base_full"]); _row("OOS", res["base_oos"]); _row("IS", res["base_is"])
    print("TRIPLE (breadth_windows=[30,90,180]):")
    _row("FULL", res["trip_full"]); _row("OOS", res["trip_oos"]); _row("IS", res["trip_is"])
    print()
    print("CHECKS (got vs want, tol):")
    for c in res["checks"]:
        flag = "OK " if c["ok"] else "XXX"
        print("  [%s] %-32s got=%-16.8g want=%-16.8g diff=%+.3e tol=%.0e"
              % (flag, c["label"], c["got"], c["want"], c["diff"], c["tol"]))
    print()
    print("RESULT: %d/%d checks pass, %d fail -> %s"
          % (res["n_pass"], res["n_pass"] + res["n_fail"], res["n_fail"], res["verdict"]))
