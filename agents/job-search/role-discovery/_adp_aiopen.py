#!/usr/bin/env python3
"""Open add_info_select_box via shadow trigger / keyboard; select USD. Then Next."""
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

# desired salary is 150,000.00 already. Now open add_info_select_box.
# Approach A: focus the element and press keys
ai = page.locator("#add_info_select_box")
ai.scroll_into_view_if_needed(timeout=2000)
try:
    ai.focus(timeout=2000)
except Exception as e:
    print("focus exc", str(e)[:60])
time.sleep(0.3)
# sdf-select opens on Enter or Space or ArrowDown
for key in ["Enter", "ArrowDown", " "]:
    page.keyboard.press(key if key != " " else "Space")
    time.sleep(0.9)
    opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    if opts:
        print("opened via key %r; opts:" % key, opts[:6])
        break
    else:
        print("key %r -> no opts" % key)

opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
if not opts:
    # Approach B: click the shadow trigger-button via JS coordinates
    box = page.evaluate(r"""
    () => {
      const el=document.getElementById('add_info_select_box');
      const t=el.shadowRoot?el.shadowRoot.querySelector('.trigger-button,[role=button]'):null;
      if(t){const r=t.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};}
      const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};
    }
    """)
    print("clicking shadow trigger at", box)
    page.mouse.click(box["x"], box["y"])
    time.sleep(1.0)
    opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    print("after coord-click opts:", opts[:6])

if opts:
    target = None
    for o in opts:
        if "united states dollar" in o.lower() or "USD" in o:
            target = o; break
    if not target:
        target = opts[0]
    page.locator("[role=option]").filter(has_text=target).first.click(timeout=3000)
    print("add_info -> %r" % target)
    time.sleep(0.8)
else:
    print("COULD NOT OPEN add_info_select_box")

page.keyboard.press("Escape"); time.sleep(0.5)

# Verify add_info now has a value
ai_val = page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  let sel=''; if(el.shadowRoot){const s=el.shadowRoot.querySelector('#selected-label,.selected-label,[part=selected-value]'); sel=s?s.innerText.trim():'';}
  return {value:el.getAttribute('value'), selectedLabel:sel};
}
""")
print("add_info value now:", ai_val)

# Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)
after = page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body)&&/Correct the information/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  return {stuck, headings:h, errs, sample:body.replace(/\s+/g,' ').slice(0,400)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
print("[done]")
