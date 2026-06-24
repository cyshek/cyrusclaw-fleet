#!/usr/bin/env python3
"""
Build ticker->sector map for the 104-name universe from SEC SIC codes.

Source: SEC submissions API (VERIFIED working from this VM):
  https://data.sec.gov/submissions/CIK<10-digit>.json  (carries `sic` + `sicDescription`)
CIKs come from data_cache/edgar_fundamentals/universe.json -> ticker_cik.

Politeness: SEC limit is 10 req/sec; we sleep ~0.15s between requests (~6-7/sec) and
cache each raw response to data_cache/edgar_submissions/<TICKER>.json so reruns are free.

SIC -> coarse sector bucket via the standard SIC major-group ranges (SIC-division ->
~10-12 GICS-ish sectors). Mega-cap granular SIC is used AS-IS (e.g. AMZN=5961 Retail,
GOOGL/META=7372 Tech-Software, AAPL=3571 Tech-Hardware) — that clusters them sensibly
for momentum and is auditable.

Writes reports/_xsec_sector_map.json with {ticker: {sic, sicDescription, sector}} plus
per-sector counts. Idempotent / cache-first.
"""
import os, json, time, urllib.request, sys

WS = os.path.dirname(os.path.abspath(__file__))
UNIV_PATH = os.path.join(WS, "data_cache", "edgar_fundamentals", "universe.json")
SUBM_DIR = os.path.join(WS, "data_cache", "edgar_submissions")
OUT_MAP = os.path.join(WS, "reports", "_xsec_sector_map.json")
UA = "trading-bench research contact@example.com"

os.makedirs(SUBM_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUT_MAP), exist_ok=True)


def fetch_submission(ticker, cik):
    """Return parsed submission JSON, cache-first. cik is zero-padded 10-digit string."""
    cache = os.path.join(SUBM_DIR, "%s.json" % ticker)
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            pass  # corrupt cache -> refetch
    url = "https://data.sec.gov/submissions/CIK%s.json" % cik
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                # handle gzip
                if resp.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
                json.dump(data, open(cache, "w"))
                return data
        except Exception as e:
            wait = 1.0 * (attempt + 1)
            sys.stderr.write("  retry %s %s (%s) wait %.1fs\n" % (ticker, url, e, wait))
            time.sleep(wait)
    raise RuntimeError("failed to fetch %s after retries" % ticker)


def sic_to_sector(sic):
    """Map a 4-digit SIC code (int) to a coarse GICS-ish sector bucket.

    Standard SIC major-group ranges, with the well-known sub-splits inside Manufacturing
    (2800s chemicals/pharma, 3570/3670/7370 tech, 3710s auto) and Transport/Utilities
    (4900s utilities) so momentum clusters land where a human would put them.
    """
    if sic is None:
        return "Unknown"
    s = int(sic)

    # --- Finance / Insurance / Real Estate (6000-6799) ---
    if 6000 <= s <= 6199:
        return "Financials"            # depository / non-depository credit
    if 6200 <= s <= 6299:
        return "Financials"            # security & commodity brokers / exchanges
    if 6300 <= s <= 6499:
        return "Financials"            # insurance
    if 6500 <= s <= 6799:
        return "RealEstate"            # real estate / REITs / holding (6798=REIT)

    # --- Tech / Software / Semiconductors (scattered across mfg + services) ---
    if 3570 <= s <= 3579:
        return "TechHardware"          # computer & office equipment (AAPL 3571)
    if 3670 <= s <= 3679:
        return "Semiconductors"        # electronic components / semis
    if s in (3661, 3663, 3669):
        return "TechHardware"          # telephone/telegraph & comms equipment
    if 3674 == s:
        return "Semiconductors"        # semiconductors specifically
    if 7370 <= s <= 7379:
        return "TechSoftware"          # computer programming/data/software services
    if s == 7372:
        return "TechSoftware"          # prepackaged software

    # --- Communications / Media / Telecom ---
    if 4800 <= s <= 4899:
        return "CommServices"          # communications (telephone 4813, wireless 4812)
    if 2700 <= s <= 2799:
        return "CommServices"          # publishing
    if 7800 <= s <= 7849:
        return "CommServices"          # motion pictures / entertainment

    # --- Healthcare / Pharma ---
    if 2830 <= s <= 2836:
        return "Pharma"                # biological/medicinal/pharmaceutical preps
    if s == 2834 or s == 2835 or s == 2836:
        return "Pharma"
    if 3840 <= s <= 3851:
        return "MedDevices"            # surgical/medical instruments & supplies
    if 8000 <= s <= 8099:
        return "Healthcare"            # health services

    # --- Energy ---
    if 1300 <= s <= 1399:
        return "Energy"                # oil & gas extraction
    if 2900 <= s <= 2999:
        return "Energy"                # petroleum refining
    if s == 1311 or s == 1389:
        return "Energy"

    # --- Materials / Chemicals ---
    if 2800 <= s <= 2829:
        return "Chemicals"             # industrial chemicals (ex-pharma)
    if 2840 <= s <= 2899:
        return "Chemicals"             # other chemicals
    if 1000 <= s <= 1099:
        return "Materials"             # metal mining
    if 1400 <= s <= 1499:
        return "Materials"             # mining/quarrying nonmetallic
    if 3300 <= s <= 3399:
        return "Materials"             # primary metal industries
    if 2600 <= s <= 2699:
        return "Materials"             # paper

    # --- Industrials (manufacturing of machinery, aero, electrical, transport eq) ---
    if 3710 <= s <= 3719:
        return "AutoTransport"         # motor vehicles
    if 3720 <= s <= 3799:
        return "Industrials"           # aircraft/aerospace/ship/rail/transport eq
    if 3500 <= s <= 3569:
        return "Industrials"           # industrial machinery & equipment
    if 3580 <= s <= 3599:
        return "Industrials"
    if 3600 <= s <= 3669:
        return "Industrials"           # electrical equipment (ex-semis/comms above)
    if 3680 <= s <= 3699:
        return "Industrials"
    if 3400 <= s <= 3499:
        return "Industrials"           # fabricated metal products
    if 3900 <= s <= 3999:
        return "Industrials"           # misc manufacturing
    if 3800 <= s <= 3839:
        return "Industrials"           # instruments (ex-medical 3840+)
    if 3852 <= s <= 3873:
        return "Industrials"

    # --- Transportation services / logistics (4000-4799) ---
    if 4000 <= s <= 4799:
        return "Industrials"           # railroads/trucking/air transport (UNP/NSC rail)

    # --- Utilities (4900-4949 strictly; 4950-4999 sanitary/waste) ---
    if 4900 <= s <= 4949:
        return "Utilities"
    if 4950 <= s <= 4999:
        return "Industrials"           # sanitary/refuse (WM 4953) -> industrials-ish

    # --- Consumer Staples (food/beverage/tobacco mfg + staples retail) ---
    if 2000 <= s <= 2199:
        return "ConsumerStaples"       # food & kindred (2080 beverage, 2111 tobacco)
    if 2100 <= s <= 2199:
        return "ConsumerStaples"
    if s in (5411,):
        return "ConsumerStaples"       # grocery stores
    if 2200 <= s <= 2399:
        return "ConsumerDiscretionary" # textiles/apparel mfg (NKE 3021? actually rubber)
    if s == 3021:
        return "ConsumerDiscretionary" # rubber/plastics footwear (NKE)
    if 3000 <= s <= 3299:
        return "ConsumerDiscretionary" # rubber/leather/stone/clay/glass (ex primary metal)

    # --- Retail / Consumer Discretionary (5200-5999) ---
    if 5200 <= s <= 5999:
        return "ConsumerDiscretionary" # retail (HD 5211, MCD 5812, AMZN 5961, COST 5331)
    if 5000 <= s <= 5199:
        return "ConsumerDiscretionary" # wholesale durable/nondurable

    # --- Services (7000-8999, residual after tech/health/media above) ---
    if 7000 <= s <= 7299:
        return "ConsumerDiscretionary" # hotels/personal/business services
    if 7300 <= s <= 7369:
        return "Industrials"           # business services (ex 7370s tech)
    if 7380 <= s <= 7399:
        return "Industrials"
    if 7400 <= s <= 8999:
        return "Industrials"           # misc services
    if 8700 <= s <= 8799:
        return "Industrials"           # engineering/accounting/research/mgmt

    # --- Agriculture / Construction (rare in this universe) ---
    if 100 <= s <= 999:
        return "Materials"             # agriculture
    if 1500 <= s <= 1799:
        return "Industrials"           # construction

    return "Other_%d" % s


def main():
    u = json.load(open(UNIV_PATH))
    tickers = u["tickers"]
    cikmap = u["ticker_cik"]

    out = {}
    n_fetched = 0
    n_cached = 0
    for t in tickers:
        cik = cikmap.get(t)
        if not cik:
            sys.stderr.write("NO CIK for %s\n" % t)
            out[t] = {"sic": None, "sicDescription": None, "sector": "Unknown"}
            continue
        cache = os.path.join(SUBM_DIR, "%s.json" % t)
        was_cached = os.path.exists(cache)
        data = fetch_submission(t, cik)
        if was_cached:
            n_cached += 1
        else:
            n_fetched += 1
            time.sleep(0.15)  # politeness; only when we actually hit the network
        sic = data.get("sic") or None
        sicdesc = data.get("sicDescription") or None
        sector = sic_to_sector(sic)
        out[t] = {"sic": sic, "sicDescription": sicdesc, "sector": sector}

    # per-sector counts
    counts = {}
    for t, info in out.items():
        counts[info["sector"]] = counts.get(info["sector"], 0) + 1

    result = {
        "as_of": u.get("as_of"),
        "universe_n": len(tickers),
        "source": "SEC submissions API sic/sicDescription -> coarse SIC-division sector",
        "ua": UA,
        "ticker_sector": out,
        "sector_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "n_fetched_now": n_fetched, "n_from_cache": n_cached,
    }
    json.dump(result, open(OUT_MAP, "w"), indent=2)

    print("fetched=%d cached=%d total=%d" % (n_fetched, n_cached, len(tickers)))
    print("\n=== SECTOR COUNTS ===")
    for sec, c in result["sector_counts"].items():
        members = sorted([t for t, info in out.items() if info["sector"] == sec])
        print("  %-22s %2d  %s" % (sec, c, " ".join(members)))
    print("\nwrote", OUT_MAP)

    # flag any singletons (will be dropped from L/S)
    singles = [s for s, c in counts.items() if c == 1]
    if singles:
        print("\nSINGLETON sectors (1 name, no within-sector L/S possible):", singles)
    return result


if __name__ == "__main__":
    main()
