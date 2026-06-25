#!/usr/bin/env python3
"""Task 3b: of the 'gone' CIKs (filed 2014, absent from current survivor list),
how many expose a ticker via submissions JSON (the only free EDGAR resolver)?
Sample N to bound free-resolvability. Expectation from Task 1: ~0% for true
delisters (ticker stripped on delist); some 'gone' are M&A where the CIK's
ticker now belongs to the acquirer (recycle), which is ALSO wrong."""
import json
import time
import urllib.request
import urllib.error

UA = "trading-bench-research research@example.com"
HDR = {"User-Agent": UA}


def get_json(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    u = json.load(open("_task3_universe.json"))
    gone_sample = u["gone_ciks_sample"]  # first 200 gone CIKs
    N = min(60, len(gone_sample))  # sample 60 to stay polite/fast
    sample = gone_sample[:N]
    print("=" * 100)
    print("TASK 3b: free ticker-resolvability of %d sampled 'gone' CIKs (filed 2014, now absent)" % N)
    print("=" * 100)
    has_ticker = 0
    empty = 0
    errs = 0
    examples_ticker = []
    examples_empty = []
    for cik in sample:
        try:
            d = get_json("https://data.sec.gov/submissions/CIK%010d.json" % int(cik))
            tickers = d.get("tickers", []) or []
            name = d.get("name", "?")
            if tickers:
                has_ticker += 1
                if len(examples_ticker) < 8:
                    examples_ticker.append((cik, name, tickers))
            else:
                empty += 1
                if len(examples_empty) < 8:
                    examples_empty.append((cik, name))
        except Exception:
            errs += 1
        time.sleep(0.2)
    ok = has_ticker + empty
    print("Resolvable submissions: %d (errors %d)" % (ok, errs))
    print("  exposed a ticker[] : %d/%d (%.0f%%)" % (has_ticker, ok, 100.0*has_ticker/max(ok,1)))
    print("  empty ticker[]     : %d/%d (%.0f%%)" % (empty, ok, 100.0*empty/max(ok,1)))
    print("")
    print("NOTE: a 'gone' CIK that DOES expose a ticker is typically an M&A where the")
    print("CIK/ticker now maps to the acquirer or a recycled symbol -> still the WRONG")
    print("price series for the original company at backtest time. Empty-ticker names are")
    print("simply unresolvable for free.")
    print("-" * 100)
    print("Sample names WITH a (suspect/recycled) ticker:")
    for cik, name, t in examples_ticker:
        print("   CIK %-8s %-40s tickers=%s" % (cik, name[:40], t))
    print("Sample names with EMPTY ticker (unresolvable free):")
    for cik, name in examples_empty:
        print("   CIK %-8s %s" % (cik, name[:50]))
    json.dump({"sampled": N, "resolvable": ok, "errors": errs,
               "has_ticker": has_ticker, "empty": empty,
               "has_ticker_pct": 100.0*has_ticker/max(ok,1)},
              open("_task3b_resolve.json", "w"), indent=2)
    print("")
    print("Wrote _task3b_resolve.json")


if __name__ == "__main__":
    main()
