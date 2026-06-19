import re
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
h=page.evaluate(r"""
() => {
  const b=document.getElementById('desiredEmplSalaryBlock');
  return b?b.outerHTML:'NOT FOUND';
}
""")
h=re.sub(r'\s+',' ',h)
h=re.sub(r'class="[^"]{50,}"','class="..."',h)
# print interactive elements + sdf components in the block
print("LEN", len(h))
print(h[:2500])
