#!/usr/bin/env python3
"""Autofill-tenant Ashby runner: upload FIRST, let autofill rebuild + prefill,
then fill remaining fields by VISIBLE LABEL (not stale plan field-names), then submit.

Usage: ashby_autofill_runner.py <plan_path> <fills_json> [--no-submit]
  fills_json: {"text": {"<label>": "<value>"}, "radios": {"<label>": "<option>"},
               "checkboxes": {"<label>": ["<opt>"]}}
"""
import json, os, sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
def log(m): print(f"[af-runner] {m}", file=sys.stderr, flush=True)

JS_FILL_BY_LABEL = r"""
(spec) => {
  const setNative=(el,val)=>{const p=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(p,'value').set.call(el,val);
    el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
  const norm=(s)=>(s||'').replace(/\u00a0/g,' ').replace(/\s+/g,' ').replace(/\*$/,'').trim().toLowerCase();
  const findContainer=(label)=>{
    const nl=norm(label);
    const els=[...document.querySelectorAll('label, span, div, p')].filter(e=>{const t=norm(e.textContent); return t===nl || (t.length<nl.length+40 && t.startsWith(nl.slice(0,Math.min(60,nl.length))));});
    for(const e of els){let c=e;for(let k=0;k<8&&c;k++){if(c.querySelector('input,textarea,button[role],div[class*="_yesno_"],label'))return c;c=c.parentElement;}}
    return null;
  };
  const out={text:[],radios:[],checkboxes:[]};
  // text: find input/textarea near label
  for(const [label,val] of Object.entries(spec.text||{})){
    const c=findContainer(label);
    let inp=c?c.querySelector('input[type=text],input:not([type]),input[type=email],input[type=tel],input[type=url],textarea'):null;
    if(!inp){
      // fallback: input whose aria-label or placeholder matches
      inp=[...document.querySelectorAll('input,textarea')].find(i=>((i.getAttribute('aria-label')||'')+(i.placeholder||'')).toLowerCase().includes(label.toLowerCase()));
    }
    if(inp){setNative(inp,val);out.text.push({label,ok:inp.value===val,val:inp.value.slice(0,18)});}
    else out.text.push({label,ok:false,reason:'no-input'});
  }
  // radios: click matching option button/label within container
  for(const [label,opt] of Object.entries(spec.radios||{})){
    const c=findContainer(label);
    if(!c){out.radios.push({label,ok:false,reason:'no-container'});continue;}
    const cand=[...c.querySelectorAll('button,label')];
    const m=cand.find(x=>x.textContent.trim()===opt)||cand.find(x=>x.textContent.trim().startsWith(opt));
    if(m){m.click();out.radios.push({label,ok:true,clicked:opt});}
    else out.radios.push({label,ok:false,reason:'no-opt',seen:cand.map(x=>x.textContent.trim()).slice(0,8)});
  }
  for(const [label,vals] of Object.entries(spec.checkboxes||{})){
    const c=findContainer(label);
    if(!c){out.checkboxes.push({label,ok:false,reason:'no-container'});continue;}
    for(const want of vals){
      const cand=[...c.querySelectorAll('button,label')];
      const m=cand.find(x=>x.textContent.trim()===want)||cand.find(x=>x.textContent.trim().startsWith(want));
      if(m){m.click();out.checkboxes.push({label,want,ok:true});}else out.checkboxes.push({label,want,ok:false});
    }
  }
  return out;
}
"""
JS_SUBMIT=r"""()=>{const b=[...document.querySelectorAll('button')].find(x=>/submit application/i.test(x.textContent));if(b){b.scrollIntoView();b.click();return 'clicked';}return 'notfound';}"""

def main():
    plan_path=sys.argv[1]; fills=json.loads(sys.argv[2]); no_submit='--no-submit' in sys.argv
    plan=json.load(open(plan_path))
    url=plan['url']; pdf=plan.get('pdf_path_staged') or plan.get('pdf_path_local')
    pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
    ctx=br.contexts[0]; page=ctx.pages[0] if ctx.pages else ctx.new_page()
    log(f"navigate {url}/application")
    page.goto(url.rstrip('/')+'/application',wait_until='domcontentloaded',timeout=45000)
    page.wait_for_timeout(2500)
    # upload FIRST (top autofill widget OR the resume field — pick first file input)
    fi=page.query_selector('input[type=file]')
    if fi: fi.set_input_files(pdf,timeout=10000); log("uploaded first")
    else: log("no file input")
    log("waiting for autofill to rebuild + prefill...")
    page.wait_for_timeout(6000)
    # fill remaining by label (real keystrokes for text where possible)
    for label,val in (fills.get('text') or {}).items():
        try:
            loc=page.get_by_label(label, exact=False).first
            loc.fill('',timeout=2500); loc.click(timeout=2500); page.keyboard.type(val,delay=8)
        except Exception as e:
            log(f"kbd fill skip {label}: {str(e)[:60]}")
    # comboboxes (Ashby typeahead: click, type, pick option) - Playwright side
    for label,val in (fills.get('comboboxes') or {}).items():
        try:
            loc=page.get_by_label(label, exact=False).first
            loc.click(timeout=3000)
            page.keyboard.type(val, delay=20)
            page.wait_for_timeout(1200)
            # pick first matching option in listbox
            opt=page.locator('[role=option]').filter(has_text=val).first
            if opt.count()==0: opt=page.locator('[role=option]').first
            opt.click(timeout=3000)
            log(f"combobox {label} -> {val}")
        except Exception as e:
            log(f"combobox fail {label}: {str(e)[:70]}")
    r=page.evaluate(JS_FILL_BY_LABEL, fills)
    log(f"fill-by-label: {json.dumps(r)[:400]}")
    page.wait_for_timeout(800)
    if no_submit:
        body=page.evaluate("()=>document.body.innerText.slice(0,1000)")
        print(json.dumps({"ok":True,"no_submit":True,"fill":r,"body":body})); return
    sc=page.evaluate(JS_SUBMIT); log(f"submit {sc}")
    page.wait_for_timeout(8000)
    body=page.evaluate("()=>document.body.innerText")
    ok='successfully submitted' in body.lower() or 'received your application' in body.lower()
    print(json.dumps({"ok":ok,"submit":sc,"fill":r,"body":body[:700]}))

if __name__=='__main__': main()
