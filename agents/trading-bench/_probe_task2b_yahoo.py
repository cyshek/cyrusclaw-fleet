#!/usr/bin/env python3
"""Task 2 (careful re-probe): Yahoo v8 on delisted tickers, well-spaced, query2,
validate a live control first to prove we are NOT throttled. Tests common
bankrupt-ticker variants (Q suffix). Stooq already proven bot-walled -> skip."""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Accept": "application/json"}
HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")


def yahoo(tkr, pause=2.5):
    last = None
    for host in HOSTS:
        url = ("https://%s/v8/finance/chart/%s"
               "?period1=0&period2=9999999999&interval=1d&events=div,split" % (host, tkr))
        req = urllib.request.Request(url, headers=HDR)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            res = d.get("chart", {}).get("result")
            if not res:
                err = d.get("chart", {}).get("error")
                last = "no-result(%s)" % (err.get("code") if err else "empty")
                continue
            ts = res[0].get("timestamp") or []
            if not ts:
                last = "0-timestamps"
                continue
            lo = datetime.fromtimestamp(min(ts), timezone.utc).strftime("%Y-%m-%d")
            hi = datetime.fromtimestamp(max(ts), timezone.utc).strftime("%Y-%m-%d")
            return (True, "OK", len(ts), "%s..%s" % (lo, hi))
        except urllib.error.HTTPError as e:
            last = "HTTP %s" % e.code
            if e.code == 429:
                time.sleep(pause * 2)
            continue
        except Exception as e:
            last = str(e)[:60]
            continue
        finally:
            time.sleep(pause)
    return (False, last, None, None)


# delisted tickers + plausible Q-suffix bankruptcy variants
TESTS = [
    ("AAPL", "Apple CONTROL-live", False),
    ("MSFT", "Microsoft CONTROL-live", False),
    ("SUNE", "SunEdison 2016", True),
    ("SUNEQ", "SunEdison BK-variant", True),
    ("SHLD", "Sears 2018", True),
    ("SHLDQ", "Sears BK-variant", True),
    ("LEH", "Lehman 2008", True),
    ("LEHMQ", "Lehman BK-variant", True),
    ("BSC", "Bear Stearns 2008", True),
    ("CC", "Circuit City 2008", True),
    ("CCTYQ", "Circuit City BK-variant", True),
    ("RSH", "RadioShack 2015", True),
    ("RSHCQ", "RadioShack BK-variant", True),
    ("WM", "WaMu (note: WM=Waste Mgmt now!)", True),
    ("WAMUQ", "WaMu BK-variant", True),
    ("EK", "Eastman Kodak old 2012", True),
    ("BBI", "Blockbuster 2010", True),
    ("BBIQ", "Blockbuster BK-variant", True),
]


def main():
    print("=" * 100)
    print("TASK 2 careful re-probe: Yahoo v8, query2-first, 2.5s spacing")
    print("=" * 100)
    out = []
    for tkr, label, is_delisted in TESTS:
        ok, msg, n, rng = yahoo(tkr)
        tag = "DELISTED" if is_delisted else "CONTROL "
        print("  [%s] %-7s %-30s ok=%s n=%s range=%s (%s)"
              % (tag, tkr, label[:30], ok, n, rng, msg))
        out.append({"ticker": tkr, "label": label, "is_delisted": is_delisted,
                    "ok": ok, "n": n, "range": rng, "msg": msg})
        time.sleep(1.0)

    controls = [r for r in out if not r["is_delisted"]]
    delisted = [r for r in out if r["is_delisted"]]
    c_ok = sum(1 for r in controls if r["ok"])
    # for delisted, count distinct COMPANIES covered (any variant ok)
    # group by company root label prefix
    comp_groups = {
        "SunEdison": ["SUNE", "SUNEQ"],
        "Sears": ["SHLD", "SHLDQ"],
        "Lehman": ["LEH", "LEHMQ"],
        "BearStearns": ["BSC"],
        "CircuitCity": ["CC", "CCTYQ"],
        "RadioShack": ["RSH", "RSHCQ"],
        "WaMu": ["WM", "WAMUQ"],
        "Kodak-old": ["EK"],
        "Blockbuster": ["BBI", "BBIQ"],
    }
    okset = {r["ticker"] for r in delisted if r["ok"]}
    comp_cov = {k: any(t in okset for t in v) for k, v in comp_groups.items()}
    n_comp = len(comp_groups)
    n_comp_ok = sum(1 for v in comp_cov.values() if v)
    print("-" * 100)
    print("CONTROL (live) coverage: %d/%d  -> proves throttle state"
          % (c_ok, len(controls)))
    if c_ok == 0:
        print("  *** CONTROLS FAILED: still throttled/blocked; delisted 0% is NOT a valid signal ***")
    print("DELISTED company coverage (any ticker variant): %d/%d" % (n_comp_ok, n_comp))
    for k, v in comp_cov.items():
        print("    %-13s %s" % (k, "COVERED" if v else "missing"))
    json.dump({"detail": out, "company_coverage": comp_cov,
               "controls_ok": c_ok, "controls_n": len(controls)},
              open("_task2b_yahoo.json", "w"), indent=2)
    print("")
    print("Wrote _task2b_yahoo.json")


if __name__ == "__main__":
    main()
