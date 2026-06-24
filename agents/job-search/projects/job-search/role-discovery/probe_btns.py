#!/usr/bin/env python3
import json
from playwright.sync_api import sync_playwright
CDP = "http://127.0.0.1:19223"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    sf_page = ctx.pages[0]
    js = """() => {
  const allBtns = [...document.querySelectorAll("[data-field-path] button")];
  return allBtns.filter(b => {const t=b.textContent.trim().toLowerCase();return t==="yes"||t==="no";}).slice(0,12).map(b => {const c=b.closest("[data-field-path]");return {fp:c?c.getAttribute("data-field-path").slice(-20):null,txt:b.textContent.trim(),cls:b.className.slice(0,80),active:/_active_/.test(b.className),option:/_option_/.test(b.className)};});
}"""
    result = sf_page.evaluate(js)
    print(json.dumps(result, indent=2))
    browser.close()
