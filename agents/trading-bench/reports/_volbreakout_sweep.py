"""Param sweep for volume_breakout_qqq through the existing WF gate.

Question: does a (volume_mult, exit_lookback) config exist that both
(a) passes the walk_forward fitness gate AND (b) actually fires enough
trades to be non-inert live? READ-ONLY: builds a temp params dict per
cell, runs runner.walk_forward.walk_forward(), reports aggregate + total
trades. Does NOT touch the live params.json.
"""
from __future__ import annotations
import json, sys
from runner import walk_forward as wf
from runner.backtest import load_strategy_module_and_params

STRAT = "volume_breakout_qqq"

# Load the live params as the base, then override per cell.
module, base_params = load_strategy_module_and_params(STRAT)
print("live base params:", json.dumps(base_params))
print()

# Sweep grid: volume_mult (the inert culprit, live=3.0) x exit_lookback (live=8, <1 day @1H)
VOL_MULTS = [1.2, 1.5, 2.0, 2.5, 3.0]
EXIT_LBS = [8, 17, 25]   # 8≈1day, 17≈2days, 25≈3days at 8.5 bars/day

def total_trades(agg) -> int:
    return sum(w.backtest.n_trades for w in agg.windows if w.backtest is not None)

print(f"{'volMult':>7s} {'exitLB':>6s} {'win':>4s} {'medRet%':>8s} {'%pos':>5s} {'beatBH':>6s} {'medShrp':>7s} {'spyExc%':>8s} {'medIR':>6s} {'trades':>6s}  gate")
results = []
for vm in VOL_MULTS:
    for elb in EXIT_LBS:
        p = dict(base_params)
        p["volume_mult"] = vm
        p["exit_lookback"] = elb
        try:
            agg = wf.walk_forward(STRAT, params=p)
        except Exception as ex:
            print(f"  cell vm={vm} elb={elb} errored: {ex}")
            continue
        ok, reason = wf.passes_fitness_gate(agg)
        tt = total_trades(agg)
        gate = "PASS" if ok else f"FAIL"
        results.append((vm, elb, ok, tt, agg.median_return_pct, agg.median_sharpe,
                        agg.median_spy_excess_ann_return, agg.median_spy_information_ratio, reason))
        print(f"{vm:>7.1f} {elb:>6d} {agg.n_windows_with_data:>4d} {agg.median_return_pct:>8.2f} "
              f"{agg.pct_positive*100:>4.0f}% {agg.pct_beat_bh_spy*100:>5.0f}% {agg.median_sharpe:>7.2f} "
              f"{agg.median_spy_excess_ann_return*100:>8.2f} {agg.median_spy_information_ratio:>6.2f} "
              f"{tt:>6d}  {gate}{('  ('+reason+')') if not ok else ''}")

print()
# Verdict logic
passing = [r for r in results if r[2] and r[3] >= 8]  # passes gate AND >=8 trades over 8 windows (non-inert)
pos_alpha = [r for r in results if r[6] > 0]
print(f"configs that PASS gate AND fire >=8 trades: {len(passing)}")
for r in passing:
    print(f"  volMult={r[0]} exitLB={r[1]} trades={r[3]} medRet={r[4]:+.2f}% spyExc={r[6]*100:+.2f}%/yr IR={r[7]:+.2f}")
print(f"configs with POSITIVE SPY-excess alpha: {len(pos_alpha)}")
for r in pos_alpha:
    print(f"  volMult={r[0]} exitLB={r[1]} spyExc={r[6]*100:+.2f}%/yr IR={r[7]:+.2f} gate={'PASS' if r[2] else 'FAIL'} trades={r[3]}")
