#!/usr/bin/env python3
import requests, re, time
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
S = requests.Session()
S.headers["User-Agent"] = UA

def try_root(host, tenant, timeout=10):
    results = []
    for path in ["/", f"/{tenant}/d/jobs", f"/{tenant}"]:
        try:
            r = S.get(f"https://{host}{path}", timeout=timeout, allow_redirects=False)
            loc = r.headers.get("Location", "")
            if loc:
                results.append(f"REDIRECT {r.status_code}: {loc}")
            if r.text:
                sites = re.findall(r"myworkdayjobs\.com/([A-Za-z0-9_]+)", r.text)
                if sites:
                    results.append(f"SITE_IN_BODY: {set(sites)}")
        except Exception as e:
            results.append(f"ERR: {str(e)[:40]}")
    return results

tests = [
    ("f5", "f5.wd1.myworkdayjobs.com"),
    ("netapp", "netapp.wd5.myworkdayjobs.com"),
    ("juniper", "juniper.wd5.myworkdayjobs.com"),
    ("ti", "ti.wd5.myworkdayjobs.com"),
    ("lamresearch", "lamresearch.wd1.myworkdayjobs.com"),
    ("synopsys", "synopsys.wd1.myworkdayjobs.com"),
    ("verizon", "verizon.wd1.myworkdayjobs.com"),
    ("honeywell", "honeywell.wd1.myworkdayjobs.com"),
    ("fidelity", "fidelity.wd1.myworkdayjobs.com"),
    ("aexp", "aexp.wd1.myworkdayjobs.com"),
    ("thomsonreuters", "thomsonreuters.wd3.myworkdayjobs.com"),
    ("fortinet", "fortinet.wd1.myworkdayjobs.com"),
    ("datadog", "datadog.wd1.myworkdayjobs.com"),
    ("caterpillar", "caterpillar.wd5.myworkdayjobs.com"),
    ("johndeere", "johndeere.wd1.myworkdayjobs.com"),
    ("rtx", "rtx.wd1.myworkdayjobs.com"),
    ("eaton", "eaton.wd1.myworkdayjobs.com"),
    ("emerson", "emerson.wd1.myworkdayjobs.com"),
    ("geaerospace", "geaerospace.wd1.myworkdayjobs.com"),
    ("l3harris", "l3harris.wd1.myworkdayjobs.com"),
]

for tenant, host in tests:
    results = try_root(host, tenant)
    print(f"{tenant}: {results}")
    time.sleep(0.2)
