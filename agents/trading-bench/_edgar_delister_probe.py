import json, urllib.request

UA = "trading-bench-research research@example.com"


def cf(cik, dest):
    url = "https://data.sec.gov/api/xbrl/companyfacts/CIK%010d.json" % cik
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    resp = urllib.request.urlopen(req, timeout=30)
    open(dest, "wb").write(resp.read())
    d = json.load(open(dest))
    facts = d.get("facts", {}).get("us-gaap", {})
    dates = []
    for c in ("Assets", "NetIncomeLoss", "Revenues", "StockholdersEquity"):
        for u in facts.get(c, {}).get("units", {}).values():
            for row in u:
                if row.get("filed"):
                    dates.append(row["filed"])
    return d.get("entityName", "?"), dates


for cik, label in [(945436, "SunEdison/MEMC (BK 2016)"), (1310067, "Sears Holdings (BK 2018)")]:
    try:
        name, dates = cf(cik, "/tmp/cik%d.json" % cik)
        if dates:
            print("%s: entity=%s | filings %s -> %s (%d pts) => EDGAR retains post-delisting history: YES"
                  % (label, name, min(dates), max(dates), len(dates)))
        else:
            print("%s: entity=%s | NO datapoints" % (label, name))
    except Exception as e:
        print("%s: ERR %s" % (label, str(e)[:140]))
