#!/usr/bin/env python3
"""Batch 3: large curated Workday candidate push + refined site guesses."""
from __future__ import annotations
import json, time
import requests
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
S = requests.Session()
S.headers.update({"Content-Type": "application/json", "User-Agent": UA,
                  "Accept": "application/json", "X-Calypso-PageBlocked": "false"})

CANDIDATES = [
    # Refined guesses for valuable 422-tenants
    ("Verizon", "verizon.wd1.myworkdayjobs.com", "verizon", "vcareers"),
    ("Verizon2", "verizon.wd1.myworkdayjobs.com", "verizon", "VerizonCareers"),
    ("Honeywell", "honeywell.wd1.myworkdayjobs.com", "honeywell", "Honeywell_External_Site"),
    ("NetApp", "netapp.wd5.myworkdayjobs.com", "netapp", "NetApp_Careers"),
    ("Synopsys", "synopsys.wd1.myworkdayjobs.com", "synopsys", "Synopsys"),
    ("Caterpillar", "caterpillar.wd5.myworkdayjobs.com", "caterpillar", "Caterpillar_External"),
    ("Fidelity", "fidelity.wd1.myworkdayjobs.com", "fidelity", "Fidelity"),
    ("Amex", "aexp.wd1.myworkdayjobs.com", "aexp", "Amex"),
    ("Fortinet", "fortinet.wd1.myworkdayjobs.com", "fortinet", "External"),
    ("Akamai", "akamai.wd1.myworkdayjobs.com", "akamai", "Akamai"),
    ("Coupa", "coupa.wd1.myworkdayjobs.com", "coupa", "coupa"),
    ("Guidewire", "guidewire.wd1.myworkdayjobs.com", "guidewire", "guidewire"),
    ("PTC", "ptc.wd5.myworkdayjobs.com", "ptc", "Careers"),
    ("Ansys", "ansys.wd1.myworkdayjobs.com", "ansys", "ansys"),
    ("Moderna", "moderna.wd1.myworkdayjobs.com", "moderna", "Careers"),
    ("Regeneron", "regeneron.wd5.myworkdayjobs.com", "regeneron", "Careers"),
    ("Boston Scientific", "bostonscientific.wd5.myworkdayjobs.com", "bostonscientific", "BSC_Careers"),
    ("Becton Dickinson", "bd.wd1.myworkdayjobs.com", "bd", "EXTERNAL_CAREER_SITE_USA"),
    ("Verisk", "verisk.wd5.myworkdayjobs.com", "verisk", "Verisk"),
    ("S&P Global", "spglobal.wd5.myworkdayjobs.com", "spglobal", "spgmarketing"),
    ("Moody's", "moodys.wd5.myworkdayjobs.com", "moodys", "MoodysCareers"),
    ("ADP", "adp.wd5.myworkdayjobs.com", "adp", "ADP"),
    ("CBRE", "cbre.wd1.myworkdayjobs.com", "cbre", "CBRECareers"),
    ("SolarWinds", "solarwinds.wd1.myworkdayjobs.com", "solarwinds", "SolarWinds"),
    ("Alteryx", "alteryx.wd5.myworkdayjobs.com", "alteryx", "alteryx"),
    ("Qlik", "qlik.wd3.myworkdayjobs.com", "qlik", "qlik"),
    ("Bentley", "bentley.wd5.myworkdayjobs.com", "bentley", "External"),
    ("Pega", "pega.wd5.myworkdayjobs.com", "pega", "PegaCareers"),
    ("Sage", "sage.wd3.myworkdayjobs.com", "sage", "sageexternal"),
    ("Five9", "five9.wd1.myworkdayjobs.com", "five9", "five9careers"),
    ("RingCentral", "ringcentral.wd1.myworkdayjobs.com", "ringcentral", "RingCentralCareers"),

    # Brand-new candidates
    ("Workday-Bld", "vmware.wd1.myworkdayjobs.com", "vmware", "VMware"),
    ("Logitech-DUP", "logitech.wd1.myworkdayjobs.com", "logitech", "Logitech"),
    ("Western Union", "westernunion.wd5.myworkdayjobs.com", "westernunion", "WesternUnionCareers"),
    ("Fiserv", "fiserv.wd5.myworkdayjobs.com", "fiserv", "EXT"),
    ("FIS", "fis.wd5.myworkdayjobs.com", "fis", "SearchJobs"),
    ("Global Payments", "globalpayments.wd5.myworkdayjobs.com", "globalpayments", "External"),
    ("Broadridge", "broadridge.wd5.myworkdayjobs.com", "broadridge", "careers"),
    ("Jack Henry", "jackhenry.wd1.myworkdayjobs.com", "jackhenry", "ExternalCareer"),
    ("Toast-WD", "toast.wd5.myworkdayjobs.com", "toast", "toastcareers"),
    ("Affirm-WD", "affirm.wd1.myworkdayjobs.com", "affirm", "External"),
    ("Coinbase-WD", "coinbase.wd1.myworkdayjobs.com", "coinbase", "Coinbase"),
    ("Chime-WD", "chime.wd1.myworkdayjobs.com", "chime", "Chime"),
    ("Plaid-WD", "plaid.wd1.myworkdayjobs.com", "plaid", "Plaid"),
    ("Marqeta-WD", "marqeta.wd1.myworkdayjobs.com", "marqeta", "Marqeta"),
    ("Bill-WD", "bill.wd1.myworkdayjobs.com", "bill", "External"),
    ("Toast2", "toast.wd1.myworkdayjobs.com", "toast", "External"),
    ("ServiceTitan", "servicetitan.wd1.myworkdayjobs.com", "servicetitan", "ServiceTitan"),
    ("Procore", "procore.wd1.myworkdayjobs.com", "procore", "Procore"),
    ("Samsara-WD", "samsara.wd1.myworkdayjobs.com", "samsara", "Samsara"),
    ("Zscaler-WD", "zscaler.wd1.myworkdayjobs.com", "zscaler", "Zscaler"),
    ("Tenable-WD", "tenable.wd1.myworkdayjobs.com", "tenable", "Tenable"),
    ("Qualys", "qualys.wd5.myworkdayjobs.com", "qualys", "External"),
    ("SailPoint", "sailpoint.wd5.myworkdayjobs.com", "sailpoint", "SailPoint"),
    ("Varonis", "varonis.wd1.myworkdayjobs.com", "varonis", "Varonis"),
    ("Dynatrace2", "dynatrace.wd3.myworkdayjobs.com", "dynatrace", "Dynatrace"),
    ("New Relic-WD", "newrelic.wd1.myworkdayjobs.com", "newrelic", "newrelic"),
    ("PagerDuty-WD", "pagerduty.wd1.myworkdayjobs.com", "pagerduty", "PagerDuty"),
    ("Asana-WD", "asana.wd1.myworkdayjobs.com", "asana", "External"),
    ("Coupang-WD", "coupang.wd3.myworkdayjobs.com", "coupang", "External"),
    ("DoorDash-WD", "doordash.wd1.myworkdayjobs.com", "doordash", "External"),
    ("Instacart-WD", "instacart.wd1.myworkdayjobs.com", "instacart", "Instacart"),
    ("Lyft-WD", "lyft.wd1.myworkdayjobs.com", "lyft", "Lyft"),
    ("Pinterest-WD", "pinterest.wd1.myworkdayjobs.com", "pinterest", "PinterestCareers"),
    ("Block2", "block.wd1.myworkdayjobs.com", "block", "External"),
    ("Roblox-WD", "roblox.wd5.myworkdayjobs.com", "roblox", "roblox"),
    ("Unity2", "unity.wd1.myworkdayjobs.com", "unity", "unitycareers"),
    ("Workato", "workato.wd1.myworkdayjobs.com", "workato", "Workato"),
    ("UKG", "ukg.wd5.myworkdayjobs.com", "ukg", "UKGCareers"),
    ("Ceridian", "ceridian.wd3.myworkdayjobs.com", "ceridian", "External"),
    ("Paychex", "paychex.wd1.myworkdayjobs.com", "paychex", "External"),
    ("Workiva", "workiva.wd1.myworkdayjobs.com", "workiva", "Workiva"),
    ("BlackLine", "blackline.wd1.myworkdayjobs.com", "blackline", "BlackLine"),
    ("Avalara", "avalara.wd5.myworkdayjobs.com", "avalara", "avalara"),
    ("Sprinklr", "sprinklr.wd1.myworkdayjobs.com", "sprinklr", "Sprinklr"),
    ("Freshworks", "freshworks.wd1.myworkdayjobs.com", "freshworks", "External"),
    ("Zuora-WD", "zuora.wd1.myworkdayjobs.com", "zuora", "Zuora"),
    ("Gainsight", "gainsight.wd1.myworkdayjobs.com", "gainsight", "Gainsight"),
    ("Smartsheet-WD", "smartsheet.wd5.myworkdayjobs.com", "smartsheet", "Smartsheet"),
    ("Qualtrics-WD", "qualtrics.wd1.myworkdayjobs.com", "qualtrics", "Qualtrics"),
    ("UiPath-WD", "uipath.wd1.myworkdayjobs.com", "uipath", "External"),
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
    conf = []
    for name, host, tenant, site in CANDIDATES:
        code, info = probe(host, tenant, site)
        if code == 200 and (info or 0) > 0:
            conf.append((name, host, tenant, site, info))
            print(f"✓ {name}: {host}/{tenant}/{site} total={info}", flush=True)
            with open("/tmp/batch3_found.txt", "a") as fh:
                fh.write(f"{name}|{host}|{tenant}|{site}|{info}\n")
        elif code == 422:
            print(f"~ {name}: 422 {host}/{tenant}", flush=True)
        else:
            print(f"✗ {name}: {code}", flush=True)
        time.sleep(0.08)
    print(f"\n=== CONFIRMED {len(conf)} ===", flush=True)


if __name__ == "__main__":
    main()
