import sys; sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
CDP_URL = "http://127.0.0.1:19223"
with sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp(CDP_URL)\n    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n    pages = ctx.pages\n    page = pages[0] if pages else ctx.new_page()
    page.goto("https://jobs.ashbyhq.com/snowflake/86570858-e425-4144-9aef-8838cefd18c3/application", timeout=30000)
    page.wait_for_timeout(5000)

    # Deep probe: check form structure, React state, and what happens when label is clicked
    r = page.evaluate("""() => {
        const cont = document.querySelector("[data-field-path*='0a2a2426']");
        if (!cont) return {error: 'no cont'};
        const radios = [...cont.querySelectorAll("input[type=radio]")];
        const results = radios.map(inp => {
            const fk = Object.keys(inp).find(k=>k.startsWith("__reactFiber$"));
            let sv=null, oc=null, ocStr=null, formCtrl=null;
            if(fk && inp[fk]){
                let f=inp[fk], d=0;
                while(f && d<80){
                    const mp=f.memoizedProps;
                    if(mp){
                        if("savedValue" in mp && sv===null) sv=mp.savedValue;
                        if("onChange" in mp && oc===null){oc=typeof mp.onChange; ocStr=mp.onChange?mp.onChange.toString().slice(0,120):null;}
                        if("name" in mp && formCtrl===null && mp.name) formCtrl=mp.name;
                    }
                    f=f.return; d++;
                }
            }
            const lab=document.querySelector('label[for="'+inp.id+'"]');
            return {
                id_tail: inp.id.slice(-35),
                checked: inp.checked,
                sv, oc, ocStr: (ocStr||'').slice(0,100), formCtrl,
                lab: ((lab||{}).innerText||'').slice(0,40)
            };
        });
        // also check what data-field-path the SURVEY form uses vs app form
        const surveyContainer = cont.closest('[id]') || cont.closest('[class*="survey"]') || cont.parentElement;
        return {
            path: cont.getAttribute('data-field-path'),
            contTag: cont.tagName,
            parentId: (cont.parentElement||{}).id,
            results
        };
    }""")
    print("0a2a2426 deep probe:")
    print("  path:", r.get("path"))
    print("  contTag:", r.get("contTag"))
    print("  parentId:", r.get("parentId"))
    for radio in r.get("results", []):
        print("  radio:", {k: v for k, v in radio.items() if k != 'ocStr'})
        if radio.get('ocStr'):
            print("    onChange:", radio['ocStr'])

    # Now navigate the full form container to understand the multi-form structure
    structure = page.evaluate("""() => {
        // Find all form containers with data-field-path
        const allContainers = [...document.querySelectorAll('[data-field-path]')];
        // Group by UUID prefix
        const prefixes = {};
        for (const c of allContainers) {
            const fp = c.getAttribute('data-field-path') || '';
            const parts = fp.split('_');
            if (parts.length >= 2) {
                const prefix = parts[0];
                if (!prefixes[prefix]) prefixes[prefix] = 0;
                prefixes[prefix]++;
            }
        }
        return {totalContainers: allContainers.length, prefixes};
    }""")
    print("\\nForm structure:", structure)

    # Now check: does clicking the label update the DOM or a React store?
    # Intercept onChange by patching it
    inject_result = page.evaluate("""() => {
        const cont = document.querySelector("[data-field-path*='0a2a2426']");
        if (!cont) return 'no cont';
        const inp = cont.querySelector("input[type=radio]");
        if (!inp) return 'no radio';
        const fk = Object.keys(inp).find(k=>k.startsWith("__reactFiber$"));
        if (!fk) return 'no fiber';
        // Find the onChange handler
        let f = inp[fk], d=0, onChangeFn=null;
        while(f && d<50){
            const mp=f.memoizedProps;
            if(mp && 'onChange' in mp && onChangeFn===null) onChangeFn=mp.onChange;
            f=f.return; d++;
        }
        if (!onChangeFn) return 'no onChange found';
        // Try calling onChange directly with a synthetic event
        try {
            onChangeFn({target: inp, currentTarget: inp, bubbles: true});
            return 'called onChange directly';
        } catch(e) {
            return 'onChange call failed: ' + e.message;
        }
    }""")
    print("\\nDirect onChange call:", inject_result)
    page.wait_for_timeout(500)
    sv_after = page.evaluate("""() => {
        const c = document.querySelector("[data-field-path*='0a2a2426']");
        if (!c) return null;
        const inp = c.querySelector("input[type=radio]");
        if (!inp) return null;
        const fk = Object.keys(inp).find(k=>k.startsWith("__reactFiber$"));
        let sv=null;
        if(fk&&inp[fk]){let f=inp[fk],d=0;while(f&&d<50){const mp=f.memoizedProps;if(mp&&"savedValue" in mp&&sv===null)sv=mp.savedValue;f=f.return;d++;}}
        return {checked:inp.checked, sv};
    }""")
    print("After direct onChange:", sv_after)
    print("DONE")
