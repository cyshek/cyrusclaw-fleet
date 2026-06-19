"""Probe Salesforce My Information source widget DOM structure.

Goal: figure out how to open the 'How Did You Hear About Us?' (source--source) dropdown
since clicking #source--source directly doesn't show the option menu and instead leaks
other widgets' promptOptions.
"""
import json, sys, time
from playwright.sync_api import sync_playwright
from pathlib import Path

CREDS = json.loads(Path(__file__).resolve().parent.parent.joinpath('.workday-creds.json').read_text())
EMAIL = CREDS['tenants']['salesforce']['email']
PASS = CREDS['shared_password']
URL = "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/job/Illinois---Chicago/Solution-Engineer--Pre-Sales---Small--Medium---Growth-Business_JR318273/apply"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(Path(__file__).resolve().parent.parent / ".workday-browser-data" / "salesforce"),
        headless=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    # try clicking apply manually if not already in flow
    for sel in ['[data-automation-id="adventureButton"]', '[data-automation-id="applyManually"]']:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                loc.click(); page.wait_for_timeout(2500)
        except Exception: pass
    # Sign in if needed
    try:
        if page.locator('[data-automation-id="signInWithEmail"]').count():
            page.locator('[data-automation-id="signInWithEmail"]').first.click()
            page.wait_for_timeout(1500)
    except Exception: pass
    # If we're on the Create Account page, click signInLink to switch to Sign In
    try:
        if page.locator('[data-automation-id="signInLink"]').count():
            page.locator('[data-automation-id="signInLink"]').first.click()
            page.wait_for_timeout(1500)
            print('switched to Sign In form')
    except Exception: pass
    # Capture full state of current page first
    page.screenshot(path='/tmp/sf-state1.png', full_page=True)
    body = page.evaluate("() => document.body.innerText.slice(0, 2500)")
    print('BODY:', body)
    inputs = page.evaluate("""() => Array.from(document.querySelectorAll('input,button')).filter(n=>n.offsetParent).map(n => ({tag:n.tagName, id:n.id, type:n.type, name:n.name, automation:n.getAttribute('data-automation-id'), aria:n.getAttribute('aria-label'), text:(n.innerText||'').slice(0,60)}))""")
    print('INPUTS:'); [print(' ', json.dumps(i)) for i in inputs[:40]]
    try:
        if page.locator('[data-automation-id="email"]').count():
            page.fill('[data-automation-id="email"]', EMAIL)
            page.fill('[data-automation-id="password"]', PASS)
            # try several submit selectors
            for sel in ['[data-automation-id="click_filter"][aria-label="Sign In"]', '[data-automation-id="signInSubmitButton"]', 'button[type="submit"][data-automation-id*="signIn"]', 'button:has-text("Sign In"):not([data-automation-id="signInLink"]):not([data-automation-id="utilityButtonSignIn"])']:
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible(timeout=1000):
                        loc.click(); print('clicked', sel); break
                except Exception: pass
            page.wait_for_timeout(5000)
    except Exception as e:
        print("signin attempt:", e)
    page.wait_for_timeout(4000)
    print("URL after signin:", page.url)
    print("URL:", page.url)
    # Inspect source--source
    dom = page.evaluate("""() => {
      const el = document.getElementById('source--source');
      if (!el) return {found: false};
      // walk up to find the labeled fieldset/container
      let cur = el;
      let chain = [];
      for (let i=0; i<6 && cur; i++) {
        chain.push({tag: cur.tagName, id: cur.id||'', cls: (cur.className||'').toString().slice(0,80), automation: cur.getAttribute && cur.getAttribute('data-automation-id') || ''});
        cur = cur.parentElement;
      }
      // find sibling/descendant buttons & listboxes near it
      const wrapper = el.closest('[data-automation-id]')?.parentElement || el.parentElement;
      const nearby = [];
      if (wrapper) {
        wrapper.querySelectorAll('button, [role=combobox], [role=button], [aria-haspopup], input').forEach(n => {
          const r = n.getBoundingClientRect();
          nearby.push({tag: n.tagName, id: n.id, role: n.getAttribute('role'), aria_haspopup: n.getAttribute('aria-haspopup'), aria_label: n.getAttribute('aria-label'), automation: n.getAttribute('data-automation-id'), text: (n.innerText||'').slice(0,50), visible: r.width>0 && r.height>0});
        });
      }
      return {
        found: true,
        chain,
        el: {tag: el.tagName, type: el.type, value: el.value, aria_haspopup: el.getAttribute('aria-haspopup'), automation: el.getAttribute('data-automation-id'), role: el.getAttribute('role')},
        nearby,
        outerHTML: el.outerHTML.slice(0, 500),
        parentHTML: el.parentElement ? el.parentElement.outerHTML.slice(0, 1500) : null,
      };
    }""")
    print(json.dumps(dom, indent=2))
    page.screenshot(path="/tmp/sf-myinfo.png", full_page=True)
    # try clicking different candidates to see what opens the menu
    print("\n-- trying click strategies --")
    for label, code in [
        ("getElementById click", "document.getElementById('source--source').click()"),
        ("parent click", "document.getElementById('source--source').parentElement.click()"),
        ("nearest haspopup", "document.getElementById('source--source').closest('[aria-haspopup]').click()"),
        ("focus + Enter via input", None),  # skip, too noisy
    ]:
        if not code: continue
        try:
            page.evaluate(code)
            page.wait_for_timeout(900)
            opts = page.evaluate("Array.from(document.querySelectorAll('[data-automation-id=\"promptOption\"]:not([hidden])')).filter(n=>n.offsetParent).map(n=>n.getAttribute('data-automation-label')).slice(0,15)")
            print(f"{label}: visible options = {opts}")
            # try clicking 'External Career Site Sources' and inspect sub
            if 'External Career Site Sources' in (opts or []):
                page.evaluate("""() => {
                  const els = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).filter(n=>n.offsetParent && n.getAttribute('data-automation-label')==='External Career Site Sources');
                  if (els.length) els[0].click();
                }""")
                page.wait_for_timeout(900)
                sub = page.evaluate("Array.from(document.querySelectorAll('[data-automation-id=\"promptOption\"]:not([hidden])')).filter(n=>n.offsetParent).map(n=>n.getAttribute('data-automation-label'))")
                print(f"  sub options under External Career Site Sources = {sub}")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        except Exception as e:
            print(f"{label}: ERR {e}")
    ctx.close()
