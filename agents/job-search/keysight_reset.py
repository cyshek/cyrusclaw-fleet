#!/usr/bin/env python3
import asyncio, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")

async def run():
    from playwright.async_api import async_playwright
    print("[reset] Connecting:", CDP)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        for pg in list(ctx.pages):
            if "keysight" in pg.url.lower():
                try: await pg.close()
                except: pass
        page = await ctx.new_page()
        await page.goto("https://careers-keysight.icims.com/jobs/53104/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        await page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/ks_step1.png")
        print("[reset] Step1 URL:", page.url)
        for f in page.frames: print("  frame:", f.url[:80])
        try:
            iframe = page.frame_locator("iframe").first
            cb = iframe.locator("input[type=\\\"checkbox\\\"]")
            cnt = await cb.count()
            print("[reset] Checkbox count:", cnt)
            if cnt > 0:
                await cb.click()
                await asyncio.sleep(1)
                nxt = iframe.locator("button").filter(has_text="Next")
                await nxt.click()
                print("[reset] Clicked Next after checkbox")
                await asyncio.sleep(3)
        except Exception as e: print("[reset] Privacy err:", e)
        try:
            iframe = page.frame_locator("iframe").first
            ei = iframe.locator("input[type=\\\"email\\\"]")
            if await ei.count() == 0: ei = iframe.locator("input").first
            await ei.fill("cyshekari@gmail.com")
            print("[reset] Email filled")
            await asyncio.sleep(1)
            nxt = iframe.locator("button").filter(has_text="Next")
            await nxt.click()
            print("[reset] Submitted email")
            await asyncio.sleep(8)
        except Exception as e: print("[reset] Email err:", e)
        await page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/ks_step2.png")
        print("[reset] Step2 URL:", page.url)
        for f in page.frames: print("  frame:", f.url[:100])
        a0 = None
        for f in page.frames:
            if "login.icims.com" in f.url: a0 = f; print("[reset] Auth0:", f.url[:100]); break
        if a0:
            try:
                rl = a0.locator("a").filter(has_text="Reset")
                cnt = await rl.count()
                print("[reset] Reset links:", cnt)
                if cnt > 0:
                    await rl.first.click()
                    print("[reset] Clicked Reset")
                    await asyncio.sleep(5)
                    await page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/ks_step3.png")
                    for f in page.frames: print("  frame after reset:", f.url[:100])
                else:
                    c = await a0.content()
                    print("[reset] Auth0 content:", c[:1000])
            except Exception as e: print("[reset] Reset err:", e)
        else: print("[reset] Auth0 frame NOT found")
        print("[reset] Done")
        await page.close()

asyncio.run(run())
