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

    # Intercept responses globally
    captured = []
    async def on_resp(response):
        url = response.url
        if "target.wd5" in url and any(k in url.lower() for k in ["skill", "autosuggest", "suggest", "search"]):
            captured.append(url[:120])
    page.on("response", on_resp)

    # Get React fiber for skills input and call onChange directly
    result = await page.evaluate("""
    () => {
        const inp = document.getElementById('skills--skills');
        if (!inp) return {error: 'no inp'};

        // Get React fiber
        const fiberKey = Object.keys(inp).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return {error: 'no fiber'};

        // Walk up to find onChange handler
        let fiber = inp[fiberKey];
        let depth = 0;
        while (fiber && depth < 30) {
            const props = fiber.memoizedProps || {};
            if (props.onChange) {
                // Found it - try calling onChange with a synthetic event
                try {
                    // Create a synthetic React event-like object
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(inp, 'Agile');

                    // Dispatch a real input event that React can intercept
                    const ev = new Event('input', {bubbles: true, cancelable: true});
                    Object.defineProperty(ev, 'target', {value: inp, writable: false});
                    inp.dispatchEvent(ev);

                    return {called: true, depth: depth, inpVal: inp.value};
                } catch(e) {
                    return {error: e.toString(), depth: depth};
                }
            }
            fiber = fiber.return;
            depth++;
        }
        return {error: 'no onChange found', depth: depth};
    }
    """)
    print("React onChange result:", result)
    await page.wait_for_timeout(3000)

    opts = await page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim().slice(0,40))")
    val = await page.evaluate("() => document.getElementById('skills--skills').value")
    print(f"Val={repr(val)}, Options ({len(opts)}):", opts[:5])
    print("Captured reqs:", captured)

    # Also check what ALL options are in the DOM currently (hidden or shown)
    all_opts = await page.evaluate("""
    () => {
        const all_listboxes = document.querySelectorAll('[role=listbox]');
        return Array.from(all_listboxes).map(lb => ({
            id: lb.id || '',
            label: lb.getAttribute('aria-label') || '',
            options: Array.from(lb.querySelectorAll('[role=option]')).slice(0,5).map(o=>o.textContent.trim().slice(0,30))
        }));
    }
    """)
    print("All listboxes:", all_opts)

    await p.stop()

asyncio.run(main())
