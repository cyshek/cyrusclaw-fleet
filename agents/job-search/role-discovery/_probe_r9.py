import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
URL="https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295"
with sync_playwright() as p:
    ctx=p.chromium.launch_persistent_context(user_data_dir=str(ROOT/".workday-browser-data"/"adobe"),headless=True,viewport={"width":1400,"height":900},user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")
    pg=ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(URL,wait_until="domcontentloaded",timeout=60000); pg.wait_for_timeout(5000)
    print("URL:",pg.url)
    print("TITLE:",pg.title())
    err=pg.evaluate("()=>{const e=document.querySelector('[data-automation-id=errorMessage],[data-automation-id=errorContainer]');return e?e.innerText.trim().slice(0,300):'(none)';}")
    print("ERROR:",err)
    body=(pg.locator('body').inner_text() or '')[:600]
    print("BODY:",body)
    aff=pg.evaluate("()=>{const o=[];for(const el of document.querySelectorAll('a,button,[data-automation-id]')){const i=el.getAttribute('data-automation-id')||'';const t=(el.textContent||'').trim();if(/apply|adventure|continue/i.test(i)||(/apply|continue/i.test(t)&&t.length<25))o.push(i||t);}return [...new Set(o)].slice(0,15);}")
    print("AFFORDANCES:",json.dumps(aff))
    ctx.close()
