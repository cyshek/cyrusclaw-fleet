#!/usr/bin/env python3
"""Debug BambooHR state portal."""
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

# Click the State button
page.evaluate("() => document.querySelector('button[aria-label*=\"State\"]')?.click()")
time.sleep(1.5)

# Now inspect full DOM for anything that looks like a state dropdown list
portal = page.evaluate("""() => {
    // Look in body's direct children for portal
    const bodychild = [...document.body.children];
    const portals = bodychild.filter(c => {
        const cls = c.className || '';
        return cls.includes('portal') || cls.includes('Portal') || cls.includes('Menu') || 
               cls.includes('overlay') || cls.includes('dropdown') || cls.includes('Overlay');
    });
    
    // Also check all visible elements
    const allVisible = [...document.querySelectorAll('*')].filter(e => {
        return e.offsetParent !== null && e.children.length > 3 && 
               e.querySelectorAll('button, [role=option], [role=menuitem], li').length > 3;
    });
    
    // Specifically look for menuitem/option roles
    const menuitems = [...document.querySelectorAll('[role=menuitem], [role=option]')];
    const visibleItems = menuitems.filter(i => i.offsetParent !== null);
    
    return {
        bodyChildCount: bodychild.length,
        portals: portals.map(p => ({tag:p.tagName, cls:p.className.slice(0,60)})),
        allVisibleContainers: allVisible.map(e => ({tag:e.tagName, cls:e.className.slice(0,40), childCount:e.children.length})).slice(0,5),
        menuItemCount: menuitems.length,
        visibleMenuItems: visibleItems.map(i => i.innerText.trim().slice(0,20)).slice(0,8),
        // Dump raw HTML of any visible menus
        rawMenuHTML: allVisible.map(e => e.outerHTML.slice(0,100)).slice(0,3)
    };
}""")
print("Portal:", json.dumps(portal, indent=2))

# Also snapshot the raw body for visible fab-Select
snapshot = page.evaluate("""() => {
    const divs = [...document.querySelectorAll('div')].filter(d => {
        return d.offsetParent !== null && 
               d.querySelectorAll('button').length > 5 &&
               d.style.position === 'absolute' || 
               window.getComputedStyle(d).position === 'absolute' ||
               window.getComputedStyle(d).position === 'fixed';
    });
    return divs.map(d => ({
        cls: d.className.slice(0,60),
        pos: window.getComputedStyle(d).position,
        btns: [...d.querySelectorAll('button')].map(b => b.innerText.slice(0,15)).slice(0,5)
    })).slice(0,5);
}""")
print("\nAbsolute divs:", json.dumps(snapshot, indent=2))

# Try locating with Playwright's locator
visible_items = page.locator('[role="menuitem"]:visible, [role="option"]:visible')
count = visible_items.count()
print(f"\nVisible menuitem/option count: {count}")
for i in range(min(count, 5)):
    print(f"  {i}: {visible_items.nth(i).inner_text()[:30]}")

page.close()
