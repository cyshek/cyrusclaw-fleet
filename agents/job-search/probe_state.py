#!/usr/bin/env python3
"""Probe the persisted browser context to see where we left off."""
import sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".workday-browser-data" / "adobe-exp-next"
DEBUG = ROOT / ".workday-debug" / "probe"
DEBUG.mkdir(parents=True, exist_ok=True)
URL = "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply/useMyLastApplication"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(DATA), headless=True,
        viewport={"width":1400,"height":900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    pages = ctx.pages
    print(f"existing pages: {len(pages)}")
    for pg in pages:
        try: print(" -", pg.url)
        except: pass
    page = pages[0] if pages else ctx.new_page()
    print("current url:", page.url)
    if "myworkdayjobs.com" not in page.url:
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)
    print("after wait url:", page.url)
    page.screenshot(path=str(DEBUG/"current.png"), full_page=True)
    html = page.content()
    (DEBUG/"current.html").write_text(html)
    # Step
    step = page.evaluate("""() => {
      const cur = document.querySelector('[data-automation-id="progressBarActiveStep"]');
      const h = document.querySelector('h2[data-automation-id]') || document.querySelector('h1[data-automation-id]');
      return {step: cur?cur.textContent.trim():'', heading: h?h.textContent.trim():'',
              title: document.title};
    }""")
    print("step:", step)
    # Errors
    errs = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('[data-automation-id="errorMessage"],.Error,[role=alert]').forEach(e=>{
        const t=(e.textContent||'').trim();
        if (t && t.length<300) out.push(t);
      });
      return out;
    }""")
    print("errors:", errs)
    # Logged in?
    auth = page.evaluate("""() => {
      const out = {};
      out.signin_link = !!document.querySelector('a[href*=login], button:has(span:contains("Sign In"))');
      out.candidate_name = (document.querySelector('[data-automation-id="utilityButtonAccount"]')||{}).textContent || '';
      return out;
    }""")
    print("auth:", auth)
    ctx.close()
