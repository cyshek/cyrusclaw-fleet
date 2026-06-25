import csv, math, itertools
from datetime import datetime
import sys
sys.path.insert(0, '.')
from runner import daily_bars_cache as dbc

# --- COR1M implied, MM/DD/YYYY, CLOSE is implied-corr x100 -> /100 to 0-1 ---
imp = {}
with open("data_cache/cboe/COR1M_History.csv") as f:
    for row in csv.DictReader(f):
        try:
            d = datetime.strptime(row["DATE"], "%m/%d/%Y").strftime("%Y-%m-%d")
            imp[d] = float(row["CLOSE"]) / 100.0
        except Exception:
            pass

SECT = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
rets = {}
for s in SECT:
    b = dbc.get_daily(s)
    rows = [(r["date"], r["adjclose"]) for r in b if r.get("adjclose")]
    rr = {}
    for i in range(1, len(rows)):
        p0, p1 = rows[i - 1][1], rows[i][1]
        if p0 and p1 and p0 > 0:
            rr[rows[i][0]] = math.log(p1 / p0)
    rets[s] = rr

common = set(rets[SECT[0]].keys())
for s in SECT[1:]:
    common &= set(rets[s].keys())
common = sorted(common)

pairs = list(itertools.combinations(range(len(SECT)), 2))
W = 21
real = {}
mat = [[rets[SECT[j]].get(d) for j in range(len(SECT))] for d in common]
for i in range(W, len(common)):
    win = mat[i - W:i]
    cols = list(zip(*win))
    cs = []
    for a, b in pairs:
        xa = cols[a]
        xb = cols[b]
        ma = sum(xa) / W
        mb = sum(xb) / W
        va = sum((x - ma) ** 2 for x in xa)
        vb = sum((x - mb) ** 2 for x in xb)
        if va > 0 and vb > 0:
            cov = sum((xa[k] - ma) * (xb[k] - mb) for k in range(W))
            cs.append(cov / math.sqrt(va * vb))
    if cs:
        real[common[i]] = sum(cs) / len(cs)

both = [d for d in common if d in imp and d in real]
imps = [imp[d] for d in both]
reals = [real[d] for d in both]
spread = [imp[d] - real[d] for d in both]
print("n common (imp&real, 21d): %d  window %s..%s" % (len(both), both[0], both[-1]))
print("mean implied  = %.4f" % (sum(imps) / len(imps)))
print("mean realized = %.4f" % (sum(reals) / len(reals)))
print("mean spread   = %+.4f   (subagent: implied 0.375 < realized 0.566, spread ~-0.19)" % (sum(spread) / len(spread)))
neg = sum(1 for x in spread if x < 0)
print("spread negative on %d/%d days = %.1f%%" % (neg, len(spread), 100 * neg / len(spread)))

spy = dbc.get_daily("SPY")
sp = {r["date"]: r["adjclose"] for r in spy if r.get("adjclose")}
spd = sorted(sp.keys())
idx = {d: i for i, d in enumerate(spd)}
fwd = {}
H = 21
for d in both:
    if d in idx and idx[d] + H < len(spd):
        p0 = sp[spd[idx[d]]]
        p1 = sp[spd[idx[d] + H]]
        if p0 > 0:
            fwd[d] = (p1 / p0 - 1.0)
rows2 = [(imp[d] - real[d], fwd[d]) for d in both if d in fwd]
rows2.sort(key=lambda x: x[0])
q = len(rows2) // 5
print("")
print("fwd21d SPY return by SPREAD quintile (ann %, Q1 low spread -> Q5 high):")
qs = []
for k in range(5):
    seg = rows2[k * q:(k + 1) * q] if k < 4 else rows2[4 * q:]
    m = sum(r[1] for r in seg) / len(seg)
    ann = (1 + m) ** (252 / 21) - 1
    qs.append(ann)
    print("  Q%d: %+6.1f%%  (n=%d)" % (k + 1, ann * 100, len(seg)))
mono = all(qs[i] <= qs[i + 1] for i in range(4)) or all(qs[i] >= qs[i + 1] for i in range(4))
print("monotone? %s" % mono)
