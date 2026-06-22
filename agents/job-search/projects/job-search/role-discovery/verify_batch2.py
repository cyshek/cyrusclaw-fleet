#!/usr/bin/env python3
"""Batch 2: more curated Workday candidates + better site guesses for known
422-tenants. Verifies against live CXS /jobs API.
"""
from __future__ import annotations
import json, time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
S = requests.Session()
S.headers.update({"Content-Type": "application/json", "User-Agent": UA,
                  "Accept": "application/json", "X-Calypso-PageBlocked": "false"})

# (name, host, tenant, site)
CANDIDATES = [
    # Retry 422-tenants with region/brand-specific site guesses
    ("SAP", "sap.wd3.myworkdayjobs.com", "sap", "SAPCareers"),
    ("SAP2", "sap.wd3.myworkdayjobs.com", "sap", "SAP"),
    ("SAP3", "sap.wd3.myworkdayjobs.com", "sap", "SAP_Jobs"),
    ("Splunk", "splunk.wd5.myworkdayjobs.com", "splunk", "splunkcareers"),
    ("Splunk2", "splunk.wd5.myworkdayjobs.com", "splunk", "Splunk_Careers"),
    ("Sony", "sony.wd1.myworkdayjobs.com", "sony", "Sony_External"),
    ("Sony2", "sony.wd1.myworkdayjobs.com", "sony", "SonyExternalCareerSite"),
    ("Sony3", "sony.wd1.myworkdayjobs.com", "sony", "SonyGlobal"),
    ("Nutanix", "nutanix.wd1.myworkdayjobs.com", "nutanix", "Nutanixcareers"),
    ("Nutanix2", "nutanix.wd1.myworkdayjobs.com", "nutanix", "NCR"),
    ("Unity", "unity.wd1.myworkdayjobs.com", "unity", "UnityTechnologies"),
    ("NetApp", "netapp.wd5.myworkdayjobs.com", "netapp", "Careers"),
    ("Juniper", "juniper.wd5.myworkdayjobs.com", "juniper", "Juniper"),
    ("TI", "ti.wd5.myworkdayjobs.com", "ti", "TIatTexasInstruments"),
    ("TI2", "ti.wd5.myworkdayjobs.com", "ti", "TexasInstruments"),
    ("Synopsys", "synopsys.wd1.myworkdayjobs.com", "synopsys", "Careers_External"),
    ("Synopsys2", "synopsys.wd1.myworkdayjobs.com", "synopsys", "SynopsysCareers"),
    ("L3Harris", "l3harris.wd1.myworkdayjobs.com", "l3harris", "Search_external"),
    ("L3Harris2", "l3harris.wd1.myworkdayjobs.com", "l3harris", "L3Harris"),
    ("Honeywell", "honeywell.wd1.myworkdayjobs.com", "honeywell", "Honeywell_External"),
    ("Honeywell2", "honeywell.wd1.myworkdayjobs.com", "honeywell", "Honeywell"),
    ("Emerson", "emerson.wd1.myworkdayjobs.com", "emerson", "Emerson"),
    ("Caterpillar", "caterpillar.wd5.myworkdayjobs.com", "caterpillar", "CaterpillarCareers"),
    ("JohnDeere", "johndeere.wd1.myworkdayjobs.com", "johndeere", "JohnDeere"),
    ("RTX", "rtx.wd1.myworkdayjobs.com", "rtx", "REC_RTX_Ext_Gateway"),
    ("RTX2", "rtx.wd1.myworkdayjobs.com", "rtx", "RTX"),
    ("Eaton", "eaton.wd1.myworkdayjobs.com", "eaton", "EatonExternal"),
    ("Fidelity", "fidelity.wd1.myworkdayjobs.com", "fidelity", "FidelityCareers"),
    ("Amex", "aexp.wd1.myworkdayjobs.com", "aexp", "AmericanExpress"),
    ("BestBuy", "bestbuy.wd5.myworkdayjobs.com", "bestbuy", "BestBuy"),
    ("Paramount", "paramount.wd5.myworkdayjobs.com", "paramount", "ParamountCareers"),
    ("Activision", "activision.wd1.myworkdayjobs.com", "activision", "ActivisionBlizzard"),
    ("ThomsonReuters", "thomsonreuters.wd3.myworkdayjobs.com", "thomsonreuters", "ThomsonReutersCareers"),
    ("Verizon", "verizon.wd1.myworkdayjobs.com", "verizon", "Verizon"),
    ("DocuSign", "docusign.wd1.myworkdayjobs.com", "docusign", "Docusign_External"),
    ("Cohesity", "cohesity.wd1.myworkdayjobs.com", "cohesity", "Cohesity_Careers"),
    ("Rapid7", "rapid7.wd5.myworkdayjobs.com", "rapid7", "Rapid7_Careers"),
    ("Teradata", "teradata.wd5.myworkdayjobs.com", "teradata", "External_Teradata"),
    ("Informatica", "informatica.wd5.myworkdayjobs.com", "informatica", "Informatica_External"),
    ("Dynatrace", "dynatrace.wd3.myworkdayjobs.com", "dynatrace", "Careers_External"),
    ("F5", "f5.wd1.myworkdayjobs.com", "f5", "f5"),
    ("Fortinet", "fortinet.wd1.myworkdayjobs.com", "fortinet", "Fortinet_Careers"),

    # New companies (not yet probed)
    ("Adobe-DUP", "adobe.wd5.myworkdayjobs.com", "adobe", "external_experienced"),
    ("VMware-DUP", "vmware.wd1.myworkdayjobs.com", "vmware", "VMware_Cloud"),
    ("Hitachi", "hitachi.wd1.myworkdayjobs.com", "hitachi", "hitachi"),
    ("Hitachi Vantara", "hitachivantara.wd1.myworkdayjobs.com", "hitachivantara", "Careers"),
    ("Siemens", "siemens.wd3.myworkdayjobs.com", "siemens", "SiemensCareers"),
    ("Schneider Electric", "schneider-electric.wd3.myworkdayjobs.com", "schneider-electric", "External"),
    ("Bose", "bose.wd1.myworkdayjobs.com", "bose", "Bose_Careers"),
    ("GoDaddy-DUP", "godaddy.wd12.myworkdayjobs.com", "godaddy", "Careers"),
    ("PTC", "ptc.wd5.myworkdayjobs.com", "ptc", "PTCExternalCareers"),
    ("Ansys", "ansys.wd1.myworkdayjobs.com", "ansys", "Careers"),
    ("Akamai", "akamai.wd1.myworkdayjobs.com", "akamai", "Akamai_Careers"),
    ("Genesys", "genesys.wd1.myworkdayjobs.com", "genesys", "Genesys"),
    ("Verint", "verint.wd1.myworkdayjobs.com", "verint", "verint"),
    ("Nuance", "nuance.wd1.myworkdayjobs.com", "nuance", "Nuance"),
    ("RingCentral", "ringcentral.wd1.myworkdayjobs.com", "ringcentral", "RingCentral"),
    ("8x8", "8x8.wd5.myworkdayjobs.com", "8x8", "8x8"),
    ("Five9", "five9.wd1.myworkdayjobs.com", "five9", "Five9"),
    ("NICE", "nice.wd3.myworkdayjobs.com", "nice", "nice"),
    ("Sabre", "sabre.wd1.myworkdayjobs.com", "sabre", "Sabre"),
    ("Sage", "sage.wd3.myworkdayjobs.com", "sage", "Sage"),
    ("Pegasystems", "pega.wd5.myworkdayjobs.com", "pega", "Careers"),
    ("Guidewire", "guidewire.wd1.myworkdayjobs.com", "guidewire", "Guidewire"),
    ("Coupa", "coupa.wd1.myworkdayjobs.com", "coupa", "Coupa"),
    ("Bentley Systems", "bentley.wd5.myworkdayjobs.com", "bentley", "Bentley"),
    ("SolarWinds", "solarwinds.wd1.myworkdayjobs.com", "solarwinds", "Careers"),
    ("Qlik", "qlik.wd3.myworkdayjobs.com", "qlik", "External"),
    ("Alteryx", "alteryx.wd5.myworkdayjobs.com", "alteryx", "AlteryxCareers"),
    ("Twilio2", "twilio.wd5.myworkdayjobs.com", "twilio", "TwilioInc"),
    ("Verisk", "verisk.wd5.myworkdayjobs.com", "verisk", "verisk"),
    ("S&P Global", "spglobal.wd5.myworkdayjobs.com", "spglobal", "SPGlobal"),
    ("Moody's", "moodys.wd5.myworkdayjobs.com", "moodys", "Careers"),
    ("Intuit-WD", "intuit.wd1.myworkdayjobs.com", "intuit", "Intuit"),
    ("ADP", "adp.wd5.myworkdayjobs.com", "adp", "ADP_External"),
    ("Cushman Wakefield", "cushwake.wd1.myworkdayjobs.com", "cushwake", "Careers"),
    ("CBRE", "cbre.wd1.myworkdayjobs.com", "cbre", "CBRE"),
    ("Boston Scientific", "bostonscientific.wd5.myworkdayjobs.com", "bostonscientific", "External"),
    ("Medtronic", "medtronic.wd1.myworkdayjobs.com", "medtronic", "External"),
    ("Stryker", "stryker.wd1.myworkdayjobs.com", "stryker", "StrykerCareers"),
    ("Abbott", "abbott.wd5.myworkdayjobs.com", "abbott", "abbottcareers"),
    ("Becton Dickinson", "bd.wd1.myworkdayjobs.com", "bd", "External"),
    ("Illumina", "illumina.wd1.myworkdayjobs.com", "illumina", "illumina-careers"),
    ("Moderna", "moderna.wd1.myworkdayjobs.com", "moderna", "M_Careers"),
    ("Regeneron", "regeneron.wd5.myworkdayjobs.com", "regeneron", "Regeneron-Careers"),
    ("Amgen", "amgen.wd1.myworkdayjobs.com", "amgen", "Careers"),
    ("Biogen", "biogen.wd5.myworkdayjobs.com", "biogen", "External"),
    ("PNC", "pnc.wd5.myworkdayjobs.com", "pnc", "External"),
    ("US Bank", "usbank.wd1.myworkdayjobs.com", "usbank", "USBankCareers"),
    ("Truist", "truist.wd1.myworkdayjobs.com", "truist", "Truist"),
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
    conf, ws = [], []
    for name, host, tenant, site in CANDIDATES:
        code, info = probe(host, tenant, site)
        if code == 200 and (info or 0) > 0:
            conf.append((name, host, tenant, site, info))
            print(f"✓ {name}: {host}/{tenant}/{site} total={info}", flush=True)
            with open("/tmp/batch2_found.txt", "a") as fh:
                fh.write(f"{name}|{host}|{tenant}|{site}|{info}\n")
        elif code == 422:
            ws.append((name, host, tenant))
            print(f"~ {name}: 422 wrong-site on {host}/{tenant}", flush=True)
        else:
            print(f"✗ {name}: {host}/{tenant}/{site} -> {code} {info}", flush=True)
        time.sleep(0.08)
    print(f"\n=== CONFIRMED {len(conf)} | 422 {len(ws)} ===", flush=True)


if __name__ == "__main__":
    main()
