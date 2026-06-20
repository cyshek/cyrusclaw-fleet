"""Aggressive Workday URL discovery: for each company, try multiple wd subdomains
and site names to find the working combo."""
from __future__ import annotations
import yaml, sys, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import http_post_json

# (host_template, tenant, site) candidates per company
# host_template: "{tenant}.wd{N}.myworkdayjobs.com" - we'll try N=1,3,5,12
# Some tenants differ from the company name

COMPANY_HINTS = {
    # company_name: [(tenant, site_candidates)]
    "Goldman Sachs":    [("GS", ["Experienced_Hire", "External", "Goldman_Sachs"]),
                         ("goldmansachs", ["External", "Experienced_Hire"])],
    "JP Morgan":        [("jpmc", ["jpmc", "External", "JPMC"]),
                         ("jpmorgan", ["External"])],
    "Atlassian":        [("atlassian", ["External", "Careers", "Atlassian"])],
    "Tesla":            [("tesla", ["Tesla", "External", "Careers"])],
    "IBM":              [("IBM", ["IBM_External", "External", "IBM"]),
                         ("ibmglobal", ["IBM_External", "External"])],
    "Snowflake":        [("snowflake", ["External", "Snowflake_Careers", "External_Career_Site"])],
    "Cisco":            [("cisco", ["External", "Cisco", "External_Career_Site"])],
    "ServiceNow":       [("servicenow", ["External", "ServiceNow"])],
    "VMware":           [("vmware", ["External", "VMware", "vmware_careers"])],
    "Box":              [("box", ["External", "Box"])],
    "Capital One":      [("capitalone", ["Capital_One", "External"])],
    "ABB":              [("abb", ["1abb", "ABB", "External"])],
    "Visa":             [("visa", ["VISA", "External", "Visa"])],
    "Discover":         [("discover", ["External", "discover", "Discover"])],
    "McKinsey":         [("mckinsey", ["McKinsey", "External", "Global"])],
    "Lockheed Martin":  [("Lockheed_Martin", ["External", "LMCareers"]),
                         ("lockheedmartin", ["External"])],
    "Dell":             [("dell", ["External", "Dell", "ExternalCareerSite"])],
    "Logitech":         [("logitech", ["External", "Logitech_Careers"])],
    "Rivian":           [("rivian", ["rivian", "External", "Rivian"])],
    "Dolby":            [("dolby", ["External", "Dolby"])],
    "Starbucks":        [("starbucks", ["starbuckscareers", "External"])],
    "EOG Resources":    [("eogresources", ["External", "EOG"])],
    "NOV":              [("nov", ["NOV", "External"])],
    "Phillips 66":      [("phillips66", ["P66", "External"])],
    "BP":               [("bp", ["bp", "External", "BP"])],
    "Oracle":           [("oracle", ["Corporate", "External"])],
    "Adobe":            [("adobe", ["external_experienced", "External"])],
}

WD_SUBDOMAINS = ["wd1", "wd3", "wd5", "wd12"]


def try_url(host, tenant, site):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = http_post_json(
            url,
            {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
            headers={"X-Calypso-PageBlocked": "false"},
            timeout=10,
        )
        if r.status_code == 200:
            try:
                total = r.json().get("total", 0)
                return ("OK", total, url)
            except Exception:
                return ("NON-JSON", 0, url)
        return (f"HTTP{r.status_code}", 0, url)
    except Exception as e:
        return (f"ERR-{type(e).__name__}", 0, url)


def discover(company, hints):
    """Try every (tenant, wd-subdomain, site) combo; return first OK."""
    results = []
    for tenant, sites in hints:
        for sub in WD_SUBDOMAINS:
            host = f"{tenant.lower()}.{sub}.myworkdayjobs.com"
            for site in sites:
                status, total, url = try_url(host, tenant, site)
                if status == "OK" and total > 0:
                    return (company, "FOUND", host, tenant, site, total, url)
                results.append((status, total, url))
    return (company, "NONE", None, None, None, 0, results[:3])


def main():
    print(f"Probing {len(COMPANY_HINTS)} companies x ~{len(WD_SUBDOMAINS)} subdomains x ~3 sites = many combos...")
    print("Limit: ~10 concurrent")
    found = []
    notfound = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(discover, c, h): c for c, h in COMPANY_HINTS.items()}
        for fut in as_completed(futs):
            r = fut.result()
            if r[1] == "FOUND":
                found.append(r)
                print(f"  FOUND  {r[0]:<20} {r[2]:<60} site={r[4]:<30} ({r[5]} jobs)")
            else:
                notfound.append(r)
                print(f"  miss   {r[0]:<20} (no working combo)")

    print("\n" + "="*100)
    print(f"\nFOUND ({len(found)}):")
    for r in found:
        print(f"  - {{ name: {r[0]:<20}, adapter: workday, host: {r[2]}, tenant: {r[3]}, site: {r[4]} }}  # {r[5]} jobs")
    print(f"\nNOT FOUND ({len(notfound)}):")
    for r in notfound:
        print(f"  - {r[0]}")
        for status, total, url in r[6]:
            print(f"      {status} {url}")


if __name__ == "__main__":
    main()
