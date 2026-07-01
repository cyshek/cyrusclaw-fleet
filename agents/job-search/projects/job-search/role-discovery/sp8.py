import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]
    page = None
    for pg in ctx.pages:
        if "target.wd5" in pg.url and "en-US" in pg.url:
            cnt = await pg.evaluate("() => document.querySelectorAll('#skills--skills').length")
            if cnt > 0:
                page = pg
                break
    if not page:
        print("No skills page")
        await p.stop()
        return
    print("Page:", page.url[:80])
    all_reqs = []
    async def on_req(request):
        url = request.url
        if "target.wd5" in url:
            all_reqs.append(f"{request.method} {url[:120]}")
    page.on("request", on_req)
    inp = page.locator('#skills--skills')
    box = await inp.bounding_box()
    print("Skills box:", box)
    if not box or box['y'] == 0:
        await page.evaluate("() => document.getElementById('skills--skills').scrollIntoView({block:'center'})")
        await page.wait_for_timeout(500)
        box = await inp.bounding_box()
        print("After scroll:", box)
    await page.evaluate("""
    () => {
        const inp = document.getElementById('skills--skills');
        const nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nv.call(inp, '');
        inp.dispatchEvent(new FocusEvent('blur', {bubbles: true}));
    }
    """)
    await page.wait_for_timeout(1000)
    if box and box['y'] > 0:
        cx = box['x'] + box['width'] / 2
        cy = box['y'] + box['height'] / 2
        print(f"Mouse click at ({cx:.0f}, {cy:.0f})")
        await page.mouse.click(cx, cy)
    else:
        await inp.click(force=True)
    await page.wait_for_timeout(500)
    focused = await page.evaluate("() => document.activeElement.id")
    print("Focused:", focused)
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(300)
    val = await page.evaluate("() => document.getElementById('skills--skills').value")
    print("Value after clear:", repr(val))
    for char in "sql":
        await page.keyboard.type(char, delay=0)
        await page.wait_for_timeout(600)
    await page.wait_for_timeout(3000)
    val2 = await page.evaluate("() => document.getElementById('skills--skills').value")
    opts = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,40))")
    print(f"Val={repr(val2)}, Options ({len(opts)}):", opts[:10])
    print("Skill reqs:", [r for r in all_reqs if "skill" in r.lower() or "suggest" in r.lower()])
    print("All WD reqs (last 5):", all_reqs[-5:] if all_reqs else [])
    await p.stop()

asyncio.run(main())
