import sys, json, os, re
sys.path.insert(0, '.')
import _ashby_runner as m
from playwright.sync_api import sync_playwright

# ---- Personal info loader --------------------------------------------------
_INFO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "personal-info.json")
with open(_INFO_PATH) as _f:\n    _pi = json.load(_f)\n_phone_raw = _pi["identity"].get("phone", "")
def _phone_fmt(p):
    d = re.sub(r'[^0-9]', '', p or '').lstrip('1')
    return f"{d[0:3]}-{d[3:6]}-{d[6:]}" if len(d)==10 else p
_PHONE = _phone_fmt(_phone_raw)

CDP = "http://127.0.0.1:19223"
URL = "https://jobs.ashbyhq.com/curri/0da884e4-ad46-44a2-9a87-3acfefe42026/application"
PHONE_FID = "c880c38b-3688-4452-a943-8ddac79c8e97"

CHECK = r"""(fid) => {
  const el = document.getElementById(fid) || document.querySelector(`[name="${fid}"]`);
  if (!el) return {found:false};
  // read what React thinks the value is via the props bag
  const k = Object.keys(el).find(x=>x.startsWith('__reactProps$'));
  const propVal = k ? el[k].value : null;
  return {found:true, domValue: el.value, reactPropValue: propVal};
}"""

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)

    print("BEFORE:", json.dumps(page.evaluate(CHECK, PHONE_FID)))

    # method A: the no-bounce commit JS
    res = page.evaluate(m._FINAL_TEXT_COMMIT_NO_BOUNCE_JS, {"fields":[{"fid":PHONE_FID,"val":_PHONE}]})
    print("no-bounce commit result:", json.dumps(res))
    page.wait_for_timeout(300)
    print("AFTER no-bounce:", json.dumps(page.evaluate(CHECK, PHONE_FID)))

    # method B: Playwright native .fill() (real keystrokes/trusted)
    try:
        loc = page.locator(f'#{PHONE_FID}, [name="{PHONE_FID}"]').first
        loc.fill(_PHONE, timeout=4000)
        page.wait_for_timeout(300)
        print("AFTER playwright.fill:", json.dumps(page.evaluate(CHECK, PHONE_FID)))
    except Exception as e:
        print("fill err:", e)

    # method C: type char by char
    try:
        loc = page.locator(f'#{PHONE_FID}, [name="{PHONE_FID}"]').first
        loc.click(timeout=3000)
        loc.press("Control+a")
        loc.press("Delete")
        loc.type(_PHONE, delay=30)
        page.wait_for_timeout(300)
        print("AFTER type-by-char:", json.dumps(page.evaluate(CHECK, PHONE_FID)))
    except Exception as e:
        print("type err:", e)

    page.close()
