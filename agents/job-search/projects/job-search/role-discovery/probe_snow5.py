
import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:19223"

JS_CHECK_BTN = """
() => {
    const cont = document.querySelector('[data-field-path*="4c8e248b"]');
    if (!cont) return {error: "no cont"};
    cont.scrollIntoView({block: "center", behavior: "instant"});
    const navEl = document.querySelector('ul[class*="navContainer"], header, nav');
    const navH = navEl ? Math.round(navEl.getBoundingClientRect().height) : 0;
    const btns = [...cont.querySelectorAll("button")];
    const btnData = btns.map(b => {
        const r = b.getBoundingClientRect();
        const topEl = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
        return {
            text: b.innerText.trim(),
            rect: {top: Math.round(r.top), bottom: Math.round(r.bottom), cx: Math.round(r.left+r.width/2), cy: Math.round(r.top+r.height/2)},
            topEl: topEl ? topEl.tagName + (topEl.className || '').slice(0,40) : null
        };
    });
    return {navH, btnData, windowH: window.innerHeight};
}
"""

JS_GET_YES_COORDS = """
() => {
    const cont = document.querySelector('[data-field-path*="4c8e248b"]');
    if (!cont) return null;
    cont.scrollIntoView({block: "center", behavior: "instant"});
    const btns = [...cont.querySelectorAll("button")];
    for (const b of btns) {
        if (b.innerText.trim() === "Yes") {
            const r = b.getBoundingClientRect();
            return {x: r.left + r.width/2, y: r.top + r.height/2, top: Math.round(r.top)};
        }
    }
    return null;
}
"""

JS_GET_SV = """
() => {
    const c = document.querySelector('[data-field-path*="4c8e248b"]');
    if (!c) return null;
    const btns = [...c.querySelectorAll("button")];
    let sv = null;
    for (const b of btns) {
        const fk = Object.keys(b).find(k => k.startsWith("__reactFiber$"));
        if (!fk) continue;
        let f = b[fk], d = 0;
        while (f && d < 40) {
            const mp = f.memoizedProps;
            if (mp && "savedValue" in mp && sv === null) sv = mp.savedValue;
            f = f.return; d++;
        }
        if (sv !== null) break;
    }
    return {savedValue: sv, btns: btns.map(b => ({text: b.innerText.trim(), active: /_active_|_selected_/.test(b.className || '')}))};
}
"""

JS_GET_SV_0A2 = """
() => {
    const c = document.querySelector('[data-field-path*="0a2a2426"]');
    if (!c) return {error: "no cont"};
    const inp = c.querySelector('input[type=radio]');
    if (!inp) return {error: "no radio"};
    const fk = Object.keys(inp).find(k => k.startsWith("__reactFiber$"));
    let sv = null;
    if (fk) {
        let f = inp[fk], d = 0;
        while (f && d < 40) {
            const mp = f.memoizedProps;
            if (mp && "savedValue" in mp && sv === null) sv = mp.savedValue;
            f = f.return; d++;
        }
    }
    return {id_tail: inp.id.slice(-25), checked: inp.checked, savedValue: sv};
}
"""

with sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp(CDP_URL)\n    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n    pages = ctx.pages\n    page = pages[0] if pages else ctx.new_page()

    page.goto("https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application", timeout=30000)
    page.wait_for_timeout(5000)

    print("=== Nav bar + button positions ===")
    info = page.evaluate(JS_CHECK_BTN)
    print(info)

    print("\n=== Getting Yes button coords ===")
    coords = page.evaluate(JS_GET_YES_COORDS)
    print("coords:", coords)

    if coords:
        print(f"\n=== Clicking at ({coords['x']:.0f}, {coords['y']:.0f}) ===")
        page.mouse.click(coords['x'], coords['y'])
        page.wait_for_timeout(500)
        sv = page.evaluate(JS_GET_SV)
        print("After mouse click:", sv)

    # Now test 0a2a2426 - find label and click it
    print("\n=== Testing 0a2a2426 label click ===")
    sv2_before = page.evaluate(JS_GET_SV_0A2)
    print("Before:", sv2_before)

    # Click label via locator
    try:
        labels = page.query_selector_all('[data-field-path*="0a2a2426"] label')
        for lab in labels:
            if "U.S. person" in (lab.inner_text() or ""):
                lab.scroll_into_view_if_needed(timeout=2000)
                r = lab.bounding_box()
                print(f"Label rect: {r}")
                page.mouse.click(r['x'] + r['width']/2, r['y'] + r['height']/2)
                page.wait_for_timeout(500)
                break
    except Exception as e:\n        print("label click err:", e)

    sv2_after = page.evaluate(JS_GET_SV_0A2)
    print("After label click:", sv2_after)

    print("\nDONE")
