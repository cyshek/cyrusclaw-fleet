"""TOM OVERLAY — PRODUCTION harness for the RECOMMENDED SHELF CONFIG.

Main asked for a clean go/no-go doc focused on the config we would actually ship,
not the tilt=1.0 stress numbers in the verdict. This harness pins:

  1. Cross-index formalization (SPY/QQQ/^GSPC/^NDX) at the SHELF config.
  2. Tradeable leveraged-ETF tilt (UPRO/TQQQ + SSO/QLD), REAL adjclose
     (decay+fees+embedded financing baked in) — no explicit margin.
  3. PROPER maxDD for the recommended shelf config: pre=2/post=3, tilt=0.5.
  4. Fully reproducible: every number below comes from
     reports/_tom_overlay_harness.py verified primitives (same library the
     verdict used). No new return math; only a re-parameterization + a DD-vs-tilt
     ladder so the cost of the recommended tilt is explicit.

SHELF CONFIG UNDER TEST
-----------------------
  Base exposure : 1.0x the index every day (keep beta).
  TOM window    : last pre=2 + first post=3 trading days of the month-turn
                  (pure calendar date mask, NO price lookahead).
  Tilt          : 0.5 EXTRA index exposure during the window (recommended start).
  Tradeable form: rotate w = tilt/(k-1) of the book into a kx ETF during TOM.
                  tilt=0.5 -> w=0.25 into a 3x ETF (UPRO/TQQQ)  [preferred]
                          -> w=0.50 into a 2x ETF (SSO/QLD)
  Cost          : 2bps one-way on every exposure change / rotation.

HONEST TESTS (same as verdict, re-run at the shelf tilt)
  - true peak-to-trough maxDD on compounded equity
  - OOS split #1 (>=2013) and #2 (>=2018) — edge must survive both
  - +1bar canary (mask shifted to the WRONG days) must DEGRADE Sharpe
  - tilt ladder 0.0 / 0.25 / 0.50 / 1.0 so the DD cost of the recommended
    0.5 is explicit and comparable to B&H and to the verdict's tilt=1.0.

Mission bar = RAW RETURN vs buy & hold. Sharpe reported, gate suspended.
This is a VERDICT/PRODUCTION harness, NOT a live wiring. No orders, no protected
files, no crontab. Writes nothing (stdout captured into the report md).
"""
from __future__ import annotations

import datetime as dt

from reports._tom_overlay_harness import (
    load, daily_returns, align_returns, tom_mask, stats,
    overlay_margin, overlay_etf, split2, line, section,
)

PRE, POST = 2, 3
SHELF_TILT = 0.5
TILT_LADDER = (0.0, 0.25, 0.50, 1.0)
FIN_REAL = 0.05  # realistic retail-margin APY for the explicit-margin reference
CUTS = (dt.date(2013, 1, 1), dt.date(2018, 1, 1))

# index -> [(ETF, mult)], 3x first (preferred: less notional turned over)
ETF_MAP = {
    "SPY":   [("UPRO", 3.0), ("SSO", 2.0)],
    "^GSPC": [("UPRO", 3.0), ("SSO", 2.0)],
    "QQQ":   [("TQQQ", 3.0), ("QLD", 2.0)],
    "^NDX":  [("TQQQ", 3.0), ("QLD", 2.0)],
}


def hdr(sym, series):
    yrs = (series[-1][0] - series[0][0]).days / 365.25
    return (f"{sym}: {len(series)} bars {series[0][0]} -> {series[-1][0]} "
            f"({yrs:.1f}yr) | TOM(pre={PRE},post={POST}) | shelf tilt={SHELF_TILT} "
            f"| cost=2.0bps")


def canary_verdict(full_rets, full_lag, label="FULL"):
    _, sh, _, _ = stats(full_rets)
    _, sh_l, _, _ = stats(full_lag)
    ok = sh_l < sh
    return (f"   +1bar CANARY [{label}]: "
            + ("PASS" if ok else "FAIL")
            + f" (lag {'degrades' if ok else 'did NOT degrade'} Sharpe "
              f"{sh:.3f}->{sh_l:.3f})"), ok


def run_index(sym, lines):
    series = load(sym)
    dates = [d for d, _ in series]
    rets = daily_returns(series)
    mask = tom_mask(dates, PRE, POST, shift=0)
    mask_lag = tom_mask(dates, PRE, POST, shift=1)
    bh = [(d, r) for d, r in rets]
    bh_stats = stats(bh)

    lines.append(section(f"INDEX: {sym}"))
    lines.append(hdr(sym, series))

    # --- buy & hold reference (FULL + both OOS cuts) ---
    lines.append("\n  [BUY & HOLD 1.0x]")
    lines.append(line("B&H FULL", bh))
    for cut in CUTS:
        _, oos_bh = split2(bh, cut)
        lines.append(line(f"B&H OOS>={cut.year}", oos_bh))

    # --- DD-vs-tilt ladder via explicit margin@5% (the clean reference) ---
    # this is where the COST of the recommended 0.5 tilt becomes explicit.
    lines.append("\n  [TILT LADDER — explicit-margin@5%/yr reference; shows DD cost of each tilt]")
    lines.append(line("tilt=0.00 (==B&H)", bh))
    for tlt in TILT_LADDER:
        if tlt == 0.0:
            continue
        ov = overlay_margin(dates, rets, mask, tlt, FIN_REAL)
        tag = "  <== SHELF" if abs(tlt - SHELF_TILT) < 1e-9 else ""
        lines.append(line(f"tilt={tlt:.2f}", ov) + tag)

    # --- recommended shelf config, explicit-margin, FULL + OOSx2 + canary ---
    ov_shelf = overlay_margin(dates, rets, mask, SHELF_TILT, FIN_REAL)
    ov_shelf_lag = overlay_margin(dates, rets, mask_lag, SHELF_TILT, FIN_REAL)
    lines.append("\n  [SHELF CONFIG tilt=0.5 — explicit-margin@5%/yr]")
    lines.append(line("shelf FULL", ov_shelf))
    for cut in CUTS:
        _, oos_o = split2(ov_shelf, cut)
        lines.append(line(f"shelf OOS>={cut.year}", oos_o))
    cline, _ = canary_verdict(ov_shelf, ov_shelf_lag, "shelf-margin")
    lines.append(cline)

    # --- TRADEABLE leveraged-ETF form at shelf tilt (the real product) ---
    lines.append("\n  [SHELF CONFIG tilt=0.5 — TRADEABLE leveraged-ETF rotation (REAL adjclose: decay+fees+fin baked in)]")
    for etf_sym, k in ETF_MAP.get(sym, []):
        etf_series = load(etf_sym)
        etf_d2r = align_returns(dates, etf_series)
        etf_start = etf_series[0][0]
        sub_series = [(d, p) for d, p in series if d >= etf_start]
        sub_dates = [d for d, _ in sub_series]
        sub_rets = daily_returns(sub_series)
        sub_mask = tom_mask(sub_dates, PRE, POST, shift=0)
        sub_mask_lag = tom_mask(sub_dates, PRE, POST, shift=1)
        w_etf = SHELF_TILT / (k - 1.0)
        bh_sub = [(d, r) for d, r in sub_rets]
        ov_etf = overlay_etf(sub_dates, sub_rets, sub_mask, SHELF_TILT, etf_d2r, k)
        ov_etf_lag = overlay_etf(sub_dates, sub_rets, sub_mask_lag, SHELF_TILT, etf_d2r, k)
        span_yr = (sub_series[-1][0] - etf_start).days / 365.25
        lines.append(f"\n   >> {etf_sym} ({int(k)}x), w={w_etf:.3f} of book into ETF during TOM; "
                     f"span {etf_start}+ ({span_yr:.1f}yr)")
        lines.append("   " + line(f"B&H 1x (sub)", bh_sub))
        lines.append("   " + line(f"ETF-tilt {etf_sym}", ov_etf))
        # DD delta is the headline cost number
        _, _, _, bh_dd = stats(bh_sub)
        _, _, _, ov_dd = stats(ov_etf)
        lines.append(f"      maxDD cost: B&H {bh_dd*100:.1f}% -> ETF-tilt {ov_dd*100:.1f}% "
                     f"(+{(ov_dd-bh_dd)*100:.1f}pp)")
        for cut in CUTS:
            if cut <= etf_start:
                continue
            _, oos_e = split2(ov_etf, cut)
            _, oos_b = split2(bh_sub, cut)
            lines.append("      " + line(f"B&H OOS>={cut.year}", oos_b))
            lines.append("      " + line(f"ETF OOS>={cut.year}", oos_e))
        cline, _ = canary_verdict(ov_etf, ov_etf_lag, etf_sym)
        lines.append(cline)


def main():
    lines = []
    lines.append("TOM OVERLAY — PRODUCTION HARNESS (recommended shelf config: pre=2/post=3, tilt=0.5)")
    lines.append("All numbers from reports/_tom_overlay_harness.py verified primitives. RAW-RETURN bar.")
    for sym in ("SPY", "QQQ", "^GSPC", "^NDX"):
        run_index(sym, lines)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
