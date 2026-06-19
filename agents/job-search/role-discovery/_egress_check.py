import json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:19223"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    out = {}
    try:
        pg.goto("https://api.ipify.org?format=json", timeout=25000)
        out["ipify"] = pg.inner_text("body")
    except Exception as e:
        out["ipify_err"] = str(e)[:200]
    try:
        pg.goto("http://ip-api.com/json", timeout=25000)
        out["ipapi"] = pg.inner_text("body")[:500]
    except Exception as e:
        out["ipapi_err"] = str(e)[:200]
    print(json.dumps(out, indent=2))
    pg.close()
