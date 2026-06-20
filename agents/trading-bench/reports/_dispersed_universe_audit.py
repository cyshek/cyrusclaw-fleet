"""Survivorship/full-history audit for the dispersed-universe xsec momentum test.

Selection rule (auditable, NOT hindsight-picked):
  - Names that were ALREADY listed + liquid in mid-2020 (verified: first daily
    bar at the 2020-07-27 data floor, >= ~1460 bars to 2026-06-01).
  - Deliberate cross-sectional DISPERSION: many sectors AND a deliberate mix of
    high-beta/high-idio-vol (tech, semis, biotech, growth, cyclical) AND
    low-beta defensives (staples, utilities, healthcare, telecom).
  - Deliberately INCLUDE known laggards/losers (BA, DIS, INTC, PYPL, PFE, T,
    WBA, etc.) so the universe is NOT a winners-only hindsight cut.
  - Any name that does NOT fetch full history from 2020-07-27 is DROPPED and
    logged (not silently included) — survivorship discipline.

This script ONLY reads bars + prints the audit. It writes the surviving
universe to baskets/dispersed_xsec.txt. No protected files touched.
"""
from __future__ import annotations
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner import bars_cache

FLOOR = "2020-07-27"
MIN_BARS = 1400  # full history from 2020-07-27 to 2026-06-01 is ~1469

# Broad candidate list, grouped by dispersion bucket. ALL were listed+liquid
# well before mid-2020 (no 2020+ IPOs). Tagged for the dispersion narrative.
CANDIDATES = {
    # --- High-beta / high-idio-vol: mega-cap tech + growth ---
    "tech_growth": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "ADBE",
                    "CRM", "ORCL", "NOW", "INTU", "PYPL", "SHOP"],
    # --- Semis (highest idio-vol cyclical-tech) ---
    "semis": ["NVDA", "AMD", "AVGO", "QCOM", "MU", "INTC", "TXN", "AMAT", "LRCX"],
    # --- Biotech / pharma (idiosyncratic, low SPY-beta dispersion) ---
    "biotech_pharma": ["GILD", "BIIB", "AMGN", "REGN", "VRTX", "MRNA", "PFE",
                       "BMY", "LLY", "ABBV"],
    # --- Consumer discretionary / cyclical ---
    "discretionary": ["TSLA", "HD", "NKE", "SBUX", "MCD", "LOW", "TGT", "DIS",
                      "BKNG", "MAR"],
    # --- Financials (mid SPY-beta) ---
    "financials": ["JPM", "BAC", "GS", "MS", "C", "WFC", "AXP", "SCHW", "BLK"],
    # --- Industrials / cyclicals incl. known laggard BA ---
    "industrials": ["CAT", "DE", "BA", "GE", "HON", "UPS", "LMT", "RTX", "MMM"],
    # --- Energy (own factor, low correlation to tech) ---
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX"],
    # --- Low-beta defensives: staples ---
    "staples": ["PG", "KO", "PEP", "WMT", "COST", "CL", "MDLZ", "KMB"],
    # --- Low-beta defensives: utilities ---
    "utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    # --- Low-beta defensives: healthcare (non-biotech) ---
    "healthcare": ["JNJ", "UNH", "MRK", "ABT", "TMO", "DHR", "CVS"],
    # --- Telecom / value laggards (deliberate losers) ---
    "value_laggard": ["VZ", "T", "CSCO", "IBM", "WBA", "MMM", "PFE"],
    # --- Materials ---
    "materials": ["LIN", "APD", "FCX", "NEM", "DOW"],
}

# Flatten + dedup (some names tagged in 2 buckets, e.g. MMM/PFE laggards).
seen = set()
ordered = []
tag_of = {}
for tag, syms in CANDIDATES.items():
    for s in syms:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
            tag_of[s] = tag

survivors = []
dropped = []
rows = []
for sym in ordered:
    try:
        b = bars_cache.get_bars(sym, "1Day", days=2200)
    except Exception as e:
        dropped.append((sym, f"fetch-error:{type(e).__name__}"))
        rows.append((sym, tag_of[sym], 0, "ERR", "ERR", "DROP"))
        continue
    n = len(b) if b else 0
    first = b[0]["t"][:10] if b else "—"
    last = b[-1]["t"][:10] if b else "—"
    ok = (n >= MIN_BARS and first == FLOOR)
    if ok:
        survivors.append(sym)
        rows.append((sym, tag_of[sym], n, first, last, "keep"))
    else:
        reason = []
        if n < MIN_BARS:
            reason.append(f"only {n} bars")
        if first != FLOOR:
            reason.append(f"first={first}!={FLOOR}")
        dropped.append((sym, ";".join(reason)))
        rows.append((sym, tag_of[sym], n, first, last, "DROP"))

print(f"# Dispersed-universe survivorship audit (floor={FLOOR}, min_bars={MIN_BARS})")
print(f"{'sym':<7}{'bucket':<16}{'bars':>6}  {'first':<11}{'last':<11}{'status'}")
for sym, tag, n, first, last, st in rows:
    print(f"{sym:<7}{tag:<16}{n:>6}  {first:<11}{last:<11}{st}")
print(f"\nSURVIVORS: {len(survivors)}")
print(" ".join(survivors))
print(f"\nDROPPED: {len(dropped)}")
for sym, why in dropped:
    print(f"  {sym}: {why}")

# Write the basket file.
basket_path = WS / "baskets" / "dispersed_xsec.txt"
basket_path.parent.mkdir(exist_ok=True)
header = [
    "# Dispersed-universe cross-sectional momentum test basket",
    "# Selection rule: listed+liquid pre-mid-2020 (first daily bar == 2020-07-27",
    "#   data floor, >= 1400 bars), many sectors, deliberate high-beta/high-idio",
    "#   (tech/semis/biotech/growth/cyclical) + low-beta (staples/utils/healthcare/",
    "#   telecom) MIX. Known laggards (BA/INTC/PYPL/PFE/T/WBA/IBM/DIS) deliberately",
    "#   retained. Any name without full history from 2020-07-27 was DROPPED.",
    f"# Survivors: {len(survivors)} names. Audit: reports/_dispersed_universe_audit.py",
]
basket_path.write_text("\n".join(header) + "\n" + "\n".join(survivors) + "\n")
print(f"\nWrote basket -> {basket_path} ({len(survivors)} names)")
