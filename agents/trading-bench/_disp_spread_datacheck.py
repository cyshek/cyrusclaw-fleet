#!/usr/bin/env python3
"""Quick data-access + scale-inspection check before building the spread probe."""
import csv
from runner import daily_bars_cache as dbc

# 1. Sector ETF basket + SPY access
basket = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB"]
for sym in basket + ["SPY"]:
    bars = dbc.get_daily(sym)
    if not bars:
        print(f"{sym}: NO DATA")
        continue
    first = bars[0]
    last = bars[-1]
    print(f"{sym:4s} n={len(bars):5d}  {first['date']} -> {last['date']}  "
          f"adjclose first={first.get('adjclose')} last={last.get('adjclose')}")

# 2. COR1M scale inspection
rows = list(csv.reader(open("data_cache/cboe/COR1M_History.csv")))[1:]
closes = [float(r[4]) for r in rows if len(r) >= 5 and r[4]]
print(f"\nCOR1M CLOSE: n={len(closes)} min={min(closes):.2f} "
      f"max={max(closes):.2f} mean={sum(closes)/len(closes):.2f}")
print("(if range ~5-90 => index level = implied corr x 100; divide by 100 to get 0-1)")
