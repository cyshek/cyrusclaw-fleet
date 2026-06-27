import json, requests, time
S = requests.Session()
S.headers.update({"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "Accept": "application/json", "X-Calypso-PageBlocked": "false"})
def probe(host, tenant, site, timeout=8):
    try:
        r = S.post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
            data=json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}), timeout=timeout)
        return r.status_code, r.json().get("total", 0) if r.status_code==200 else None
    except:
        return None, None
DCS = ["wd2", "wd3", "wd5", "wd6", "wd10", "wd12", "wd103", "wd501"]
SITES = ["External", "Careers", "VZCareers", "VerizonCareers", "mycareer", "External_Career_Site"]
for dc in DCS:
    host = f"verizon.{dc}.myworkdayjobs.com"
    for site in SITES:
        code, total = probe(host, "verizon", site)
        if code == 200:
            print(f"HIT! verizon.{dc}/{site} total={total}")
            break
        elif code == 422:
            print(f"422 (tenant exists): verizon.{dc} - trying more sites...")
            break
        time.sleep(0.05)
