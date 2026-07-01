from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.goto("https://careers-keysight.icims.com/jobs/53104/login?in_iframe=1", wait_until="domcontentloaded", timeout=15000)
    time.sleep(3)
    txt = pg.evaluate("()=>document.body.innerText.slice(0,500)")
    print("Page text:", txt[:400])
    links = pg.evaluate("""()=>[...document.querySelectorAll('a,button')].map(el=>({text:(el.innerText||el.textContent).trim(),href:el.href||null})).filter(x=>x.text)""")
    print("Links/buttons:")
    for link in links[:20]:
        print(f"  [{link['text'][:40]}] {(link['href'] or "")[:60]}")
    pg.close()
