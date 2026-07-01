from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    for ctx in b.contexts:
        for pg in ctx.pages:
            url = pg.url or ""
            if "login.icims.com/u/login/identifier" in url:
                try:
                    txt = pg.frames[0].evaluate("()=>document.body.innerText")
                    print(f"URL: {url[:70]}")
                    print(f"FULL TEXT:
{txt[:500]}")
                    links = pg.frames[0].evaluate("""()=>[...document.querySelectorAll('a,button')].map(el=>({text:(el.innerText||el.textContent||'').trim(),href:el.href||null})).filter(x=>x.text.length>0)""")
                    print("Links:")
                    for l in links:
                        print(f"  [{l['text'][:50]}] {(l['href'] or "")[:60]}")
                    break
                except Exception as e:
                    print("err:", e)
