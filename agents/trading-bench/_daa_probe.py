import json, glob, sys
sys.path.insert(0, ".")
f = sorted(glob.glob("reports/_daa_confirm_*.json"))[-1]
r = json.load(open(f))
print("LATEST JSON:", f)
print("DAA window:", r["daa0"]["window"])
print("CTRL window:", r["control_rotation_top2"]["window"])
print()


def show(tag, blk):
    for k in ("is", "oos"):
        b = blk.get("split", {}).get(k)
        if b:
            s = b["stats"]
            print("  %-22s %s  FP %.3f CAGR %.2f%% maxDD %.2f%% (%s..%s)" % (
                tag, k.upper(), b["fp_sharpe"], s["cagr_pct"],
                s["max_drawdown_pct"], b["start"], b["end"]))


show("DAA", r["daa0"])
show("CONTROL", r["control_rotation_top2"])
show("SPX", r["spx"])
print()
print("DAA n_rebalances:", r["daa0"]["n_rebalances"],
      " regimes:", r["daa0"]["regime_counts"])
print("avg_defensive_frac:", round(r["daa0"]["avg_defensive_frac"], 4))
