import json
from playwright.sync_api import sync_playwright
URL="https://jobs.ashbyhq.com/tessera-labs/ea05dfd6-92d7-4ccc-aa53-2f31a85928c5/application"
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp("http://127.0.0.1:19223")
    ctx=b.contexts[0]; pg=ctx.new_page()
    pg.goto(URL,timeout=45000,wait_until="domcontentloaded")
    pg.wait_for_timeout(4500)
    info=pg.evaluate(r"""()=>{
      const out=[];
      document.querySelectorAll('div[class*=_fieldEntry_], fieldset').forEach(fe=>{
        const lbl=(fe.querySelector('label')||{}).innerText||(fe.innerText||'').slice(0,60);
        if(!/authoriz|sponsor/i.test(lbl))return;
        const yesno=fe.querySelector('div[class*=_yesno_]');
        const radios=fe.querySelectorAll('input[type=radio]');
        const txt=fe.querySelectorAll('input[type=text],textarea');
        const btns=[...fe.querySelectorAll('button')].map(b=>b.innerText).filter(Boolean);
        out.push({label:lbl.slice(0,50),yesno:!!yesno,nradio:radios.length,ntext:txt.length,buttons:btns.slice(0,4)});
      });
      return out;
    }""")
    print(json.dumps(info,indent=2))
    b.close()
