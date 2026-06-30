"""TOM OVERLAY verdict RUNNER — drives the harness, prints the full report body.

Usage: python3 -m reports._tom_overlay_run   (run from workspace root)
Writes nothing; stdout is captured into the timestamped VERDICT md by the caller.
"""
from __future__ import annotations

import datetime as dt

from reports._tom_overlay_harness import (
    load, daily_returns, align_returns, tom_mask, stats,
    overlay_margin, overlay_etf, split2, line, section,
)

PRE, POST, TILT = 2, 3, 1.0          # base TOM window + extra-exposure target
FIN_SWEEP = (0.0, 0.03, 0.05, 0.07, 0.10)
CUTS = (dt.date(2013, 1, 1), dt.date(2018, 1, 1))

# index -> (2x ETF, 3x ETF)
ETF_MAP = {
    "SPY":   [("SSO", 2.0), ("UPRO", 3.0)],
    "^GSPC": [("SSO", 2.0), ("UPRO", 3.0)],   # ETFs track S&P; ^GSPC index leg
    "QQQ":   [("QLD", 2.0), ("TQQQ", 3.0)],
    "^NDX":  [("QLD", 2.0), ("TQQQ", 3.0)],
}


def hdr(sym, series):
    yrs = (series[-1][0] - series[0][0]).days / 365.25
    return (f"{sym}: {len(series)} bars {series[0][0]} -> {series[-1][0]} "
            f"({yrs:.1f}yr), cost={2.0}bps, TOM(pre={PRE},post={POST}), tilt={TILT}")


def break_even_financing(dates, rets, mask, bh_full_cum):
    """Find the financing APY at which FULL overlay cum return == B&H FULL cum.
    Linear-bisection on fin in [0, 0.40]."""
    def ov_cum(fin):
        _, _, cum, _ = stats(overlay_margin(dates, rets, mask, TILT, fin))
        return cum
    lo, hi = 0.0, 0.40
    if ov_cum(hi) > bh_full_cum:
        return None  # never dies within a sane range
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if ov_cum(mid) > bh_full_cum:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def run_index(sym, lines):
    series = load(sym)
    dates = [d for d, _ in series]
    rets = daily_returns(series)
    # rets is aligned to dates[1:]; the harness overlay fns index rets[k-1] for dates[k]
    lines.append(section(f"INDEX: {sym}"))
    lines.append(hdr(sym, series))

    mask = tom_mask(dates, PRE, POST, shift=0)
    mask_lag = tom_mask(dates, PRE, POST, shift=1)

    bh = [(d, r) for d, r in rets]
    bh_full = stats(bh)
    lines.append("\n--- BUY & HOLD (1.0x always-long) ---")
    lines.append(line("FULL", bh))
    for cut in CUTS:
        is_bh, oos_bh = split2(bh, cut)
        lines.append(line(f"IS<{cut.year}", is_bh))
        lines.append(line(f"OOS>={cut.year}", oos_bh))

    # ---- (i) EXPLICIT MARGIN: financing sweep ----
    lines.append("\n--- (i) EXPLICIT-MARGIN OVERLAY: base 1.0x + tilt 1.0x borrowed; financing sweep ---")
    for fin in FIN_SWEEP:
        ov = overlay_margin(dates, rets, mask, TILT, fin)
        lines.append(line(f"FULL fin={int(fin*100)}%", ov))
    # OOS detail at the realistic 5%
    ov5 = overlay_margin(dates, rets, mask, TILT, 0.05)
    lines.append("   OOS detail @ fin=5%/yr:")
    for cut in CUTS:
        is_o, oos_o = split2(ov5, cut)
        lines.append("   " + line(f"IS<{cut.year}", is_o))
        lines.append("   " + line(f"OOS>={cut.year}", oos_o))
    # break-even financing
    be = break_even_financing(dates, rets, mask, bh_full[2])
    if be is None:
        lines.append("   BREAK-EVEN financing: NONE within 0-40%/yr (edge survives any sane rate)")
    else:
        lines.append(f"   BREAK-EVEN financing (FULL cum == B&H): {be*100:.1f}%/yr")
    # canary on the explicit-margin variant @5%
    ov5_lag = overlay_margin(dates, rets, mask_lag, TILT, 0.05)
    _, sh_full, _, _ = stats(ov5)
    _, sh_lag, _, _ = stats(ov5_lag)
    for cut in (dt.date(2013, 1, 1),):
        _, oos_o = split2(ov5, cut)
        _, oos_lag = split2(ov5_lag, cut)
        _, sh_oos, _, _ = stats(oos_o)
        _, sh_oos_lag, _, _ = stats(oos_lag)
    lines.append("   +1BAR CANARY (margin@5%, tilt on WRONG days):")
    lines.append("   " + line("FULL(lag)", ov5_lag))
    lines.append("   " + line("OOS>=2013(lag)", oos_lag))
    verdict = ("PASS (lag degrades OOS Sharpe %.3f->%.3f)" % (sh_oos, sh_oos_lag)
               if sh_oos_lag < sh_oos else
               "FAIL (lag did NOT degrade OOS Sharpe %.3f->%.3f)" % (sh_oos, sh_oos_lag))
    lines.append("   CANARY: " + verdict)

    # ---- (ii) LEVERAGED-ETF TILT (tradeable) ----
    lines.append("\n--- (ii) LEVERAGED-ETF OVERLAY (tradeable: rotate into kx ETF during TOM) ---")
    lines.append("   (uses REAL ETF adjclose return = decay+fees+embedded-financing baked in)")
    for etf_sym, k in ETF_MAP.get(sym, []):
        etf_series = load(etf_sym)
        etf_d2r = align_returns(dates, etf_series)
        etf_start = etf_series[0][0]
        # restrict the comparison window to where the ETF exists (apples-to-apples)
        w_sub = [(d, r) for d, r in rets if d >= etf_start]
        dates_sub = [d for d, _ in series if d >= etf_start]
        # need rets aligned to dates_sub axis for overlay_etf
        # rebuild a (dates, rets) pair restricted to etf span
        sub_series = [(d, p) for d, p in series if d >= etf_start]
        sub_dates = [d for d, _ in sub_series]
        sub_rets = daily_returns(sub_series)
        sub_mask = tom_mask(sub_dates, PRE, POST, shift=0)
        sub_mask_lag = tom_mask(sub_dates, PRE, POST, shift=1)
        w_etf = TILT / (k - 1.0)

        ov_etf = overlay_etf(sub_dates, sub_rets, sub_mask, TILT, etf_d2r, k)
        bh_sub = [(d, r) for d, r in sub_rets]
        # explicit-margin @5% on the SAME sub-window for a like-for-like compare
        ov_marg_sub = overlay_margin(sub_dates, sub_rets, sub_mask, TILT, 0.05)
        lines.append(f"\n   >> {etf_sym} ({int(k)}x), w_etf={w_etf:.3f} of book rotated in during TOM; span {etf_start}+ ({(sub_series[-1][0]-etf_start).days/365.25:.1f}yr)")
        lines.append("   " + line(f"B&H 1x (sub)", bh_sub))
        lines.append("   " + line(f"MARGIN@5% (sub)", ov_marg_sub))
        lines.append("   " + line(f"ETF-TILT {etf_sym}", ov_etf))
        for cut in CUTS:
            if cut <= etf_start:
                continue
            is_e, oos_e = split2(ov_etf, cut)
            is_b, oos_b = split2(bh_sub, cut)
            lines.append("      " + line(f"B&H OOS>={cut.year}", oos_b))
            lines.append("      " + line(f"ETF  OOS>={cut.year}", oos_e))
        # canary on the ETF variant
        ov_etf_lag = overlay_etf(sub_dates, sub_rets, sub_mask_lag, TILT, etf_d2r, k)
        _, sh_e, _, _ = stats(ov_etf)
        _, sh_el, _, _ = stats(ov_etf_lag)
        cv = ("PASS (lag degrades FULL Sharpe %.3f->%.3f)" % (sh_e, sh_el)
              if sh_el < sh_e else
              "FAIL (lag did NOT degrade %.3f->%.3f)" % (sh_e, sh_el))
        lines.append("      +1bar CANARY: " + cv)


def main():
    lines = []
    for sym in ("SPY", "QQQ", "^GSPC", "^NDX"):
        run_index(sym, lines)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
