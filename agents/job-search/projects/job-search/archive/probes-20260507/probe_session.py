"""Test if Workday tenants require session cookies from careers page first."""
import requests, json

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0",
    "Accept": "*/*",
})

# Step 1: visit careers page to get session cookies
careers = s.get("https://gs.wd1.myworkdayjobs.com/Experienced_Hire", timeout=15)
print(f"Careers page: {careers.status_code}")
print(f"Cookies set: {dict(s.cookies)}")
print(f"Final URL: {careers.url}\n")

# Step 2: try API with session
url = "https://gs.wd1.myworkdayjobs.com/wday/cxs/GS/Experienced_Hire/jobs"
r = s.post(url, json={"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
           headers={"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": "https://gs.wd1.myworkdayjobs.com/Experienced_Hire"},
           timeout=15)
print(f"API call with session: {r.status_code}")
print(f"Body: {r.text[:300]}")

# Try the same for Tesla
print("\n=== Tesla ===")
s2 = requests.Session()
s2.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0",
    "Accept": "*/*",
})
careers = s2.get("https://tesla.wd5.myworkdayjobs.com/TSLA", timeout=15)
print(f"Careers page: {careers.status_code} -> {careers.url}")
print(f"Cookies: {dict(s2.cookies)}")
url = "https://tesla.wd5.myworkdayjobs.com/wday/cxs/tesla/TSLA/jobs"
r = s2.post(url, json={"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Referer": "https://tesla.wd5.myworkdayjobs.com/TSLA"},
            timeout=15)
print(f"API call: {r.status_code} {r.text[:200]}")
