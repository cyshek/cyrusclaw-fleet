#!/usr/bin/env python3
import json, time
from playwright.sync_api import sync_playwright
CDP = "http://127.0.0.1:19223"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    sf_page = ctx.pages[0]
    # Click the in-office Yes button ONCE and check state after
    js_click_and_check = """() => {
  const c = document.querySelector("[data-field-path=\\"4c8e248b-f134-416f-9fa5-38c9e679f7b1\\"]");
  if(!c) return {e:"no container"};
  const btns=[...c.querySelectorAll("button")];
  const yes=btns.find(b=>b.textContent.trim().toLowerCase()==="yes");
  if(!yes) return {e:"no yes btn", btns:btns.map(b=>b.textContent.trim())};
  // Get state BEFORE click
  const beforeCls = yes.className;
  // Fire onClick via React props
  const rk=Object.keys(yes).find(k=>k.startsWith("__reactProps$"));
  const rp=rk?yes[rk]:{};
  const r = yes.getBoundingClientRect();
  const cx = r.left+r.width/2, cy = r.top+r.height/2;
  const ev = {bubbles:true,cancelable:true,composed:true,view:window,clientX:cx,clientY:cy};
  yes.dispatchEvent(new MouseEvent("click", ev));
  // Get state AFTER click (immediate)
  const afterCls = yes.className;
  // Also get no button class
  const no = btns.find(b=>b.textContent.trim().toLowerCase()==="no");
  const noCls = no ? no.className : null;
  return {beforeCls, afterCls, noCls, sameClass: beforeCls===afterCls};
}"""
    result = sf_page.evaluate(js_click_and_check)
    print("After single YES click:")
    print(json.dumps(result, indent=2))
    # Wait 300ms then check again
    sf_page.wait_for_timeout(300)
    js_check2 = """() => {
  const c = document.querySelector("[data-field-path=\\"4c8e248b-f134-416f-9fa5-38c9e679f7b1\\"]");
  if(!c) return {e:"no container"};
  const btns=[...c.querySelectorAll("button")];
  return btns.map(b=>({txt:b.textContent.trim(),cls:b.className.slice(0,100)}));
}"""
    result2 = sf_page.evaluate(js_check2)
    print("300ms after YES click:")
    print(json.dumps(result2, indent=2))
    browser.close()
