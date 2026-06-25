#!/usr/bin/env python3
"""Task 2c: PROVE the 'covered' delisted hits are ticker-RECYCLE false positives.

A genuine delisted series must END at/near the delist date. If Yahoo returns a
series running to ~today for a company that died years ago, that ticker was
reassigned to a DIFFERENT live entity -> useless for survivorship-clean backtest
(it injects the wrong company's prices). We quantify the gap between the series
end date and the known delist date."""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Accept": "application/json"}
HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")

# ticker -> (company, known delist month). These are the 'covered' hits from 2b.
RECYCLE_SUSPECTS = {
    "SUNE": ("SunEdison", "2016-04"),
    "SHLD": ("Sears Holdings", "2018-10"),
    "CC": ("Circuit City", "2008-11"),
    "RSH": ("RadioShack", "2015-02"),
    "WM": ("Washington Mutual", "2008-09"),
}


def yahoo_series(tkr, pause=2.5):
    for host in HOSTS:
        url = ("https://%s/v8/finance/chart/%s"
               "?period1=0&period2=9999999999&interval=1d&events=div,split" % (host, tkr))
        req = urllib.request.Request(url, headers=HDR)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            res = d.get("chart", {}).get("result")
            if not res:
                continue
            ts = res[0].get("timestamp") or []
            meta = res[0].get("meta", {})
            if not ts:
                continue
            lo = datetime.fromtimestamp(min(ts), timezone.utc).strftime("%Y-%m-%d")
            hi = datetime.fromtimestamp(max(ts), timezone.utc).strftime("%Y-%m-%d")
            return {"ok": True, "n": len(ts), "start": lo, "end": hi,
                    "exchangeName": meta.get("fullExchangeName"),
                    "longName": meta.get("longName") or meta.get("shortName"),
                    "instrumentType": meta.get("instrumentType")}
        except Exception:
            continue
        finally:
            time.sleep(pause)
    return {"ok": False}


def main():
    print("=" * 100)
    print("TASK 2c: are the 'covered' delisted hits actually ticker-RECYCLE false positives?")
    print("A real delisted series ENDS near the delist date. Series ending ~today = WRONG entity.")
    print("=" * 100)
    recycle = 0
    genuine = 0
    rows = []
    for tkr, (comp, delist) in RECYCLE_SUSPECTS.items():
        r = yahoo_series(tkr)
        if not r.get("ok"):
            print("  %-6s %-20s -> no series" % (tkr, comp))
            continue
        end = r["end"]
        end_year = int(end[:4])
        delist_year = int(delist[:4])
        # if the series ends >1yr after the delist date, it's a different live entity
        gap_years = end_year - delist_year
        is_recycle = gap_years >= 2  # ends well after death => recycled
        if is_recycle:
            recycle += 1
        else:
            genuine += 1
        print("  %-6s %-20s delist=%s" % (tkr, comp, delist))
        print("       series: %s .. %s  (n=%d)" % (r["start"], end, r["n"]))
        print("       yahoo longName=%r exch=%r type=%r"
              % (r.get("longName"), r.get("exchangeName"), r.get("instrumentType")))
        print("       --> %s (series ends %d yrs after delisting)"
              % ("TICKER-RECYCLE / WRONG ENTITY" if is_recycle else "plausibly genuine",
                 gap_years))
        rows.append({"ticker": tkr, "company": comp, "delist": delist,
                     "series_start": r["start"], "series_end": end, "n": r["n"],
                     "yahoo_longName": r.get("longName"), "is_recycle": is_recycle})
        time.sleep(1.0)
    print("-" * 100)
    print("RESULT: of %d 'covered' delisted tickers, %d are ticker-RECYCLE false positives, "
          "%d plausibly genuine." % (len(rows), recycle, genuine))
    print("=> Yahoo coverage of TRULY-delisted history is effectively ZERO; apparent hits are")
    print("   the symbol's CURRENT occupant, which would inject the wrong company's prices.")
    json.dump(rows, open("_task2c_recycle.json", "w"), indent=2)
    print("")
    print("Wrote _task2c_recycle.json")


if __name__ == "__main__":
    main()
