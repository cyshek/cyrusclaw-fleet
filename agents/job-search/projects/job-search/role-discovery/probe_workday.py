#!/usr/bin/env python3
"""Probe Workday CXS jobs API to verify (host, tenant, site) and job count.

Usage:
  python probe_workday.py <host> <tenant> [site1 site2 ...]
  python probe_workday.py --batch         # run built-in candidate list

For each candidate, tries the CXS jobs endpoint with a few likely site names
and prints which combo returns jobs (total count). The exact `site` segment is
the hard part — this brute-forces common patterns.
"""
from __future__ import annotations
import sys, json, time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Common Workday external-site path segments seen across tenants.
COMMON_SITES = [
    "External", "external",
    "External_Career_Site", "ExternalCareerSite",
    "Careers", "careers", "Careers_External",
    "Global_Careers", "GlobalCareers",
    "External_Careers", "ExternalCareers",
    "Search", "jobs", "Jobs", "JOBS",
    "External_Site", "ExternalSite",
    "ExternalCareers_Site",
    "Professional", "Corporate", "CorporateCareers",
]


def probe(host: str, tenant: str, site: str, timeout: int = 15):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        r = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "User-Agent": UA,
                "Accept": "application/json",
                "X-Calypso-PageBlocked": "false",
            },
            data=json.dumps(body),
            timeout=timeout,
        )
    except Exception as e:
        return ("ERR", str(e)[:80], None)
    if r.status_code != 200:
        return (r.status_code, None, None)
    try:
        data = r.json()
    except Exception:
        return ("NOJSON", None, None)
    total = data.get("total")
    n = len(data.get("jobPostings", []) or [])
    return (200, total, n)


def probe_tenant(host: str, tenant: str, sites=None):
    sites = sites or COMMON_SITES
    found = []
    for site in sites:
        code, total, n = probe(host, tenant, site)
        if code == 200 and (total or 0) > 0:
            found.append((site, total))
            print(f"  ✓ {host} / {tenant} / {site}  ->  total={total}")
        elif code == 200:
            # 200 but 0 jobs — site valid but empty (still note)
            print(f"  ~ {host} / {tenant} / {site}  ->  200 total={total} (empty)")
        time.sleep(0.15)
    return found


# Workday data-center subdomains seen in the wild.
DATACENTERS = ["wd1", "wd2", "wd3", "wd5", "wd6", "wd10", "wd12", "wd103", "wd501"]


def sweep(tenant: str, sites=None, dcs=None):
    """Brute-force host (data center) x site for a tenant. Returns list of
    (host, site, total) that return jobs."""
    sites = sites or COMMON_SITES
    dcs = dcs or DATACENTERS
    hits = []
    for dc in dcs:
        host = f"{tenant}.{dc}.myworkdayjobs.com"
        # cheap reachability check: one site probe; if DNS/host dead, skip fast
        any_200 = False
        for site in sites:
            code, total, n = probe(host, tenant, site, timeout=10)
            if code == 200:
                any_200 = True
                if (total or 0) > 0:
                    hits.append((host, site, total))
                    print(f"  ✓ {host} / {tenant} / {site}  ->  total={total}")
            time.sleep(0.1)
        if not any_200:
            # host likely doesn't exist for this DC; quiet
            pass
    return hits


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--sweep":
        tenant = args[1]
        sites = args[2:] if len(args) > 2 else None
        print(f"Sweeping tenant={tenant} across data centers...")
        hits = sweep(tenant, sites)
        if hits:
            best = max(hits, key=lambda x: x[2] or 0)
            print(f"BEST: host={best[0]} site={best[1]} total={best[2]}")
        else:
            print("NONE found")
        sys.exit(0)
    host, tenant = args[0], args[1]
    sites = args[2:] if len(args) > 2 else None
    print(f"Probing {host} (tenant={tenant})...")
    found = probe_tenant(host, tenant, sites)
    if found:
        best = max(found, key=lambda x: x[1] or 0)
        print(f"BEST: site={best[0]} total={best[1]}")
    else:
        print("NONE found")
