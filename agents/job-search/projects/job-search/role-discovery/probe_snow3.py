import sys; sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
CDP_URL = "http://127.0.0.1:19223"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    pages = ctx.pages
    page = pages[0] if pages else ctx.new_page()
    page.goto("https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application", timeout=30000)
    page.wait_for_timeout(5000)
    # click yes for 4c8e248b
    try:
        cont = page.query_selector("[data-field-path*='4c8e248b']")
        if cont:
            for btn in cont.query_selector_all("button"):
                if btn.inner_text().strip() == "Yes":
                    btn.click(timeout=3000)
                    break
            page.wait_for_timeout(400)
            # check savedValue
            sv = page.evaluate("""() => {
                const c = document.querySelector("[data-field-path*='4c8e248b']");
                if (!c) return null;
                const btns = [...c.querySelectorAll("button")];
                let sv = null;
                for (const b of btns) {
                    const fk = Object.keys(b).find(k=>k.startsWith("__reactFiber$"));
                    if (!fk) continue;
                    let f=b[fk],d=0;
                    while(f&&d<40){
                        const mp=f.memoizedProps;
                        if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;
                        f=f.return;d++;
                    }
                    if(sv!==null) break;
                }
                return {active:/_active_|_selected_/.test((c.querySelector("button:first-child")||{}).className||""), savedValue:sv};
            }""")
            print("4c8e248b after click:", sv)
        else:
            print("4c8e248b: no container!")
    except Exception as e:
        print("Error:", e)
    # check 0a2a2426
    try:
        cont2 = page.query_selector("[data-field-path*='0a2a2426']")
        if cont2:
            for lab in cont2.query_selector_all("label"):
                if "U.S. person" in (lab.inner_text() or ""):
                    lab.click(timeout=3000)
                    break
            page.wait_for_timeout(400)
            sv2 = page.evaluate("""() => {
                const c = document.querySelector("[data-field-path*='0a2a2426']");
                if (!c) return null;
                const inp = c.querySelector("input[type=radio]");
                if (!inp) return {error: "no radio"};
                const fk = Object.keys(inp).find(k=>k.startsWith("__reactFiber$"));
                let sv=null;
                if(fk){let f=inp[fk],d=0;while(f&&d<40){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}}
                return {id_tail: inp.id.slice(-30), checked: inp.checked, savedValue: sv};
            }""")
            print("0a2a2426 after label click:", sv2)
        else:
            print("0a2a2426: no container!")
    except Exception as e:
        print("Error:", e)
    print("DONE")