"""Fine lookback scan at MONTHLY cadence around the 126-189-252d region to test
whether 189d is a robust plateau edge or an isolated spike. Also scan the whole
100-260d band at fine resolution. Monthly only (the sweep proved monthly is the
best cadence for every lookback)."""
import sys
sys.path.insert(0, ".")
from _rot_lookback_cadence_sweep import run_rotation, slice_block, full_block, ASSETS, OOS_SPLIT

B_full, B_is, B_oos, B_raw = 0.9069, 0.9293, 0.8752, 1210.1
print("Fine lookback scan @ MONTHLY cadence (baseline 63d: full %.3f IS %.3f OOS %.3f raw %.0f%%)" % (B_full,B_is,B_oos,B_raw))
print("%5s  %8s %8s %8s %9s %8s  %s" % ("lb","full","IS","OOS","raw%","maxDD%","off/def"))
band = list(range(105, 261, 10)) + [126,189,252,168,210,231]
band = sorted(set(band))
rows = {}
for lb in band:
    r = run_rotation(ASSETS, lb_days=lb, cadence_months=1, start="2005-01-01")
    f = full_block(r); is_ = slice_block(r,"2005-01-01",OOS_SPLIT); oos = slice_block(r,"2019-01-01","2099-12-31")
    rows[lb] = (f,is_,oos,r)
    flag = ""
    if f["total_return_pct"]>B_raw and f["sharpe"]>=B_full and oos["sharpe"]>=B_oos and is_["sharpe"]>=B_is:
        flag = " <-- beats on ALL (incl IS)"
    elif f["total_return_pct"]>B_raw and f["sharpe"]>=B_full and oos["sharpe"]>=B_oos:
        flag = " <-- beats raw+full+OOS but IS<base"
    print("%4dd  %8.4f %8.4f %8.4f %9.1f %8.2f  %.2f/%.2f%s" % (
        lb, f["sharpe"], is_["sharpe"], oos["sharpe"], f["total_return_pct"], f["maxdd_pct"],
        r["avg_offense_w"], r["avg_defense_w"], flag))
print()
print("KEY TEST: is the region around 189d a PLATEAU (contiguous run of cells beating baseline")
print("on full+OOS+IS) or a SPIKE (189d alone)? Look at the run of flags above.")
