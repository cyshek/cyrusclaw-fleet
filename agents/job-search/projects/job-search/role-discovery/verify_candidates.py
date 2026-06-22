#!/usr/bin/env python3
"""Verify a curated list of candidate (name, host, tenant, site) Workday triples
against the live CXS /jobs API. Prints which are CONFIRMED (200 + jobs).

Run: python verify_candidates.py
"""
from __future__ import annotations
import json, time
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

# (name, host, tenant, site) — best-guess triples for known Workday tenants.
CANDIDATES = [
    # Big tech / enterprise software
    ("Salesforce-DUP", "salesforce.wd12.myworkdayjobs.com", "salesforce", "External_Career_Site"),
    ("SAP", "sap.wd3.myworkdayjobs.com", "sap", "SAP_SuccessFactors"),
    ("Splunk", "splunk.wd5.myworkdayjobs.com", "splunk", "splunk_careers"),
    ("Sony Electronics", "sony.wd1.myworkdayjobs.com", "sony", "SonyGlobalCareers"),
    ("Nutanix", "nutanix.wd1.myworkdayjobs.com", "nutanix", "Nutanix_Careers"),
    ("Autodesk", "autodesk.wd1.myworkdayjobs.com", "autodesk", "Ext"),
    ("Workday-DUP", "workday.wd5.myworkdayjobs.com", "workday", "Workday"),
    ("Pure Storage", "purestorage.wd1.myworkdayjobs.com", "purestorage", "PSExternal"),
    ("Unity", "unity.wd1.myworkdayjobs.com", "unity", "Careers"),
    ("Roku-WD", "roku.wd1.myworkdayjobs.com", "roku", "Roku"),
    ("Equinix", "equinix.wd1.myworkdayjobs.com", "equinix", "EQ"),
    ("NetApp", "netapp.wd5.myworkdayjobs.com", "netapp", "NetAppExternalCareerSite"),
    ("Juniper Networks", "juniper.wd5.myworkdayjobs.com", "juniper", "JuniperNetworks"),
    ("Western Digital", "wdc.wd5.myworkdayjobs.com", "wdc", "Search_Professional"),
    ("Micron", "micron.wd1.myworkdayjobs.com", "micron", "External"),
    ("Texas Instruments", "ti.wd5.myworkdayjobs.com", "ti", "External"),
    ("Analog Devices", "analogdevices.wd1.myworkdayjobs.com", "analogdevices", "External"),
    ("KLA", "kla.wd1.myworkdayjobs.com", "kla", "Search"),
    ("Lam Research", "lamresearch.wd1.myworkdayjobs.com", "lamresearch", "External"),
    ("Applied Materials", "amat.wd1.myworkdayjobs.com", "amat", "External"),
    ("Marvell", "marvell.wd1.myworkdayjobs.com", "marvell", "MarvellCareers"),
    ("Cadence", "cadence.wd1.myworkdayjobs.com", "cadence", "External_Careers"),
    ("Synopsys", "synopsys.wd1.myworkdayjobs.com", "synopsys", "Careers"),
    # Aerospace / defense / industrial
    ("Northrop Grumman", "ngc.wd1.myworkdayjobs.com", "ngc", "External"),
    ("L3Harris", "l3harris.wd1.myworkdayjobs.com", "l3harris", "L3Harris_External"),
    ("GE Aerospace", "geaerospace.wd1.myworkdayjobs.com", "geaerospace", "External"),
    ("GE Vernova", "gevernova.wd5.myworkdayjobs.com", "gevernova", "External"),
    ("Honeywell", "honeywell.wd1.myworkdayjobs.com", "honeywell", "Honeywell_External_Career_Site"),
    ("Emerson", "emerson.wd1.myworkdayjobs.com", "emerson", "Emerson_Careers"),
    ("Caterpillar", "caterpillar.wd5.myworkdayjobs.com", "caterpillar", "External"),
    ("John Deere", "johndeere.wd1.myworkdayjobs.com", "johndeere", "External"),
    ("3M", "3m.wd1.myworkdayjobs.com", "3m", "Search"),
    ("Collins Aerospace", "rtx.wd1.myworkdayjobs.com", "rtx", "External_RTX"),
    ("Eaton", "eaton.wd1.myworkdayjobs.com", "eaton", "External"),
    # Finance / fintech
    ("Stripe-WD", "stripe.wd1.myworkdayjobs.com", "stripe", "Stripe"),
    ("Fidelity", "fidelity.wd1.myworkdayjobs.com", "fidelity", "FidelityCareers"),
    ("Charles Schwab", "schwab.wd5.myworkdayjobs.com", "schwab", "External"),
    ("American Express", "aexp.wd1.myworkdayjobs.com", "aexp", "External"),
    ("Wells Fargo", "wf.wd1.myworkdayjobs.com", "wf", "WellsFargoJobs"),
    ("Citi", "citi.wd5.myworkdayjobs.com", "citi", "2"),
    ("Morgan Stanley", "ms.wd5.myworkdayjobs.com", "ms", "External"),
    ("BlackRock", "blackrock.wd1.myworkdayjobs.com", "blackrock", "BlackRock_Professional"),
    ("Block-WD", "block.wd1.myworkdayjobs.com", "block", "Block"),
    ("Nasdaq", "nasdaq.wd1.myworkdayjobs.com", "nasdaq", "Global_External_Site"),
    ("Robinhood-WD", "robinhood.wd1.myworkdayjobs.com", "robinhood", "Robinhood"),
    # Consumer / retail / media
    ("Nike", "nike.wd1.myworkdayjobs.com", "nike", "nike"),
    ("Target", "target.wd5.myworkdayjobs.com", "target", "targetcareers"),
    ("Walmart", "walmart.wd5.myworkdayjobs.com", "walmart", "WalmartExternal"),
    ("Best Buy", "bestbuy.wd5.myworkdayjobs.com", "bestbuy", "External"),
    ("Comcast", "comcast.wd5.myworkdayjobs.com", "comcast", "Comcast_Careers"),
    ("Warner Bros Discovery", "warnerbros.wd5.myworkdayjobs.com", "warnerbros", "global"),
    ("Paramount", "paramount.wd5.myworkdayjobs.com", "paramount", "Careers"),
    ("Electronic Arts-WD", "ea.wd1.myworkdayjobs.com", "ea", "ea"),
    ("Activision", "activision.wd1.myworkdayjobs.com", "activision", "External"),
    ("Thomson Reuters", "thomsonreuters.wd3.myworkdayjobs.com", "thomsonreuters", "External"),
    # Health / pharma / bio
    ("Thermo Fisher", "thermofisher.wd5.myworkdayjobs.com", "thermofisher", "External"),
    ("Pfizer", "pfizer.wd1.myworkdayjobs.com", "pfizer", "PfizerCareers"),
    ("Gilead", "gilead.wd1.myworkdayjobs.com", "gilead", "gileadcareers"),
    ("CVS Health", "cvshealth.wd1.myworkdayjobs.com", "cvshealth", "External"),
    # Telecom / cloud / other tech
    ("T-Mobile", "tmobile.wd1.myworkdayjobs.com", "tmobile", "External"),
    ("Verizon", "verizon.wd1.myworkdayjobs.com", "verizon", "External"),
    ("AT&T", "att.wd1.myworkdayjobs.com", "att", "External"),
    ("Cloudflare-WD", "cloudflare.wd1.myworkdayjobs.com", "cloudflare", "cloudflarecareers"),
    ("Twilio-WD", "twilio.wd5.myworkdayjobs.com", "twilio", "twilio"),
    ("DocuSign", "docusign.wd1.myworkdayjobs.com", "docusign", "Docusign"),
    ("Dropbox-WD", "dropbox.wd5.myworkdayjobs.com", "dropbox", "dropbox"),
    ("Zendesk", "zendesk.wd1.myworkdayjobs.com", "zendesk", "zendesk"),
    ("Okta-WD", "okta.wd5.myworkdayjobs.com", "okta", "OktaCareers"),
    ("MongoDB-WD", "mongodb.wd1.myworkdayjobs.com", "mongodb", "MongoDB"),
    ("Elastic-WD", "elastic.wd1.myworkdayjobs.com", "elastic", "elastic"),
    ("GitLab-WD", "gitlab.wd5.myworkdayjobs.com", "gitlab", "GitLab"),
    ("Cohesity", "cohesity.wd1.myworkdayjobs.com", "cohesity", "Cohesity"),
    ("Rapid7", "rapid7.wd5.myworkdayjobs.com", "rapid7", "Rapid7"),
    ("Cloudera", "cloudera.wd5.myworkdayjobs.com", "cloudera", "External_Career_Site"),
    ("Teradata", "teradata.wd5.myworkdayjobs.com", "teradata", "External"),
    ("Informatica", "informatica.wd5.myworkdayjobs.com", "informatica", "Informatica"),
    ("Dynatrace", "dynatrace.wd3.myworkdayjobs.com", "dynatrace", "Careers"),
    ("F5", "f5.wd1.myworkdayjobs.com", "f5", "f5jobs"),
    ("Fortinet", "fortinet.wd1.myworkdayjobs.com", "fortinet", "Careers"),
    ("Palo Alto Networks", "paloaltonetworks.wd5.myworkdayjobs.com", "paloaltonetworks", "PaloAltoNetworks"),
    ("CrowdStrike", "crowdstrike.wd5.myworkdayjobs.com", "crowdstrike", "crowdstrikecareers"),
    ("Datadog-WD", "datadog.wd1.myworkdayjobs.com", "datadog", "Datadog"),
]


def probe(host, tenant, site, timeout=12):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        r = S.post(url, data=json.dumps(body), timeout=timeout)
    except Exception as e:
        return ("ERR", str(e)[:50])
    if r.status_code == 200:
        try:
            return (200, r.json().get("total"))
        except Exception:
            return ("NOJSON", None)
    return (r.status_code, None)


def main():
    confirmed, wrong_site, wrong_host, other = [], [], [], []
    for name, host, tenant, site in CANDIDATES:
        code, info = probe(host, tenant, site)
        if code == 200 and (info or 0) > 0:
            confirmed.append((name, host, tenant, site, info))
            print(f"✓ {name}: {host}/{tenant}/{site} total={info}")
        elif code == 422:
            wrong_site.append((name, host, tenant))
            print(f"~ {name}: {host} tenant OK, WRONG site '{site}' (422)")
        elif code == 404:
            wrong_host.append((name, host, tenant, site))
            print(f"✗ {name}: 404 wrong host/site {host}/{tenant}/{site}")
        else:
            other.append((name, host, tenant, site, code, info))
            print(f"? {name}: {host}/{tenant}/{site} -> {code} {info}")
        time.sleep(0.1)
    print(f"\n=== CONFIRMED: {len(confirmed)} | wrong-site(422): {len(wrong_site)} | "
          f"wrong-host(404): {len(wrong_host)} | other: {len(other)} ===")
    print("\nCONFIRMED YAML-READY:")
    for name, host, tenant, site, total in confirmed:
        print(f"{name}|{host}|{tenant}|{site}|{total}")
    print("\nWRONG-SITE (tenant exists, need correct site):")
    for name, host, tenant in wrong_site:
        print(f"{name}|{host}|{tenant}")


if __name__ == "__main__":
    main()
