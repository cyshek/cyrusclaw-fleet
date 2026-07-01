from playwright.sync_api import sync_playwright
import time, json

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    # Go to the actual job posting - not the iframe
    pg.goto("https://careers-keysight.icims.com/jobs/53104/rfu-field-solutions-engineer/job", wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)
    txt = pg.evaluate("()=>document.body.innerText.slice(0,600)")
    print("Page text:", txt[:500])
    pg.close()
