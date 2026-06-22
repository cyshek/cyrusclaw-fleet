#!/usr/bin/env python3
"""Brute-force the correct Workday `site` segment on a KNOWN host+tenant.

Given (host, tenant) pairs that already return 422 (tenant exists, wrong site),
sweep a large site wordlist (incl. brand variants) until a 200 with jobs.

Edit PAIRS below, then: python brute_sites.py
"""
from __future__ import annotations
import json, time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
S = requests.Session()
S.headers.update({
    "Content-Type": "application/json", "User-Agent": UA,
    "Accept": "application/json", "X-Calypso-PageBlocked": "false",
})

# (name, host, tenant) — confirmed-existing tenants needing the right site.
PAIRS = [
    ("SAP", "sap.wd3.myworkdayjobs.com", "sap"),
    ("Splunk", "splunk.wd5.myworkdayjobs.com", "splunk"),
    ("Sony", "sony.wd1.myworkdayjobs.com", "sony"),
    ("Nutanix", "nutanix.wd1.myworkdayjobs.com", "nutanix"),
    ("Unity", "unity.wd1.myworkdayjobs.com", "unity"),
    ("Roku", "roku.wd1.myworkdayjobs.com", "roku"),
    ("NetApp", "netapp.wd5.myworkdayjobs.com", "netapp"),
    ("Juniper", "juniper.wd5.myworkdayjobs.com", "juniper"),
    ("Texas Instruments", "ti.wd5.myworkdayjobs.com", "ti"),
    ("Lam Research", "lamresearch.wd1.myworkdayjobs.com", "lamresearch"),
    ("Synopsys", "synopsys.wd1.myworkdayjobs.com", "synopsys"),
    ("L3Harris", "l3harris.wd1.myworkdayjobs.com", "l3harris"),
    ("GE Aerospace", "geaerospace.wd1.myworkdayjobs.com", "geaerospace"),
    ("Honeywell", "honeywell.wd1.myworkdayjobs.com", "honeywell"),
    ("Emerson", "emerson.wd1.myworkdayjobs.com", "emerson"),
    ("Caterpillar", "caterpillar.wd5.myworkdayjobs.com", "caterpillar"),
    ("John Deere", "johndeere.wd1.myworkdayjobs.com", "johndeere"),
    ("RTX", "rtx.wd1.myworkdayjobs.com", "rtx"),
    ("Eaton", "eaton.wd1.myworkdayjobs.com", "eaton"),
    ("Fidelity", "fidelity.wd1.myworkdayjobs.com", "fidelity"),
    ("American Express", "aexp.wd1.myworkdayjobs.com", "aexp"),
    ("Best Buy", "bestbuy.wd5.myworkdayjobs.com", "bestbuy"),
    ("Paramount", "paramount.wd5.myworkdayjobs.com", "paramount"),
    ("Activision", "activision.wd1.myworkdayjobs.com", "activision"),
    ("Thomson Reuters", "thomsonreuters.wd3.myworkdayjobs.com", "thomsonreuters"),
    ("Verizon", "verizon.wd1.myworkdayjobs.com", "verizon"),
    ("DocuSign", "docusign.wd1.myworkdayjobs.com", "docusign"),
    ("Cohesity", "cohesity.wd1.myworkdayjobs.com", "cohesity"),
    ("Rapid7", "rapid7.wd5.myworkdayjobs.com", "rapid7"),
    ("Teradata", "teradata.wd5.myworkdayjobs.com", "teradata"),
    ("Informatica", "informatica.wd5.myworkdayjobs.com", "informatica"),
    ("Dynatrace", "dynatrace.wd3.myworkdayjobs.com", "dynatrace"),
    ("F5", "f5.wd1.myworkdayjobs.com", "f5"),
    ("Fortinet", "fortinet.wd1.myworkdayjobs.com", "fortinet"),
]

BASE = [
    "External", "external", "EXTERNAL", "Ext", "ext",
    "External_Career_Site", "ExternalCareerSite", "External_Career_site",
    "Careers", "careers", "CAREERS", "Careers_External", "Career", "career",
    "External_Careers", "ExternalCareers", "External_Careers_Site", "Externalcareers",
    "Global_Careers", "GlobalCareers", "Global", "GlobalCareerSite", "global",
    "Search", "search", "jobs", "Jobs", "JOBS", "Job", "job",
    "Professional", "professional", "Corporate", "CorporateCareers", "Corporate_Careers",
    "External_Site", "ExternalSite", "Sites", "site", "Site",
    "Recruiting", "recruiting", "TalentCommunity", "talent",
    "USA", "US", "NorthAmerica", "Americas",
    "External_Experienced", "Experienced", "Professionals", "Experienced_Professionals",
    "CareerSite", "Career_Site", "careersite", "Careersite",
    "1", "2", "3",
    "Search_Professional", "Professional_Careers", "ProfessionalCareers",
    "External_Global", "Global_External", "Global_External_Site",
]


def brand(tenant):
    cap = tenant.capitalize(); up = tenant.upper(); low = tenant.lower()
    return [
        cap, up, low,
        f"{cap}Careers", f"{cap}_Careers", f"{cap}careers", f"{low}careers", f"{low}_careers",
        f"{cap}External", f"{cap}_External", f"{up}External",
        f"{cap}ExternalCareerSite", f"{cap}External_Career_Site",
        f"{cap}ExternalCareers", f"{cap}CareerSite", f"{cap}_Career_Site",
        f"{cap}Jobs", f"{low}jobs", f"{cap}_Jobs", f"Jobsat{cap}", f"jobsat{cap}",
        f"Careers_{cap}", f"External_{cap}", f"{cap}Global",
        f"{up}_External_Career_Site", f"{cap}GlobalCareers",
    ]


def probe(host, tenant, site, timeout=12):
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


def main():
    found = []
    for name, host, tenant in PAIRS:
        sites = brand(tenant) + BASE
        seen = set()
        hit = None
        for s in sites:
            if s in seen:
                continue
            seen.add(s)
            code, total = probe(host, tenant, s)
            if code == 200 and (total or 0) > 0:
                hit = (s, total)
                break
            time.sleep(0.04)
        if hit:
            found.append((name, host, tenant, hit[0], hit[1]))
            line = f"{name}|{host}|{tenant}|{hit[0]}|{hit[1]}"
            print(f"✓ {name}: {host}/{tenant}/{hit[0]} total={hit[1]}", flush=True)
            with open("/tmp/brute_found.txt", "a") as fh:
                fh.write(line + "\n")
        else:
            print(f"✗ {name}: no site matched ({len(seen)} tried)", flush=True)
    print(f"\n=== FOUND {len(found)}/{len(PAIRS)} ===")
    for name, host, tenant, site, total in found:
        print(f"{name}|{host}|{tenant}|{site}|{total}")


if __name__ == "__main__":
    main()
