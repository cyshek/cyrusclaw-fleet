from playwright.sync_api import sync_playwright

def check():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
        for ctx in b.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "icims" in url or "login" in url:
                    try:
                        txt = pg.frames[0].evaluate("()=>document.body.innerText.slice(0,200)")
                        print(f"URL: {url[:70]}")
                        print(f"  => {txt[:120]}")
                    except:
                        pass

check()
