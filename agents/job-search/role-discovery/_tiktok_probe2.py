#!/usr/bin/env python3
"""Probe v2: open select[0] with retries + longer waits, dump option text and
any portal DOM, to learn WHY index-0 options come back empty."""
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
        page = b.contexts[0].new_page()
        page.goto(apply_url, wait_until="domcontentloaded")
        for _ in range(20):
            page.wait_for_timeout(1500)
            if page.evaluate("()=>document.querySelectorAll('.ud__select.select__1A5Um').length>=2"): break
        for i in (0,1):
            print(f"=== select[{i}] ===")
            for attempt in range(4):
                page.evaluate("(i)=>document.querySelectorAll('.ud__select.select__1A5Um')[i].scrollIntoView({block:'center'})", i)
                page.wait_for_timeout(700)
                box=page.evaluate("(i)=>{const r=document.querySelectorAll('.ud__select.select__1A5Um')[i].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}}", i)
                page.mouse.click(box["x"], box["y"])
                page.wait_for_timeout(900)
                dump=page.evaluate(r"""()=>{
                  const items=[...document.querySelectorAll('.ud__select__list__item')];
                  const vis=items.filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;});
                  // any dropdown portal present?
                  const portals=[...document.querySelectorAll('[class*="ud__select__list"],[class*="dropdown"],[class*="portal"]')].map(e=>e.className).slice(0,8);
                  return {totalItems:items.length, visItems:vis.length, visText:vis.map(e=>e.innerText.trim()), portals};
                }""")
                print(f"  attempt{attempt}:", json.dumps(dump))
                if dump["visItems"]>0:
                    break
                page.keyboard.press("Escape"); page.wait_for_timeout(300)
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        page.close()

if __name__=="__main__":
    main(sys.argv[1])
