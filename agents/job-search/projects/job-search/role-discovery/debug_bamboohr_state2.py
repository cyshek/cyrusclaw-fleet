#!/usr/bin/env python3
"""Debug BambooHR fab-SelectToggle interaction."""
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

# Inspect the State control HTML
html = page.evaluate("""() => {
    const stateBtn = document.querySelector('button[aria-label*="State"]');
    if (!stateBtn) return 'NO BTN';
    // Get parent 5 levels up
    let p = stateBtn;
    for (let i = 0; i < 6; i++) p = p.parentElement;
    return p ? p.outerHTML.slice(0, 1500) : 'NO PARENT';
}""")
print("State control HTML:", html[:800])

# Also try interacting with the select using Playwright's select_option
# The native select might need to be revealed
print("\nAttempting native select interaction...")
state_info = page.evaluate("""() => {
    const sel = document.getElementById('fab-select359');
    if (!sel) return null;
    // Try to get its options loaded (some BambooHR versions load lazily)
    const parent = sel.parentElement;
    return {
        tag: sel.tagName,
        options_count: sel.options.length,
        parentHTML: parent ? parent.outerHTML.slice(0, 400) : null,
        style: window.getComputedStyle(sel).display,
        zIndex: window.getComputedStyle(sel).zIndex
    };
}""")
print("Select info:", json.dumps(state_info, indent=2))

# Check if clicking the button expands a list in the fab-SelectToggle structure
page.evaluate("() => document.querySelector('button[aria-label*=\"State\"]')?.click()")
time.sleep(1.5)

expanded = page.evaluate("""() => {
    // Look for any expanded list after clicking
    const everything = [...document.querySelectorAll('*')].filter(e => e.offsetParent !== null);
    const lists = everything.filter(e => {
        const tag = e.tagName;
        const cls = e.className || '';
        return (tag === 'UL' || tag === 'OL' || 
                cls.includes('list') || cls.includes('List') || 
                cls.includes('options') || cls.includes('Options') ||
                cls.includes('dropdown') || cls.includes('Dropdown') ||
                cls.includes('menu') || cls.includes('Menu')) &&
               e.children.length > 2;
    });
    const stateSection = document.querySelector('.fab-SelectToggle--open, [aria-expanded="true"], .fab-FormField--focused .fab-SelectToggle');
    return {
        listCount: lists.length,
        lists: lists.map(l => ({tag:l.tagName, cls:l.className.slice(0,60), children:l.children.length})).slice(0,5),
        stateSection: stateSection ? stateSection.className.slice(0,80) : null,
        // Look at what classes changed on state button
        stateBtnClasses: (document.querySelector('button[aria-label*="State"]') || {className:''}).className.slice(0,80)
    };
}""")
print("\nAfter click:", json.dumps(expanded, indent=2))

# Check the actual fab-SelectToggle source - maybe there's a listbox
listbox = page.evaluate("""() => {
    const lbs = [...document.querySelectorAll('[role="listbox"]')];
    const visLbs = lbs.filter(l => l.offsetParent !== null);
    return {
        total: lbs.length,
        visible: visLbs.length,
        visibleContent: visLbs.map(l => l.outerHTML.slice(0,200))
    };
}""")
print("\nListboxes:", json.dumps(listbox, indent=2))

page.close()
