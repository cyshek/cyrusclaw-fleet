"""Charity check: a DEFENSIVE-ONLY regime variant (only DE-risk in risk-OFF; stay
on the validated static weight in risk-ON) under the honest exmed threshold and a
high-NFCI absolute threshold. If anything helps maxDD/Sharpe without wrecking raw
return that's the AMBER case; otherwise RED stands."""
import sys, json
sys.path.insert(0, ".")
import _regime_allocator as ra
import _allocator_blend_tests as ab

S = ra.load_sleeves()
dates = S["common_dates"]
sleeves = [S["tqqq_r"], S["rot_r"]]
mo = ra.month_open_indices(dates)
mo_dates = [dates[i] for i in mo]
nfci_pit = ra.build_nfci_pit(mo_dates)

seq = [(d, nfci_pit[d][0]) for d in mo_dates if d in nfci_pit]
nvals = [v for _, v in seq]
nfci_pos = {d: k for k, d in enumerate([d for d, _ in seq])}

def exmed(vals, k):
    sub = sorted(vals[:k + 1]); n = len(sub)
    return sub[n // 2] if n % 2 else 0.5 * (sub[n // 2 - 1] + sub[n // 2])

# Defensive-only wfn: w = static - tilt when risk-OFF, else EXACT static (no upside tilt).
def make_def_only(tilt, mode):
    def fn(idx):
        w_static = ra.static_invvol_w_tqqq(sleeves, idx)
        D = dates[idx]
        if D not in nfci_pos:
            return [w_static, 1.0 - w_static]
        k = nfci_pos[D]
        v = nvals[k]
        if mode == "exmed":
            off = v > exmed(nvals, k)
        elif mode == "p75":   # only the tightest quartile counts as risk-OFF
            sub = sorted(nvals[:k + 1]); n = len(sub)
            thr = sub[3 * n // 4] if n >= 4 else 0.0
            off = v > thr
        else:
            off = v > 0.0
        w = (w_static - tilt) if off else w_static
        w = max(0.0, min(1.0, w))
        return [w, 1.0 - w]
    return fn

def summ(b, name):
    r = ra.summarize(b, name)
    return r

static_b = ab.blend_portfolio(dates, sleeves, ra.make_static_wfn(sleeves), blend_cost_bps=2.0, vol_lookback_days=63)
sr = ra.summarize(static_b, "static")
print("STATIC: totret %.0f%% Sharpe %.3f maxDD %.1f%% | OOS totret %.0f%% Sh %.3f maxDD %.1f%%" % (
    sr["full"]["total_return_pct"], sr["full"]["sharpe"], sr["full"]["maxdd_pct"],
    sr["oos_2019_today"]["total_return_pct"], sr["oos_2019_today"]["sharpe"], sr["oos_2019_today"]["maxdd_pct"]))
print()
for mode in ["exmed", "p75"]:
    for tilt in [0.15, 0.25, 0.35]:
        b = ab.blend_portfolio(dates, sleeves, make_def_only(tilt, mode), blend_cost_bps=2.0, vol_lookback_days=63)
        r = ra.summarize(b, "defonly_%s_%.2f" % (mode, tilt))
        f = r["full"]; o = r["oos_2019_today"]
        beat_full = f["total_return_pct"] > sr["full"]["total_return_pct"]
        dd_better = f["maxdd_pct"] > sr["full"]["maxdd_pct"]   # less negative = better
        sh_better = f["sharpe"] > sr["full"]["sharpe"]
        print("defonly %-6s t%.2f: totret %.0f%% Sharpe %.3f maxDD %.1f%% | OOS totret %.0f%% Sh %.3f | beatRawFull=%s ddBetter=%s shBetter=%s" % (
            mode, tilt, f["total_return_pct"], f["sharpe"], f["maxdd_pct"],
            o["total_return_pct"], o["sharpe"], beat_full, dd_better, sh_better))

# Also: the honest symmetric exmed IS vs OOS explicitly
print("\n-- honest symmetric exmed (real ~50/50 regime switch) IS/OOS --")
for tilt in [0.15, 0.25, 0.35]:
    wfn = ra.make_regime_wfn(dates, sleeves, nfci_pit, tilt, "exmed", baa_pit=None, composite="nfci")
    b = ab.blend_portfolio(dates, sleeves, wfn, blend_cost_bps=2.0, vol_lookback_days=63)
    r = ra.summarize(b, "exmed_%.2f" % tilt)
    print("exmed t%.2f: IS totret %.0f%% Sh %.3f | OOS totret %.0f%% Sh %.3f | full Sh %.3f maxDD %.1f%%" % (
        tilt, r["is_2010_2018"]["total_return_pct"], r["is_2010_2018"]["sharpe"],
        r["oos_2019_today"]["total_return_pct"], r["oos_2019_today"]["sharpe"],
        r["full"]["sharpe"], r["full"]["maxdd_pct"]))
print("STATIC IS totret %.0f%% Sh %.3f | OOS totret %.0f%% Sh %.3f" % (
    sr["is_2010_2018"]["total_return_pct"], sr["is_2010_2018"]["sharpe"],
    sr["oos_2019_today"]["total_return_pct"], sr["oos_2019_today"]["sharpe"]))
