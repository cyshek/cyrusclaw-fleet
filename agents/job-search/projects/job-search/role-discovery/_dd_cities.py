from playwright.sync_api import sync_playwright
import time
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
page=None
for ctx in br.contexts:
  for p in ctx.pages:
    if 'datadog' in p.url and 'recaptcha' not in p.url: page=p
# open the cities select and list options
js_open=r"""()=>{const inp=document.getElementById('question_64361675[]');if(!inp)return 'noinput';const ctrl=inp.closest('.select__control');const r=ctrl.getBoundingClientRect();['mousedown','mouseup','click'].forEach(t=>ctrl.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:r.left+5,clientY:r.top+5})));return 'opened';}"""
print(page.evaluate(js_open))
time.sleep(0.6)
js_opts=r"""()=>{const m=document.querySelector('.select__menu');if(!m)return JSON.stringify(['NOMENU']);return JSON.stringify([...m.querySelectorAll('.select__option,[role=option]')].map(o=>o.textContent.trim()).slice(0,40));}"""
print(page.evaluate(js_opts))
