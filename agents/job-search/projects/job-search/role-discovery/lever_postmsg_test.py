"""
Test: intercept hCaptcha token via postMessage listener.
When hCaptcha's challenge is solved (either auto or via visual), it sends
a postMessage to the parent with {data: ..., source: 'hcaptcha'}.
We install a listener BEFORE clicking submit, then click submit,
and wait for the token to arrive via postMessage.
"""
import sys, json, time
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:19223"  # residential
URL = "https://jobs.lever.co/angellist/1e049808-452a-4e0c-a43d-d665047b65b0/apply"
RESUME = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/aeva-c7d1ac3c/Cyrus_Shekari_Resume_lever-aeva_c7d1ac3c_v2.pdf"

def log(msg): print(f"[test] {msg}", flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.new_context()
    page = ctx.new_page()
    
    # Hide webdriver
    page.add_init_script("""
      Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
      // hCaptcha postMessage interceptor - install BEFORE page loads
      window.__hcaptchaMessages = [];
      const _origAddEventListener = window.addEventListener;
      window.__captchaTokenPromise = new Promise(resolve => {
        window.__resolveCaptchaToken = resolve;
      });
      window.addEventListener('message', function(e) {
        const d = e.data;
        if (!d) return;
        // hCaptcha sends: {data: {token, eKey, ...}, source: 'hcaptcha'}
        // OR: data: {id: 'xxx', response: 'token...'}
        let tok = null;
        try {
          if (typeof d === 'string') {
            const p = JSON.parse(d);
            if (p.response && p.response.length > 20) tok = p.response;
            if (p.token && p.token.length > 20) tok = p.token;
          } else {
            if (d.response && String(d.response).length > 20) tok = d.response;
            if (d.token && String(d.token).length > 20) tok = d.token;
            if (d.data && typeof d.data === 'object') {
              if (d.data.response) tok = d.data.response;
              if (d.data.token) tok = d.data.token;
            }
          }
        } catch(e) {}
        if (tok) {
          window.__capturedHcaptchaToken = tok;
          console.log('[postmsg] captured hcaptcha token len=' + tok.length);
          if (window.__resolveCaptchaToken) window.__resolveCaptchaToken(tok);
        }
        window.__hcaptchaMessages.push(String(typeof d === 'object' ? JSON.stringify(d).slice(0,100) : d).slice(0,100));
      }, true);
    """)
    
    log("Loading page...")
    page.goto(URL, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    
    log("Filling form fields...")
    page.evaluate("""() => {
      const vals = {name:'Cyrus Shekari', email:'cyshekari@gmail.com', phone:'346-804-0227', org:'Microsoft'};
      Object.entries(vals).forEach(([n,v]) => {
        const el = document.querySelector('input[name="' + n + '"]');
        if (!el) return;
        try { Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set.call(el, v); } catch(_) { el.value = v; }
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
      });
    }""")
    
    log("Uploading resume...")
    upload_input = page.query_selector('input[type="file"]')
    if upload_input:
        upload_input.set_input_files(RESUME)
        page.wait_for_timeout(4000)
        sid = page.evaluate("() => (document.querySelector('input[name=resumeStorageId]') || {value:''}).value")
        log(f"resumeStorageId: {sid}")
    
    log("Clicking submit button (will trigger hCaptcha)...")
    submit_btn = page.query_selector('button[type="submit"]')
    if submit_btn:
        submit_btn.click()
    else:
        page.evaluate("""() => {
          const btn = document.querySelector('[data-qa="btn-submit"]') || document.querySelector('button');
          if (btn) btn.click();
        }""")
    
    log("Waiting for hCaptcha postMessage (up to 60s)...")
    # Poll for token capture
    tok = None
    for i in range(60):
        time.sleep(1)
        try:
            tok = page.evaluate("() => window.__capturedHcaptchaToken")
            msgs = page.evaluate("() => window.__hcaptchaMessages.slice(-5)")
            if i % 10 == 0:
                log(f"  [{i}s] msgs={msgs}")
            if tok and len(tok) > 20:
                log(f"GOT TOKEN via postMessage! len={len(tok)}")
                break
        except Exception as e:
            log(f"  eval error: {e}")
    
    if not tok:
        log("No postMessage token in 60s")
        msgs = page.evaluate("() => window.__hcaptchaMessages")
        log(f"All captured messages ({len(msgs)}): {msgs[:10]}")
    
    url = page.url
    body_text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 300) : ''")
    log(f"Final URL: {url}")
    log(f"Final body: {body_text[:200]}")
    
    page.close(); ctx.close(); browser.close()
