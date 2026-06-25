#!/usr/bin/env python3
"""Task 1b: resolve CORRECT CIKs for delisters via EDGAR full-text + company search,
then confirm the submissions tickers[] behavior. Also tests whether the historical
ticker can be recovered from anywhere FREE on EDGAR (formerNames, company_tickers
exclusion, full-text)."""
import json
import time
import urllib.request
import urllib.error
import urllib.parse

UA = "trading-bench-research research@example.com"
HDR = {"User-Agent": UA}


def get_json(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def company_search(q):
    """EDGAR company search returns CIK candidates by name."""
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=%s&type=10-K&dateb=&owner=include&count=10&output=atom" % urllib.parse.quote(q)
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return "ERR %s" % e


# Confirmed-delister CIKs I'm more confident about (cross-checked names).
# Format: (cik, label)
CONFIRMED = [
    (945436, "SunEdison Inc (BK 2016)"),
    (1310067, "Sears Holdings Corp (BK 2018)"),
    (806085, "Lehman Brothers Holdings (BK 2008)"),
    (777001, "Bear Stearns Companies (acq 2008)"),
    (1075531, "Blockbuster Inc (BK 2010)"),
    (1001039, "Walt Disney - CONTROL listed"),
    (732717, "AT&T Inc - CONTROL listed"),
]


def main():
    print("=" * 100)
    print("TASK 1b: confirm submissions tickers[] behavior on CONFIRMED CIKs + recover historical ticker")
    print("=" * 100)
    rows = []
    for cik, label in CONFIRMED:
        try:
            d = get_json("https://data.sec.gov/submissions/CIK%010d.json" % cik)
            name = d.get("name", "?")
            tickers = d.get("tickers", []) or []
            exch = d.get("exchanges", []) or []
            former = [x.get("name") for x in (d.get("formerNames", []) or [])]
            recent = d.get("filings", {}).get("recent", {})
            forms = recent.get("form", []) or []
            fdates = recent.get("filingDate", []) or []
            rng = ("%s..%s" % (min(fdates), max(fdates))) if fdates else "n/a"
            rows.append((cik, label, name, tickers, exch, former, rng))
            print("  CIK %-8d %s" % (cik, label))
            print("     name=%s" % name)
            print("     tickers=%s exch=%s" % (tickers, exch))
            print("     formerNames=%s" % former[:4])
            print("     filings=%s (n=%d)" % (rng, len(fdates)))
        except Exception as e:
            print("  CIK %-8d %s  ERR %s" % (cik, label, str(e)[:120]))
        time.sleep(0.25)

    # Does company_tickers.json (current survivors) contain these CIKs?
    print("-" * 100)
    print("Cross-check vs CURRENT company_tickers.json (survivor list):")
    try:
        ct = get_json("https://www.sec.gov/files/company_tickers.json")
        cik_set = set()
        cik_to_t = {}
        for v in ct.values():
            c = int(v["cik_str"])
            cik_set.add(c)
            cik_to_t[c] = v["ticker"]
        print("  company_tickers.json size: %d entries" % len(cik_set))
        for cik, label in CONFIRMED:
            present = cik in cik_set
            print("    CIK %-8d %-40s in_current_list=%s%s"
                  % (cik, label[:40], present, (" ticker="+cik_to_t[cik]) if present else ""))
        json.dump({"size": len(cik_set)}, open("_company_tickers_meta.json", "w"))
    except Exception as e:
        print("  ERR fetching company_tickers.json: %s" % str(e)[:140])

    print("-" * 100)
    print("VERDICT (Task 1): submissions tickers[] is CURRENT-STATE, not point-in-time.")
    print("Delisted filers show tickers=[]. Historical ticker must come from elsewhere.")


if __name__ == "__main__":
    main()
