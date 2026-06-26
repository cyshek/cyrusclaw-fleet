"""Decisive confound check: does the longer-lookback 'win' come at the cost of
the crash protection that is the rotation sleeve's ENTIRE purpose? Compare the
baseline 63d/monthly vs the 189d/monthly 'winner' across stress sub-windows
(2008 GFC, 2022 bear) and the rest. Also check dual-lookbacks for any IS-stable beat."""
import sys
sys.path.insert(0, ".")
from _rot_lookback_cadence_sweep import run_rotation, slice_block, full_block, ASSETS
import json

def sub(r, s, e):
    b = slice_block(r, s, e)
    return b

print("=== STRESS-WINDOW DECOMPOSITION: 63d/monthly (baseline) vs 189d/monthly ('winner') ===")
configs = {"63d_monthly": (63,1,None), "189d_monthly": (189,1,None)}
res = {}
for name,(lb,cm,dl) in configs.items():
    res[name] = run_rotation(ASSETS, lb_days=lb, cadence_months=cm, start="2005-01-01", dual_lb=dl)

windows = [
    ("GFC 2007-11..2009-06", "2007-11-01", "2009-06-30"),
    ("calm 2009-07..2019-12","2009-07-01","2019-12-31"),
    ("2020 COVID",           "2020-01-01","2020-12-31"),
    ("2022 bear",            "2022-01-01","2022-12-31"),
    ("2023-2026 bull",       "2023-01-01","2026-06-25"),
]
print("%-24s | %22s | %22s" % ("window", "63d/monthly", "189d/monthly"))
print("%-24s | %7s %7s %7s | %7s %7s %7s" % ("","Sharpe","ret%","maxDD","Sharpe","ret%","maxDD"))
for label,s,e in windows:
    a = sub(res["63d_monthly"],s,e); b = sub(res["189d_monthly"],s,e)
    print("%-24s | %7.3f %7.1f %7.1f | %7.3f %7.1f %7.1f" % (
        label, a.get("sharpe",0),a.get("total_return_pct",0),a.get("maxdd_pct",0),
        b.get("sharpe",0),b.get("total_return_pct",0),b.get("maxdd_pct",0)))
print()
print("Reading: if 189d gives up Sharpe/drawdown in GFC+2022 (the regimes the rotation")
print("sleeve exists to survive) and only wins in the 2019+ bull, the 'edge' is era-luck+beta, not robustness.")
print()

# Dual-lookback IS check from the saved grid
with open("reports/_rot_lookback_cadence_result.json") as f:
    D = json.load(f)

print("=== DUAL-LOOKBACK: any blend with IS>=0.929 AND full>=0.907 AND OOS>=0.875 AND raw>1210? ===")
B_full,B_is,B_oos,B_raw = 0.9069,0.9293,0.8752,1210.1
for key,cads in D["dual_lookback"].items():
    for c,v in cads.items():
        f=v["full"]["sharpe"]; is_=v["is_2005_2018"]["sharpe"]; oos=v["oos_2019_today"]["sharpe"]; raw=v["full"]["total_return_pct"]
        beats_all = f>=B_full and is_>=B_is and oos>=B_oos and raw>B_raw
        tag = " <== BEATS ALL incl IS" if beats_all else (" (IS<base)" if is_<B_is else "")
        if raw>B_raw or beats_all:
            print("  dual %-8s %-9s full %.4f IS %.4f OOS %.4f raw %.1f%% off/def %.2f/%.2f%s" % (
                key,c,f,is_,oos,raw,v["avg_offense_w"],v["avg_defense_w"],tag))
