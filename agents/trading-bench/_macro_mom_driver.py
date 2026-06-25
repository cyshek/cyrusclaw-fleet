"""Driver: macro-vs-price head-to-head pre-flight. Prints the decisive table."""
from __future__ import annotations

import _macro_mom_engine as E

# Window: basket bounded by DBC inception 2006-02; need 252d price warmup +
# macro 12m trend with 2m PIT lag -> start signals ~2007-04. Use 2007-04-01.
START = "2007-04-01"
END = "2026-06-24"

print("Loading macro series (PIT)...")
macro = E.load_macro("2004-01-01", END)

variants = {}
print("Running PRICE-only (top-2 EW, 12-1)...")
variants["price"] = E.run_strategy("price", macro, START, END)
print("Running MACRO-only long-top2 EW...")
variants["macro"] = E.run_strategy("macro", macro, START, END)
print("Running MACRO L/S (long top2 / short bottom2)...")
variants["macro_ls"] = E.run_strategy("macro", macro, START, END, ls=True)
print("Running COMBINED (z(price)+z(macro), top-2 EW)...")
variants["combined"] = E.run_strategy("combined", macro, START, END)

# SPY benchmark on the price variant's date path (all share same path length)
base = variants["price"]
spy_rets = E.spy_path(base["panel"], base["panel_dates"], base["dates"])

def block(label, rets, dates, spy_aligned):
    shp = E.sharpe_from_returns(rets, E.BPY)
    cg = E.cagr(rets)
    tr = E.total_return(rets) * 100
    mdd = E.max_drawdown(rets) * 100
    c = E.corr(rets, spy_aligned)
    return dict(label=label, n=len(rets), start=dates[0] if dates else None,
                end=dates[-1] if dates else None, sharpe=shp, cagr=cg,
                totret=tr, maxdd=mdd, corr_spy=c)

rows = []
for key in ["macro", "macro_ls", "price", "combined"]:
    v = variants[key]
    # align spy to this variant's dates
    spy_v = E.spy_path(v["panel"], v["panel_dates"], v["dates"])
    rows.append(block(key, v["net"], v["dates"], spy_v))
# SPY itself
rows.append(block("SPY_buyhold", spy_rets, base["dates"], spy_rets))

print()
print("=== HEAD-TO-HEAD (full continuous span) ===")
hdr = f"{'variant':12s} {'n':>5s} {'start':>10s} {'end':>10s} {'Sharpe':>7s} {'CAGR%':>7s} {'TotRet%':>9s} {'MaxDD%':>8s} {'corrSPY':>8s}"
print(hdr)
for r in rows:
    print(f"{r['label']:12s} {r['n']:5d} {str(r['start']):>10s} {str(r['end']):>10s} "
          f"{r['sharpe']:7.2f} {r['cagr']:7.2f} {r['totret']:9.1f} {r['maxdd']:8.2f} {r['corr_spy']:8.2f}")

# crisis windows for macro-only vs SPY
print()
print("=== CRISIS-WINDOW RETURNS (cumulative, %) ===")
crises = [
    ("2008 GFC",   "2008-01-01", "2009-03-31"),
    ("2020 COVID", "2020-02-01", "2020-04-30"),
    ("2022 bear",  "2022-01-01", "2022-10-31"),
]
print(f"{'window':12s} {'span':>25s} {'macro%':>9s} {'macro_ls%':>10s} {'price%':>9s} {'combined%':>10s} {'SPY%':>9s}")
for name, lo, hi in crises:
    mr, nn = E.window_return(variants["macro"]["dates"], variants["macro"]["net"], lo, hi)
    mlr, _ = E.window_return(variants["macro_ls"]["dates"], variants["macro_ls"]["net"], lo, hi)
    pr, _ = E.window_return(variants["price"]["dates"], variants["price"]["net"], lo, hi)
    cr, _ = E.window_return(variants["combined"]["dates"], variants["combined"]["net"], lo, hi)
    sr, _ = E.window_return(base["dates"], spy_rets, lo, hi)
    print(f"{name:12s} {lo+'..'+hi:>25s} {mr:9.1f} {mlr:10.1f} {pr:9.1f} {cr:10.1f} {sr:9.1f}  (n={nn})")

# selection diagnostics: how often does macro pick the same top-2 as price?
print()
print("=== SELECTION OVERLAP (macro vs price top-2) ===")
pw = {d: set(s for s, w in wd.items() if w > 0) for d, wd in variants["price"]["weights"]}
mw = {d: set(s for s, w in wd.items() if w > 0) for d, wd in variants["macro"]["weights"]}
common_dates = sorted(set(pw) & set(mw))
overlaps = []
for d in common_dates:
    inter = len(pw[d] & mw[d])
    overlaps.append(inter)
if overlaps:
    avg = sum(overlaps) / len(overlaps)
    both2 = sum(1 for x in overlaps if x == 2)
    print(f"rebalances={len(overlaps)} avg_shared_of_2={avg:.2f} "
          f"identical_top2_count={both2} ({100*both2/len(overlaps):.0f}%)")

# per-asset macro selection frequency (does it use TLT/VNQ that price never did?)
print()
print("=== MACRO per-asset LONG-selection frequency ===")
cnt = {s: 0 for s in E.BASKET}
tot = 0
for d, wd in variants["macro"]["weights"]:
    tot += 1
    for s in E.BASKET:
        if wd[s] > 0:
            cnt[s] += 1
for s in E.BASKET:
    print(f"  {s:4s} selected {cnt[s]:3d}/{tot} ({100*cnt[s]/tot:.0f}%)")

print()
print("=== PRICE per-asset LONG-selection frequency (baseline) ===")
cntp = {s: 0 for s in E.BASKET}
totp = 0
for d, wd in variants["price"]["weights"]:
    totp += 1
    for s in E.BASKET:
        if wd[s] > 0:
            cntp[s] += 1
for s in E.BASKET:
    print(f"  {s:4s} selected {cntp[s]:3d}/{totp} ({100*cntp[s]/totp:.0f}%)")
