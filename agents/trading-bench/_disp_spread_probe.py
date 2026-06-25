#!/usr/bin/env python3
"""DISPERSION SPREAD PROBE — implied-minus-realized pairwise correlation (the
correlation risk premium). Decides GREEN/AMBER/RED on the spread, after the naive
COR LEVEL was already FALSIFIED (corr(dCOR3M,SPY)=-0.609 lagging beta; level sort
backwards).

spread = COR1M_implied(0-1 scale) - realized_avg_pairwise_corr(rolling window)
Gate:
 1. Orthogonality: |corr(spread, SPY trend)| < 0.3  (vs both dSPY ret + SPY trend)
 2. Monotone fwd sort: fwd SPY ret (5d AND 21d) by spread quintile must be monotone
    with a sensible sign (high implied-minus-realized = complacency/overpriced
    corr insurance => expect LOWER fwd equity returns, OR consistent direction).
Pure measurement. NO trading, NO config.
"""
import csv, math, statistics as st
from runner import daily_bars_cache as dbc

BASKET = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB"]

# ---------- load adjclose series ----------
def load_adj(sym):
    out = {}
    for b in dbc.get_daily(sym):
        a = b.get("adjclose")
        if a is None:
            continue
        out[b["date"]] = float(a)
    return out

spy = load_adj("SPY")
sectors = {s: load_adj(s) for s in BASKET}

# COR1M close, parse MM/DD/YYYY -> YYYY-MM-DD, scale /100 to 0-1
cor = {}
for r in list(csv.reader(open("data_cache/cboe/COR1M_History.csv")))[1:]:
    if len(r) < 5 or not r[4]:
        continue
    mm, dd, yy = r[0].split("/")
    cor[f"{yy}-{int(mm):02d}-{int(dd):02d}"] = float(r[4]) / 100.0

# ---------- common trading-day axis across SPY + all 9 sectors ----------
common = set(spy) & set(cor)
for s in BASKET:
    common &= set(sectors[s])
days = sorted(common)
print(f"common days (SPY & COR1M & all 9 sectors): {len(days)} ({days[0]} -> {days[-1]})")

# precompute daily log returns per sector on the common axis
def log_rets(series):
    r = [None]
    for i in range(1, len(days)):
        a = series[days[i-1]]; b = series[days[i]]
        r.append(math.log(b/a))
    return r

sec_rets = {s: log_rets(sectors[s]) for s in BASKET}
spx = [spy[d] for d in days]

PAIRS = [(i, j) for i in range(len(BASKET)) for j in range(i+1, len(BASKET))]  # 36

def pearson(a, b):
    n = len(a)
    if n < 3:
        return float('nan')
    ma = sum(a)/n; mb = sum(b)/n
    num = sum((a[k]-ma)*(b[k]-mb) for k in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in a)); db = math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float('nan')

def avg_pairwise_corr(end_idx, win):
    """avg of 36 pairwise Pearson corrs over [end_idx-win+1 .. end_idx] of log returns."""
    lo = end_idx - win + 1
    if lo < 1:
        return None
    # extract each sector's return window
    wins = {}
    for s in BASKET:
        wins[s] = sec_rets[s][lo:end_idx+1]
    syms = BASKET
    cs = []
    for (i, j) in PAIRS:
        c = pearson(wins[syms[i]], wins[syms[j]])
        if not math.isnan(c):
            cs.append(c)
    if not cs:
        return None
    return sum(cs)/len(cs)

def corr(a, b):
    n = len(a)
    ma = sum(a)/n; mb = sum(b)/n
    num = sum((a[k]-ma)*(b[k]-mb) for k in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in a)); db = math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float('nan')

# ---------- build realized series + spread for a given window ----------
def build_spread(win):
    idxs = []; realized = []; spread = []; implied = []
    for k in range(len(days)):
        rc = avg_pairwise_corr(k, win)
        if rc is None:
            continue
        idxs.append(k)
        realized.append(rc)
        implied.append(cor[days[k]])
        spread.append(cor[days[k]] - rc)
    return idxs, implied, realized, spread

# ---------- orthogonality + sort tests for a window ----------
def run_window(win, verbose=True):
    idxs, implied, realized, spread = build_spread(win)
    # SPY daily log return aligned to idxs (return ending at idx k)
    dspy = []
    sp_for_corr = []
    for n, k in enumerate(idxs):
        if k == 0:
            continue
        dspy.append(math.log(spx[k]/spx[k-1]))
        sp_for_corr.append(spread[n])
    # SPY trend proxy: 50d log return ending at k; and price/200d SMA - 1
    trend50 = []; sp_t50 = []
    trend200 = []; sp_t200 = []
    for n, k in enumerate(idxs):
        if k >= 50:
            trend50.append(math.log(spx[k]/spx[k-50]))
            sp_t50.append(spread[n])
        if k >= 200:
            sma = sum(spx[k-199:k+1])/200.0
            trend200.append(spx[k]/sma - 1.0)
            sp_t200.append(spread[n])

    c_dspy = corr(sp_for_corr, dspy)
    c_t50 = corr(sp_t50, trend50)
    c_t200 = corr(sp_t200, trend200)

    if verbose:
        print(f"\n===== REALIZED WINDOW = {win}d  (n_spread={len(idxs)}, "
              f"{days[idxs[0]]} -> {days[idxs[-1]]}) =====")
        print(f"  spread mean={sum(spread)/len(spread):+.3f} "
              f"sd={st.pstdev(spread):.3f} min={min(spread):+.3f} max={max(spread):+.3f}")
        print(f"  implied mean={sum(implied)/len(implied):.3f}  "
              f"realized mean={sum(realized)/len(realized):.3f}")
        print(f"  [ORTHO 1] corr(spread, dSPY daily ret)     = {c_dspy:+.3f}")
        print(f"  [ORTHO 2] corr(spread, SPY 50d trend ret)  = {c_t50:+.3f}")
        print(f"  [ORTHO 3] corr(spread, SPY price/200dSMA-1)= {c_t200:+.3f}")

    # ---------- monotone forward sort by spread quintile ----------
    sort_results = {}
    for H in (5, 21):
        pairs = []
        for n, k in enumerate(idxs):
            if k + H >= len(days):
                continue
            fwd = math.log(spx[k+H]/spx[k])
            pairs.append((spread[n], fwd))
        if not pairs:
            continue
        sv = sorted(p[0] for p in pairs)
        import bisect
        def pct(x):
            return bisect.bisect_left(sv, x)/len(sv)
        buckets = {b: [] for b in range(5)}
        for s, f in pairs:
            b = min(4, int(pct(s)*5))
            buckets[b].append(f)
        means = []
        rows = []
        for b in range(5):
            v = buckets[b]
            ann = (sum(v)/len(v))*(252/H)*100 if v else float('nan')
            means.append(sum(v)/len(v) if v else float('nan'))
            rows.append((b, len(v), ann))
        # monotonicity check
        mono_up = all(means[b] <= means[b+1] for b in range(4))
        mono_dn = all(means[b] >= means[b+1] for b in range(4))
        sort_results[H] = (rows, mono_up, mono_dn, means)
        if verbose:
            labels = ["Q1 (lowest spread)","Q2","Q3","Q4","Q5 (highest spread)"]
            print(f"\n  forward {H}d SPY log-ret by SPREAD quintile (annualized %):")
            for (b, nb, ann) in rows:
                print(f"    {labels[b]:24s} n={nb:4d}  fwd{H}d ann = {ann:+7.1f}%")
            verdict = "MONOTONE-UP (high spread->HIGHER fwd ret)" if mono_up else \
                      "MONOTONE-DOWN (high spread->LOWER fwd ret)" if mono_dn else \
                      "NON-MONOTONE"
            print(f"    -> {verdict}")
    return {
        "win": win, "n": len(idxs),
        "c_dspy": c_dspy, "c_t50": c_t50, "c_t200": c_t200,
        "sort": sort_results,
    }

# ---------- run primary (21d) + robustness (63d) ----------
res21 = run_window(21, verbose=True)
res63 = run_window(63, verbose=True)

# ---------- GATE VERDICT (primary = 21d realized window) ----------
print("\n" + "="*70)
print("GATE VERDICT (primary realized window = 21d, matching COR1M ~1-mo horizon)")
print("="*70)
ortho_max = max(abs(res21["c_dspy"]), abs(res21["c_t50"]), abs(res21["c_t200"]))
ortho_pass = ortho_max < 0.30
print(f"  Orthogonality: max|corr(spread, SPY trend/ret)| = {ortho_max:.3f}  "
      f"-> {'PASS (<0.30)' if ortho_pass else 'FAIL (>=0.30)'}")
mono5 = res21["sort"].get(5, (None, False, False, None))
mono21 = res21["sort"].get(21, (None, False, False, None))
m5 = mono5[1] or mono5[2]
m21 = mono21[1] or mono21[2]
# sensible sign consistency: both horizons same direction
dir5 = "up" if mono5[1] else ("dn" if mono5[2] else "none")
dir21 = "up" if mono21[1] else ("dn" if mono21[2] else "none")
both_mono = m5 and m21
consistent = (dir5 == dir21) and dir5 != "none"
print(f"  Monotone 5d:  {'YES' if m5 else 'NO'} ({dir5});  "
      f"Monotone 21d: {'YES' if m21 else 'NO'} ({dir21});  "
      f"consistent sign: {'YES' if consistent else 'NO'}")
sort_pass = both_mono and consistent
if ortho_pass and sort_pass:
    verdict = "GREEN"
elif ortho_pass or sort_pass:
    verdict = "AMBER"
else:
    verdict = "RED"
print(f"\n  >>> GATE: {verdict}")
