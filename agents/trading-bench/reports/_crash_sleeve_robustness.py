"""Robustness add-on: does a FASTER regime trigger (trailing-drawdown breach,
which engages quicker than the laggy 200d SMA) break the DD-vs-raw tradeoff any
better than the SMA-200 gate? Reuses the probe driver's machinery."""
import sys, json
sys.path.insert(0, ".")
sys.path.insert(0, "reports")
from _crash_sleeve_probe_driver import (
    build_sleeves, stats_from_returns, run_config, SMA_WIN,
)
import _crash_sleeve_probe_driver as P

S = build_sleeves()
dates = S["common_dates"]; tqqq_r = S["tqqq_r"]; rot_r = S["rot_r"]; spx_r = S["spx_r"]
spx_curve = stats_from_returns(dates, spx_r)
spx_dates = spx_curve["dates"]; spx_equity = spx_curve["equity"]
hedge_cash = [0.0] * len(dates)


def build_dd_flags(spx_r, dd_thresh, extra_lag=0):
    """regime_on[idx] = SPX trailing drawdown (from running peak) worse than
    dd_thresh, computed PAST-ONLY through idx-1-extra_lag."""
    n = len(spx_r)
    price = [1.0] * n
    for i in range(1, n):
        price[i] = price[i - 1] * (1.0 + spx_r[i])
    flags = [False] * n
    for idx in range(n):
        cut = idx - 1 - extra_lag
        if cut < 1:
            flags[idx] = False
            continue
        peak = max(price[: cut + 1])
        dd = price[cut] / peak - 1.0
        flags[idx] = dd <= dd_thresh
    return flags


# baseline
base_rep, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity,
                         [False] * len(dates), 0.0, "baseline")
base_oos_dd = base_rep["oos_2019_today"]["maxdd_pct"]
base_raw = base_rep["full"]["total_return_pct"]
print("BASELINE OOS maxDD %.2f%%  raw %.0f%%" % (base_oos_dd, base_raw))
print()
print("=== FASTER trigger: trailing-DD breach, cash hedge ===")
print("%-28s %8s %8s %8s %8s %9s" % ("trigger/weight", "raw%", "OOSdd%", "giveup", "DDcut", "DDpp/100"))
for thr in [-0.05, -0.08, -0.10, -0.15]:
    flags = build_dd_flags(spx_r, thr, extra_lag=0)
    on_oos = sum(1 for i, dd in enumerate(dates) if dd >= "2019-01-01" and flags[i])
    n_oos = sum(1 for dd in dates if dd >= "2019-01-01")
    for w_h in [0.15, 0.25]:
        rep, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flags, w_h, "dd%d_wh%d" % (int(thr*100), int(w_h*100)))
        oos_dd = rep["oos_2019_today"]["maxdd_pct"]
        raw = rep["full"]["total_return_pct"]
        ddcut = oos_dd - base_oos_dd
        giveup = base_raw - raw
        eff = ddcut / max(1.0, giveup) * 100.0
        hd = rep["hedge_diag"]
        print("DD<%d%%/wh%d  on=%4.1f%%oos  %8.0f %8.2f %8.0f %+8.2f %9.2f" % (
            int(thr*100), int(w_h*100), 100.0*on_oos/max(1,n_oos), raw, oos_dd, giveup, ddcut, eff))

# canary on the most aggressive faster-trigger
print()
print("=== CANARY +1bar on DD<-5%/wh25 (fastest+biggest) ===")
flags_sb = build_dd_flags(spx_r, -0.05, extra_lag=0)
flags_lag = build_dd_flags(spx_r, -0.05, extra_lag=1)
sb, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flags_sb, 0.25, "sb")
lg, _ = run_config(dates, tqqq_r, rot_r, hedge_cash, spx_dates, spx_equity, flags_lag, 0.25, "lg")
print("same-bar OOSdd %.2f%% raw %.0f%% OOSsh %.3f" % (sb["oos_2019_today"]["maxdd_pct"], sb["full"]["total_return_pct"], sb["oos_2019_today"]["sharpe"]))
print("lag+1    OOSdd %.2f%% raw %.0f%% OOSsh %.3f" % (lg["oos_2019_today"]["maxdd_pct"], lg["full"]["total_return_pct"], lg["oos_2019_today"]["sharpe"]))
print()
print("static-haven (rejected) exchange rate: 1.49 DD-pp per 100pp raw (full maxDD basis)")
print("SMA-200 cash gate exchange rate: ~1.40 DD-pp per 100pp raw (OOS basis)")
