"""Robustness battery for the DAA confirm-or-kill verdict.

Checks:
  1. +1-bar lag effect on IS and OOS separately (not just full-period) — a real
     signal degrades under extra lag in BOTH; timing noise improves somewhere.
  2. OOS-split sensitivity (2018/2019/2020/2021 cutoffs) — verdict shouldn't
     hinge on one arbitrary split.
  3. Cost sensitivity (2 vs 5 vs 10 bps) — DAA turns over a lot (avg ~1.09/rebal).
  4. Canary attribution: compare DAA (canary cascade) vs a NO-CANARY control that
     just holds top-6 G12 EW every month (same risk universe, no de-risk switch).
     If DAA's tail protection ~= the no-canary version, the canary adds nothing.
"""
import sys
sys.path.insert(0, ".")
from _daa_confirm import run_daa, _fp_sharpe, _daily_rets, RISK_G12, BENCH, COST_BPS
from _sigimprove_tests import run_sector_rotation
from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity


def split_fp(dates, equity, split):
    is_idx = [k for k, d in enumerate(dates) if d <= split]
    oos_idx = [k for k, d in enumerate(dates) if d > split]
    out = {}
    for tag, idx in (("is", is_idx), ("oos", oos_idx)):
        if len(idx) >= 2:
            eq = [equity[k] for k in idx]
            eq = [v / eq[0] for v in eq]
            st = _stats_from_equity([dates[k] for k in idx], eq)
            fp, _ = _fp_sharpe(eq)
            out[tag] = (fp, st.max_drawdown_pct, st.cagr_pct)
    return out


print("=" * 78)
print("1) +1-BAR LAG effect on IS and OOS separately")
print("=" * 78)
d0 = run_daa(signal_lag_extra=0)
d1 = run_daa(signal_lag_extra=1)
for split in ["2019-12-31"]:
    s0 = split_fp(d0["strategy"]["dates"], d0["strategy"]["equity"], split)
    s1 = split_fp(d1["strategy"]["dates"], d1["strategy"]["equity"], split)
    for seg in ("is", "oos"):
        f0 = s0[seg][0]
        f1 = s1[seg][0]
        verdict = "robust (degrades)" if f1 <= f0 + 0.05 else "IMPROVES -> noise"
        print("  %s  lag0 FP %.3f -> +1bar FP %.3f  delta %+.3f  [%s]" % (
            seg.upper(), f0, f1, f1 - f0, verdict))

print()
print("=" * 78)
print("2) OOS-SPLIT SENSITIVITY (DAA vs CONTROL vs SPX, OOS FP-Sharpe)")
print("=" * 78)
ctrl = run_sector_rotation(["SPY", "QQQ", "GLD", "TLT"], bench=BENCH, lookback_months=3,
                           hold_top=2, cost_bps=COST_BPS,
                           start=d0["window"]["start"], end=d0["window"]["end"])
for split in ["2017-12-31", "2018-12-31", "2019-12-31", "2020-12-31", "2021-12-31"]:
    sd = split_fp(d0["strategy"]["dates"], d0["strategy"]["equity"], split)
    sc = split_fp(ctrl["strategy"]["dates"], ctrl["strategy"]["equity"], split)
    ss = split_fp(d0["strategy"]["dates"], d0["spx"]["equity"], split)
    win = "DAA" if sd["oos"][0] > sc["oos"][0] else "CTRL"
    print("  split %s  OOS: DAA %.3f | CTRL %.3f | SPX %.3f   -> %s wins OOS" % (
        split, sd["oos"][0], sc["oos"][0], ss["oos"][0], win))

print()
print("=" * 78)
print("3) COST SENSITIVITY (DAA full-period FP-Sharpe / CAGR / maxDD)")
print("=" * 78)
for bps in [0.0, 2.0, 5.0, 10.0]:
    dd = run_daa(cost_bps=bps)
    fp, _ = _fp_sharpe(dd["strategy"]["equity"])
    st = dd["strategy"]["stats"]
    print("  %4.1f bps  FP %.3f  CAGR %.2f%%  maxDD %.2f%%  totRet %.1f%%" % (
        bps, fp, st["cagr_pct"], st["max_drawdown_pct"], st["total_return_pct"]))

print()
print("=" * 78)
print("4) CANARY ATTRIBUTION: DAA cascade vs NO-CANARY top-6 G12 EW (same universe)")
print("=" * 78)
# no-canary = always-on top-6 of G12 by simple 3m momentum (run_sector_rotation),
# i.e. the risk universe WITHOUT the de-risk switch. If its maxDD ~= DAA's, the
# canary cascade adds nothing; if DAA is much shallower, the canary IS the edge.
nocan = run_sector_rotation(RISK_G12, bench=BENCH, lookback_months=3, hold_top=6,
                            cost_bps=COST_BPS, start=d0["window"]["start"],
                            end=d0["window"]["end"])
ncfp, _ = _fp_sharpe(nocan["strategy"]["equity"])
ncst = nocan["strategy"]["stats"]
d0fp, _ = _fp_sharpe(d0["strategy"]["equity"])
d0st = d0["strategy"]["stats"]
print("  DAA (canary cascade) : FP %.3f  CAGR %.2f%%  maxDD %.2f%%" % (
    d0fp, d0st["cagr_pct"], d0st["max_drawdown_pct"]))
print("  NO-CANARY top6 G12 EW: FP %.3f  CAGR %.2f%%  maxDD %.2f%%" % (
    ncfp, ncst["cagr_pct"], ncst["max_drawdown_pct"]))
dd_gap = ncst["max_drawdown_pct"] - d0st["max_drawdown_pct"]
print("  -> canary cuts %.1fpp of maxDD vs always-on same risk universe" % dd_gap)
print("  -> FP delta from canary: %+.3f" % (d0fp - ncfp))
