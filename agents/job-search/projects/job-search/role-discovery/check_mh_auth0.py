from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "login.icims.com/u/login/identifier" in (pg.url or ""):
                fr = pg.frames[0]
                txt = fr.evaluate("()=>document.body.innerText")
                print("URL:", pg.url[:70])
                print("TEXT:", txt[:400])
                break
