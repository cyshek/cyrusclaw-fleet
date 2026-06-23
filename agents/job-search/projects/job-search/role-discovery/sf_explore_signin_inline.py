import sys, time, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import json
_PI_PATH = os.path.join(HERE, "..", "personal-info.json")
with open(_PI_PATH) as f:\n    _PI = json.load(f)\n\nfrom playwright.sync_api import sync_playwright\n\ndef main():
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    
    apply_url = (
        "https://career8.successfactors.com/career?company=aosmith"
        "&career_ns=job_save&career_job_req_id=27523"
        "&navBarLevel=JOB_SEARCH&career_os=job_listing"
        "&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    )
    page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
    print("URL:", page.url)
    print("Title:", page.title())
    
    links = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].map(a => ({
            text: a.innerText.trim().substring(0, 100),
            href: a.href,
            id: a.id
        })).filter(l => l.text || l.href);
    }""")
    print("\n=== ALL LINKS ===")
    for l in links:
        print(f"  [{l['id']}] {l['text']!r} -> {l['href']}")
    
    forms = page.evaluate("""() => {
        return [...document.querySelectorAll('form')].map(f => ({
            id: f.id,
            action: f.action,
            method: f.method,
            fields: [...f.querySelectorAll('input,select,textarea')].map(el => ({
                name: el.name, id: el.id, type: el.type or '', value: el.value.substring(0, 50)
            }))
        }));
    }""")
    print("\n=== FORMS ===")
    for f in forms:
        print(f"  form id={f['id']} action={f['action']}")
        for fld in f['fields']:
            print(f"    name={fld['name']} id={fld['id']} type={fld['type']} value={fld['value']!r}")
    
    page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug/signin_inline.png")
    print("\nDone. Check screenshot at .sf-debug/signin_inline.png")
    
    page.close()
    pw.stop()

main()
