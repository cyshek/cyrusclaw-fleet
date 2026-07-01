from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]
    # Check Google cookies
    cookies = ctx.cookies("https://accounts.google.com")
    google_cookies = [c for c in cookies if "google" in c.get("domain", "")]
    print(f"Google cookies: {len(google_cookies)}")
    for c in google_cookies[:5]:
        print(f"  {c['name']}: {c['domain']}")
