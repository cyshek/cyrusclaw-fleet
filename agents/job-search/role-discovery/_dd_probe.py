from playwright.sync_api import sync_playwright
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
page=None
for ctx in br.contexts:
  for p in ctx.pages:
    if 'datadog' in p.url and 'recaptcha' not in p.url: page=p
js=r"""()=>{
const els=[...document.querySelectorAll('input[required],select[required],textarea[required]')].filter(e=>!e.value&&e.type!=='file'&&e.offsetParent);
return JSON.stringify(els.map(e=>{
  let c=e, txt='';
  for(let i=0;i<6&&c;i++){c=c.parentElement;if(c&&c.innerText&&c.innerText.trim()){txt=c.innerText.slice(0,90);break;}}
  return {tag:e.tagName,type:e.type,name:e.name,id:e.id,role:e.getAttribute('role'),ctx:txt.replace(/\n/g,' ')};
}));}"""
print(page.evaluate(js))
