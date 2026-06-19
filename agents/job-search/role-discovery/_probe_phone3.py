import sys, json, re, os
sys.path.insert(0, '.')
import _ashby_runner as m
from playwright.sync_api import sync_playwright

# ---- Personal info loader --------------------------------------------------
_INFO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "personal-info.json")
def _info():
    with open(_INFO_PATH) as _f:\n        return json.load(_f)\n_pi = _info()\n_ident = _pi["identity"]
def _phone_fmt(p):
    d = re.sub(r'[^0-9]', '', p or '').lstrip('1')
    return f"{d[0:3]}-{d[3:6]}-{d[6:]}" if len(d)==10 else p

CDP = "http://127.0.0.1:19223"
URL = "https://jobs.ashbyhq.com/curri/0da884e4-ad46-44a2-9a87-3acfefe42026/application"
PHONE_FID = "c880c38b-3688-4452-a943-8ddac79c8e97"
NAME_FID  = "__systemfield_name"
EMAIL_FID = "__systemfield_email"

# capture submit POST responses
def run(method):
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = ctx.new_page()
        resps = []
        def on_resp(r):
            try:
                if 'submitApplicationForm' in (r.request.post_data or '') or 'ApiSubmit' in r.url or 'submitApplication' in (r.request.post_data or ''):
                    resps.append(r)
            except Exception:
                pass
        page.on("response", on_resp)
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)

        # Minimal fill: name, email, phone only via the chosen method, then submit and read server error
        page.fill(f'[name="{NAME_FID}"], #{NAME_FID}', f"{_ident['first_name']} {_ident['last_name']}", timeout=4000)
        page.fill(f'[name="{EMAIL_FID}"], #{EMAIL_FID}', _ident["email"], timeout=4000)

        loc = page.locator(f'#{PHONE_FID}, [name="{PHONE_FID}"]').first
        if method == "fill":
            loc.fill(_phone_fmt(_ident["phone"]), timeout=4000)
        elif method == "type":
            loc.click(timeout=3000); loc.press("Control+a"); loc.press("Delete")
            loc.type(_phone_fmt(_ident["phone"]), delay=40)
        elif method == "pressSequentially":
            loc.click(timeout=3000); loc.press("Control+a"); loc.press("Delete")
            loc.press_sequentially(_phone_fmt(_ident["phone"]), delay=40)
        page.wait_for_timeout(400)
        # read react prop value for phone
        chk = page.evaluate("""(fid)=>{const el=document.getElementById(fid)||document.querySelector(`[name="${fid}"]`);const k=Object.keys(el).find(x=>x.startsWith('__reactProps$'));return {dom:el.value, react:k?el[k].value:null};}""", PHONE_FID)
        print(f"[{method}] phone after fill: {json.dumps(chk)}")

        # click submit
        try:
            sub = page.locator('button:has-text("Submit Application")').first
            sub.click(timeout=5000)
        except Exception as e:
            print("submit click err:", e)
        page.wait_for_timeout(3500)
        # find phone error in resps
        phone_err = None
        for r in resps:
            try:
                body = r.text()
                if 'Phone' in body and 'Missing' in body:
                    phone_err = 'Missing Phone'
                if '"__typename":"FormSubmitSuccess"' in body:
                    phone_err = 'SUCCESS'
            except Exception:
                pass
        print(f"[{method}] server verdict: {phone_err}  (resps={len(resps)})")
        page.close()

for mth in ["fill", "type", "pressSequentially"]:
    try:
        run(mth)
    except Exception as e:
        print(f"[{mth}] ERR", e)
