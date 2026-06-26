"""Diagnostic: how often does each regime threshold actually fire risk-OFF, and
is the 'nfci_zero' tilt just a near-constant TQQQ overweight (confound)?"""
import sys, json, bisect
sys.path.insert(0, ".")
import _regime_allocator as ra

S = ra.load_sleeves()
dates = S["common_dates"]
sleeves = [S["tqqq_r"], S["rot_r"]]
mo = ra.month_open_indices(dates)
mo_dates = [dates[i] for i in mo]
nfci_pit = ra.build_nfci_pit(mo_dates)

# ordered nfci at month-opens
seq = [(d, nfci_pit[d][0]) for d in mo_dates if d in nfci_pit]
nvals = [v for _, v in seq]

# expanding median series
def exmed(vals, k):
    sub = sorted(vals[:k + 1]); n = len(sub)
    return sub[n // 2] if n % 2 else 0.5 * (sub[n // 2 - 1] + sub[n // 2])

n = len(seq)
off_zero = sum(1 for _, v in seq if v > 0.0)
off_exmed = sum(1 for k, (_, v) in enumerate(seq) if v > exmed(nvals, k))
print("month-opens with NFCI signal:", n)
print("risk-OFF fires under thr=ZERO : %d / %d  (%.1f%%)" % (off_zero, n, 100 * off_zero / n))
print("risk-OFF fires under thr=EXMED: %d / %d  (%.1f%%)" % (off_exmed, n, 100 * off_exmed / n))

# nfci value distribution at month-opens
sv = sorted(nvals)
print("NFCI@month-opens: min %.3f  p25 %.3f  median %.3f  p75 %.3f  max %.3f" % (
    sv[0], sv[n // 4], sv[n // 2], sv[3 * n // 4], sv[-1]))

# For thr=zero tilt: realized w_tqqq distribution (static vs regime tilt 0.35)
import statistics as stt
wfn_static = ra.make_static_wfn(sleeves)
wfn_zero035 = ra.make_regime_wfn(dates, sleeves, nfci_pit, 0.35, "zero", baa_pit=None, composite="nfci")
wfn_exmed035 = ra.make_regime_wfn(dates, sleeves, nfci_pit, 0.35, "exmed", baa_pit=None, composite="nfci")

# evaluate at each month-open (only where signal active for the regime ones)
w_static = []
w_zero = []
w_exmed = []
for i in mo:
    w_static.append(wfn_static(i)[0])
    w_zero.append(wfn_zero035(i)[0])
    w_exmed.append(wfn_exmed035(i)[0])

print("\navg realized w_tqqq:")
print("  static            : %.3f" % stt.mean(w_static))
print("  regime zero  t0.35 : %.3f  (delta vs static %+.3f)" % (stt.mean(w_zero), stt.mean(w_zero) - stt.mean(w_static)))
print("  regime exmed t0.35 : %.3f  (delta vs static %+.3f)" % (stt.mean(w_exmed), stt.mean(w_exmed) - stt.mean(w_static)))

# How much of the time does zero-tilt equal static+0.35 (i.e. risk-ON, capped)?
on_zero = sum(1 for k, (_, v) in enumerate(seq) if v <= 0.0)
print("\nzero-tilt is risk-ON (adds +tilt) on %d/%d (%.1f%%) signalled months -> ~constant overweight" % (
    on_zero, n, 100 * on_zero / n))

# Compare to the original report's STATIC fixed blends to show 'nfci_zero tilt' ~ a fixed higher-w blend
print("\n=> If zero-tilt is ~always +0.35 over static (avg w_tqqq ~%.2f), it is effectively a FIXED" % stt.mean(w_zero))
print("   higher-TQQQ blend (~the report's 60/40-70/30 lane), NOT a regime switch. Check Sharpe/maxDD:")
res = json.load(open("reports/_regime_allocator_result.json"))
for nm in ["nfci_zero_tilt0.35", "nfci_zero_tilt0.25", "nfci_zero_tilt0.15"]:
    r = res["regime_grid"][nm]["full"]
    print("   %-20s totret %.0f%% Sharpe %.3f maxDD %.1f%%" % (nm, r["total_return_pct"], r["sharpe"], r["maxdd_pct"]))
print("   %-20s totret %.0f%% Sharpe %.3f maxDD %.1f%%" % ("STATIC", res["static_invvol_63d"]["full"]["total_return_pct"], res["static_invvol_63d"]["full"]["sharpe"], res["static_invvol_63d"]["full"]["maxdd_pct"]))
