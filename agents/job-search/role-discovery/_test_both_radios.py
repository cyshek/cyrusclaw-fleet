import json, time
from playwright.sync_api import sync_playwright
import importlib.util, pathlib
HERE = pathlib.Path(".").resolve()
spec = importlib.util.spec_from_file_location("_ashby_runner", HERE / "_ashby_runner.py")
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
plan = json.load(open("output/inline-plan-klarity-4843b6cd-405e-412f-8261-d1a2d6acd850.json"))
FP = "5658b589-ea7a-4582-b9c7-92a4c5809fbd"
TARGET = "I am a US Citizen / Green Card Holder"
RELOC_FP = None
for r in plan.get("radios", []):
    if "office" in (r.get("label") or "").lower() or "relocat" in (r.get("label") or "").lower():
        RELOC_FP = r.get("name", "").split("_", 1)[1] if "_" in r.get("name", "") else r.get("name")
print("reloc fp tail:", RELOC_FP)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    pg = b.contexts[0].new_page()
    # capture submit POSTs
    posts = []
    def on_resp(r):
        try:
            if "graphql" in r.url.lower() or "application" in r.url.lower():
                bd = r.text()
                if "submitApplication" in bd or "FormSubmit" in bd or "FormRender" in bd:
                    posts.append(bd[:500])
        except Exception:
            pass
    pg.on("response", on_resp)
    pg.goto("https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850/application", timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(4500)
    print("just probing whether radio survives to a manual submit; NOT a real submit test")
    res = pg.evaluate(ar._RADIO_FORCE_COMMIT_IN_CONTAINER_JS, {"field_paths": [FP], "target": TARGET})
    print("sponsor commit:", json.dumps(res))
    # check both radios state
    st = pg.evaluate(r"""()=>{
      const out={};
      document.querySelectorAll('[data-field-path]').forEach(fe=>{
        const lbl=(fe.querySelector('label')||{}).innerText||'';
        if(/sponsor|office|relocat/i.test(lbl)){
          const radios=[...fe.querySelectorAll('input[type=radio]')];
          out[lbl.slice(0,30)]={checkedIdx:radios.findIndex(r=>r.checked), n:radios.length};
        }
      });
      return out;
    }""")
    print("BOTH RADIO STATES:", json.dumps(st, indent=2))
    b.close()
