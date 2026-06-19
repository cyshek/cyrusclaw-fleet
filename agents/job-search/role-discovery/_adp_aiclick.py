import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Plain element click on add_info_select_box (same as worked for question_1/3)
ai=page.locator("#add_info_select_box")
ai.scroll_into_view_if_needed(timeout=2000)
print("ai box:", ai.bounding_box())
# click directly on the element center
ai.click(timeout=3000)
time.sleep(1.3)
opts=page.evaluate("()=>[...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>({t:x.innerText.trim().slice(0,30),id:(x.id||'').slice(0,30)}))")
print("opts after plain click:", json.dumps(opts[:8])[:500])

# Maybe options DO render but under a different selector. Dump anything that looks like a listbox/menu now
menus=page.evaluate(r"""
()=>{
  const m=[...document.querySelectorAll('[role=listbox],[role=menu],ul,.dropdown-menu,sdf-select-simple-option,[class*=option],[class*=menu-item]')].filter(x=>x.offsetWidth>0);
  return m.slice(0,12).map(x=>({tag:x.tagName,role:x.getAttribute('role'),cls:(x.className||'').toString().slice(0,30),txt:(x.innerText||'').trim().slice(0,30)}));
}
""")
print("visible menus/options:", json.dumps(menus)[:700])
