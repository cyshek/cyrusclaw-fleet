import asyncio
import json

async def main():
    from playwright.async_api import async_playwright
    creds_file = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.workday-creds.json"
    creds = json.load(open(creds_file))
    ms_cred = creds.get("ms", {})
    if not ms_cred:
        print("No MS creds")
        return
    email = ms_cred.get("email")
    pw = ms_cred.get("password") or ms_cred.get("pw")
    print("email:", email)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        url = "https://ms.wd5.myworkdayjobs.com/External/job/Seattle-Washington-United-States-of-America/Program-Manager---Parametric_PT-JR037957-1/apply"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        body = await page.evaluate("() => document.body.innerText")
        if "sign in" in body.lower() or "create account" in body.lower():
            try:
                t = page.locator("[data-automation-id=auth_signin_link]").first
                if await t.count():
                    await t.click()
                    await page.wait_for_timeout(800)
            except Exception: pass
            try:
                await page.fill("input[data-automation-id=email]", email)
                await page.fill("input[data-automation-id=password]", pw)
                await page.click("button[data-automation-id=signInSubmitButton]")
                await page.wait_for_timeout(4000)
            except Exception as e: print("sign-in err:", e)
        body2 = await page.evaluate("() => document.body.innerText")
        print("URL:", page.url)
        print("Body snippet:", body2[:200])
        if "My Information" not in body2:
            print("Not on My Info")
            await page.close()
            return
        info = await page.evaluate("""() => {
            const inp = document.querySelector("input#source--source");
            if (!inp) return {found:false};
            return {found:true, value:inp.value,
                ariaRequired:inp.getAttribute("aria-required"),
                ariaHaspopup:inp.getAttribute("aria-haspopup"),
                role:inp.getAttribute("role"),
                autocomplete:inp.getAttribute("aria-autocomplete")};
        }""")
        print("source input:", info)
        await page.evaluate("document.querySelector('input#source--source')?.click()")
        await page.wait_for_timeout(1200)
        opts_raw = await page.evaluate("""() => {
            return [...document.querySelectorAll("[data-automation-id=promptOption],[role=option]")]
                .slice(0,25).map(o=>({
                    text:(o.textContent||"").trim().slice(0,50),
                    aid:o.getAttribute("data-automation-id")||""
                }));
        }""")
        print("Options:", opts_raw)
        tgt = next((o["text"] for o in opts_raw if o["text"] and "(+" not in o["text"] and o["text"].lower() != "select one"), None)
        if tgt:
            print("Picking:", tgt)
        await page.evaluate(f"const opts=[...document.querySelectorAll('[data-automation-id=promptOption],[role=option]')]; const t=opts.find(o=>o.textContent.includes('{tgt[:15]}')); if(t)t.click();")
            await page.wait_for_timeout(1500)
            after = await page.evaluate("""() => {
                const inp = document.querySelector("input#source--source");
                let pill=false; let scope=inp;
                for(let i=0;i<12&&scope;i++){
                    scope=scope.parentElement; if(!scope) break;
                    if(scope.querySelector("[data-automation-id=selectedItem],[data-automation-id=DELETE_charm]")){pill=true; break;}
                }
                const gp=document.querySelector("[data-automation-id=selectedItem]");
                return {val:inp?inp.value:"?", pill, gpText:gp?(gp.textContent||"").trim().slice(0,50):null,
                    reqEmpty:[...document.querySelectorAll("input[aria-required=true]")]
                        .filter(e=>!(e.value||"").trim()).map(e=>e.id||e.name||"?")};
            }""")
            print("After pick:", after)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(800)
            after2 = await page.evaluate("""() => {
                const inp = document.querySelector("input#source--source");
                let pill=false; let scope=inp;
                for(let i=0;i<12&&scope;i++){
                    scope=scope.parentElement; if(!scope) break;
                    if(scope.querySelector("[data-automation-id=selectedItem],[data-automation-id=DELETE_charm]")){pill=true; break;}
                }
                return {val:inp?inp.value:"?", pill,
                    reqEmpty:[...document.querySelectorAll("input[aria-required=true]")]
                        .filter(e=>!(e.value||"").trim()).map(e=>e.id||e.name||"?")};
            }""")
            print("After Escape:", after2)
        await page.close()

asyncio.run(main())
