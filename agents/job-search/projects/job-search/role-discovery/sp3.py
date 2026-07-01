import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]

    for i, pg in enumerate(ctx.pages):
        t = await pg.title()
        print(f"Page {i}: {t[:40]} | {pg.url[:60]}")

    page = None
    for pg in ctx.pages:
        if "target.wd5" in pg.url:
            cnt = await pg.evaluate("() => document.querySelectorAll('#skills--skills').length")
            if cnt > 0:
                page = pg
                print("Found skills form:", pg.url[:80])
                break

    if not page:
        print("No page with skills found")
        await p.stop()
        return

    skill_reqs = []
    def on_req(request):
        if "skill" in request.url.lower():
            skill_reqs.append(request.url)
    page.on("request", on_req)

    inp = page.locator("#skills--skills")
    await inp.scroll_into_view_if_needed()
    await inp.click(force=True)
    await page.wait_for_timeout(300)
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(200)

    for char in "Agile":
        await page.keyboard.type(char)
        await page.wait_for_timeout(300)

    await page.wait_for_timeout(2500)

    opts = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,50))")
    print(f"Options ({len(opts)}):", opts[:8])
    print("Skill reqs:", skill_reqs)

    await p.stop()

asyncio.run(main())
