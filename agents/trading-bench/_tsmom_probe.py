from runner import daily_bars_cache as dbc

UNIV = ['SPY', 'DBC', 'GLD', 'TLT', 'UUP', 'IEF', 'SLV', 'USO', 'VNQ', 'EFA', 'EEM', 'QQQ']
for s in UNIV:
    try:
        b = dbc.get_daily(s)
        print(f'{s:5s} n={len(b):5d}  {b[0]["date"]} -> {b[-1]["date"]}  adj0={b[0]["adjclose"]:.4f} adjN={b[-1]["adjclose"]:.4f}')
    except Exception as e:
        print(f'{s:5s} ERR {type(e).__name__}: {e}')
