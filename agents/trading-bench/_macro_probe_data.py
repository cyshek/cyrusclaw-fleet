"""Constructibility probe: confirm basket ETFs + FRED macro series fetch and
have history back to ~2007. Pure read; no protected file touched."""
from __future__ import annotations

import datetime as dt

from runner import daily_bars_cache as dbc
from runner import fred_cache

BASKET = ["SPY", "EFA", "TLT", "GLD", "DBC", "VNQ", "UUP"]

print("=== BASKET ETF availability (Yahoo adjclose) ===")
for s in BASKET:
    try:
        bars = dbc.get_daily(s)
        good = [b for b in bars if b.get("adjclose") is not None]
        print(f"{s:5s} n={len(good):5d} first={good[0]['date']} last={good[-1]['date']}")
    except Exception as e:
        print(f"{s:5s} ERROR {type(e).__name__}: {e}")

print()
print("=== FRED macro series availability (keyed API) ===")
MACRO = [
    ("INDPRO",   "Industrial Production (growth)",      True),
    ("CPIAUCSL", "CPI (inflation)",                     True),
    ("T10Y2Y",   "10y-2y curve slope",                  False),
    ("DGS10",    "10y Treasury level",                  False),
    ("BAA10Y",   "Baa corporate spread (credit)",       False),
    ("DTWEXBGS", "Broad dollar index",                  False),
    ("PAYEMS",   "Nonfarm payrolls (growth alt)",       True),
    ("UNRATE",   "Unemployment rate (growth alt)",      True),
]
START = "2005-01-01"
END = "2026-06-24"
for sid, human, revised in MACRO:
    try:
        rows = fred_cache.get_series(sid, START, END, vintage="latest")
        real = [r for r in rows if r["value"] is not None]
        freq_note = ""
        if len(real) >= 3:
            d0 = dt.date.fromisoformat(real[-2]["date"])
            d1 = dt.date.fromisoformat(real[-1]["date"])
            gap = (d1 - d0).days
            freq_note = "daily" if gap <= 5 else ("monthly" if gap <= 40 else f"~{gap}d")
        covers07 = any(r["date"].startswith("2007") for r in real)
        covers06 = any(r["date"].startswith("2006") for r in real)
        print(f"{sid:9s} n={len(real):5d} first={real[0]['date']} last={real[-1]['date']} "
              f"freq={freq_note:7s} rev={revised} cov2006={covers06} cov2007={covers07}  ({human})")
    except Exception as e:
        print(f"{sid:9s} ERROR {type(e).__name__}: {e}")
