import json
from playwright.sync_api import sync_playwright
URL = "https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850/application"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    pg = b.contexts[0].new_page()
    pg.goto(URL, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(4500)
    info = pg.evaluate(r"""()=>{
      const out=[];
      document.querySelectorAll('[data-field-path]').forEach(fe=>{
        const lbl=(fe.querySelector('label')||{}).innerText||(fe.innerText||'').slice(0,40);
        if(!/sponsor/i.test(lbl))return;
        out.push({
          fp: fe.getAttribute('data-field-path'),
          radios: fe.querySelectorAll('input[type=radio]').length,
          inputs: fe.querySelectorAll('input').length,
          sel: fe.querySelectorAll('select').length,
          btn: fe.querySelectorAll('button').length,
          combobox: fe.querySelectorAll('[role=combobox]').length,
          radiogroup: fe.querySelectorAll('[role=radiogroup]').length,
          checkedRadios: [...fe.querySelectorAll('input[type=radio]')].filter(r=>r.checked).map(r=>r.value||r.id),
          html: fe.innerHTML.slice(0,600)
        });
      });
      return out;
    }""")
    print(json.dumps(info, indent=2)[:3000])
    b.close()
