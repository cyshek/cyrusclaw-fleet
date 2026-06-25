import asyncio, json, os, sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
os.environ["ENABLE_CAPSOLVER"] = "1"
from playwright.async_api import async_playwright
from captcha_presubmit import solve_and_inject_recaptcha_v3
ASHBY_SITEKEY = "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"
CDP_URL = "http://127.0.0.1:18800"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "thought-machine" in pg.url:
                page = pg; break
        if not page:
            print("ERROR: page not found", flush=True); return
        print(f"Found: {page.url}", flush=True)
        state = await page.evaluate("""
            () => { const g = [...document.querySelectorAll("div[class*=\\"_yesno_\\"]")]; return g.map((g,gi) => { const b=[...g.querySelectorAll("button")]; return {gi, btns: b.map(b2=>({text:b2.textContent.trim(),active:/_active_/.test(b2.className)}))}; }); }
        """)
        print("YesNo:", state, flush=True)
        vals = await page.evaluate("() => ({name: document.getElementById(\"_systemfield_name\")?.value, email: document.getElementById(\"_systemfield_email\")?.value})")
        print("Fields:", vals, flush=True)
        result = solve_and_inject_recaptcha_v3(page, fallback_sitekey=ASHBY_SITEKEY, action="job_apply")
        print("Captcha:", result, flush=True)
        resp = await page.evaluate("""
            async () => {
                const orig = window.fetch; let last=null;
                window.fetch = async (...a) => { const r=await orig(...a); try{last=await r.clone().text();}catch(e){} return r; };
                const btn=[...document.querySelectorAll("button")].find(b=>/submit application/i.test(b.textContent.trim()));
                if(!btn) return {error:"no btn"};
                btn.click();
                await new Promise(r=>setTimeout(r,7000));
                return {body:last?last.slice(0,600):null};
            }
        """)
        print("Submit:", resp, flush=True)
        body = await page.evaluate("() => document.body.innerText.slice(0,600)")
        print("Body:", body, flush=True)

asyncio.run(main())
