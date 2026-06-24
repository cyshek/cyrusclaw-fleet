import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
import json, time

CDP = 'http://127.0.0.1:18800'
URL = 'https://jobs.lever.co/veeva/6bcc8228-5b43-43e5-b96b-d62679b8c64a/apply'
FAKE_TOKEN = 'P1_FAKE_12345678901234567890_FAKE'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.new_context()
    page = ctx.new_page()
    
    page.add_init_script("""
      // Intercept hcaptcha.execute to log when it's called
      let _origExecute = null;
      Object.defineProperty(window, 'hcaptcha', {
        get: function() { return window.__hcaptcha_real; },
        set: function(val) {
          window.__hcaptcha_real = val;
          if (val && typeof val.execute === 'function' && !val._instrumented) {
            const origExec = val.execute.bind(val);
            val.execute = function(...args) {
              console.log('[diag] hcaptcha.execute called! args=' + JSON.stringify(args));
              return origExec(...args);
            };
            val._instrumented = true;
          }
        },
        configurable: true
      });
      // Also watch for hcaptchaResponseInput changes
      window.__tokenHistory = [];
      const origDescriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      Object.defineProperty(HTMLInputElement.prototype, 'value', {
        set: function(v) {
          if (this.id === 'hcaptchaResponseInput') {
            console.log('[diag] hcaptchaResponseInput.value set to len=' + String(v).length);
            window.__tokenHistory.push({len: String(v).length, ts: Date.now()});
          }
          return origDescriptor.set.call(this, v);
        },
        get: origDescriptor.get,
        configurable: true,
      });
    """)
    
    console_logs = []
    page.on('console', lambda m: console_logs.append(m.text) if '[diag]' in m.text else None)
    
    page.goto(URL, wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(4000)
    
    # Set our fake token
    set_result = page.evaluate(f"""() => {{
        const el = document.getElementById('hcaptchaResponseInput');
        if (!el) return {{err: 'not found'}};
        const proto = Object.getPrototypeOf(el);
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(el, '{FAKE_TOKEN}');
        else el.value = '{FAKE_TOKEN}';
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return {{set: 'ok', readback: el.value}};
    }}""")
    print("SET RESULT:", set_result)
    
    # Click the submit button
    print("Clicking btn-submit...")
    page.evaluate("""() => {
        const btn = document.getElementById('btn-submit');
        if (btn) btn.click();
    }""")
    
    # Wait 3 seconds and check what happened
    page.wait_for_timeout(3000)
    
    # Read the current state
    state = page.evaluate("""() => {
        const el = document.getElementById('hcaptchaResponseInput');
        return {
            currentValue: el?.value?.length,
            url: location.href,
            tokenHistory: window.__tokenHistory || [],
        };
    }""")
    print("STATE AFTER CLICK:", json.dumps(state))
    print("CONSOLE LOGS:", console_logs)
    
    # Check if page navigated
    print("CURRENT URL:", page.url)
    
    ctx.close()
