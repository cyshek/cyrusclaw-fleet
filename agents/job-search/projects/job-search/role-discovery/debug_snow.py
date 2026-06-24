import sys
sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
import json

CDP_URL = "http://127.0.0.1:19223"

failing_uuids = [
    "a3cc08ef-4552-444a-b493-c608c65670df",
    "0a2a2426-a42d-4c4f-a68f-5083d6b8a72a",
    "5c859149-0940-42e7-8962-ec82679d8074",
]

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    pages = ctx.pages
    page = pages[0] if pages else ctx.new_page()
    print("Navigating...")
    page.goto("https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application", timeout=30000)
    page.wait_for_timeout(4000)
    # Find all radio containers
    result = page.evaluate("""() => {
        const containers = [...document.querySelectorAll('[data-field-path]')];
        return containers.filter(c =>
            c.querySelectorAll('input[type=radio]').length > 0 ||
            c.querySelector('div[class*="_yesno_"]')
        ).map(c => ({
            path: c.getAttribute('data-field-path'),
            radioCount: c.querySelectorAll('input[type=radio]').length,
            hasYesno: !!c.querySelector('div[class*="_yesno_"]'),
            label: ((c.querySelector('label,legend') || {}).textContent || '').trim().slice(0, 80)
        }));
    }""")
    print("=== containers with radios ===")
    for r in result:
        print(f"  path={r['path']}")
        print(f"    radios={r['radioCount']}, yesno={r['hasYesno']}, label={r['label']!r}")
    
    # Test lookup for 3 failing fields
    print("=== field lookup ===")
    for uuid in failing_uuids:
        r = page.evaluate("""(uuid) => {
            let cont = document.querySelector('[data-field-path="' + uuid + '"]');
            if (cont) return {found: 'exact', path: cont.getAttribute('data-field-path')};
            cont = document.querySelector('[data-field-path$="_' + uuid + '"]');
            if (cont) return {found: 'endswith', path: cont.getAttribute('data-field-path'), radios: cont.querySelectorAll('input[type=radio]').length};
            return {found: false};
        }""", uuid)
        print(f"  {uuid[:12]}... -> {r}")
    
    print("Done.")
    # Inspect the radio structure for US person and PwC fields
    print("\n=== Radio input details for 0a2a2426 and 5c859149 ===")
    for uuid in ['0a2a2426-a42d-4c4f-a68f-5083d6b8a72a', '5c859149-0940-42e7-8962-ec82679d8074']:
        r = page.evaluate("""(uuid) => {
            const cont = document.querySelector('[data-field-path="' + uuid + '"]');
            if (!cont) return {error: 'no-container'};
            const radios = [...cont.querySelectorAll('input[type=radio]')];
            return {
                containerClass: cont.className.slice(0, 60),
                radios: radios.map(inp => {
                    const label = document.querySelector('label[for="' + inp.id + '"]');
                    let savedValue = null, fiberValue = null;
                    const fk = Object.keys(inp).find(k => k.startsWith('__reactFiber$'));
                    if (fk) {
                        let f = inp[fk], d = 0;
                        while (f && d < 40) {
                            const mp = f.memoizedProps;
                            if (mp) {
                                if ('value' in mp && 'fieldEntryId' in mp && fiberValue === null) fiberValue = mp.value;
                                if ('savedValue' in mp && savedValue === null) savedValue = mp.savedValue;
                            }
                            f = f.return; d++;
                        }
                    }
                    return {
                        id: (inp.id || '').slice(0, 50),
                        name: (inp.name || '').slice(0, 60),
                        value: inp.value,
                        checked: inp.checked,
                        savedValue: savedValue,
                        fiberValue: fiberValue,
                        labelId: (label || {}).id,
                        labelFor: (label || {}).getAttribute?.('for'),
                        labelClass: ((label || {}).className || '').slice(0, 60),
                        labelText: ((label || {}).textContent || '').trim().slice(0, 60)
                    };
                })
            };
        }""", uuid)
        print(f"\n  {uuid[:12]}...")
        if isinstance(r, dict) and 'radios' in r:\n            print(f"    containerClass: {r['containerClass']!r}")
            for radio in r['radios']:
                print(f"    radio: {radio}")
        else:
            print(f"    {r}")
