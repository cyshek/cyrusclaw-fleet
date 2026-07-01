from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    # Find MH Auth0 password page
    pw_pg = None
    for ctx in b.contexts:
        for pg in ctx.pages:
            url = pg.url or ""
            if "login.icims.com/u/login/password" in url:
                pw_pg = pg
                break
        if pw_pg:
            break
    
    if pw_pg:
        print("Password page found:", pw_pg.url[:80])
        txt = pw_pg.frames[0].evaluate("()=>document.body.innerText.slice(0,400)")
        print("Text:", txt[:300])
    else:
        print("No password page open")
        # List all login.icims pages
        for ctx in b.contexts:
            for pg in ctx.pages:
                if "login.icims" in (pg.url or ""):
                    print(" Open:", (pg.url or "")[:80])
                    try:
                        txt = pg.frames[0].evaluate("()=>document.body.innerText.slice(0,100)")
                        print("  =>", txt[:80])
                    except:
                        pass
