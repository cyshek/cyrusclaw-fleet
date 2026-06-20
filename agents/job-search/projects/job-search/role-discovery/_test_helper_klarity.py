import json
from playwright.sync_api import sync_playwright
import importlib.util, pathlib
HERE = pathlib.Path(".").resolve()
spec = importlib.util.spec_from_file_location("_ashby_runner", HERE / "_ashby_runner.py")
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)

URL = "https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850/application"
FP = "5658b589-ea7a-4582-b9c7-92a4c5809fbd"
TARGET = "I am a US Citizen / Green Card Holder"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    pg = b.contexts[0].new_page()
    pg.goto(URL, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    # run my helper
    res = pg.evaluate(ar._RADIO_FORCE_COMMIT_IN_CONTAINER_JS, {"field_paths": [FP], "target": TARGET})
    print("HELPER RESULT:", json.dumps(res))
    pg.wait_for_timeout(800)
    # read back which radio is checked + React-visible value
    chk = pg.evaluate(r"""(fp)=>{
      const fe=[...document.querySelectorAll('[data-field-path]')].find(e=>e.getAttribute('data-field-path')===fp);
      if(!fe)return{err:'no-fe'};
      const radios=[...fe.querySelectorAll('input[type=radio]')];
      return {
        checkedIdx: radios.findIndex(r=>r.checked),
        checkedVal: (radios.find(r=>r.checked)||{}).value,
        labels: [...fe.querySelectorAll('label')].map(l=>l.innerText).filter(Boolean),
        allChecked: radios.map(r=>r.checked)
      };
    }""", FP)
    print("READBACK:", json.dumps(chk, indent=2))
    b.close()
