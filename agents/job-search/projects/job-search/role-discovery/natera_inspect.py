"""
Inspect Natera form DOM to find multi_value_single_select elements.
"""
import json, time, sys, os
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright

CDP_URL = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:18800')

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(30000)
    
    page.goto('https://job-boards.greenhouse.io/natera/jobs/6099223004', wait_until='domcontentloaded', timeout=30000)
    time.sleep(2)
    
    # Click Apply
    apply_btn = page.query_selector('a:has-text("Apply"), button:has-text("Apply")')
    if apply_btn:
        apply_btn.click()
        time.sleep(2)
    
    # Inspect the form for multi_value_single_select fields
    result = page.evaluate("""()=>{
        // Find question_19071377004 (authorized to work) area
        const qIds = [
            'question_19071374004',  // 18+
            'question_19071375004',  // prev worked at natera
            'question_19071377004',  // authorized
            'question_19071378004',  // sponsorship
            'question_19071379004',  // non-compete
            'question_19071382004',  // state
        ];
        const results = {};
        for (const qid of qIds) {
            // Try direct ID
            const el = document.getElementById(qid);
            if (el) {
                results[qid] = {found_by_id: true, tag: el.tagName, type: el.type, value: el.value};
            } else {
                // Try inputs with name
                const inputs = [...document.querySelectorAll(`input[name="${qid}"]`)];
                const selects = [...document.querySelectorAll(`select[name="${qid}"]`)];
                const textareas = [...document.querySelectorAll(`textarea[name="${qid}"]`)];
                
                results[qid] = {
                    found_by_id: false,
                    inputs: inputs.map(i => ({type: i.type, value: i.value, id: i.id, checked: i.checked})),
                    selects: selects.map(s => ({value: s.value, opts: [...s.options].map(o=>({v:o.value, t:o.text})).slice(0,5)})),
                    textareas: textareas.length
                };
                
                // Try data-field-path attribute
                const fieldEl = document.querySelector(`[data-field-path="${qid}"]`) || 
                                 document.querySelector(`[name="${qid}"]`);
                if (fieldEl) {
                    results[qid].data_field_path = {
                        tag: fieldEl.tagName,
                        outerHTML: fieldEl.outerHTML.slice(0, 300)
                    };
                }
            }
        }
        
        // Also find all elements with IDs matching question_*
        const questionEls = [...document.querySelectorAll('[id^="question_"]')];
        results._question_els = questionEls.map(e => ({
            id: e.id, tag: e.tagName, type: e.type || null, value: e.value || null, 
            outerHTML: e.outerHTML.slice(0, 100)
        }));
        
        return JSON.stringify(results);
    }""")
    data = json.loads(result)
    print(json.dumps(data, indent=2))
    page.close()
