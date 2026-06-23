"""Probe: fetch/verify all candidate universe symbols via daily_bars_cache (Yahoo v8 adjclose)."""
import sys, time
from pathlib import Path
WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
from runner import daily_bars_cache as dbc

syms = ['SPY','QQQ','XLK','XLF','XLE','XLV','TLT','IEF','SHY','GLD','SLV','USO','VNQ','EFA','EEM','DBC']
rows = []
for s in syms:
    try:
        d = dbc.get_daily(s)
        if d and len(d) > 0:
            print(f'{s:5s}: {len(d):5d} bars, inception {d[0]["date"]}, latest {d[-1]["date"]}, last_adj={d[-1]["adjclose"]:.2f}')
            rows.append((s, d[0]["date"], d[-1]["date"], len(d)))
        else:
            print(f'{s:5s}: EMPTY')
    except Exception as e:
        print(f'{s:5s}: ERROR {type(e).__name__}: {e}')
    time.sleep(0.3)

if rows:
    latest_inception = max(r[1] for r in rows)
    earliest_end = min(r[2] for r in rows)
    print()
    print(f'Latest inception across universe (common-window start floor): {latest_inception}')
    print(f'Earliest last-bar across universe: {earliest_end}')
