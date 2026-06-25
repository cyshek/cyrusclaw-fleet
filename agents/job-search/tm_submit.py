import os, json, asyncio, sys, time
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.environ['ENABLE_CAPSOLVER'] = '1'
from playwright.async_api import async_playwright
from capsolver_client import CapSolverClient

RESUME = "/tmp/openclaw/uploads/Cyrus_Shekari_Resume_ashby-thought-machine_c6d119df_v2.pdf"
URL = "https://jobs.ashbyhq.com/thought-machine/c6d119df-b5e3-4d94-8a4f-22d5040a0924/application"

INJECT_JS = "(tok) => { ['g-recaptcha-response','g-recaptcha-response-100000'].forEach(id => { let el=document.getElementById(id); if(!el){el=document.createElement('textarea');el.id=id;el.name=id;el.style.display='none';document.body.appendChild(el);} el.value=tok; }); return tok.length; }"
YESNO_JS = "() => { const gs=[...document.querySelectorAll('div[class*=_yesno_]')]; return gs.map((g,gi)=>({gi,btns:[...g.querySelectorAll('button')].map(b=>({t:b.textContent.trim(),a:b.className.includes('_active_')}))})); }"
SUBMIT_JS = "async () => { const orig=window.fetch; let last=null,lastStatus=null; window.fetch=async(...a)=>{const r=await orig(...a);lastStatus=r.status;try{last=await r.clone().text();}catch(e){}return r;}; const btn=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim())); if(!btn)return {error:'no btn'}; btn.click(); await new Promise(r=>setTimeout(r,8000)); return {status:lastStatus,body:last?last.slice(0,500):null,url:location.href}; }"
FILL_JS = "(vals) => { const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; const taSetter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set; Object.entries(vals).forEach(([id,v])=>{ let el=document.getElementById(id); if(!el)return; const s=el.tagName==='TEXTAREA'?taSetter:setter; s.call(el,v); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }); return 'ok'; }"

async def run():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:18800')
        ctx = b.contexts[0]
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await asyncio.sleep(2)
        print("page loaded")
        # Fill text fields
        await page.evaluate(FILL_JS, {'_systemfield_name': 'Cyrus Shekari', '_systemfield_email': 'cyshekari@gmail.com'})
        await asyncio.sleep(0.3)
        # Type via playwright for email field to trigger React
        name_el = await page.query_selector('#_systemfield_name')
        if name_el:
            await name_el.fill('Cyrus Shekari')
        email_el = await page.query_selector('#_systemfield_email')
        if email_el:
            await email_el.fill('cyshekari@gmail.com')
        # Phone - find tel input
        tel = await page.query_selector('input[type=tel]')
        if tel:
            await tel.fill('3468040227')
        await asyncio.sleep(0.3)
        # Upload resume
        resume_input = await page.query_selector('#_systemfield_resume')
        if resume_input:
            await resume_input.set_input_files(RESUME)
            await asyncio.sleep(3)  # wait for autofill
            print("resume uploaded, re-filling after autofill wipe")
        # Re-fill after autofill wipe
        await page.evaluate(FILL_JS, {'_systemfield_name': 'Cyrus Shekari', '_systemfield_email': 'cyshekari@gmail.com'})
        # Notice period
        notice_inputs = await page.query_selector_all('input[type=text]')
        for inp in notice_inputs:
            ph = await inp.get_attribute("placeholder")
            if ph and 'type here' in ph.lower():
                await inp.fill('2 weeks'); break
        # Click No for sponsorship (group 0)
        groups = await page.query_selector_all('div[class*="_yesno_"]')
        for gi, g in enumerate(groups):
            btns = await g.query_selector_all('button')
            want = 'No' if gi == 0 else 'Yes'
            for btn in btns:
                txt = (await btn.text_content() or "").strip()
                if txt == want:
                    await btn.scroll_into_view_if_needed()
                    await btn.click()
                    await asyncio.sleep(0.5)
                    print(f"clicked gi={gi} want={want}")
                    break
        await asyncio.sleep(0.5)
        # LinkedIn radio
        li_radios = await page.query_selector_all('input[type=radio]')
        for r in li_radios:
            rid = await r.get_attribute("id") or ""
            lbl = await page.query_selector(f"label[for=\"{rid}\"]")
            if lbl:
                ltxt = (await lbl.text_content() or "").strip()
                if ltxt == "LinkedIn":
                    await lbl.click(); print("LinkedIn clicked"); break
        # Privacy checkbox
        cbs = await page.query_selector_all('input[type=checkbox]')
        for cb in cbs:
            name = await cb.get_attribute("name") or ""
            if 'd6aebef6' in name or 'acknowledge' in name.lower() or 'privacy' in name.lower():
                checked = await cb.is_checked()
                if not checked: await cb.click()
                print("privacy cb clicked, name:", name)
                break
        await asyncio.sleep(0.3)
        # Verify state
        state = await page.evaluate(YESNO_JS)
        print("yesno state:", state)
        vals = await page.evaluate("() => ({name: document.getElementById(\"_systemfield_name\")?.value, email: document.getElementById(\"_systemfield_email\")?.value})")
        print("fields:", vals)
        # Solve captcha
        c = CapSolverClient()
        token = c.recaptcha_v3(sitekey='6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y', page_url=URL, action='job_apply')
        print("token_len:", len(token))
        r = await page.evaluate(INJECT_JS, token)
        print("injected:", r)
        # Submit immediately
        result = await page.evaluate(SUBMIT_JS)
        print("submit result:", result)
        body = await page.evaluate("() => document.body.innerText.slice(0,600)")
        print("body:", body)

asyncio.run(run())
