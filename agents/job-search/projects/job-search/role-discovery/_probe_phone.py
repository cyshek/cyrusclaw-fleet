import sys, json
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:19223"
URL = "https://jobs.ashbyhq.com/curri/0da884e4-ad46-44a2-9a87-3acfefe42026/application"

PROBE = r"""() => {
  const out = {tels: [], phoneContainers: []};
  // all tel inputs + their react props keys
  document.querySelectorAll('input[type=tel], input[name*=phone i], input[id*=phone i]').forEach(el => {
    const propKeys = Object.keys(el).filter(k => k.startsWith('__react'));
    out.tels.push({
      tag: el.tagName, type: el.type, id: (el.id||'').slice(-30), name: el.name,
      cls: (el.className||'').slice(0,60), value: el.value,
      reactKeys: propKeys,
      ariaHidden: el.getAttribute('aria-hidden'),
      placeholder: el.placeholder,
    });
  });
  // look for the phone field container + any hidden inputs near it
  const conts = [...document.querySelectorAll('[data-field-path], div[class*=_fieldEntry_]')];
  for (const c of conts) {
    const lbl = ((c.querySelector('label')||{}).textContent||'');
    if (/phone/i.test(lbl)) {
      const inputs = [...c.querySelectorAll('input')].map(i => ({
        type: i.type, name: i.name, id: (i.id||'').slice(-24), cls:(i.className||'').slice(0,50),
        value: i.value, hidden: i.type==='hidden'||i.getAttribute('aria-hidden')==='true'
      }));
      // does the container input have a React onChange?
      const main = c.querySelector('input[type=tel]') || c.querySelector('input');
      let onChangeInfo = null;
      if (main) {
        const k = Object.keys(main).find(x=>x.startsWith('__reactProps$'));
        if (k) { const p = main[k]; onChangeInfo = {hasOnChange: typeof p.onChange==='function', hasOnInput: typeof p.onInput==='function', propKeys: Object.keys(p).slice(0,15)}; }
      }
      out.phoneContainers.push({label: lbl.slice(0,60), fieldPath: c.getAttribute('data-field-path'), inputs, onChangeInfo});
    }
  }
  return out;
}"""

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)
    res = page.evaluate(PROBE)
    print(json.dumps(res, indent=2))
    page.close()
