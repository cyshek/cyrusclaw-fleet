#!/usr/bin/env python3
"""Investigate RemoteOK apply flow."""
from playwright.sync_api import sync_playwright
import time

CDP = "http://127.0.0.1:18800"
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

for p in list(ctx.pages):
    try:
        if "remoteok" in p.url:
            p.close()
    except:
        pass

page = ctx.new_page()
page.goto("https://remoteok.com/remote-jobs/1133393", wait_until="domcontentloaded", timeout=20000)
time.sleep(2)

new_pages = []
ctx.on("page", lambda p: new_pages.append(p))

all_req_urls = []
page.on("request", lambda r: all_req_urls.append(r.url[:120]))

# Try clicking Apply
apply_btn = page.locator('a[href*="/l/1133393"]').first
print(f"Apply button found: {apply_btn.count() > 0}")

if apply_btn.count():
    try:
        with page.expect_popup(timeout=5000) as popup_info:
            apply_btn.click(timeout=5000)
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(3)
        print(f"Popup URL: {popup.url}")
        popup.close()
    except Exception as exc:
        print(f"Popup failed: {exc}")
        print(f"New pages: {[p.url[:80] for p in new_pages]}")
        print(f"Main page after click: {page.url}")

time.sleep(1)

# Also check the job JSON for apply_url
job_data = page.evaluate("""() => {
    // Find apply_url in any script or data attribute
    const rows = [...document.querySelectorAll('tr.job')];
    for (const row of rows) {
        const d = row.dataset;
        if (d) {
            const keys = Object.keys(d);
            const result = {};
            for (const k of keys) result[k] = (d[k]||'').slice(0,80);
            if (Object.keys(result).length) return result;
        }
    }
    // Check JSON-LD
    const ld = document.querySelector('script[type=\"application/ld+json\"]');
    if (ld) {
        try {
            const j = JSON.parse(ld.textContent);
            return {jsonld: JSON.stringify(j).slice(0, 300)};
        } catch(e) {}
    }
    return null;
}""")
print(f"Job data: {job_data}")

# Get the actual apply URL from API
import urllib.request, json
req = urllib.request.Request(
    "https://remoteok.com/api",
    headers={"User-Agent": "curl/7.88.1", "Accept": "application/json"}
)
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read())

target_ids = ["1133393", "1131256", "1131146", "1131100", "1130985", "1130461"]
for job_id in target_ids:
    jobs = [j for j in data if isinstance(j, dict) and str(j.get("id", "")) == job_id]
    if jobs:
        j = jobs[0]
        print(f"API {job_id}: company={j.get('company')} url={j.get('url','?')[:60]} apply={j.get('apply_url','?')[:80]}")
    else:
        print(f"API {job_id}: not found (likely expired/removed)")

page.close()
