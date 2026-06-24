#!/usr/bin/env python3
"""
Discover actual ATS URLs for RemoteOK jobs.
RemoteOK apply URLs are at /l/{id} which open in a new window/redirect.
"""
import time, json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"

JOBS = [
    (3358, "1133393", "PadSplit", "Product Manager"),
    (3359, "1131256", "Automox", "Associate Product Manager"),
    (3360, "1131146", "Lively", "Product Manager"),
    (3361, "1131100", "WorkOS", "Product Manager"),
    (3362, "1130985", "Verse", "Product Manager Energy Storage Controls"),
    (3363, "1130461", "Lavendo", "Technical Product Manager"),
]

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

results = {}

for role_id, rok_id, company, role in JOBS:
    print(f"--- {company}: {role} (ROK {rok_id}) ---")
    
    # Close any extra tabs
    for p in list(ctx.pages):
        try:
            if "remoteok" in p.url or p.url in ("about:blank",):
                p.close()
        except:
            pass
    
    page = ctx.new_page()
    url = f"https://remoteok.com/remote-jobs/{rok_id}"
    
    # Listen for new pages
    new_pages = []
    ctx.on("page", lambda p: new_pages.append(p))
    
    print(f"Loading: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
    except Exception as e:
        print(f"Load error: {e}")
        results[role_id] = {"error": str(e)[:100]}
        page.close()
        continue
    
    # Check if redirected to homepage (blocked)
    final_url = page.url
    print(f"Final URL: {final_url}")
    
    if "remoteok.com" in final_url and "/remote-jobs/" in final_url:
        # We're on the job page - look for Apply button
        apply_info = page.evaluate("""() => {
            // Look for apply button/link
            const applyBtns = [...document.querySelectorAll('a, button')].filter(el => {
                const t = (el.innerText||'').toLowerCase();
                return t.includes('apply') || t.includes('apply now') || t.includes('apply for job');
            });
            const applyLinks = [...document.querySelectorAll('a[href]')].filter(a => {
                const h = (a.href||'').toLowerCase();
                return h.includes('/l/') || (a.href && !a.href.includes('remoteok.com') && a.href.startsWith('http'));
            });
            return {
                applyBtns: applyBtns.map(b => ({tag:b.tagName, text:(b.innerText||'').trim().slice(0,40), href:b.href||null})).slice(0,5),
                applyLinks: applyLinks.map(a => ({text:(a.innerText||'').trim().slice(0,40), href:a.href})).slice(0,5)
            };
        }""")
        print(f"Apply buttons: {apply_info['applyBtns']}")
        print(f"Apply links: {apply_info['applyLinks']}")
        
        # Try clicking the apply link to discover destination
        apply_link = None
        for info in apply_info.get("applyBtns", []) + apply_info.get("applyLinks", []):
            href = info.get("href")
            if href and "/l/" in href:
                apply_link = href
                break
        
        if apply_link:
            print(f"Trying apply link: {apply_link}")
            # Listen for new window
            pre_count = len(ctx.pages)
            try:
                with ctx.expect_page(timeout=8000) as new_page_info:
                    page.evaluate(f"() => window.open('{apply_link}', '_blank')")
                new_page = new_page_info.value
                new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)
                dest_url = new_page.url
                print(f"Destination URL: {dest_url}")
                results[role_id] = {"apply_url": dest_url, "rok_id": rok_id}
                new_page.close()
            except Exception as e:
                print(f"Popup failed: {e}")
                # Try direct navigation
                dest_page = ctx.new_page()
                dest_page.goto(apply_link, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                dest_url = dest_page.url
                print(f"Direct nav URL: {dest_url}")
                results[role_id] = {"apply_url": dest_url, "rok_id": rok_id}
                dest_page.close()
    else:
        print("Redirected or blocked")
        # Try direct API approach
        results[role_id] = {"error": f"redirected to {final_url[:60]}"}
    
    page.close()
    time.sleep(1)

print("" + "="*50)
print("RESULTS:")
for role_id, info in results.items():
    print(f"  {role_id}: {json.dumps(info)}")
