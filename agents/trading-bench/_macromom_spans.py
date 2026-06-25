"""Confirm history spans for the candidate macro basket symbols.

Broader cross-asset basket than the failed 6:
  equities    SPY, EFA, EEM
  rates       TLT, IEF
  commodities DBC, GLD, USO
  credit/REIT LQD, VNQ
  dollar      UUP

Print first/last/count for each so we can choose a clean 2008+ or 2010+ window
and drop any too-short symbol.
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import daily_bars_cache as dbc

CANDIDATES = [
    "SPY", "EFA", "EEM",        # equities
    "TLT", "IEF",               # rates
    "DBC", "GLD", "USO",        # commodities
    "LQD", "VNQ",               # credit / REIT
    "UUP",                      # dollar
]


def main() -> None:
    rows = []
    for sym in CANDIDATES:
        try:
            sp = dbc.span(sym)
            rows.append((sym, sp["first"], sp["last"], sp["n"]))
        except Exception as e:  # noqa: BLE001
            rows.append((sym, f"ERR {type(e).__name__}", str(e)[:60], 0))
    rows.sort(key=lambda r: str(r[1]))
    print(f"{'SYM':6s} {'FIRST':12s} {'LAST':12s} {'N':>6s}")
    for sym, first, last, n in rows:
        print(f"{sym:6s} {str(first):12s} {str(last):12s} {n:>6}")


if __name__ == "__main__":
    main()
