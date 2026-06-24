import sys, os, time
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
import json

CDP = 'http://127.0.0.1:18800'
URL = 'https://jobs.lever.co/veeva/6bcc8228-5b43-43e5-b96b-d62679b8c64a/apply'

# Fresh token from 2captcha (just solved)
TOKEN = "P1_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.haJwZACjZXhwzmo63wincGFzc2tlecUFm6K_Fu6yApM_BNjBXCLWAkiPgelubeaqNH42fwdTCz2aOa7ztahN-qHzHIJEaeiOtOAOFHHieK9O4XC4GW7uJT6zmtSIm5tQD9Dy6UDMuq1GNjiIr3x5chZbujBrcRgol8lNF4_DnujiTdWxagK-7lpUmaYGIQM4Hk1VuDXhgqYo4diB23lv5hkoKVyUf2PduIA2iXDiBRF9oN5NT1MsBoYSoVeHRFiaBFN95RSLndVsy2py7lJXHyaUIKAz2RqBtuZ7MpmJ0gXRD5vyEIvzW3UtYyvJqbZpNYuURIQe60AQYDZfKFlmGRX7YkUD3ySH-aHHDFr-w7nvNF9E6wl7E3LmH1tx4faVD7yjrJHlegG2YdNHLHUQYOBe3pfmIzKfejyC7IFk5h-xF8g8MObZ6aAuJMyFknaDlZM3AqOwEWwfeqg4w8wbcyV0_J52wPI_wA5euLOCXqtJWlD1WOwg4e3X-6eOBx36XsCKwtjHaqMXeOro57FFL1uCNN7H26K21nPhLQGaBYi5NafnVSPpoDXwzf0p5MTJqqh5jV5Wu9jpka1uYrdA6NAMCmiXfP4bkA5eUKvX94Y0wKxr_nPfJ8lHpG9hNjVhz6s8G5nXsr8qd9lQLNWpbo0IoH4nMnGTK30-c1vRaWR0aRdKE4RB5af-7tEDqgdu75dVD1RGDXic89nfVwQ9F992apPpeowvh-omlqCoZnauZKfXZjBUWdZ5i0ZXEQ5QegMBg2VDkRbctjVR0drodNTQK1GvtAPwYrbyV9PstHzSoRWphm9Ubc5HYMlN6_GpeLi2eZlx_2VrZ75c8YLunK_WEbJndLurUzkz6FkR36KkaFxGo2LOy0Y8Si1Tewkqqc73O1IYulRF08Jwz4EkDN89t45eVpuIrDc6JUkgQIFiknPxyyCc29Zy-66LA8S4ZsjDWSRYRukA2FgwPBaBLHf5t9NDSB_CoMNPwZi24CXCb_500igArvtQEWdiC5aKdztxBYmdcamRcVcbl_PS2kC7fpJ45O95Sz-FwfpJDDdo8GDg6t-oc8u6rtQ2bsKqzIWbY5g2kHntSl7U1r6ug1gT3IOFDgHjtVkOlJnh_xWBNDOFXVV9ye_JxRebf2DPlDl7Tn7Oy5iAirWVS0F9jXUYG2NAb81nYkxo4UR5GWagmqN9qJWPcTWjJfftUsLHPkXf_VQhmZZF9PQH20_7L1WqmVS46qFxNYvSWNUNZGW-nVN5mtEgYH5Qn2XNIrwwazPHSMJkK9lI6yqNUkgipeG8Cv5wHzpKmTEidWu9Rt6tX_0MEh5BFFIZX0ii7k0h2rfytsUCO4oF3qr8PIkZ2GyYjdKxh-CzxliyX2-iHblv8gOHyRsWxAGdG8MVZgm5u01kXJIRTcg5dfUAlIrsGeqY1-JkWZYlr4vi9qf3KdaAwl4KtwevTle2KHo6LmmqPhTSDFtR6r9MW6YgfmQDyR8nBLoZbDorMVcaUrLE8ph_6urzNeDfNRDyHYlIKbPxUvwJnJF2cWNutNw-xHqGXbB165cJqiKQco44_-8sKF-JY33Ea_jrBBWFY7xBVmJiPSEAfQo-uZjLSQNxlFPo3oWS6OZeGTVnwJhQoQujDNvrZw9Ydc7_d9uYDHMADoSgHa33fD3DgCiVVkGUkZRvZjazaF3G8o1kbmkCuhPJZPQaftJEMklVhDDDJqw5W-1p1ZobroOV_EmsIad9Cw4SYK6eksOC5ul21QLK_gWXVpOUChuWZR582si4faWxbUdDolC4zM5NRIXc5MqHv3Bow6BHPKkJy8Vuex3k6xWZaVMAu93jyMa8lUubrO2_CCEoUBekpoRRAgDWhadRkeDBmDmTWl0sPkXHUJtnRl4IJE_sTJ1GR8aaLBqMJ-Py4tplU5jC0M2JFgerfWLUMLwIgFz3qTmia3KnNmVjZTA5ZKhzaGFyZF9pZM4UPIQf.Ve7QdhsawWxo0dt02Y7Vpz5LFtJR1KAUVWRUASX7cUA"

print(f"Token len: {len(TOKEN)}", flush=True)
print(f"Elapsed since solve: ~30s", flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.new_context()
    page = ctx.new_page()
    
    page.goto(URL, wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(4000)
    
    # Fill form minimally
    page.evaluate("""(t) => {
        const set_val = (el, v) => {
            if (!el) return;
            const proto = Object.getPrototypeOf(el);
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, v); else el.value = v;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        };
        set_val(document.querySelector('input[name="name"]'), 'Cyrus Shekari');
        set_val(document.querySelector('input[name="email"]'), 'cyshekari@gmail.com');
        set_val(document.querySelector('input[name="phone"]'), '346-804-0227');
        set_val(document.querySelector('input[name="org"]'), 'Microsoft');
        set_val(document.getElementById('hcaptchaResponseInput'), t);
        console.log('[test] token injected, len=' + t.length);
    }""", TOKEN)
    
    print("Token injected, checking value...", flush=True)
    val_check = page.evaluate("() => document.getElementById('hcaptchaResponseInput')?.value?.length")
    print(f"hcaptchaResponseInput.value.length = {val_check}", flush=True)
    
    # Now use fetch-POST to test server-side validation 
    # (without resume, to isolate the captcha error)
    result = page.evaluate("""async (tok) => {
        const form = document.querySelector('form');
        if (!form) return {err: 'no form'};
        const fd = new FormData(form);
        fd.delete('resume');
        fd.set('h-captcha-response', tok);
        fd.set('g-recaptcha-response', tok);
        // Log all keys being sent
        const keys = [];
        for (const [k, v] of fd.entries()) {
            keys.push(k + '=' + (k.includes('captcha') ? '<len:'+v.length+'>' : String(v).slice(0,40)));
        }
        const resp = await fetch(location.href, {method: 'POST', body: fd, credentials: 'include', redirect: 'follow'});
        const text = await resp.text();
        const errEls = new DOMParser().parseFromString(text, 'text/html').querySelectorAll('.error-message, [class*="error"]');
        const errs = [...errEls].map(e => e.textContent.trim()).filter(Boolean);
        return {status: resp.status, url: resp.url, fields_count: keys.length, errs: errs.slice(0,5), keys: keys};
    }""", TOKEN)
    
    print(f"RESULT: status={result.get('status')} url={result.get('url','?')}", flush=True)
    print(f"ERRS: {result.get('errs', [])}", flush=True)
    print(f"FIELDS: {result.get('keys', [])[:10]}", flush=True)
    
    ctx.close()
