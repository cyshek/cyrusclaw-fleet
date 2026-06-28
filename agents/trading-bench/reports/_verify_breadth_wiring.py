#!/usr/bin/env python3
"""Verify the live strategy.py breadth wiring reproduces the validated tiebreak.

Two-part proof (read-only; writes nothing outside stdout):

  PART A — SCALER PARITY: the live strategy.py breadth_gate_scaler MUST produce
    bit-identical g values to the validated tiebreak driver's make_breadth_scaler
    ((30,90,180)) AND its make_base_scaler (single 200), evaluated on the SAME
    QQQ adjclose history through every decision day. If the scalers match and the
    weight application w=clamp(g*vt) is the same formula already proven at engine
    parity (max|Δequity|=0 in the tiebreak), the resulting equity curve is
    guaranteed identical -> the live wiring inherits the validated
    +0.018 OOS / -22.55% maxDD result.

  PART B — END-TO-END via the validated simulate(): swap the tiebreak driver's
    scaler for the LIVE strategy.py scaler and re-run simulate() under the live
    convention (vix_gate=False). Confirm the headline metrics match the recorded
    JSON for {30,90,180} and that the binary fallback matches base.

No orders, no spend, no protected-file writes. Reuses the on-disk validated
driver as the oracle.
"""
import sys
import json
import importlib.util
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
sys.path.insert(0, str(WS))


def _load(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Live strategy under test — import via its REAL package path so @dataclass
# resolves cls.__module__ correctly (a custom spec name breaks dataclasses).
import importlib  # noqa: E402
live = importlib.import_module("strategies.leveraged_long_trend_paper.strategy")
# Validated tiebreak driver (the oracle). It runs its harness on import-time only
# inside __main__, so importing as a module just gives us the functions.
drv = _load("tb_driver", WS / "reports/_ens_breadth_tiebreak_driver.py")

# Recorded result JSON (the numbers we must reproduce)
RES = json.load(open(WS / "reports/_ens_breadth_tiebreak_result.json"))

TRIPLE = (30, 90, 180)

# ---- gather the underlying (QQQ) adjclose history exactly as the driver does --
import strategies_candidates.leveraged_long_trend.backtest_daily as bd  # noqa: E402

under_bars = bd.dbc.get_daily(drv.UNDERLYING)
under_dates = [b["date"] for b in under_bars]
under_close = [float(b["adjclose"]) for b in under_bars]
import bisect  # noqa: E402


def under_closes_through(d_iso):
    idx = bisect.bisect_right(under_dates, d_iso)
    return under_close[:idx]

# Decision calendar = sleeve dates (same as simulate's cal)
sleeve_bars = bd.dbc.get_daily(drv.SLEEVE)
cal = [b["date"] for b in sleeve_bars]

# Oracle scalers from the validated driver
oracle_breadth = drv.make_breadth_scaler(TRIPLE)
oracle_base = drv.make_base_scaler()

# ===================== PART A: scaler parity ============================
max_abs_diff_breadth = 0.0
max_abs_diff_base = 0.0
n_checked = 0
mism_breadth = 0
mism_base = 0
for d in cal:
    uc = under_closes_through(d)
    g_live_b = live.breadth_gate_scaler(uc, [30, 90, 180])
    g_oracle_b = oracle_breadth(uc)
    g_live_base = live.breadth_gate_scaler(uc, [200])
    g_oracle_base = oracle_base(uc)
    db = abs(g_live_b - g_oracle_b)
    dbase = abs(g_live_base - g_oracle_base)
    if db > max_abs_diff_breadth:
        max_abs_diff_breadth = db
    if dbase > max_abs_diff_base:
        max_abs_diff_base = dbase
    if db > 1e-12:
        mism_breadth += 1
    if dbase > 1e-12:
        mism_base += 1
    n_checked += 1

print("=" * 70)
print("PART A  — SCALER PARITY (live strategy.py vs validated tiebreak oracle)")
print("=" * 70)
print(f"  decision days checked        : {n_checked}")
print(f"  {{30,90,180}} max|g_live - g_oracle| : {max_abs_diff_breadth:.3e}   mismatches: {mism_breadth}")
print(f"  {{200}} base max|g_live - g_oracle|  : {max_abs_diff_base:.3e}   mismatches: {mism_base}")
breadth_ok = (max_abs_diff_breadth == 0.0 and mism_breadth == 0)
base_ok = (max_abs_diff_base == 0.0 and mism_base == 0)
print(f"  breadth scaler BIT-IDENTICAL : {breadth_ok}")
print(f"  base scaler   BIT-IDENTICAL  : {base_ok}")

# ===================== PART B: end-to-end via simulate ===================
# Re-run the validated simulate() with the LIVE strategy.py scaler and confirm
# the headline metrics reproduce the recorded JSON for {30,90,180} + base.
print()
print("=" * 70)
print("PART B  — END-TO-END via validated simulate() (live scaler swapped in)")
print("=" * 70)


def live_breadth_scaler(uc):
    return live.breadth_gate_scaler(uc, [30, 90, 180])


def live_base_scaler(uc):
    return live.breadth_gate_scaler(uc, [200])


VIX_LIVE = drv.VIX_GATE_LIVE  # False

sim_breadth = drv.simulate(live_breadth_scaler, vix_gate=VIX_LIVE, lag_extra=0)
sim_breadth_can = drv.simulate(live_breadth_scaler, vix_gate=VIX_LIVE, lag_extra=1)
sim_base = drv.simulate(live_base_scaler, vix_gate=VIX_LIVE, lag_extra=0)

SPLIT = drv.SPLIT


def m(sim, a=None, b=None):
    return drv.slice_metrics(sim, a, b)


live_b_oos = m(sim_breadth, SPLIT, None)
live_b_oos_can = m(sim_breadth_can, SPLIT, None)
live_base_oos = m(sim_base, SPLIT, None)

rec_b_oos = RES["triples"]["30-90-180"]["oos"]
rec_b_oos_can = RES["triples"]["30-90-180"]["canary_oos"]
rec_base_oos = RES["base"]["oos"]


def cmp_row(label, live_blk, rec_blk):
    keys = ["sharpe_fp", "total_ret_pct", "maxdd_pct"]
    print(f"  {label}")
    allok = True
    for k in keys:
        lv = live_blk[k]
        rv = rec_blk[k]
        d = abs(lv - rv)
        ok = d < 1e-6
        allok = allok and ok
        print(f"      {k:14s}: live {lv:+.6f}  recorded {rv:+.6f}  Δ {d:.2e}  {'OK' if ok else 'MISMATCH'}")
    return allok


ok1 = cmp_row("{30,90,180} OOS         (live simulate vs recorded JSON)", live_b_oos, rec_b_oos)
ok2 = cmp_row("{30,90,180} OOS+canary  (live simulate vs recorded JSON)", live_b_oos_can, rec_b_oos_can)
ok3 = cmp_row("base (single SMA-200) OOS (live simulate vs recorded JSON)", live_base_oos, rec_base_oos)

# Deltas (the actual claim)
dS = live_b_oos["sharpe_fp"] - live_base_oos["sharpe_fp"]
dS_can = live_b_oos_can["sharpe_fp"] - m(sim_base, SPLIT, None)["sharpe_fp"]  # noqa (base canary not run; approximate)
ddd = live_b_oos["maxdd_pct"] - live_base_oos["maxdd_pct"]
print()
print("  CLAIM REPRODUCED (live-scaler-driven):")
print(f"      OOS ΔSharpe(breadth - base) = {dS:+.4f}   (claim +0.018)")
print(f"      OOS maxDD breadth {live_b_oos['maxdd_pct']:+.2f}% vs base {live_base_oos['maxdd_pct']:+.2f}%  (claim -22.55% vs -34.52%)")

print()
print("=" * 70)
allgood = breadth_ok and base_ok and ok1 and ok2 and ok3
print(f"OVERALL: {'PASS — live wiring reproduces the validated result bit-for-bit' if allgood else 'FAIL — investigate'}")
print("=" * 70)
sys.exit(0 if allgood else 1)
