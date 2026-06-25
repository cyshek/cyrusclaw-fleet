#!/usr/bin/env python3
"""Task 1: CIK -> historical ticker resolution for KNOWN DELISTED names."""
import json
import time
import urllib.request
import urllib.error

UA = "trading-bench-research research@example.com"
HDR = {"User-Agent": UA}

DELISTERS = [
    (945436, "SunEdison/MEMC (BK 2016)", "SUNE"),
    (1310067, "Sears Holdings (BK 2018)", "SHLD"),
    (806085, "Lehman Brothers Holdings (BK 2008)", "LEH"),
    (777001, "Bear Stearns (acq 2008)", "BSC"),
    (933136, "Washington Mutual (BK 2008)", "WM/WAMU"),
    (914208, "Circuit City Stores (BK 2008)", "CC"),
    (96021, "RadioShack/Tandy (BK 2015)", "RSH"),
    (29915, "Eastman Kodak (BK 2012)", "EK/KODK"),
    (320193, "Apple (CONTROL - listed survivor)", "AAPL"),
]


def fetch_submission(cik):
    url = "https://data.sec.gov/submissions/CIK%010d.json" % cik
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    results = []
    for cik, label, hint in DELISTERS:
        rec = {"cik": cik, "label": label, "hint": hint}
        try:
            d = fetch_submission(cik)
            rec["entityName"] = d.get("name", "?")
            tickers = d.get("tickers", []) or []
            exchanges = d.get("exchanges", []) or []
            rec["tickers"] = tickers
            rec["exchanges"] = exchanges
            fn = d.get("formerNames", []) or []
            rec["formerNames"] = [x.get("name") for x in fn][:3]
            rec["has_ticker"] = len(tickers) > 0
            rec["sic"] = d.get("sicDescription", "")
            rec["stateOfIncorp"] = d.get("stateOfIncorporation", "")
            recent = d.get("filings", {}).get("recent", {})
            fdates = recent.get("filingDate", []) or []
            if fdates:
                rec["filing_range"] = "%s..%s" % (min(fdates), max(fdates))
            rec["ok"] = True
        except urllib.error.HTTPError as e:
            rec["ok"] = False
            rec["err"] = "HTTP %s" % e.code
        except Exception as e:
            rec["ok"] = False
            rec["err"] = str(e)[:140]
        results.append(rec)
        time.sleep(0.25)

    print("=" * 100)
    print("TASK 1: CIK -> historical ticker via submissions JSON")
    print("=" * 100)
    n_total = 0
    n_ticker = 0
    for r in results:
        if not r.get("ok"):
            print("  [%-40s] CIK %s  ERR: %s" % (r["label"][:40], r["cik"], r.get("err")))
            continue
        n_total += 1
        if r["has_ticker"]:
            n_ticker += 1
        print("  [%-40s] CIK %d" % (r["label"][:40], r["cik"]))
        print("      entityName : %s" % r.get("entityName"))
        print("      tickers    : %s   exchanges: %s   has_ticker=%s"
              % (r.get("tickers"), r.get("exchanges"), r["has_ticker"]))
        if r.get("formerNames"):
            print("      formerNames: %s" % r.get("formerNames"))
        print("      sic/state  : %s / %s   filings: %s"
              % (r.get("sic"), r.get("stateOfIncorp"), r.get("filing_range")))
    print("-" * 100)
    print("SUMMARY: %d/%d resolvable CIKs exposed a non-empty tickers[] field (%.0f%%)"
          % (n_ticker, n_total, 100.0 * n_ticker / max(n_total, 1)))
    deln = [r for r in results if r.get("ok") and "CONTROL" not in r["label"]]
    deln_t = [r for r in deln if r["has_ticker"]]
    print("DELISTERS-ONLY: %d/%d delisted names exposed a ticker (%.0f%%)"
          % (len(deln_t), len(deln), 100.0 * len(deln_t) / max(len(deln), 1)))

    out = {}
    for r in results:
        if r.get("ok") and r["has_ticker"]:
            out[str(r["cik"])] = {
                "label": r["label"],
                "ticker": r["tickers"][0],
                "all_tickers": r["tickers"],
                "exchange": (r["exchanges"][0] if r.get("exchanges") else None),
            }
    json.dump(out, open("_task1_resolved.json", "w"), indent=2)
    print("")
    print("Wrote %d resolved (cik->ticker) to _task1_resolved.json" % len(out))


if __name__ == "__main__":
    main()
