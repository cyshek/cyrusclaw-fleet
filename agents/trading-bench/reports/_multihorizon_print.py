import json
d = json.load(open("reports/_multihorizon_trend_ensemble_result.json"))
print("=== MULTI-HORIZON TREND ENSEMBLE — TQQQ vol-target sleeve ===")
print("horizons:", d["horizons"], "| OOS split:", d["oos_split"], "|", d["design"])
print()
hdr = f"{'gate':14s} {'seg':4s} {'Sharpe':>8s} {'CAGR':>8s} {'maxDD':>8s} {'totRet':>10s} {'rebal':>6s} {'ndays':>6s}"
def row(name, seg, m, reb=None):
    return f"{name:14s} {seg:4s} {m['sharpe']:>8.3f} {m['cagr']*100:>7.1f}% {m['maxdd']*100:>7.1f}% {m['total_ret']*100:>9.1f}% {('' if reb is None else str(reb)):>6s} {m['n_days']:>6d}"
print("--- PRIMARY (no extra lag) ---")
print(hdr)
for g in ["baseline","ens_majority","ens_fraction"]:
    gg = d["gates"][g]
    print(row(g,"FULL",gg["full"],gg["n_rebalances"]))
    print(row(g,"IS",gg["is"]))
    print(row(g,"OOS",gg["oos"]))
    print()
print("--- +1 EXTRA-DAY-LAG CANARY (edge must survive) ---")
print(hdr)
for g in ["baseline","ens_majority","ens_fraction"]:
    gg = d["canary"][g]
    print(row(g,"FULL",gg["full"],gg["n_rebalances"]))
    print(row(g,"OOS",gg["oos"]))
    print()
# deltas vs baseline
print("--- ENSEMBLE EDGE vs BASELINE (Sharpe delta) ---")
for seg in ["full","is","oos"]:
    b = d["gates"]["baseline"][seg]["sharpe"]
    maj = d["gates"]["ens_majority"][seg]["sharpe"]
    fr = d["gates"]["ens_fraction"][seg]["sharpe"]
    print(f"  {seg.upper():4s}: baseline {b:+.3f} | majority {maj:+.3f} (Δ{maj-b:+.3f}) | fraction {fr:+.3f} (Δ{fr-b:+.3f})")
print("--- canary OOS Sharpe delta (does edge survive +1 day stale?) ---")
b0 = d["gates"]["baseline"]["oos"]["sharpe"]; bc = d["canary"]["baseline"]["oos"]["sharpe"]
for g in ["baseline","ens_majority","ens_fraction"]:
    o = d["gates"][g]["oos"]["sharpe"]; c = d["canary"][g]["oos"]["sharpe"]
    print(f"  {g:14s}: primary OOS {o:+.3f} -> canary OOS {c:+.3f} (decay {c-o:+.3f})")
