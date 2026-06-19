#!/usr/bin/env python3
"""Full Questions handler test: answer all 4 required Qs, verify no required-empty remains.
Q0 referred -> 'N/A'; Q1 how-heard -> 'LinkedIn'(or first sensible); Q2 comp -> 150000 + USD; Q3 VISA -> 'No'.
"""
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

def close_portals():
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    time.sleep(0.3)

def select_sdf(qid, want_values):
    """Open an sdf-select-simple by element id, click the option matching any of want_values."""
    el = page.locator("#%s" % qid)
    el.scroll_into_view_if_needed(timeout=2000)
    el.click(timeout=3000)
    time.sleep(1.0)
    # list options
    opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    print("  %s options:" % qid, opts)
    target = None
    for w in want_values:
        for o in opts:
            if o.strip().lower() == w.lower():
                target = o; break
        if target: break
    if not target:
        for w in want_values:
            for o in opts:
                if w.lower() in o.strip().lower():
                    target = o; break
            if target: break
    if not target and opts:
        target = opts[0]  # fallback first non-empty
    if target:
        opt = page.locator("[role=option]").filter(has_text=target).first
        opt.click(timeout=3000)
        print("  %s -> selected %r" % (qid, target))
        time.sleep(0.8)
        return True
    print("  %s -> NO option matched" % qid)
    return False

# Q0: referred-by text
page.locator("#question_0").fill("N/A", timeout=3000)
print("Q0 filled N/A")

# Q1: how did you hear -> LinkedIn
select_sdf("question_1", ["LinkedIn", "Internet", "Job Board", "Company Website", "Other"])
close_portals()

# Q2: total compensation requirements (currency text)
page.locator("#question_2").fill("150000", timeout=3000)
print("Q2 filled 150000")
# currency type react-select -> USD
try:
    cur = page.locator("#question_currency_type_2")
    cur.click(timeout=2500)
    time.sleep(0.8)
    # react-select options appear as [class*=option] or [role=option]
    page.locator("#question_currency_type_2").type("USD", delay=40, timeout=3000)
    time.sleep(1.0)
    usd = page.locator("[id*=react-select][id*=option], [class*=MDFSelectBox__option], [role=option]").filter(has_text="USD").first
    if usd.count() > 0:
        usd.click(timeout=2500); print("currency -> USD")
    else:
        page.keyboard.press("Enter"); print("currency -> Enter")
    time.sleep(0.6)
except Exception as exc:
    print("currency exc:", str(exc)[:120])

# Q3: VISA sponsorship -> No
select_sdf("question_3", ["No"])
close_portals()

# verify required-empty
time.sleep(1)
req = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const out=[];
  document.querySelectorAll('[aria-required=true],[required]').forEach(el=>{
    if(!vis(el))return;
    let v=(el.value||'').trim();
    // for sdf-select, check selected label in shadow
    if(el.tagName==='SDF-SELECT-SIMPLE' && el.shadowRoot){
      const sl=el.shadowRoot.querySelector('#selected-label,[part=selected-value],.selected-label');
      v=(sl&&sl.innerText)||el.getAttribute('value')||'';
    }
    if(!v) out.push({id:el.id||el.name, tag:el.tagName, ai:el.getAttribute('aria-invalid')});
  });
  return out;
}
""")
print("REQUIRED-EMPTY after answers:", json.dumps(req))
print("[done — not clicking Next]")
