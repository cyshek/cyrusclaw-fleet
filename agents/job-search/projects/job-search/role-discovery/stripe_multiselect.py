import time, sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7594208", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    # Open the multiselect q63282213
    open_result = page.evaluate("""() => {
        const inp = document.getElementById('question_63282212');
        if (!inp) return 'no q63282212';
        const ctrl = inp.closest('.select__control');
        if (!ctrl) return 'no ctrl for q63282212';
        ctrl.scrollIntoView({block:'center'});
        const r = ctrl.getBoundingClientRect();
        const fire = (el,t) => el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:r.left+5,clientY:r.top+5}));
        fire(ctrl,'mousedown'); fire(ctrl,'mouseup'); fire(ctrl,'click');
        return 'opened';
    }""")
    print("Open q63282212:", open_result)
    time.sleep(0.5)
    # Now look for the multi-select question_63282213
    multi_info = page.evaluate("""() => {
        // Find the container for q63282213
        const inputs = [...document.querySelectorAll('[id^="question_63282213"]')];
        return inputs.slice(0, 5).map(el => {
            const label = el.closest('li, label, div')?.textContent?.trim()?.slice(0,50) || '';
            return {id: el.id, type: el.type, checked: el.checked, label};
        });
    }""")
    print("Multiselect inputs:", json.dumps(multi_info, indent=2))
    page.keyboard.press("Escape")
    time.sleep(0.3)
    # Now open the multi question directly
    # The multiselect container
    container_info = page.evaluate("""() => {
        const labels = [...document.querySelectorAll('label')];
        const target = labels.find(l => l.textContent.includes('anticipate working'));
        if (!target) return {err: 'no label found'};
        const container = target.closest('div, section, fieldset');
        if (!container) return {err: 'no container'};
        const inp = container.querySelector('input');
        return {label_text: target.textContent.slice(0,80), inp_id: inp ? inp.id : 'none', container_tag: container.tagName};
    }""")
    print("Multiselect container:", json.dumps(container_info))
    page.close()
    br.close()
