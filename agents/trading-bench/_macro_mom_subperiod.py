"""Sub-period robustness: does macro beat price OUTSIDE 2008 too? Split the
span into 2007-2009 (incl GFC), 2010-2019, 2020-2026 and score each."""
from __future__ import annotations
import _macro_mom_engine as E

START = "2007-04-01"
END = "2026-06-24"
macro = E.load_macro("2004-01-01", END)

vmac = E.run_strategy("macro", macro, START, END)
vpri = E.run_strategy("price", macro, START, END)
spy_m = E.spy_path(vmac["panel"], vmac["panel_dates"], vmac["dates"])
spy_p = E.spy_path(vpri["panel"], vpri["panel_dates"], vpri["dates"])


def sub(label, dates, rets, lo, hi):
    seg = [(d, r) for d, r in zip(dates, rets) if lo <= d <= hi]
    if not seg:
        return None
    rr = [r for _, r in seg]
    shp = E.sharpe_from_returns(rr, E.BPY)
    cg = E.cagr(rr)
    mdd = E.max_drawdown(rr) * 100
    return shp, cg, mdd, len(rr)


periods = [
    ("2007-2009 (incl GFC)", "2007-01-01", "2009-12-31"),
    ("2010-2019 (expansion)", "2010-01-01", "2019-12-31"),
    ("2020-2026 (covid+infl)", "2020-01-01", "2026-12-31"),
]
print(f"{'period':24s} {'MACRO Sh/CAGR/DD':>30s}   {'PRICE Sh/CAGR/DD':>30s}")
for name, lo, hi in periods:
    m = sub("m", vmac["dates"], vmac["net"], lo, hi)
    p = sub("p", vpri["dates"], vpri["net"], lo, hi)
    ms = f"{m[0]:.2f} / {m[1]:5.1f}% / {m[2]:6.1f}%" if m else "n/a"
    ps = f"{p[0]:.2f} / {p[1]:5.1f}% / {p[2]:6.1f}%" if p else "n/a"
    print(f"{name:24s} {ms:>30s}   {ps:>30s}")

# what fraction of macro's total outperformance is 2008-only?
import math
def cum(dates, rets, lo, hi):
    eq = 1.0
    for d, r in zip(dates, rets):
        if lo <= d <= hi:
            eq *= (1 + r)
    return eq
print()
m_ex08 = E.cagr([r for d, r in zip(vmac["dates"], vmac["net"]) if not ("2008-01-01" <= d <= "2009-06-30")])
p_ex08 = E.cagr([r for d, r in zip(vpri["dates"], vpri["net"]) if not ("2008-01-01" <= d <= "2009-06-30")])
mm = [r for d, r in zip(vmac["dates"], vmac["net"]) if not ("2008-01-01" <= d <= "2009-06-30")]
pp = [r for d, r in zip(vpri["dates"], vpri["net"]) if not ("2008-01-01" <= d <= "2009-06-30")]
print("EXCLUDING 2008-01..2009-06 (drop the GFC window entirely):")
print(f"  macro: Sharpe={E.sharpe_from_returns(mm, E.BPY):.2f} CAGR={m_ex08:.2f}% MaxDD={E.max_drawdown(mm)*100:.1f}%")
print(f"  price: Sharpe={E.sharpe_from_returns(pp, E.BPY):.2f} CAGR={p_ex08:.2f}% MaxDD={E.max_drawdown(pp)*100:.1f}%")
