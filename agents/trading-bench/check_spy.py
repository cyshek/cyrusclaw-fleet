import urllib.request, json
from datetime import datetime

url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=1167609600&period2=9999999999&interval=1d"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.load(r)
ts = data["chart"]["result"][0]["timestamp"]
d0 = datetime.fromtimestamp(ts[0]).date()
d1 = datetime.fromtimestamp(ts[-1]).date()
ac = data["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"]
print("SPY days:", len(ts))
print("Date range:", d0, "->", d1)
print("Last adjclose:", ac[-1])
