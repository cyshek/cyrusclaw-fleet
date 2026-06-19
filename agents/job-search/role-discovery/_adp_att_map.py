import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-50:])

d=page.evaluate(r"""
()=>{
  const c=document.querySelector('input[name="self_att_agree_chk"]');
  if(!c) return 'no-input';
  const r=c.getBoundingClientRect();
  const cs=getComputedStyle(c);
  // the visible proxy: check parent chain + siblings for a rendered box
  const parent=c.parentElement;
  const pHtml=parent?parent.outerHTML.slice(0,500):'';
  // find clickable visible element near the checkbox
  let proxy=null;
  if(parent){
    const cand=[...parent.querySelectorAll('*')].filter(e=>{const rr=e.getBoundingClientRect(); const s=getComputedStyle(e); return rr.width>4&&rr.height>4&&s.display!=='none'&&s.visibility!=='hidden'&&e!==c;});
    proxy=cand.map(e=>({tag:e.tagName,cls:(e.className||'').toString().slice(0,40),role:e.getAttribute('role'),x:Math.round(e.getBoundingClientRect().x+e.getBoundingClientRect().width/2),y:Math.round(e.getBoundingClientRect().y+e.getBoundingClientRect().height/2)})).slice(0,8);
  }
  return {inputId:c.id, inputRect:{w:Math.round(r.width),h:Math.round(r.height),x:Math.round(r.x),y:Math.round(r.y)}, inputDisplay:cs.display, inputOpacity:cs.opacity, parentTag:parent?parent.tagName:'', parentHtml:pHtml, proxies:proxy};
}
""")
print(json.dumps(d, indent=1)[:1800])
