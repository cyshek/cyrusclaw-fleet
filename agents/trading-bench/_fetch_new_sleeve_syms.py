import time, sys
sys.path.insert(0, ".")
from runner import daily_bars_cache as dbc


def fetch_one(s):
    for attempt in range(4):
        try:
            bars = dbc.get_daily(s, refresh=False)
            print(f'{s}: OK  {bars[0]["date"]} -> {bars[-1]["date"]}  ({len(bars)} bars)', flush=True)
            return True
        except Exception as e:
            wait = 1.5 * (2 ** attempt)
            print(f'{s}: attempt {attempt+1} failed: {str(e)[:120]} -> backoff {wait:.1f}s', flush=True)
            time.sleep(wait)
    print(f'{s}: GAVE UP after backoff', flush=True)
    return False


for s in ["UUP", "DBMF", "KMLM"]:
    fetch_one(s)
    time.sleep(2.0)
