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

    # Check overall form structure and survey form visibility
    r = page.evaluate("""() => {
        const survey = document.querySelector("[data-field-path*='0a2a2426']");
        if (!survey) return {error: "no survey container"};
        const surveyRoot = survey.closest("[data-testid], form, [role=form], .ashby-application-form") || survey.parentElement;
        const rect = survey.getBoundingClientRect();
        const yesnoBtn = document.querySelector("[data-field-path*='4c8e248b'] button");
        const yesnoBtnRect = yesnoBtn ? yesnoBtn.getBoundingClientRect() : null;
        // check for overlapping elements at the yesno button position
        let topEl = null;
        if (yesnoBtnRect) {
            const cx = yesnoBtnRect.left + yesnoBtnRect.width/2;
            const cy = yesnoBtnRect.top + yesnoBtnRect.height/2;
            topEl = document.elementFromPoint(cx, cy);
        }
        return {
            surveyContainerTag: survey.tagName,
            surveyVisible: rect.width > 0 && rect.height > 0,
            surveyInViewport: rect.top >= 0 && rect.bottom <= window.innerHeight,
            surveyRect: {top: Math.round(rect.top), bottom: Math.round(rect.bottom), left: Math.round(rect.left)},
            yesnoBtnRect: yesnoBtnRect ? {top: Math.round(yesnoBtnRect.top), bottom: Math.round(yesnoBtnRect.bottom)} : null,
            yesnoBtnClass: (yesnoBtn || {}).className,
            topElAtBtn: topEl ? topEl.tagName + (topEl.className ? "." + topEl.className.slice(0,40) : "") : null,
            windowHeight: window.innerHeight,
            windowWidth: window.innerWidth,
        };
    }""")
    print("Form structure:", r)

    # Try scrolling to the survey section, then clicking
    try:
        cont = page.query_selector("[data-field-path*='4c8e248b']")
        if cont:
            cont.scroll_into_view_if_needed(timeout=2000)
            page.wait_for_timeout(500)
            for btn in cont.query_selector_all("button"):
                if btn.inner_text().strip() == "Yes":
                    btn.scroll_into_view_if_needed(timeout=2000)
                    page.wait_for_timeout(200)
                    btn.click(timeout=3000)
                    page.wait_for_timeout(500)
                    sv = page.evaluate("""() => {
                        const c = document.querySelector("[data-field-path*='4c8e248b']");
                        const btns = [...c.querySelectorAll("button")];
                        let sv = null;
                        for (const b of btns) {
                            const fk = Object.keys(b).find(k=>k.startsWith("__reactFiber$"));
                            if (!fk) continue;
                            let f=b[fk],d=0;
                            while(f&&d<40){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}
                            if(sv!==null) break;
                        }
                        const yb = c.querySelector("button:nth-child(2)");
                        return {savedValue: sv, firstBtnActive: /_active_|_selected_/.test((c.querySelector("button")||{}).className||""), btnCount: btns.length};
                    }""")
                    print("4c8e248b after scroll+click:", sv)
                    break
    except Exception as e:
        print("Error:", e)
    print("DONE")