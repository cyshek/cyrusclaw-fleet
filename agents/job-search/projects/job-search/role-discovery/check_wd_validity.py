import json, requests, time, yaml
S = requests.Session()
S.headers.update({"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "Accept": "application/json", "X-Calypso-PageBlocked": "false"})

def probe(host, tenant, site, timeout=8):
    try:
        r = S.post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
            data=json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}), timeout=timeout)
        if r.status_code == 200:
            return 200, r.json().get("total", 0)
        return r.status_code, None
    except:
        return None, None

with open("companies.yaml") as f:
    data = yaml.safe_load(f)

companies = data.get("companies", [])
wd_companies = [c for c in companies if c.get("adapter") == "workday" and not c.get("skip")]
print(f"Checking {len(wd_companies)} active Workday entries...")
broken = []
for c in wd_companies:
    name = c.get("name")
    host = c.get("host")
    tenant = c.get("tenant")
    site = c.get("site")
    if not all([host, tenant, site]):
        print(f"INCOMPLETE: {name}")
        continue
    code, total = probe(host, tenant, site)
    if code == 200 and (total or 0) > 0:
        pass  # OK
    elif code == 200:
        print(f"EMPTY {name}: 200 but 0 jobs")
    elif code == 422:
        print(f"BROKEN-422 {name}: site={site}")
        broken.append(name)
    elif code == 404:
        print(f"BROKEN-404 {name}: host={host}")
        broken.append(name)
    else:
        print(f"{code} {name}")
    time.sleep(0.1)
print(f"Done. Broken: {broken}")
