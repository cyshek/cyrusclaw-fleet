#!/usr/bin/env python3
import sys, json
from playwright.sync_api import sync_playwright
CDP = "http://127.0.0.1:19223"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else None
    if not ctx: print("No context"); sys.exit(1)
    pages = ctx.pages
    print(f"Pages: {len(pages)}")
    sf_page = next((pg for pg in pages if "ashbyhq" in pg.url or "snowflake" in pg.url.lower()), pages[0] if pages else None)
    if not sf_page: print("No page!"); sys.exit(1)
    print(f"Using: {sf_page.url[:80]}")
    js = """() => {
  const c = [...document.querySelectorAll('[data-field-path]')];
  const m = c.filter(x=>x.getAttribute('data-field-path').includes('4c8e248b'));
  if(!m.length) return [{e:"no 4c8e248b", fps: c.slice(0,5).map(x=>x.getAttribute('data-field-path'))}];
  return m.map(o => {
    const fp = o.getAttribute('data-field-path');
    const yn = o.querySelector('div[class*=_yesno_]');
    if(!yn) return {fp, e:"no yesno"};
    const btns=[...yn.querySelectorAll('button')];
    const yes=btns.find(b=>b.textContent.trim().toLowerCase()==="yes");
    if(!yes) return {fp, e:"no yes btn", btns:btns.map(b=>b.textContent.trim())};
    const rk=Object.keys(yes).find(k=>k.startsWith('__reactProps$'));
    const rp=rk?yes[rk]:{};
    return {fp, active:/_active_/.test(yes.className), onKeys:Object.keys(rp).filter(k=>k.startsWith('on')), onClick:typeof rp.onClick, onPD:typeof rp.onPointerDown, dis:yes.disabled, cls:yes.className.slice(0,80)};
  });
}"""
    result = sf_page.evaluate(js)
    print(json.dumps(result, indent=2))
    browser.close()
