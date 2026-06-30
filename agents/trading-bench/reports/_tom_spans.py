from runner import daily_bars_cache as dbc

for s in ("SPY", "QQQ", "^GSPC", "^NDX", "SSO", "QLD", "UPRO", "TQQQ"):
    try:
        sp = dbc.span(s)
        print(f"{s:8s} n={sp['n']:5d} {sp['first']} -> {sp['last']}")
    except Exception as e:
        print(f"{s:8s} ERR {type(e).__name__}: {e}")
