#!/usr/bin/env python3
"""Task 3: universe-scale feasibility. Compare the point-in-time filer set from
xbrl/frames (CY2014Q4I Assets, ~7,494 CIKs) against the CURRENT company_tickers
survivor list (~8,021). Estimate the delisted-and-unresolvable fraction.

Key idea: any CIK that filed Assets in CY2014Q4 but is NOT in the current
company_tickers.json is a 'gone' filer (delisted, merged, BK, or went private).
Those are exactly the names a survivorship-clean backtest needs but a survivor
list omits. The price-resolvability of that gone set (from Task 2) bounds how
much survivorship bias we can actually remove for free."""
import json
import time
import urllib.request

UA = "trading-bench-research research@example.com"
HDR = {"User-Agent": UA}


def get_json(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    print("=" * 100)
    print("TASK 3: universe-scale survivorship feasibility")
    print("=" * 100)

    # 1. point-in-time filer set: who reported Assets as of CY2014Q4 (instant)
    frame = get_json("https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2014Q4I.json")
    pit_ciks = set(int(d["cik"]) for d in frame.get("data", []))
    print("CY2014Q4I Assets frame: %d unique CIKs (point-in-time filer set)" % len(pit_ciks))

    time.sleep(0.4)
    # 2. current survivor list
    ct = get_json("https://www.sec.gov/files/company_tickers.json")
    cur_ciks = set(int(v["cik_str"]) for v in ct.values())
    cur_t = {int(v["cik_str"]): v["ticker"] for v in ct.values()}
    print("Current company_tickers.json: %d CIKs (survivor list)" % len(cur_ciks))

    # 3. the 'gone' set: filed in 2014 but absent from current list
    gone = pit_ciks - cur_ciks
    still = pit_ciks & cur_ciks
    print("-" * 100)
    print("Of the %d CY2014Q4 filers:" % len(pit_ciks))
    print("  STILL in current list (survivors)   : %d (%.1f%%)"
          % (len(still), 100.0*len(still)/len(pit_ciks)))
    print("  GONE from current list (delisted/M&A/private): %d (%.1f%%)"
          % (len(gone), 100.0*len(gone)/len(pit_ciks)))
    print("")
    print("INTERPRETATION: a survivor-only universe drops the %.1f%% 'gone' names ->"
          % (100.0*len(gone)/len(pit_ciks)))
    print("that IS the survivorship bias magnitude for a 2014->today backtest at the filer level.")

    # persist gone CIK list so we can (optionally) sample-resolve their tickers
    json.dump({"pit_total": len(pit_ciks), "survivors": len(still),
               "gone": len(gone),
               "gone_pct": 100.0*len(gone)/len(pit_ciks),
               "gone_ciks_sample": sorted(gone)[:200]},
              open("_task3_universe.json", "w"), indent=2)
    print("")
    print("Wrote _task3_universe.json (gone_ciks_sample = first 200 for follow-up resolution)")
    return sorted(gone)


if __name__ == "__main__":
    main()
