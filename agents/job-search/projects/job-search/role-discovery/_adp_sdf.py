#!/usr/bin/env python3
"""Probe sdf-select-simple interaction: open #question_3 (VISA), read options, structure."""
import time, json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]
page = None
for p in ctx.pages:
    if "workforcenow.adp.com" in p.url:
        page = p
        break
print("attached:", page.url[:110])

# Inspect the sdf-select-simple internal structure (shadow DOM?)
struct = page.evaluate(r"""
() => {
  const el=document.getElementById('question_3');
  if(!el) return {found:false};
  const info={found:true, tag:el.tagName, attrs:{}, hasShadow:!!el.shadowRoot, innerHTML:el.innerHTML.slice(0,300)};
  for(const a of el.attributes) info.attrs[a.name]=a.value.slice(0,40);
  // sdf components often expose options via attribute or child <sdf-select-option> / property
  info.childTags=[...el.children].map(c=>c.tagName);
  // try reading a 'options' property
  try{ info.optionsProp = JSON.stringify(el.options||el.value||null).slice(0,200);}catch(e){info.optionsProp='err';}
  if(el.shadowRoot){
    info.shadowHTML=el.shadowRoot.innerHTML.slice(0,400);
    info.shadowControls=[...el.shadowRoot.querySelectorAll('button,input,[role=button],select')].map(c=>({tag:c.tagName,role:c.getAttribute('role'),txt:(c.innerText||'').slice(0,20)}));
  }
  return info;
}
""")
print("STRUCT #question_3:", json.dumps(struct, indent=1)[:1400])

# Try clicking it to open the dropdown and capture options (portal-enabled -> options render in a portal at body level)
try:
    q3 = page.locator("#question_3")
    q3.scroll_into_view_if_needed(timeout=2000)
    q3.click(timeout=3000)
    print("clicked #question_3")
    time.sleep(1.5)
    opts = page.evaluate(r"""
    () => {
      // portal options often [role=option] or sdf-select-simple-option anywhere
      const o=[...document.querySelectorAll('[role=option],sdf-select-simple-option,sdf-select-option,li[role=option],.sdf-select-option')];
      return o.filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim().slice(0,40)).slice(0,15);
    }
    """)
    print("VISA dropdown options:", opts)
except Exception as exc:
    print("click exc:", str(exc)[:120])

print("[done]")
