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
    r = page.evaluate("""() => {
        const cont = document.querySelector("[data-field-path*=\"4c8e248b\"]");
        if (!cont) return {error: "no container"};
        const buttons = [...cont.querySelectorAll("button")];
        return {path: cont.getAttribute("data-field-path"), buttons: buttons.map(b => {
            const fk = Object.keys(b).find(k=>k.startsWith("__reactFiber$"));
            let sv=null; if(fk){let f=b[fk],d=0;while(f&&d<30){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}}
            return {text:(b.innerText||"").trim(),active:/_active_|_selected_/.test(b.className||""),savedValue:sv};
        })};
    }""")
    print("4c8e248b BEFORE:", r)

    # Click Yes
    try:
        page.locator("[data-field-path*="4c8e248b"] button").filter(has_text="Yes").first.click(timeout=3000)
        page.wait_for_timeout(400)
    except Exception as e: print("click err:", e)

    r2 = page.evaluate("""() => {
        const cont = document.querySelector("[data-field-path*=\"4c8e248b\"]");
        if (!cont) return {error: "no container"};
        const buttons = [...cont.querySelectorAll("button")];
        return {path: cont.getAttribute("data-field-path"), buttons: buttons.map(b => {
            const fk = Object.keys(b).find(k=>k.startsWith("__reactFiber$"));
            let sv=null; if(fk){let f=b[fk],d=0;while(f&&d<30){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}}
            return {text:(b.innerText||"").trim(),active:/_active_|_selected_/.test(b.className||""),savedValue:sv};
        })};
    }""")
    print("4c8e248b AFTER YES:", r2)

    # Check 0a2a2426 - click label
    try:
        page.locator("[data-field-path*="0a2a2426"] label").filter(has_text="I am a U.S. person").first.click(timeout=3000)
        page.wait_for_timeout(400)
    except Exception as e: print("label click err:", e)

    r3 = page.evaluate("""() => {
        const cont = document.querySelector("[data-field-path*=\"0a2a2426\"]");
        if (!cont) return {error: "no container"};
        return {path: cont.getAttribute("data-field-path"),
            radios: [...cont.querySelectorAll("input[type=radio]")].map(inp=>{
                const fk=Object.keys(inp).find(k=>k.startsWith("__reactFiber$"));
                let sv=null; if(fk){let f=inp[fk],d=0;while(f&&d<30){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}}
                const lab=document.querySelector("label[for=\""+ inp.id +"\"]");
                return {id_tail:inp.id.slice(-25),checked:inp.checked,saved:sv,labText:((lab||{}).innerText||"").trim().slice(0,40)};
            })};
    }""")
    print("0a2a2426 AFTER LABEL CLICK:", r3)
    print("DONE")