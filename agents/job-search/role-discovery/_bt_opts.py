from playwright.sync_api import sync_playwright
import json,time
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start();br=pw.chromium.connect_over_cdp(CDP);ctx=br.contexts[0]
pg=[p for p in ctx.pages if '7899566' in p.url][0]
for qid in ["question_66541725","question_66541727"]:
    opts=pg.evaluate("""async (id)=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const inp=document.getElementById(id);if(!inp)return['noinput'];const ctrl=inp.closest('.select__control');const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(350);const o=[...document.querySelectorAll('.select__option,[role=option]')].map(x=>x.textContent.trim());fire(document.body,'mousedown',0,0);return o;}""",qid)
    print(qid,"=>",json.dumps(opts))
