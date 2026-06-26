"""Plateau / knife-edge analysis of the lookback x cadence grid.
Baseline = 63d/monthly. A cell 'beats' iff it improves raw return AND holds
Sharpe (full & OOS) without wrecking maxDD. Plateau requires adjacent lookbacks
AND the adjacent (slower) cadence to also beat/match."""
import json
with open("reports/_rot_lookback_cadence_result.json") as f:
    D = json.load(f)

base = D["baseline_63_monthly"]
B_full = base["full"]["sharpe"]; B_is = base["is_2005_2018"]["sharpe"]
B_oos = base["oos_2019_today"]["sharpe"]; B_raw = base["full"]["total_return_pct"]
B_dd = base["full"]["maxdd_pct"]
print("BASELINE 63d/monthly: full %.4f  IS %.4f  OOS %.4f  raw %.1f%%  maxDD %.2f%%  off/def %.2f/%.2f" % (
    B_full, B_is, B_oos, B_raw, B_dd, base["avg_offense_w"], base["avg_defense_w"]))
print()

LBS = [21,42,63,126,189,252]
CADS = ["monthly","bimonthly","quarterly"]
grid = D["grid"]

# Print grids
def grid_print(metric, label, fmt="%7.4f"):
    print("=== %s ===" % label)
    hdr = "lb\\cad   " + "".join("%-12s" % c for c in CADS)
    print(hdr)
    for lb in LBS:
        row = "%4dd   " % lb
        for c in CADS:
            v = grid[str(lb)][c]
            if metric == "full": x = v["full"]["sharpe"]
            elif metric == "is": x = v["is_2005_2018"]["sharpe"]
            elif metric == "oos": x = v["oos_2019_today"]["sharpe"]
            elif metric == "raw": x = v["full"]["total_return_pct"]
            elif metric == "dd": x = v["full"]["maxdd_pct"]
            row += ("%-12s" % (fmt % x))
        print(row)
    print()

grid_print("full","FULL Sharpe (baseline 0.9069)")
grid_print("is","IS Sharpe 2005-2018 (baseline 0.9293)")
grid_print("oos","OOS Sharpe 2019+ (baseline 0.8752)")
grid_print("raw","RAW total return % (baseline 1210.1)", fmt="%7.1f")
grid_print("dd","maxDD % (baseline -28.98)", fmt="%7.2f")

# Robust-beat classification: beats baseline on raw AND full-Sharpe AND OOS-Sharpe,
# AND maxDD not worse by >3pts.
print("=== ROBUST-BEAT MAP (raw> AND fullS>= AND oosS>= AND maxDD within 3pts) ===")
print("lb\\cad   " + "".join("%-12s" % c for c in CADS))
beat_cells = []
for lb in LBS:
    row = "%4dd   " % lb
    for c in CADS:
        v = grid[str(lb)][c]
        raw = v["full"]["total_return_pct"]; fs = v["full"]["sharpe"]
        os_ = v["oos_2019_today"]["sharpe"]; dd = v["full"]["maxdd_pct"]
        beats = (raw > B_raw) and (fs >= B_full - 0.005) and (os_ >= B_oos - 0.005) and (dd >= B_dd - 3.0)
        mark = "BEAT" if beats else "."
        if beats: beat_cells.append((lb,c))
        row += "%-12s" % mark
    print(row)
print()
print("Cells that beat baseline on raw+full+OOS (maxDD-tolerant):", beat_cells)
print()

# For each beat cell, check plateau: are BOTH lookback-neighbors AND the next
# slower cadence also 'beat or match' (raw>=baseline-2%, fullS>=baseline-0.02)?
def soft_beat(lb, c):
    if c not in CADS or lb not in LBS: return None
    v = grid[str(lb)][c]
    return (v["full"]["total_return_pct"] >= B_raw*0.98) and (v["full"]["sharpe"] >= B_full-0.02) and (v["oos_2019_today"]["sharpe"] >= B_oos-0.02)

for (lb,c) in beat_cells:
    li = LBS.index(lb); ci = CADS.index(c)
    neigh = []
    if li>0: neigh.append((LBS[li-1],c))
    if li<len(LBS)-1: neigh.append((LBS[li+1],c))
    if ci<len(CADS)-1: neigh.append((lb,CADS[ci+1]))
    if ci>0: neigh.append((lb,CADS[ci-1]))
    results = [(n, soft_beat(*n)) for n in neigh]
    allgood = all(r[1] for r in results)
    print("PLATEAU CHECK %dd/%s -> %s" % (lb, c, "PLATEAU" if allgood else "KNIFE-EDGE"))
    for n,ok in results:
        nv = grid[str(n[0])][n[1]]
        print("    neighbor %dd/%-9s soft-beat=%s  (raw %.1f%% fullS %.4f OOS %.4f)" % (
            n[0], n[1], ok, nv["full"]["total_return_pct"], nv["full"]["sharpe"], nv["oos_2019_today"]["sharpe"]))
    # beta confound
    v = grid[str(lb)][c]
    print("    beta-mix: off/def %.2f/%.2f vs baseline 0.58/0.40 (Δoff %+.2f)" % (
        v["avg_offense_w"], v["avg_defense_w"], v["avg_offense_w"]-base["avg_offense_w"]))
    print()
