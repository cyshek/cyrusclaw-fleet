import sys; sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright

CDP_URL = 'http://127.0.0.1:19223'

with sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp(CDP_URL)\n    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n    pages = ctx.pages\n    page = pages[0] if pages else ctx.new_page()

    print('Current URL:', page.url)
    print('Navigating...')
    page.goto('https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application', timeout=30000)
    page.wait_for_timeout(5000)

    # Check the yesno button structure for 4c8e248b (in-office)
    r = page.evaluate("""() => {
        const cont = document.querySelector('[data-field-path*="4c8e248b"]');
        if (!cont) return {error: 'no container'};
        const buttons = [...cont.querySelectorAll('button')];
        return {
            path: cont.getAttribute('data-field-path'),
            buttons: buttons.map(b => {
                const fk = Object.keys(b).find(k => k.startsWith('__reactFiber$'));
                let savedValue = null, fbValue = null;
                if (fk) {
                    let f = b[fk], d = 0;
                    while (f && d < 40) {
                        const mp = f.memoizedProps;
                        if (mp) {
                            if ('savedValue' in mp && savedValue === null) savedValue = mp.savedValue;
                            if ('value' in mp && fbValue === null) fbValue = mp.value;
                        }
                        f = f.return; d++;
                    }
                }
                return {
                    text: (b.innerText || '').trim(),
                    active: /_active_|_selected_/.test(b.className || ''),
                    savedValue: savedValue,
                    fbValue: fbValue
                };
            })
        };
    }""")
    print('4c8e248b (in-office) BEFORE CLICK:')
    print(f'  path: {r.get("path")}')
    for btn in r.get('buttons', []):
        print(f'  btn: {btn}')

    # Click YES button for in-office via trusted Playwright
    print('\nClicking YES via Playwright...')
    try:
        cont_loc = page.locator('[data-field-path*="4c8e248b"]').first
        yes_btn = cont_loc.locator('button', has_text='Yes').first
        yes_btn.click(timeout=3000)
        page.wait_for_timeout(300)
    except Exception as e:\n        print(f'Click error: {e}')

    r2 = page.evaluate("""() => {
        const cont = document.querySelector('[data-field-path*="4c8e248b"]');
        if (!cont) return {error: 'no container'};
        const buttons = [...cont.querySelectorAll('button')];
        return {
            path: cont.getAttribute('data-field-path'),
            buttons: buttons.map(b => {
                const fk = Object.keys(b).find(k => k.startsWith('__reactFiber$'));
                let savedValue = null, fbValue = null;
                if (fk) {
                    let f = b[fk], d = 0;
                    while (f && d < 40) {
                        const mp = f.memoizedProps;
                        if (mp) {
                            if ('savedValue' in mp && savedValue === null) savedValue = mp.savedValue;
                            if ('value' in mp && fbValue === null) fbValue = mp.value;
                        }
                        f = f.return; d++;
                    }
                }
                return {
                    text: (b.innerText || '').trim(),
                    active: /_active_|_selected_/.test(b.className || ''),
                    savedValue: savedValue,
                    fbValue: fbValue
                };
            })
        };
    }""")
    print('\n4c8e248b AFTER CLICK:')
    for btn in r2.get('buttons', []):
        print(f'  btn: {btn}')

    # Now check 0a2a2426
    print('\nClicking "I am a U.S. person" via label...')
    try:
        # Label-first
        label_loc = page.locator('[data-field-path*="0a2a2426"] label').filter(has_text='I am a U.S. person').first
        label_loc.click(timeout=3000)
        page.wait_for_timeout(300)
    except Exception as e:\n        print(f'Click error: {e}')

    r3 = page.evaluate("""() => {
        const cont = document.querySelector('[data-field-path="0a2a2426-a42d-4c4f-a68f-5083d6b8a72a"]') ||
                     document.querySelector('[data-field-path*="0a2a2426"]');
        if (!cont) return {error: 'no container'};
        const radios = [...cont.querySelectorAll('input[type=radio]')];
        return {
            path: cont.getAttribute('data-field-path'),
            radios: radios.map(inp => {
                const label = document.querySelector('label[for="' + inp.id + '"]');
                let savedValue = null;
                const fk = Object.keys(inp).find(k => k.startsWith('__reactFiber$'));
                if (fk) {
                    let f = inp[fk], d = 0;
                    while (f && d < 40) {
                        const mp = f.memoizedProps;
                        if (mp && 'savedValue' in mp && savedValue === null) savedValue = mp.savedValue;
                        f = f.return; d++;
                    }
                }
                return {
                    id_tail: (inp.id || '').slice(-25),
                    checked: inp.checked,
                    savedValue: savedValue,
                    labelText: ((label || {}).innerText || '').trim().slice(0, 50)
                };
            })
        };
    }""")
    print('0a2a2426 AFTER LABEL CLICK:')
    for radio in r3.get('radios', []):
        print(f'  radio: {radio}')

    print('\nDone.')
