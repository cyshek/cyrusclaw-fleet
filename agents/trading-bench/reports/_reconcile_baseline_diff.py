"""THROWAWAY reconciliation — why does the PASS driver's hand-rolled baseline
(_ensemble_trend_driver.simulate(baseline)) give OOS Sharpe 0.778/+287% while the
REAL engine backtest_daily_voltarget.run_backtest_voltarget gives 0.858/+387%
for the SAME single-SMA-200 vol-target sleeve?

Reads caches only. No orders, no spend, no writes outside reports/.
"""
import sys, math
sys.path.insert(0, ".")
sys.path.insert(0, "strategies_candidates/leveraged_long_trend")

import backtest_daily_voltarget as bv
from backtest_daily_voltarget import VolTargetParams, run_backtest_voltarget, TRADING_DAYS

# import the PASS driver's simulate + gates from workspace root
sys.path.insert(0, ".")
import importlib.util
spec = importlib.util.spec_from_file_location("passdrv", "_ensemble_trend_driver.py")
passdrv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(passdrv)

OOS = "2018-01-01"

def fp_sharpe(equity):
    rets = [equity[i]/equity[i-1]-1 for i in range(1,len(equity)) if equity[i-1] > 0]
    n = len(rets)
    if n < 2: return 0.0
    m = sum(rets)/n
    v = sum((r-m)**2 for r in rets)/(n-1)
    return (m/math.sqrt(v))*math.sqrt(TRADING_DAYS) if v > 0 else 0.0

# ---- 1) REAL engine baseline ----
p = VolTargetParams(
    sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
    gate_mode="sma200", sma_window=200, vix_gate=True, vix_ratio_thr=1.0,
    switch_cost_bps=2.0, use_tbill_cash=True,
    target_ann_vol=0.25, vol_window=20, w_max=1.0,
)
real_full = run_backtest_voltarget(p)
# the real engine returns the full-span; slice OOS off its dates/equity
rd = real_full["strategy"]["dates"]; re_eq = real_full["strategy"]["equity"]
rw = real_full["strategy"]["weights"]
# find OOS start index
import bisect
oidx = bisect.bisect_left(rd, OOS)
real_oos_eq = [1.0] + [re_eq[i]/re_eq[oidx-1] for i in range(oidx, len(re_eq))] if oidx>0 else re_eq
print("REAL engine baseline:")
print(f"  FULL fpS={fp_sharpe(re_eq):.3f}  ret={ (re_eq[-1]/re_eq[0]-1)*100:8.1f}%  n={len(re_eq)}")
print(f"  OOS  fpS={fp_sharpe(real_oos_eq):.3f}  ret={(real_oos_eq[-1]/real_oos_eq[0]-1)*100:8.1f}%  oidx={oidx} date0={rd[oidx] if oidx<len(rd) else 'NA'}")

# ---- 2) PASS driver hand-rolled baseline ----
pp = passdrv.base_params()
hr_full = passdrv.simulate(passdrv.GATES["baseline_sma200"], pp, lag_extra=0)
hr_oos  = passdrv.simulate(passdrv.GATES["baseline_sma200"], pp, lag_extra=0, start=OOS)
print("\nPASS-driver hand-rolled baseline:")
print(f"  FULL fpS={hr_full['fp_sharpe']:.3f}  ret={hr_full['total_ret_pct']:8.1f}%  n={hr_full['n_days']}  avgW={hr_full['avg_weight']:.3f} rebal={hr_full['n_rebal']}")
print(f"  OOS  fpS={hr_oos['fp_sharpe']:.3f}  ret={hr_oos['total_ret_pct']:8.1f}%  n={hr_oos['n_days']}  avgW={hr_oos['avg_weight']:.3f} rebal={hr_oos['n_rebal']}")

# ---- 3) DIFF: span endpoints + avg weight + first divergence ----
print("\nDIFF DIAGNOSIS:")
print(f"  real FULL n={len(rd)} span {rd[0]}..{rd[-1]}")
print(f"  hand FULL n={hr_full['n_days']} span {hr_full['dates'][0]}..{hr_full['dates'][-1]}")
print(f"  real OOS ret +{(real_oos_eq[-1]/real_oos_eq[0]-1)*100:.1f}%  vs hand OOS ret +{hr_oos['total_ret_pct']:.1f}%")
# compare average weight over full
print(f"  real avg weight? (not returned by engine dict directly) — hand avgW full={hr_full['avg_weight']:.3f}")

# Does the real engine apply vol-target weight even when trend is UP via target_weight(trend_up)?
# Probe: how many in-market days does each have?
hr_inmkt = sum(1 for w in hr_full['weights'] if w > 0)
print(f"  hand in-market days (w>0) full = {hr_inmkt}/{len(hr_full['weights'])}")

# real engine weights start at i=1, so weights align to dates[1:]
real_inmkt = sum(1 for w in rw if w > 0)
real_avgw = sum(rw)/len(rw) if rw else 0.0
print(f"  real in-market days (w>0) full = {real_inmkt}/{len(rw)}  real avgW full={real_avgw:.3f}")

# First date where weights diverge materially (align by date)
real_w_by_date = {rd[i+1]: rw[i] for i in range(len(rw))}
hand_w_by_date = {hr_full['dates'][i+1]: hr_full['weights'][i] for i in range(len(hr_full['weights']))}
common = sorted(set(real_w_by_date) & set(hand_w_by_date))
print(f"  common dated weights = {len(common)} (real {len(real_w_by_date)} / hand {len(hand_w_by_date)})")
ndiv = 0
first_div = None
maxdiff = 0.0
for d in common:
    diff = abs(real_w_by_date[d] - hand_w_by_date[d])
    if diff > 1e-6:
        ndiv += 1
        if first_div is None:
            first_div = (d, real_w_by_date[d], hand_w_by_date[d])
        maxdiff = max(maxdiff, diff)
print(f"  weight-divergent days = {ndiv}/{len(common)}  maxdiff={maxdiff:.4f}")
print(f"  first divergence: {first_div}")
