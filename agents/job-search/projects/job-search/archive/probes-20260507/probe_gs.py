"""Try several Goldman Sachs Workday URL variants with Referer header."""
import requests

variants = [
    ("higher.gs.com", "GS", "Experienced_Hire"),
    ("higher.gs.com", "GS", "External"),
    ("higher.gs.com", "GS", "Higher"),
    ("higher.gs.com", "GS", "External_Career_Site"),
    ("gs.wd1.myworkdayjobs.com", "GS", "Experienced_Hire"),
    ("gs.wd5.myworkdayjobs.com", "GS", "Experienced_Hire"),
    ("goldmansachs.wd1.myworkdayjobs.com", "goldmansachs", "External"),
]

for host, tenant, site in variants:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = requests.post(
            url,
            json={"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Referer": f"https://{host}/",
            },
            timeout=10,
        )
        body_preview = r.text[:200] if r.status_code != 200 else f"total={r.json().get('total','?')}"
        print(f"  [{r.status_code}] {url}\n    {body_preview}\n")
    except Exception as e:
        print(f"  [ERR] {url} - {e}\n")
