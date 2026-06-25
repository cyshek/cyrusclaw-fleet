#!/usr/bin/env python3
"""Task 2 (MAKE-OR-BREAK): can we get FREE daily price history for DELISTED tickers
covering their active window?

Tests, per delisted ticker:
  (A) Yahoo v8 chart API   -> expected 404/empty on dead tickers
  (B) stooq.com CSV        -> the key candidate for delisted archives
  (C) Alpha Vantage        -> only if key present in .env (it is NOT, per check)
We use well-known historical tickers for confirmed delisters (resolution itself
requires an external map per Task 1).
"""
import json
import os
import time
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HDR = {"User-Agent": UA}

# (ticker, company, delist_year, last_active_approx)
DELISTED = [
    ("SUNE", "SunEdison", 2016, "2016-04"),
    ("SHLD", "Sears Holdings", 2018, "2018-10"),
    ("LEH", "Lehman Brothers", 2008, "2008-09"),
    ("BSC", "Bear Stearns", 2008, "2008-03"),
    ("CC", "Circuit City", 2008, "2008-11"),
    ("RSHCQ", "RadioShack", 2015, "2015-02"),
    ("WAMUQ", "Washington Mutual", 2008, "2008-09"),
    ("EK", "Eastman Kodak (old)", 2012, "2012-01"),
    ("BBI", "Blockbuster", 2010, "2010-09"),
    ("GM", "General Motors (old, pre-BK)", 2009, "2009-06"),
    ("AAPL", "Apple (CONTROL listed)", None, "live"),
    ("MSFT", "Microsoft (CONTROL listed)", None, "live"),
]


def yahoo_chart(tkr):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
           "?period1=0&period2=9999999999&interval=1d&events=div,split" % tkr)
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        res = d.get("chart", {}).get("result")
        if not res:
            err = d.get("chart", {}).get("error")
            return (False, "no result (%s)" % (err.get("code") if err else "empty"), None, None)
        ts = res[0].get("timestamp") or []
        if not ts:
            return (False, "result but 0 timestamps", None, None)
        import datetime as dt
        lo = dt.datetime.utcfromtimestamp(min(ts)).strftime("%Y-%m-%d")
        hi = dt.datetime.utcfromtimestamp(max(ts)).strftime("%Y-%m-%d")
        return (True, "OK", len(ts), "%s..%s" % (lo, hi))
    except urllib.error.HTTPError as e:
        return (False, "HTTP %s" % e.code, None, None)
    except Exception as e:
        return (False, str(e)[:80], None, None)


def stooq(tkr):
    # stooq uses lowercase .us suffix
    url = "https://stooq.com/q/d/l/?s=%s.us&i=d" % tkr.lower()
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        # header: Date,Open,High,Low,Close,Volume
        if not lines or not lines[0].lower().startswith("date"):
            return (False, "no csv header (got: %r)" % (raw[:60]), None, None, raw)
        data = lines[1:]
        if not data:
            return (False, "header only, 0 rows", 0, None, raw)
        # check for "no data" sentinel
        if len(data) == 1 and "n/a" in data[0].lower():
            return (False, "N/D sentinel", 0, None, raw)
        first = data[0].split(",")[0]
        last = data[-1].split(",")[0]
        return (True, "OK", len(data), "%s..%s" % (first, last), raw)
    except urllib.error.HTTPError as e:
        return (False, "HTTP %s" % e.code, None, None, "")
    except Exception as e:
        return (False, str(e)[:80], None, None, "")


def alphavantage(tkr, key):
    url = ("https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
           "&symbol=%s&outputsize=full&apikey=%s" % (tkr, key))
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        ts = d.get("Time Series (Daily)")
        if not ts:
            note = d.get("Note") or d.get("Information") or d.get("Error Message") or str(d)[:80]
            return (False, "no series (%s)" % note[:60], None, None)
        ks = sorted(ts.keys())
        return (True, "OK", len(ks), "%s..%s" % (ks[0], ks[-1]))
    except Exception as e:
        return (False, str(e)[:80], None, None)


def main():
    # check for av key
    av_key = None
    envp = ".env"
    if os.path.exists(envp):
        for ln in open(envp):
            if ln.startswith("ALPHAVANTAGE") or ln.startswith("ALPHA_VANTAGE") or ln.startswith("AV_API"):
                av_key = ln.split("=", 1)[1].strip()
    print("=" * 100)
    print("TASK 2: FREE daily price history for DELISTED tickers (make-or-break)")
    print("AlphaVantage key present: %s" % bool(av_key))
    print("=" * 100)

    summary = []
    for tkr, name, dyear, last in DELISTED:
        is_control = dyear is None
        yok, ymsg, yn, yrng = yahoo_chart(tkr)
        time.sleep(0.4)
        sok, smsg, sn, srng, sraw = stooq(tkr)
        time.sleep(0.6)
        aok, amsg, an, arng = (None, "skipped (no key)", None, None)
        if av_key:
            aok, amsg, an, arng = alphavantage(tkr, av_key)
            time.sleep(13)  # AV free tier 5 req/min
        print("  %-6s %-26s delist=%s last~%s  CONTROL=%s"
              % (tkr, name[:26], dyear, last, is_control))
        print("     Yahoo : ok=%s n=%s range=%s  (%s)" % (yok, yn, yrng, ymsg))
        print("     Stooq : ok=%s n=%s range=%s  (%s)" % (sok, sn, srng, smsg))
        if av_key:
            print("     AlphaV: ok=%s n=%s range=%s  (%s)" % (aok, an, arng, amsg))
        # decide: did ANY free source cover the active window for a DELISTED name?
        got = bool(yok) or bool(sok) or bool(aok)
        summary.append({
            "ticker": tkr, "name": name, "delist_year": dyear, "is_control": is_control,
            "yahoo": {"ok": bool(yok), "n": yn, "range": yrng},
            "stooq": {"ok": bool(sok), "n": sn, "range": srng},
            "alphav": {"ok": bool(aok), "n": an, "range": arng},
            "any_free_cover": got,
        })

    print("-" * 100)
    delisted_only = [s for s in summary if not s["is_control"]]
    cov_yahoo = sum(1 for s in delisted_only if s["yahoo"]["ok"])
    cov_stooq = sum(1 for s in delisted_only if s["stooq"]["ok"])
    cov_any = sum(1 for s in delisted_only if s["any_free_cover"])
    N = len(delisted_only)
    print("DELISTED-NAME PRICE COVERAGE (n=%d):" % N)
    print("  Yahoo v8 : %d/%d (%.0f%%)" % (cov_yahoo, N, 100.0*cov_yahoo/N))
    print("  Stooq    : %d/%d (%.0f%%)" % (cov_stooq, N, 100.0*cov_stooq/N))
    print("  ANY free : %d/%d (%.0f%%)" % (cov_any, N, 100.0*cov_any/N))
    json.dump(summary, open("_task2_price_coverage.json", "w"), indent=2)
    print("")
    print("Wrote _task2_price_coverage.json")


if __name__ == "__main__":
    main()
