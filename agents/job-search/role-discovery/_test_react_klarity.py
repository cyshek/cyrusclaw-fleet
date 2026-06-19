import json
from playwright.sync_api import sync_playwright
URL = "https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850/application"
FP = "5658b589-ea7a-4582-b9c7-92a4c5809fbd"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    pg = b.contexts[0].new_page()
    pg.goto(URL, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    # Method: real Playwright trusted click on the option-0 radio input by id
    rid = pg.evaluate(r"""(fp)=>{
      const fe=[...document.querySelectorAll('[data-field-path]')].find(e=>e.getAttribute('data-field-path')===fp);
      const r=fe.querySelector('input[type=radio]');
      return r? r.id : null;
    }""", FP)
    print("radio0 id:", rid)
    try:
        pg.locator(f"#{rid}").click(timeout=4000, force=True)
        print("playwright click OK")
    except Exception as e:
        print("playwright click FAIL:", e)
    pg.wait_for_timeout(600)
    # Also try invoking React onChange via fiber props on the input
    react_res = pg.evaluate(r"""(rid)=>{
      const el=document.getElementById(rid);
      if(!el)return{err:'no-el'};
      const key=Object.keys(el).find(k=>k.startsWith('__reactProps$'));
      if(!key)return{noprops:true, checked: el.checked};
      const props=el[key];
      let fired=false;
      try{ if(props.onChange){ props.onChange({target:el, currentTarget:el, type:'change'}); fired=true; } }catch(e){ return {err:String(e)}; }
      return {fired, checked: el.checked};
    }""", rid)
    print("REACT onChange:", json.dumps(react_res))
    pg.wait_for_timeout(600)
    chk = pg.evaluate(r"""(fp)=>{
      const fe=[...document.querySelectorAll('[data-field-path]')].find(e=>e.getAttribute('data-field-path')===fp);
      const radios=[...fe.querySelectorAll('input[type=radio]')];
      return {checkedIdx: radios.findIndex(r=>r.checked), allChecked: radios.map(r=>r.checked)};
    }""", FP)
    print("FINAL READBACK:", json.dumps(chk))
    b.close()
