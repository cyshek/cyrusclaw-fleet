"""Try Microsoft Eightfold with CSRF token from session."""
import requests
import re

hdrs = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html"}
s = requests.Session()
s.headers.update(hdrs)

# Get careers page for CSRF
r = s.get("https://apply.careers.microsoft.com/careers", timeout=20)
print("careers page:", r.status_code)

# Extract CSRF from meta tag
m = re.search(r'name="_csrf"\s+content="([^"]+)"', r.text)
csrf = m.group(1) if m else None
print("csrf:", csrf[:50] if csrf else "NOT FOUND")
print("cookies:", list(s.cookies.keys()))

if csrf:
    api = "https://apply.careers.microsoft.com/api/apply/v2/jobs"
    params = {
        "domain": "microsoft.com",
        "num": 10,
        "start": 0,
        "query": "product manager",
        "Country": "United States",
        "triggerGoButton": "true",
    }
    extra = {"csrf-token": csrf, "X-CSRF-Token": csrf, "Accept": "application/json"}
    r2 = s.get(api, params=params, headers=extra, timeout=20)
    print(f"api: {r2.status_code}")
    print(r2.text[:500])
    if r2.status_code == 200 and r2.headers.get("content-type", "").startswith("application/json"):
        j = r2.json()
        print("keys:", list(j.keys())[:10])
        if "positions" in j:
            print("count:", len(j["positions"]))
            if j["positions"]:
                p = j["positions"][0]
                print("sample title:", p.get("name"))
                print("sample location:", p.get("location") or p.get("locations"))
                print("sample id:", p.get("id"))
                print("sample keys:", list(p.keys())[:20])
