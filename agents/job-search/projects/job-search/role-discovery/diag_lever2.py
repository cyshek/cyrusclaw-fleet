import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
import json

CDP = 'http://127.0.0.1:18800'
URL = 'https://jobs.lever.co/veeva/6bcc8228-5b43-43e5-b96b-d62679b8c64a/apply'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.new_context()
    page = ctx.new_page()
    
    page.add_init_script("""
      // Override btn-submit click to log what it sees
      document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
          const btn = document.getElementById('btn-submit');
          if (btn) {
            const origHandler = btn.onclick;
            btn._instrumented = true;
            console.log('[diag] btn-submit found, adding instrumentation');
          }
        }, 2000);
      });
    """)
    
    page.goto(URL, wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(4000)
    
    # Check if hcaptchaResponseInput is React-controlled
    react_info = page.evaluate("""() => {
        const el = document.getElementById('hcaptchaResponseInput');
        if (!el) return {found: false};
        // Check for React fiber
        const keys = Object.keys(el);
        const fiberKey = keys.find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
        const propsKey = keys.find(k => k.startsWith('__reactProps'));
        return {
            found: true,
            name: el.name, id: el.id, type: el.type,
            value: el.value,
            hasFiber: !!fiberKey,
            hasProps: !!propsKey,
            reactKeys: keys.filter(k => k.startsWith('__react')).slice(0, 5),
        };
    }""")
    print("HCAPTCHA INPUT REACT INFO:", json.dumps(react_info, indent=2))
    
    # Set the value via native setter and check if it sticks
    set_result = page.evaluate("""() => {
        const el = document.getElementById('hcaptchaResponseInput');
        if (!el) return {err: 'not found'};
        // Set via native setter (React-safe)
        const proto = Object.getPrototypeOf(el);
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(el, 'P1_TEST_TOKEN_12345');
        else el.value = 'P1_TEST_TOKEN_12345';
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        // Read back
        return {set: 'ok', readback: el.value, len: el.value.length};
    }""")
    print("SET RESULT:", json.dumps(set_result))
    
    # Wait a tick and read again (check if React re-sets it to '')
    page.wait_for_timeout(500)
    readback = page.evaluate("""() => {
        const el = document.getElementById('hcaptchaResponseInput');
        return {value: el?.value, len: el?.value?.length};
    }""")
    print("READBACK AFTER 500ms:", json.dumps(readback))
    
    # Also check: what does Lever's btn-submit listener check?
    # Peek at the event listeners
    listener_info = page.evaluate("""() => {
        const btn = document.getElementById('btn-submit');
        if (!btn) return {err: 'no btn'};
        // Check onclick
        const fn = btn.onclick;
        return {
            hasOnclick: !!fn,
            listeners: Object.keys(btn).filter(k => k.includes('listener') || k.includes('event')),
        };
    }""")
    print("BTN LISTENER INFO:", json.dumps(listener_info))
    
    ctx.close()
