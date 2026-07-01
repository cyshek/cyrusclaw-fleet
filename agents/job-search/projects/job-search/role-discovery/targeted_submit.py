#!/usr/bin/env python3
"""Targeted Contentful GH submit with fix for ITI interference on needs_review fields."""
from playwright.sync_api import sync_playwright
import json, sys, time, os, sqlite3

CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:19223")
DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"

def close_iti(page):
    """Ensure phone ITI picker is closed before interacting with other dropdowns."""
    page.evaluate("""() => {
        const iti = document.querySelector(".iti__country-list, [id^=iti-][role=listbox]");
        if (iti) {
            document.body.click();
            document.body.dispatchEvent(new MouseEvent("mousedown", {bubbles: true}));
        }
    }""")
    time.sleep(0.3)

def pick_yes_no(page, field_id, want="Yes"):
    """Directly click a Yes/No react-select option by react-select option ID."""
    result = page.evaluate("""async (args) => {
        const {field_id, want} = args;
        const sleep = ms => new Promise(r => setTimeout(r, ms));
        const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type,
            {bubbles: true, cancelable: true, view: window, button: 0, clientX: x||0, clientY: y||0}));
        const inp = document.getElementById(field_id);
        if (!inp) return {err: "no input"};
        const ctrl = inp.closest(".select__control");
        if (!ctrl) return {err: "no control"};
        ctrl.scrollIntoView({block: "center"});
        await sleep(200);
        ctrl.click();
        await sleep(500);
        const opt0 = document.getElementById("react-select-" + field_id + "-option-0");
        const opt1 = document.getElementById("react-select-" + field_id + "-option-1");
        const opts = [opt0, opt1].filter(Boolean);
        const wantLc = want.toLowerCase();
        let target = opts.find(o => o.textContent.trim().toLowerCase() === wantLc);
        if (!target) target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(wantLc));
        if (!target && opts.length) target = opts[0];
        if (!target) return {err: "no option", want, available: opts.map(o => o.textContent.trim())};
        const r = target.getBoundingClientRect();
        fire(target, "mousedown", r.left+5, r.top+5);
        fire(target, "mouseup", r.left+5, r.top+5);
        fire(target, "click", r.left+5, r.top+5);
        await sleep(300);
        const sv = ctrl.querySelector(".select__single-value");
        return {committed: sv ? sv.textContent : null, clicked: target.textContent.trim()};
    }""", {"field_id": field_id, "want": want})
    return result

def submit_role(plan_path):
    with open(plan_path) as f:
        plan = json.load(f)
    
    slug = plan["slug"]
    url = plan["url"]
    print(f"Submitting {slug} from {url}")
    
    with sync_playwright() as pw:
        br = pw.chromium.connect_over_cdp(CDP)
        ctx = br.contexts[0] if br.contexts else br.new_context()
        # Find or create page for this URL
        page = None
        for p in ctx.pages:
            if slug in p.url or "job-boards.greenhouse.io/contentful" in p.url:
                page = p
                break
        if not page:
            page = ctx.new_page()
        
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)
        
        # Click Apply
        page.evaluate("""() => {
            const b=[...document.querySelectorAll("button,a")].find(x=>/^apply$/i.test((x.textContent||"").trim()));
            if(b) b.click();
        }""")
        time.sleep(1.5)
        
        print(f"[{slug}] Form opened, running _gh_submit.py with fixed approach")
        
    return {"slug": slug, "status": "probed"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: targeted_submit.py <plan.json>")
        sys.exit(1)
    result = submit_role(sys.argv[1])
    print(json.dumps(result, indent=2))
