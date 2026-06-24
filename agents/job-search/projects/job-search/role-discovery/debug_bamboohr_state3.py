#!/usr/bin/env python3
"""Final check - BambooHR state menu after click."""
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

# Click State button using Playwright click (not JS)
state_btn = page.locator('button[aria-label*="State"]').first
print("State btn count:", state_btn.count())
state_btn.click(timeout=5000)
time.sleep(1.5)

# Now check for the opened menu
result = page.evaluate("""() => {
    // Find by data-menu-id association or just look at what's visible
    const stateBtn = document.querySelector('button[aria-label*="State"]');
    const menuId = stateBtn ? stateBtn.getAttribute('data-menu-id') : null;
    const menu = menuId ? document.getElementById(menuId) : null;
    
    // Check aria-expanded
    const expanded = stateBtn ? stateBtn.getAttribute('aria-expanded') : null;
    
    // Check for fab-Menu elements
    const fabMenus = [...document.querySelectorAll('[class*="fab-Menu"], [id*="fab-menu"]')];
    const optLists = [...document.querySelectorAll('ul, [role="listbox"]')].filter(e => e.offsetParent !== null);
    
    return {
        menuId,
        expanded,
        menuFound: !!menu,
        menuChildCount: menu ? menu.children.length : 0,
        menuHTML: menu ? menu.outerHTML.slice(0,500) : null,
        fabMenuCount: fabMenus.length,
        fabMenus: fabMenus.map(m => ({id:m.id, cls:m.className.slice(0,50), children:m.children.length})),
        visLists: optLists.map(l => ({tag:l.tagName, cls:l.className.slice(0,40), children:l.children.length})).slice(0,5)
    };
}""")
print(json.dumps(result, indent=2))

# Try type searching
print("\nTrying type to search:")
state_btn2 = page.locator('button[aria-label*="State"]').first
state_btn2.click()
time.sleep(0.5)
# After click, type to filter
page.keyboard.type("Washington")
time.sleep(0.5)

filtered = page.evaluate("""() => {
    const menu = document.querySelector('[id^="fab-menu"]');
    const items = menu ? [...menu.querySelectorAll('button, [role="option"], [role="menuitem"], li')] : [];
    return {
        found: !!menu,
        menuId: menu ? menu.id : null,
        itemCount: items.length,
        items: items.map(i => i.innerText.slice(0,20)).slice(0,8)
    };
}""")
print("After typing:", json.dumps(filtered, indent=2))

page.close()
