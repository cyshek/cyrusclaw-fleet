from playwright.sync_api import sync_playwright
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
page=None
for ctx in br.contexts:
  for p in ctx.pages:
    if 'datadog' in p.url and 'recaptcha' not in p.url: page=p
js=r"""()=>{
const out=[];
document.querySelectorAll('.select__control').forEach(c=>{
  const sv=c.querySelector('.select__single-value');
  const inp=c.querySelector('input');
  // find the question label above
  let n=c, lbl='';
  for(let i=0;i<6&&n;i++){n=n.parentElement;if(n){const l=n.querySelector('label');if(l){lbl=l.textContent.trim();break;}}}
  out.push({label:lbl.slice(0,60),value:sv?sv.textContent.trim():null,inputId:inp?inp.id:null});
});
return JSON.stringify(out);}"""
print(page.evaluate(js))
