import asyncio, json, re
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

    # Try to call Workday skills API directly via page.evaluate (same-origin)
    result = await page.evaluate("""
    async () => {
        // Try to find the API endpoint by looking at existing WD API calls
        // Workday skill search usually goes to /wday/cxs/<tenant>/<site>/autosuggest
        const url = window.location.origin;
        const pathParts = window.location.pathname.split('/');
        // Build candidate API URL
        const tenant = 'target';
        const site = 'targetcareers';
        const apiUrl = `${url}/wday/cxs/${tenant}/${site}/skills/autosuggest`;
        try {
            const resp = await fetch(apiUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({searchKey: 'Project', limit: 10})
            });
            if (!resp.ok) return {status: resp.status, url: apiUrl};
            const data = await resp.json();
            return {status: resp.status, data: JSON.stringify(data).slice(0, 200), url: apiUrl};
        } catch(e) {
            return {error: e.toString(), url: apiUrl};
        }
    }
    """)
    print("Skills API result:", result)

    # Try another endpoint pattern
    result2 = await page.evaluate("""
    async () => {
        const url = window.location.origin;
        // Try the suggest endpoint used by typeahead
        const apiUrl = `${url}/wday/cxs/target/targetcareers/skillsuggest`;
        try {
            const resp = await fetch(apiUrl + '?searchKey=Project&limit=10');
            return {status: resp.status, url: apiUrl};
        } catch(e) {
            return {error: e.toString()};
        }
    }
    """)
    print("Skills API2:", result2)

    # Try to intercept by looking at already loaded XHR responses (performance entries)
    perf = await page.evaluate("""
    () => {
        const entries = performance.getEntriesByType('resource');
        return entries
            .filter(e => e.name.includes('wday') || e.name.includes('skill') || e.name.includes('suggest'))
            .map(e => e.name.slice(0, 120))
            .slice(0, 20);
    }
    """)
    print("Performance entries:", perf[:10])

    # Check WD service worker or global state for skills endpoint
    wd_state = await page.evaluate("""
    () => {
        // WD often stores API config in window globals
        const keys = Object.keys(window).filter(k =>
            k.includes('wd') || k.includes('skill') || k.includes('suggest') || k.includes('Suggest')
        );
        return keys.slice(0, 20);
    }
    """)
    print("WD globals:", wd_state)

    await p.stop()

asyncio.run(main())
