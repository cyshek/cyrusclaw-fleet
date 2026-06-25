"""Fetch SPY adjclose daily history from Yahoo v8 chart API, cache to root scratch json."""
import json
import datetime as dt
import urllib.request
from pathlib import Path

CACHE = Path("_spy_daily_l165.json")
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY"
       "?period1=0&period2=9999999999&interval=1d&events=div,split")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def main():
    if CACHE.exists():
        d = json.loads(CACHE.read_text())
        print("CACHED:", len(d["dates"]), "days", d["dates"][0], "->", d["dates"][-1])
        return
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = json.loads(r.read().decode())
    res = raw["chart"]["result"][0]
    ts = res["timestamp"]
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    dates = []
    closes = []
    for t, c in zip(ts, adj):
        if c is None:
            continue
        day = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        dates.append(day)
        closes.append(float(c))
    out = {"dates": dates, "adjclose": closes}
    CACHE.write_text(json.dumps(out))
    print("FETCHED:", len(dates), "days", dates[0], "->", dates[-1])
    print("sample last 3:", list(zip(dates[-3:], [round(x, 2) for x in closes[-3:]])))


if __name__ == "__main__":
    main()
