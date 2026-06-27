#!/usr/bin/env python3
"""Sweep all 422-returning tenants from verify_candidates.py to find correct site segments.
Uses an expanded site wordlist.
"""
from __future__ import annotations
import sys, json, time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

S = requests.Session()
S.headers.update({
    "Content-Type": "application/json",
    "User-Agent": UA,
    "Accept": "application/json",
    "X-Calypso-PageBlocked": "false",
})

# Extended site wordlist
SITES = [
    # Generic
    "External", "external", "External_Career_Site", "ExternalCareerSite",
    "External_Careers", "ExternalCareers", "External_Site", "ExternalSite",
    "Careers", "careers", "Careers_External", "CareersExternal",
    "Global_Careers", "GlobalCareers", "Global_External_Site",
    "Search", "jobs", "Jobs", "JOBS",
    "Professional", "Corporate", "CorporateCareers",
    "Recruiting", "Hire", "hiring",
    # Company-specific variants seen in the wild
    "verizon", "verizonexternal", "VerizonCareers", "Verizon",
    "honeywell", "HoneywellCareers", "Honeywell",
    "netapp", "NetApp", "NetAppCareers", "NetAppExternal",
    "synopsys", "SynopsysCareers", "Synopsys",
    "fidelity", "FidelityCareers", "Fidelity_Careers", "Fidelity",
    "amex", "AmericanExpress", "aexp", "AmericanExpress_External",
    "fortinet", "FortinetCareers", "Fortinet",
    "akamai", "AkamaiCareers", "Akamai",
    "moderna", "ModernaCareers", "Moderna",
    "nutanix", "NutanixCareers", "Nutanix",
    "unity", "UnityTechnologies", "unity_careers", "Unity",
    "roku", "RokuCareers", "Roku",
    "juniper", "JuniperNetworks", "JuniperCareers", "Juniper",
    "ti", "TexasInstruments", "Texas_Instruments",
    "lamresearch", "LamResearch", "LamCareers",
    "l3harris", "L3Harris", "L3Harris_External",
    "geaerospace", "GEAerospace", "GECareers", "GE",
    "emerson", "EmersonCareers", "Emerson",
    "caterpillar", "CaterpillarCareers", "CAT", "Cat",
    "deere", "JohnDeere", "johndeere",
    "rtx", "RTX", "CollinsAerospace", "Collins",
    "eaton", "EatonCareers", "Eaton",
    "bestbuy", "BestBuy", "BestBuyCareers",
    "paramount", "ParamountCareers", "Paramount",
    "ea", "Electronic_Arts", "ElectronicArts", "EA",
    "activision", "ActivisionCareers", "Activision",
    "thomsonreuters", "ThomsonReuters", "Thomson_Reuters",
    "cloudflare", "CloudflareCareers",
    "twilio", "TwilioCareers", "Twilio",
    "docusign", "DocuSignCareers", "DocuSign",
    "dropbox", "DropboxCareers", "Dropbox",
    "okta", "OktaCareers", "Okta",
    "mongodb", "MongoDBCareers", "MongoDB",
    "elastic", "ElasticCareers", "Elastic",
    "gitlab", "GitLabCareers", "GitLab",
    "cohesity", "CohesityCareers", "Cohesity",
    "rapid7", "Rapid7Careers", "Rapid7",
    "teradata", "TeradataCareers", "Teradata",
    "informatica", "InformaticaCareers", "Informatica",
    "dynatrace", "DynatraceCareers", "Dynatrace",
    "f5", "F5Careers", "f5jobs", "F5",
    "sap", "SAPCareers", "SAP_External", "SAP",
    "splunk", "SplunkCareers", "Splunk",
    "sony", "SonyElectronics", "SonyGlobal", "Sony",
    "block", "BlockCareers", "Block",
    "datadog", "DatadogCareers", "Datadog",
    # Block/Square variants
    "Square", "square", "Cash_App",
    # More generic fallbacks
    "1", "2", "US", "US_External", "NA_External",
]


def probe(host, tenant, site, timeout=12):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        r = S.post(url, data=json.dumps(body), timeout=timeout)
    except Exception:
        return ("ERR", None)
    if r.status_code == 200:
        try:
            total = r.json().get("total", 0)
            return (200, total)
        except Exception:
            return ("NOJSON", None)
    return (r.status_code, None)


# All 422 tenants from verify_candidates run
CANDIDATES_422 = [
    ("SAP", "sap.wd3.myworkdayjobs.com", "sap"),
    ("Splunk", "splunk.wd5.myworkdayjobs.com", "splunk"),
    ("Sony Electronics", "sony.wd1.myworkdayjobs.com", "sony"),
    ("Nutanix", "nutanix.wd1.myworkdayjobs.com", "nutanix"),
    ("Unity", "unity.wd1.myworkdayjobs.com", "unity"),
    ("Roku", "roku.wd1.myworkdayjobs.com", "roku"),
    ("NetApp", "netapp.wd5.myworkdayjobs.com", "netapp"),
    ("Juniper Networks", "juniper.wd5.myworkdayjobs.com", "juniper"),
    ("Texas Instruments", "ti.wd5.myworkdayjobs.com", "ti"),
    ("Lam Research", "lamresearch.wd1.myworkdayjobs.com", "lamresearch"),
    ("Synopsys", "synopsys.wd1.myworkdayjobs.com", "synopsys"),
    ("L3Harris", "l3harris.wd1.myworkdayjobs.com", "l3harris"),
    ("GE Aerospace", "geaerospace.wd1.myworkdayjobs.com", "geaerospace"),
    ("Honeywell", "honeywell.wd1.myworkdayjobs.com", "honeywell"),
    ("Emerson", "emerson.wd1.myworkdayjobs.com", "emerson"),
    ("Caterpillar", "caterpillar.wd5.myworkdayjobs.com", "caterpillar"),
    ("John Deere", "johndeere.wd1.myworkdayjobs.com", "johndeere"),
    ("Collins Aerospace", "rtx.wd1.myworkdayjobs.com", "rtx"),
    ("Eaton", "eaton.wd1.myworkdayjobs.com", "eaton"),
    ("Fidelity", "fidelity.wd1.myworkdayjobs.com", "fidelity"),
    ("American Express", "aexp.wd1.myworkdayjobs.com", "aexp"),
    ("Block", "block.wd1.myworkdayjobs.com", "block"),
    ("Best Buy", "bestbuy.wd5.myworkdayjobs.com", "bestbuy"),
    ("Paramount", "paramount.wd5.myworkdayjobs.com", "paramount"),
    ("Electronic Arts", "ea.wd1.myworkdayjobs.com", "ea"),
    ("Activision", "activision.wd1.myworkdayjobs.com", "activision"),
    ("Thomson Reuters", "thomsonreuters.wd3.myworkdayjobs.com", "thomsonreuters"),
    ("Verizon", "verizon.wd1.myworkdayjobs.com", "verizon"),
    ("Cloudflare", "cloudflare.wd1.myworkdayjobs.com", "cloudflare"),
    ("Twilio", "twilio.wd5.myworkdayjobs.com", "twilio"),
    ("DocuSign", "docusign.wd1.myworkdayjobs.com", "docusign"),
    ("Dropbox", "dropbox.wd5.myworkdayjobs.com", "dropbox"),
    ("Okta", "okta.wd5.myworkdayjobs.com", "okta"),
    ("MongoDB", "mongodb.wd1.myworkdayjobs.com", "mongodb"),
    ("Elastic", "elastic.wd1.myworkdayjobs.com", "elastic"),
    ("GitLab", "gitlab.wd5.myworkdayjobs.com", "gitlab"),
    ("Cohesity", "cohesity.wd1.myworkdayjobs.com", "cohesity"),
    ("Rapid7", "rapid7.wd5.myworkdayjobs.com", "rapid7"),
    ("Teradata", "teradata.wd5.myworkdayjobs.com", "teradata"),
    ("Informatica", "informatica.wd5.myworkdayjobs.com", "informatica"),
    ("Dynatrace", "dynatrace.wd3.myworkdayjobs.com", "dynatrace"),
    ("F5", "f5.wd1.myworkdayjobs.com", "f5"),
    ("Fortinet", "fortinet.wd1.myworkdayjobs.com", "fortinet"),
    ("Datadog", "datadog.wd1.myworkdayjobs.com", "datadog"),
]


def main():
    confirmed = []
    failed = []

    for name, host, tenant in CANDIDATES_422:
        print(f"\n=== {name} ({host}) ===")
        found = None
        for site in SITES:
            code, total = probe(host, tenant, site)
            if code == 200 and (total or 0) > 0:
                found = (site, total)
                print(f"  FOUND: site={site} total={total}")
                break
            elif code == 200:
                print(f"  ~ site={site} -> 200 but total=0")
            time.sleep(0.08)

        if found:
            confirmed.append((name, host, tenant, found[0], found[1]))
            print(f"  >> CONFIRMED: {name}|{host}|{tenant}|{found[0]}|{found[1]}")
        else:
            failed.append((name, host, tenant))
            print(f"  >> NOT FOUND for {name}")

    print(f"\n\n=== SWEEP RESULTS: {len(confirmed)} confirmed, {len(failed)} failed ===")
    print("\nCONFIRMED YAML-READY:")
    for name, host, tenant, site, total in confirmed:
        print(f"  {name}|{host}|{tenant}|{site}|{total}")
    print("\nFAILED (site not in wordlist):")
    for name, host, tenant in failed:
        print(f"  {name}|{host}|{tenant}")


if __name__ == "__main__":
    main()
