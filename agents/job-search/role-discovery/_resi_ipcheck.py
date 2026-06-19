from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    ctx = b.contexts[0]
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto("https://api.ipify.org?format=text", timeout=20000)
    print("Chrome-egress IP:", pg.inner_text("body").strip())
    b.close()
