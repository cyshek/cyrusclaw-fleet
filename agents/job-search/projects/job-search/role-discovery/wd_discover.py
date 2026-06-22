#!/usr/bin/env python3
"""Workday tenant+site discovery via CXS status-code signal.

Key insight (verified):
  - POST /wday/cxs/<tenant>/<site>/jobs
  - 200 = correct tenant+host+site (returns total)
  - 422 = correct tenant+host, WRONG site  -> keep trying sites on this host
  - 404 = wrong host (data center) for this tenant
  - 406 = bot-blocked root (tenant exists)

Strategy per tenant slug:
  1. Find the data-center host where a probe returns 200 or 422 (not 404).
  2. On that host, brute-force a large site wordlist until a 200.

Usage:
  python wd_discover.py <tenant1> <tenant2> ...
"""
from __future__ import annotations
import sys, json, time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

DATACENTERS = ["wd1", "wd3", "wd5", "wd2", "wd6", "wd10", "wd12", "wd103", "wd501", "wd505"]

# Broad site wordlist (case variants + brand placeholder filled per-tenant).
BASE_SITES = [
    "External", "external", "EXTERNAL",
    "External_Career_Site", "ExternalCareerSite", "External_Career_site",
    "Careers", "careers", "CAREERS", "Careers_External", "Career",
    "External_Careers", "ExternalCareers", "External_Careers_Site",
    "Global_Careers", "GlobalCareers", "Global", "GlobalCareerSite",
    "Search", "jobs", "Jobs", "JOBS", "Job",
    "Professional", "Corporate", "CorporateCareers", "Corporate_Careers",
    "External_Site", "ExternalSite", "Sites", "site",
    "Recruiting", "recruiting", "TalentCommunity",
    "USA", "US", "NorthAmerica",
    "External_Experienced", "Experienced", "Professionals",
    "CareerSite", "Career_Site", "careersite",
]

# Per-tenant brand-name site variants (filled with capitalized tenant).
def brand_sites(tenant: str):
    cap = tenant.capitalize()
    up = tenant.upper()
    return [
        cap, up, tenant,
        f"{cap}External", f"{cap}_External", f"{cap}Careers", f"{cap}_Careers",
        f"{cap}ExternalCareerSite", f"{cap}External_Career_Site",
        f"{up}External", f"{up}ExternalCareerSite", f"{up}_External",
        f"{cap}ExternalCareers", f"{cap}CareerSite",
        f"Jobsat{cap}", f"jobsat{cap}", f"{cap}Jobs",
        f"Careers_{cap}", f"External_{cap}",
    ]

S = requests.Session()
S.headers.update({
    "Content-Type": "application/json",
    "User-Agent": UA,
    "Accept": "application/json",
    "X-Calypso-PageBlocked": "false",
})


def probe(host: str, tenant: str, site: str, timeout=12):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        r = S.post(url, data=json.dumps(body), timeout=timeout)
    except Exception:
        return (None, None)
    if r.status_code == 200:
        try:
            return (200, r.json().get("total"))
        except Exception:
            return ("NOJSON", None)
    return (r.status_code, None)


def find_host(tenant: str):
    """Find data-center host returning 200/422 (tenant exists there)."""
    for dc in DATACENTERS:
        host = f"{tenant}.{dc}.myworkdayjobs.com"
        code, total = probe(host, tenant, "External")
        if code == 200:
            return host, ("External", total)
        if code == 422:
            return host, None  # right host, need site search
        time.sleep(0.05)
    return None, None


def discover_tenant(tenant: str):
    host, hit = find_host(tenant)
    if host is None:
        return tenant, None, None
    if hit is not None:
        return tenant, host, hit  # found on first try
    # brute-force sites on the confirmed host
    sites = brand_sites(tenant) + BASE_SITES
    for site in sites:
        code, total = probe(host, tenant, site)
        if code == 200 and (total or 0) > 0:
            return tenant, host, (site, total)
        if code == 200:
            # valid empty site; remember but keep looking for a populated one
            pass
        time.sleep(0.05)
    return tenant, host, None  # host exists, no site matched


def main(tenants):
    results = {}
    for t in tenants:
        ten, host, hit = discover_tenant(t)
        if hit:
            site, total = hit
            results[t] = (host, site, total)
            print(f"[{t}] ✓ host={host} site={site} total={total}")
        elif host:
            print(f"[{t}] host={host} exists (422) but NO site matched wordlist")
        else:
            print(f"[{t}] no Workday tenant (404 all DCs)")
    print("\n=== SUMMARY (verified, populated) ===")
    for t, (h, s, tot) in results.items():
        print(f"{t}: host={h} site={s} total={tot}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1:])
