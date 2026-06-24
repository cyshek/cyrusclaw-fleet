#!/usr/bin/env python3
"""Check RemoteOK jobs via browser to get actual apply URLs."""
import time, json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"

JOBS = {
    3358: "1133393",
    3359: "1131256", 
    3360: "1131146",
    3361: "1131100",
    3362: "1130985",
    3363: "1130461",
}

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

results = {}

for role_id, rok_id in JOBS.items():
    # Close remoteok tabs
    for p in list(ctx.pages):
        try:
            if "remoteok" in p.url:
                p.close()
        except:
            pass
    
    page = ctx.new_page()
    
    # Track all network requests
    tracked_urls = []
    def on_request(req):
        u = req.url
        if "remoteok.com" not in u or "/l/" in u:
            tracked_urls.append(u[:120])
    page.on("request", on_request)
    
    # Also track new pages
    new_pages_seen = []
    def on_new_page(p):
        new_pages_seen.append(p)
    ctx.on("page", on_new_page)
    
    url = f"https://remoteok.com/remote-jobs/{rok_id}"
    print(f"\n=== ROK {rok_id} (role {role_id}) ===")
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(1.5)
        
        final = page.url
        print(f"URL: {final}")
        
        if "remoteok.com/l/" in final or "404" in page.title().lower():
            print("  -> 404 or expired")
            results[role_id] = "EXPIRED"
            page.close()
            continue
        
        # Get apply URL from page
        apply_url = page.evaluate("""() => {
            // Look for apply URL in job data
            const scripts = [...document.querySelectorAll('script')];
            for (const s of scripts) {
                const t = s.textContent || '';
                if (t.includes('apply_url') || t.includes('applyUrl')) {
                    const m = t.match(/"apply_url":\s*"([^"]+)"/);
                    if (m) return m[1];
                }
            }
            // Look for direct apply link
            const applyBtns = [...document.querySelectorAll('a')].filter(a => {
                const h = a.href || '';
                return h.includes('remoteok.com/l/') || 
                       (h.startsWith('http') && !h.includes('remoteok.com'));
            });
            if (applyBtns.length) return applyBtns[0].href;
            return null;
        }""")
        
        print(f"  apply_url from page: {apply_url}")
        
        if apply_url and "/l/" in apply_url:
            # Follow the /l/ link to get actual destination
            tracked_urls.clear()
            new_pages_seen.clear()
            
            # Use fetch to check what /l/ redirects to
            dest = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('{apply_url}', {{method:'HEAD', redirect:'follow'}});
                    return r.url;
                }} catch(e) {{
                    return 'FETCH_ERR:' + e.message;
                }}
            }}""")
            print(f"  /l/ dest (fetch HEAD): {dest}")
            
            if dest and "remoteok.com" not in dest and dest.startswith("http"):
                results[role_id] = dest
            else:
                # Try window.open interception
                page.evaluate(f"""() => {{
                    let orig = window.open;
                    window._capturedUrl = null;
                    window.open = function(url, ...args) {{
                        window._capturedUrl = url;
                        return null;
                    }};
                    // Click apply button
                    const btn = document.querySelector('a[href="{apply_url}"]');
                    if (btn) btn.click();
                    window.open = orig;
                }}""")
                time.sleep(0.5)
                captured = page.evaluate("() => window._capturedUrl")
                print(f"  window.open captured: {captured}")
                
                if captured and "remoteok.com" not in captured:
                    results[role_id] = captured
                else:
                    results[role_id] = f"LOOPBACK:{apply_url}"
        elif apply_url and not apply_url.startswith("https://remoteok.com"):
            results[role_id] = apply_url
        else:
            results[role_id] = "NO_APPLY_URL"
    except Exception as exc:
        print(f"  ERROR: {exc}")
        results[role_id] = f"ERROR:{str(exc)[:60]}"
    
    page.close()
    time.sleep(1)

print("\n=== RESULTS ===")
for role_id, dest in results.items():
    print(f"  {role_id}: {dest}")
