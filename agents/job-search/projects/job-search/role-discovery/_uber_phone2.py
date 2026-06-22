import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright
_PI = json.loads((Path(__file__).resolve().parents[1] / "personal-info.json").read_text())
_PHONE_RAW = _PI["contact"]["phone"].replace("-", "")  # 10-digit: 3468040227
_PHONE_FMT = _PI["contact"]["phone"]  # 346-804-0227
CDP = "http://127.0.0.1:18800"
job = sys.argv[1]
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
page = None
for ctx in br.contexts:
    for p in ctx.pages:
        if f'/careers/apply/form/{job}' in p.url:
            page = p
            break
    if page:
        break
if not page:
    print("NO PAGE")
    sys.exit(2)

meta = page.evaluate("""()=>{
  const el=document.querySelector('input[name="mobileNumber"]');
  if(!el) return 'NO_FIELD';
  const around=el.closest('div')?.parentElement?.innerText||'';
  const combos=[...(el.closest('div')?.parentElement?.querySelectorAll('[role=combobox],select,button')||[])].map(c=>(c.innerText||c.getAttribute('aria-label')||'').trim()).filter(Boolean).slice(0,6);
  return JSON.stringify({type:el.type, placeholder:el.placeholder, value:el.value, ariaInvalid:el.getAttribute('aria-invalid'), pattern:el.pattern, maxLength:el.maxLength, label:around.slice(0,140), combos});
}""")
print("META:", meta)

el = page.locator('input[name="mobileNumber"]').first


def try_format(val):
    try:
        el.click()
        el.fill("")
        time.sleep(0.2)
        el.type(val, delay=40)
        el.blur()
        time.sleep(0.7)
    except Exception as e:
        print("type err", str(e)[:80])
    st = page.evaluate("""()=>{const el=document.querySelector('input[name="mobileNumber"]'); return {value:el.value, ariaInvalid:el.getAttribute('aria-invalid')};}""")
    print(f"  try '{val}' -> value={st['value']!r} invalid={st['ariaInvalid']}")
    return st['ariaInvalid'] != 'true'


for fmt in [_PHONE_RAW, f"+1{_PHONE_RAW}", f"({_PHONE_RAW[:3]}) {_PHONE_RAW[3:6]}-{_PHONE_RAW[6:]}", _PHONE_FMT, f"1{_PHONE_RAW}"]:
    if try_format(fmt):
        print("VALID_FORMAT:", fmt)
        break

final = page.evaluate("""()=>{const inv=[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id||e.getAttribute('aria-label')||e.tagName); const sub=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.innerText)); return JSON.stringify({invalid:inv, submitFound:!!sub, submitDisabled: sub?(sub.disabled||sub.getAttribute('aria-disabled')==='true'):null});}""")
print("FINAL_STATE:", final)
