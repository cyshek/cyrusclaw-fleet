from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    pw_pg = None
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "login.icims.com/u/login/password" in (pg.url or ""):
                pw_pg = pg; break
        if pw_pg: break
    
    if not pw_pg:
        print("No password page")
    else:
        print("Password page:", pw_pg.url[:80])
        pw_inp = pw_pg.query_selector("input[type=password]")
        if not pw_inp:
            print("No password input")
        else:
            # Use real keyboard type
            pw_inp.click()
            time.sleep(0.2)
            # Select all and delete any existing content
            pw_pg.keyboard.press("Control+a")
            pw_pg.keyboard.press("Delete")
            time.sleep(0.1)
            # Type with real keystrokes
            pw_pg.keyboard.type("JobSearch2026!amd", delay=50)
            time.sleep(0.5)
            val = pw_inp.evaluate("el => el.value")
            print(f"After keyboard.type: len={len(val)} val={val[:5]}...")
            
            pw_pg.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug/pw-keyboard-type.png")
            
            # Now click LOG IN
            btn = pw_pg.query_selector("button[type=submit],button[name=action]")
            if btn:
                btn.click()
                time.sleep(6)
                print(f"After LOG IN, URL: {pw_pg.url[:80]}")
                pw_pg.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug/pw-after-login.png")
                txt = pw_pg.evaluate("()=>document.body.innerText.slice(0,200)")
                print(f"Body: {txt[:150]}")
            else:
                print("No LOG IN button")
