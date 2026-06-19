#!/usr/bin/env python3
"""Probe a TikTok referral apply form: enumerate ALL .ud__select dropdowns,
read each one's question label + options, count required selects. Reuses the
live authed CDP session. Usage: _tiktok_probe.py <job_id>"""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CDP = "http://127.0.0.1:18800"
REFERRALS = ROOT / ".referrals.json"

def tok():
    d = json.loads(REFERRALS.read_text())
    return d["tiktok"]["referral_link"].split("token=",1)[1].split("&",1)[0]

def main(job_id):
    t = tok()
    apply_url = f"https://lifeattiktok.com/referral/tiktok/resume/{job_id}/apply?token={t}"
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = ctx.new_page()
        page.goto(apply_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        # wait for form
        for _ in range(20):
            page.wait_for_timeout(1500)
            n = page.evaluate("()=>document.querySelectorAll('.ud__select.select__1A5Um').length")
            if n >= 1:
                break
        print("URL:", page.url)
        info = page.evaluate(r"""()=>{
          const out=[];
          const sels=[...document.querySelectorAll('.ud__select.select__1A5Um')];
          sels.forEach((s,i)=>{
            // find nearest question label: walk up to a container, grab preceding text
            let label='';
            let p=s;
            for(let up=0; up<6 && p; up++){
              p=p.parentElement;
              if(!p) break;
              const t=(p.innerText||'').trim();
              if(t && t.length<400){ label=t.split('\n')[0]; break; }
            }
            const cur=(s.innerText||'').trim();
            out.push({index:i, label:label.slice(0,200), current:cur});
          });
          // also detect required markers / other required inputs
          const reqStars=[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /required|\*/i.test(e.textContent||'')).length;
          const fileInputs=document.querySelectorAll('input[type=file]').length;
          const allSelects=document.querySelectorAll('.ud__select').length;
          return {selects:out, ud__select_1A5Um:sels.length, ud__select_total:allSelects, fileInputs};
        }""")
        print(json.dumps(info, indent=2))
        # Now open each select and read its options
        for i in range(info["ud__select_1A5Um"]):
            page.evaluate("(i)=>{const s=document.querySelectorAll('.ud__select.select__1A5Um')[i];s.scrollIntoView({block:'center'});}", i)
            page.wait_for_timeout(400)
            box=page.evaluate("(i)=>{const s=document.querySelectorAll('.ud__select.select__1A5Um')[i];const r=s.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};}", i)
            page.mouse.click(box["x"], box["y"])
            page.wait_for_timeout(500)
            opts=page.evaluate("""()=>[...document.querySelectorAll('.ud__select__list__item')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;}).map(e=>e.innerText.trim())""")
            print(f"SELECT[{i}] options:", opts)
            # close dropdown
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        page.close()

if __name__=="__main__":
    main(sys.argv[1])
