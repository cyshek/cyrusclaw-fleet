"""Try different body shapes for Workday CXS jobs API."""
import requests, json

url = "https://gs.wd1.myworkdayjobs.com/wday/cxs/GS/Experienced_Hire/jobs"
hdrs = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://gs.wd1.myworkdayjobs.com/Experienced_Hire",
}

bodies = [
    # base
    {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
    # with explicit empty searchText
    {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": ""},
    # with no searchText
    {"appliedFacets": {}, "limit": 5, "offset": 0},
    # with locations facet shape
    {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager", "locations": []},
    # different limit
    {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "manager"},
    # with different field name
    {"appliedFacets": {}, "limit": 5, "offset": 0, "search_text": "manager"},
    # totally minimal
    {"limit": 5, "offset": 0},
    # truly empty
    {},
]

for i, body in enumerate(bodies):
    try:
        r = requests.post(url, json=body, headers=hdrs, timeout=10)
        body_preview = r.text[:200] if r.status_code != 200 else f"OK total={r.json().get('total','?')}"
        print(f"[{i}] [{r.status_code}] body={json.dumps(body)}\n     {body_preview}\n")
    except Exception as e:
        print(f"[{i}] ERR {e}\n")

# Also try GET (some Workday tenants accept GET on /jobs)
print("=== GET ===")
try:
    r = requests.get(url, headers=hdrs, timeout=10)
    print(f"GET [{r.status_code}] {r.text[:200]}")
except Exception as e:
    print(f"GET ERR {e}")

# And try the alternate endpoint /jobs/refreshFacet
print("=== alt: /list ===")
try:
    url2 = url.rsplit("/", 1)[0] + "/jobs/list"
    r = requests.post(url2, json={"appliedFacets":{}, "limit":5, "offset":0}, headers=hdrs, timeout=10)
    print(f"[{r.status_code}] {r.text[:200]}")
except Exception as e:
    print(f"ERR {e}")
