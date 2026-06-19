import os,json
from playwright.sync_api import sync_playwright
CDP=os.environ.get("JOBSEARCH_CDP","http://127.0.0.1:18800")
URL="https://jobs.ashbyhq.com/hudu/fa361248-7260-4b1b-8800-2e7f37deaccd/application"
pw=sync_playwright().start();b=pw.chromium.connect_over_cdp(CDP)
pg=b.contexts[0].new_page();pg.goto(URL,wait_until="domcontentloaded");pg.wait_for_timeout(5000)
res=pg.evaluate("""()=>{const out=[];for(const el of document.querySelectorAll('[data-field-path]')){const lbl=(el.querySelector('label')||{}).textContent||'';const radios=[...el.querySelectorAll('input[type=radio]')].map(r=>{const l=document.querySelector(`label[for='${r.id}']`)||r.closest('label');return l?l.textContent.trim():r.value;});if(radios.length)out.push({lbl:lbl.slice(0,90),opts:radios});}return out;}""")
print(json.dumps(res,indent=1));pg.close()
