#!/usr/bin/env python3
"""Debug BambooHR state dropdown."""
from playwright.sync_api import sync_playwright
import time, json

CDP = "http://127.0.0.1:18800"
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

for p in list(ctx.pages):
    try:
        if "bamboohr" in p.url:
            p.close()
    except:
        pass

page = ctx.new_page()
page.goto("https://uphold.bamboohr.com/careers/838", wait_until="domcontentloaded", timeout=30000)
time.sleep(2)
page.locator('a:has-text("Apply for This Job"), button:has-text("Apply for This Job")').first.click(timeout=8000)
time.sleep(3)

# Check the state select
state_info = page.evaluate("""() => {
    const sel = document.getElementById('fab-select359') || document.querySelector('[name="state.value"]');
    if (!sel) return {found: false};
    const opts = [...sel.options].map(o => ({val:o.value, text:o.text})).slice(0,5);
    return {
        found: true,
        id: sel.id,
        name: sel.name,
        value: sel.value,
        optionCount: sel.options.length,
        firstOpts: opts,
        style: window.getComputedStyle(sel).display,
        visible: sel.offsetParent !== null
    };
}""")
print("State select:", json.dumps(state_info, indent=2))

# Try page.select_option
try:
    result = page.select_option("[name='state.value']", label="Washington", timeout=5000)
    print("select_option result:", result)
    val = page.evaluate("() => document.querySelector('[name=\"state.value\"]')?.value")
    print("After select value:", val)
except Exception as exc:
    print("select_option failed:", str(exc)[:100])

# Try via select element directly (BambooHR might have native select hidden behind button)
try:
    # Use JavaScript to set the select value and trigger React
    result = page.evaluate("""() => {
        const sel = document.getElementById('fab-select359') || document.querySelector('[name="state.value"]');
        if (!sel) return 'NO_SELECT';
        
        // React native setter
        const proto = window.HTMLSelectElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(sel, 'WA');
        else sel.value = 'WA';
        
        sel.dispatchEvent(new Event('change', {bubbles: true}));
        sel.dispatchEvent(new Event('input', {bubbles: true}));
        return 'SET:' + sel.value + ' options=' + sel.options.length;
    }""")
    print("JS set result:", result)
    val = page.evaluate("() => document.querySelector('[name=\"state.value\"]')?.value")
    print("After JS set value:", val)
    
    # Check button text now
    btn_text = page.evaluate("() => document.querySelector('button[aria-label*=\"State\"]')?.innerText || 'N/A'")
    print("State btn text after set:", btn_text)
except Exception as exc:
    print("JS set failed:", str(exc)[:100])

page.close()
