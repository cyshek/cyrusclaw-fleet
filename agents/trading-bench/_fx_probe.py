import urllib.request, json, datetime
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
syms = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCHF=X","USDCAD=X"]
for sym in syms:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + sym + "?period1=0&period2=9999999999&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        d = json.loads(resp.read().decode())
        res = d["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        cl = q["close"]
        f = datetime.datetime.utcfromtimestamp(ts[0]).date().isoformat()
        l = datetime.datetime.utcfromtimestamp(ts[-1]).date().isoformat()
        nn = sum(1 for c in cl if c is not None)
        has_adj = "adjclose" in res["indicators"]
        print(sym, "n=", len(ts), "nonnull=", nn, "first=", f, "last=", l, "c0=", cl[0], "cN=", cl[-1], "adj=", has_adj)
    except Exception as e:
        print(sym, "ERR", repr(e))
