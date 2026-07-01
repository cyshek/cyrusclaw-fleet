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
    
    if pw_pg:
        print("Password page:", pw_pg.url[:80])
        pw_inp = pw_pg.query_selector("input[type=password]")
        if pw_inp:
            # Check current state
            val = pw_inp.evaluate("el => el.value")
            print("Current value length:", len(val))
            react_fiber = pw_inp.evaluate("""el => {
                const keys = Object.keys(el);
                const fk = keys.find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
                if (!fk) return null;
                const fiber = el[fk];
                if (!fiber) return null;
                const pending = fiber.pendingProps;
                return {
                    type: pending ? pending.type : null,
                    valueFromProps: pending ? pending.value : null,
                    onChange: pending ? typeof pending.onChange : null
                };
            }""")
            print("React fiber:", react_fiber)
            # Try filling via keyboard simulation  
            pw_inp.click()
            pw_inp.select_all()
            pw_pg.keyboard.press("Control+a")
            pw_pg.keyboard.type("JobSearch2026!amd", delay=30)
            time.sleep(0.5)
            val2 = pw_inp.evaluate("el => el.value")
            print("After keyboard type length:", len(val2))
            pw_pg.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug/pw-filled-state.png")
        else:
            print("No password input found")
    else:
        print("No password page")
