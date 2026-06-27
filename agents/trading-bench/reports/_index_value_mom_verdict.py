"""Final verdict table: for each value leg, evaluate the JOINT gate condition.
GATE-PASS requires ALL of:
  (A) imperfect-negative corr to mom: corr_to_mom in roughly (-0.7, -0.05)
      (negative enough to diversify, but NOT ~ -1 i.e. not short-mom)
  (B) own non-negative standalone expectancy: fp_sharpe >= 0 AND oos_sharpe >= 0
  (C) survives 1-day-lag canary (already shown stable lag1 vs lag2)
A leg that is negative-corr but loses money standalone is a DRAG (partly
short-mom), not a premium. A leg with positive corr is not a diversifier.
"""
import json
res = json.load(open("reports/_index_value_mom_probe_result.json"))
legs = res["value_legs"]
disc = res["discrimination"]

print(f"{'leg':26s} {'corrMom':>8s} {'margin':>7s} {'fpShrp':>7s} {'oosShrp':>7s} "
      f"{'A:negimp':>9s} {'B:ownret':>9s} {'GATE':>6s}")
for k in legs:
    if k.startswith("_"):
        continue
    st = legs[k]
    d = disc[k]
    cm = d["corr_value_to_mom"]
    fp = st["fp_sharpe"]; oos = st["oos_sharpe"]
    A = (-0.7 < cm < -0.05)
    B = (fp >= 0.0 and oos >= 0.0)
    gate = A and B
    print(f"{k:26s} {cm:8.3f} {d['distinctness_margin_vs_shortmom']:7.3f} "
          f"{fp:7.3f} {oos:7.3f} {str(A):>9s} {str(B):>9s} {str(gate):>6s}")

print()
print("REFERENCE -1x mom: corr_to_mom =",
      disc["_NEGATIVE_MOM_REFERENCE"]["corr_value_to_mom"],
      "(by construction; any leg approaching this IS short-mom)")
print()
print("MOM book:", res["momentum_book"]["fp_sharpe"], "fpSharpe,",
      res["momentum_book"]["oos_sharpe"], "OOS")
print()
# Count gate passes
passes = [k for k in legs if not k.startswith("_")
          and (-0.7 < disc[k]["corr_value_to_mom"] < -0.05)
          and (legs[k]["fp_sharpe"] >= 0 and legs[k]["oos_sharpe"] >= 0)]
print("LEGS PASSING JOINT GATE (neg-imperfect-corr AND own non-neg return):", passes)
