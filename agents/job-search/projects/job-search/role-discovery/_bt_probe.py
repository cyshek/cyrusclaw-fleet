from playwright.sync_api import sync_playwright
import json
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start();br=pw.chromium.connect_over_cdp(CDP);ctx=br.contexts[0]
pg=[p for p in ctx.pages if '7899566' in p.url][0]
r=pg.evaluate("""()=>{
  const errs=[...document.querySelectorAll('.error,[aria-invalid=true]')].map(e=>e.textContent.trim().slice(0,80)).filter(Boolean).slice(0,12);
  const sel=[...document.querySelectorAll('.select__control')].filter(c=>c.offsetParent!==null&&!c.querySelector('.select__single-value,.select__multi-value')).map(c=>{const i=c.querySelector('input[role=combobox]');let lbl='';let n=c;for(let k=0;k<7&&n;k++){n=n.parentElement;if(!n)break;const le=n.querySelector?n.querySelector('label,legend'):null;if(le){lbl=le.textContent.trim().slice(0,70);break;}}return{id:i?i.id:null,lbl};});
  const cbs=[...document.querySelectorAll('input[type=checkbox],input[type=radio]')].filter(c=>c.offsetParent!==null&&(c.required||c.getAttribute('aria-required')==='true')&&!c.checked).map(c=>({id:c.id,name:c.name,desc:c.getAttribute('description')||'',type:c.type}));
  return {errs,unfilledSelects:sel,uncheckedReq:cbs};
}""")
print(json.dumps(r,indent=1))
