import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
import json

CDP_URL = "http://127.0.0.1:19223"

failing_uuids = [
    'a3cc08ef-4552-444a-b493-c608c65670df',
    '0a2a2426-a42d-4c4f-a68f-5083d6b8a72a',
    '5c859149-0940-42e7-8962-ec82679d8074',
]

with sync_playwright() as p:\n+    browser = p.chromium.connect_over_cdp(CDP_URL)\n+    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n+    pages = ctx.pages\n+    page = pages[0] if pages else ctx.new_page()

    print("Navigating...")
    page.goto(
        "https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application",
        timeout=30000
    )
    page.wait_for_timeout(4000)

    # Inspect radio details for the 3 failing fields
    print("\n=== Radio details for 3 failing fields ===")
    for uuid in failing_uuids:
        r = page.evaluate(
            """(uuid) => {
                const cont = document.querySelector('[data-field-path="' + uuid + '"]') ||
                              document.querySelector('[data-field-path$="_' + uuid + '"]');
                if (!cont) return {error: 'no-container', uuid};
                const hasYesno = !!cont.querySelector('div[class*="_yesno_"]');
                const radios = [...cont.querySelectorAll('input[type=radio]')];
                return {
                    uuid: uuid,
                    actualPath: cont.getAttribute('data-field-path'),
                    hasYesno: hasYesno,
                    radioCount: radios.length,
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
                            id: (inp.id || '').slice(0, 55),
                            htmlValue: inp.value,
                            checked: inp.checked,
                            savedValue: savedValue,
                            fiberValue: fiberValue,
                            labelFor: (label || {}).getAttribute?.('for')?.slice(0, 55),
                            labelClass: ((label || {}).className || '').slice(0, 60),
                            labelText: ((label || {}).textContent || '').trim().slice(0, 70)
                        };
                    })
                };
            }""",
            uuid
        )
        print(f"\n  {uuid[:12]}...")
        print(f"    actualPath: {r.get('actualPath')}")
        print(f"    hasYesno: {r.get('hasYesno')}, radioCount: {r.get('radioCount')}")
        for radio in r.get('radios', []):
            print(f"    radio: {radio}")

    print("\nDone.")
