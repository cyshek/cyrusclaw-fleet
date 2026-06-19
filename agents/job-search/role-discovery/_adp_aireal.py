import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Ensure salary text filled (required)
ds=page.locator("#desiredSalaryId"); ds.scroll_into_view_if_needed(timeout=2000)
if (ds.input_value() or "").strip() in ("","0.00"):
    ds.click(timeout=2500); ds.press("Control+a"); ds.press("Delete"); page.keyboard.type("150000",delay=50); page.keyboard.press("Tab"); time.sleep(0.5)
print("salary:", ds.input_value())

# Playwright pierces shadow DOM: target the trigger-button inside add_info_select_box
# Use locator chaining: the sdf-select-simple #add_info_select_box >> its internal trigger
ai = page.locator("#add_info_select_box")
opened=False
# Try Playwright's shadow-piercing: locate role=button within the element
try:
    trigger = ai.locator("[role=button], .trigger-button").first
    print("trigger count:", trigger.count())
    if trigger.count()>0:
        trigger.click(timeout=3000, force=True)
        time.sleep(1.0)
        opts=page.evaluate("()=>[...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
        print("opts after trigger click:", opts[:6])
        opened=bool(opts)
except Exception as e:
    print("trigger click exc:", str(e)[:100])

# fallback: openPicker() method
if not opened:
    r=page.evaluate("()=>{const el=document.getElementById('add_info_select_box'); if(el&&typeof el.openPicker==='function'){el.openPicker(); return 'called openPicker';} return 'no openPicker';}")
    print("openPicker:", r)
    time.sleep(1.0)
    opts=page.evaluate("()=>[...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    print("opts after openPicker:", opts[:6])
    opened=bool(opts)

if opened:
    opt=page.locator("[role=option]").filter(has_text="United States Dollar").first
    if opt.count()==0:
        opt=page.locator("[role=option]").filter(has_text="USD").first
    opt.click(timeout=3000)
    print("clicked USD option")
    time.sleep(0.8)

# read selected + react currencyValidation
chk=page.evaluate(r"""
()=>{
  const el=document.getElementById('add_info_select_box');
  let sel=''; if(el.shadowRoot){const s=el.shadowRoot.querySelector('#selected-label,.selected-label,[part=selected-value]'); sel=s?s.innerText.trim():'';}
  // walk fiber for currencyValidation
  const fk=Object.keys(el).find(k=>k.startsWith('__reactFiber'));
  let cv=null,vs=null;
  if(fk){let f=el[fk]; for(let i=0;i<14&&f;i++){const mp=f.memoizedProps; if(mp&&('currencyValidation'in mp)){cv=mp.currencyValidation; vs=mp.validState; break;} f=f.return;}}
  return {selectedLabel:sel, currencyValidation:cv, validState:vs};
}
""")
print("CHECK:", json.dumps(chk))
