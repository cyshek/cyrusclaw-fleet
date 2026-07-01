import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = b.contexts[0]

    # Find the page with skills form
    page = None
    for pg in ctx.pages:
        if "target.wd5" in pg.url:
            cnt = await pg.evaluate("() => document.querySelectorAll('#skills--skills').length")
            if cnt > 0:
                page = pg
                break

    if not page:
        print("No page with skills form")
        await p.stop()
        return

    print("Page:", page.url[:80])

    # Use CDP directly to dispatch proper key events
    session = await page.context.new_cdp_session(page)

    # Focus the element first
    await page.evaluate("() => { document.getElementById('skills--skills').focus(); }")
    await page.wait_for_timeout(200)

    # Select all text and delete
    await session.send("Input.dispatchKeyEvent", {
        "type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65
    })
    await session.send("Input.dispatchKeyEvent", {
        "type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65
    })
    await page.wait_for_timeout(100)
    await session.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    await session.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    await page.wait_for_timeout(200)

    val = await page.evaluate("() => document.getElementById('skills--skills').value")
    print("After clear:", repr(val))

    # Now type "Agile" via CDP insertText (bypasses keydown/keyup but triggers input event)
    await session.send("Input.insertText", {"text": "Agile"})
    await page.wait_for_timeout(3000)

    val2 = await page.evaluate("() => document.getElementById('skills--skills').value")
    print("After typing:", repr(val2))

    opts = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,50))")
    print(f"Options after 'Agile' ({len(opts)}):", opts[:10])

    # Also check via network intercept - look at currently loaded resources
    resources = await session.send("Network.getAllCookies", {})
    print("Cookies count:", len(resources.get("cookies", [])))

    # Try typing char by char with dispatchKeyEvent
    await page.evaluate("() => { const i = document.getElementById('skills--skills'); i.value = ''; i.dispatchEvent(new Event('input', {bubbles:true})); }")
    await page.wait_for_timeout(300)

    search_word = "Project"
    for char in search_word:
        key_code = ord(char.upper())
        await session.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": char, "code": f"Key{char.upper()}",
            "windowsVirtualKeyCode": key_code, "text": char
        })
        await session.send("Input.dispatchKeyEvent", {
            "type": "char", "key": char, "text": char
        })
        await session.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": char, "code": f"Key{char.upper()}",
            "windowsVirtualKeyCode": key_code, "text": char
        })
        await page.wait_for_timeout(200)

    await page.wait_for_timeout(2500)

    val3 = await page.evaluate("() => document.getElementById('skills--skills').value")
    opts2 = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,50))")
    print(f"After 'Project': value={repr(val3)}, options={opts2[:10]}")

    await p.stop()

asyncio.run(main())
