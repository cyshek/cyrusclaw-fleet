import asyncio, json
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
        print("No skills page found")
        await p.stop()
        return

    print("Page:", page.url[:80])

    captured_resps = []
    async def on_response(response):
        url = response.url
        if ("skill" in url.lower() or "suggest" in url.lower()) and "target.wd5" in url:
            captured_resps.append(url[:100])
            print("RESPONSE:", url[:100])
    page.on("response", on_response)

    await page.evaluate("""
    () => {
        const inp = document.getElementById('skills--skills');
        if (inp) inp.blur();
    }
    """)
    await page.wait_for_timeout(500)

    inp_val = await page.evaluate("() => document.getElementById('skills--skills').value")
    print("Current value:", repr(inp_val))

    await page.evaluate("""
    () => {
        const inp = document.getElementById('skills--skills');
        const nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nv.call(inp, '');
        inp.dispatchEvent(new Event('input', {bubbles: true}));
    }
    """)
    await page.wait_for_timeout(500)

    await page.evaluate("() => document.getElementById('skills--skills').scrollIntoView()")
    await page.wait_for_timeout(300)

    inp = page.locator('#skills--skills')
    box = await inp.bounding_box()
    if box:
        print(f"Clicking at ({box['x']:.0f}, {box['y']:.0f})")
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    else:
        await inp.click()
    await page.wait_for_timeout(500)

    focused_id = await page.evaluate("() => document.activeElement ? document.activeElement.id : 'none'")
    print("Focused element:", focused_id)

    search = "Agil"
    for char in search:
        await page.keyboard.press(char)
        await page.wait_for_timeout(400)

    await page.wait_for_timeout(2000)

    val = await page.evaluate("() => document.getElementById('skills--skills').value")
    opts = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,40))")
    print(f"After typing: val={repr(val)}")
    print(f"Options ({len(opts)}):", opts[:10])
    print("Captured reqs:", captured_resps)

    await p.stop()

asyncio.run(main())
