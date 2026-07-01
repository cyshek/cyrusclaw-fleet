from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    # Find identifier page
    target_pg = None
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "login.icims.com/u/login/identifier" in (pg.url or ""):
                target_pg = pg
                break
        if target_pg:
            break
    
    if not target_pg:
        print("No identifier page - navigating fresh")
        ctx = b.contexts[0]
        target_pg = ctx.new_page()
        target_pg.goto("https://login.icims.com/u/login/identifier?state=hqFo2SA0VXB5MzhFY1BKN", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
    
    print("Current URL:", target_pg.url[:80])
    
    # Find the Google button
    btn_res = target_pg.frames[0].evaluate("""()=>{
        const btns = [...document.querySelectorAll('button,a')];
        const google = btns.find(b => /google/i.test(b.textContent||b.getAttribute('data-provider')||b.getAttribute('data-connection')||b.className));
        if (google) {
            return {text: google.textContent.trim(), href: google.href, class: google.className.slice(0,50)};
        }
        return null;
    }""")
    print("Google button:", btn_res)
