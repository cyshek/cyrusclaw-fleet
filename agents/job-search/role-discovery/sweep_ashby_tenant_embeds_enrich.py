"""Enrich sweep JSON with CDP-render verdicts (real form vs JD-only page)."""
import json, time, requests, websocket, sys

CDP_HTTP = "http://127.0.0.1:18802"

def open_tab(url):
    r = requests.put(f"{CDP_HTTP}/json/new?{url}", timeout=10); r.raise_for_status()
    return r.json()
def close_tab(tid):
    try: requests.get(f"{CDP_HTTP}/json/close/{tid}", timeout=5)
    except: pass
def eval_js(ws, expr):
    mid = int(time.time()*1000)%1000000
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True,"awaitPromise":True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id")==mid:
            return m.get("result",{}).get("result",{}).get("value")

def render_probe(url, wait=8):
    tab = open_tab(url)
    try:
        ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
        time.sleep(wait)
        r = eval_js(ws, """(function(){
            const scripts = [...document.scripts].map(s=>s.src).filter(s=>/recaptcha|hcaptcha|turnstile|cloudflare/i.test(s));
            const resume = !!document.querySelector('#_systemfield_resume');
            const fileInputs = [...document.querySelectorAll('input[type=file]')].length;
            const applyLinks = [...document.querySelectorAll('a')].filter(a=>/apply/i.test(a.textContent||'')||/apply/i.test(a.getAttribute('aria-label')||'')).map(a=>({text:(a.textContent||'').trim().slice(0,60),href:a.href}));
            const subBtns = [...document.querySelectorAll('button')].filter(b=>/submit|apply/i.test(b.textContent||'')).map(b=>(b.textContent||'').trim().slice(0,60));
            return {captchaScripts:scripts, hasResumeInput:resume, fileInputs, applyLinks, submitButtons:subBtns,
                    grecaptcha: typeof window.grecaptcha !== 'undefined',
                    turnstile: typeof window.turnstile !== 'undefined',
                    hcaptcha: typeof window.hcaptcha !== 'undefined'};
        })()""")
        ws.close()
        return r
    finally: close_tab(tab["id"])

sweep_path = sys.argv[1]
with open(sweep_path) as f: data = json.load(f)

for t in data["tenants"]:
    w = t.get("winner")
    if not w or t["verdict"] != "embed_clean":
        continue
    url = w["url"]
    print(f"  CDP probe: {t['tenant']} → {url}")
    try:
        r = render_probe(url)
    except Exception as e:
        r = {"error": str(e)}
    w["cdp_probe"] = r
    # Determine true verdict: needs hasResumeInput=True AND no captcha to qualify as "inlined-form embed"
    if r.get("hasResumeInput") and not (r.get("grecaptcha") or r.get("turnstile") or r.get("hcaptcha") or r.get("captchaScripts")):
        t["verdict"] = "embed_form_inlined_clean"
        t["verdict_reason"] = "cdp: hasResumeInput=True, no captcha globals"
    elif r.get("hasResumeInput") and (r.get("grecaptcha") or r.get("turnstile") or r.get("hcaptcha")):
        t["verdict"] = "embed_form_inlined_captcha"
        t["verdict_reason"] = f"cdp: hasResumeInput=True but captcha global present"
    else:
        # Only JD-detail page; apply link goes back to ashbyhq.com
        apply_to_ashby = any("ashbyhq.com" in (l.get("href") or "") for l in (r.get("applyLinks") or []))
        t["verdict"] = "jd_page_only_links_to_ashby" if apply_to_ashby else "jd_page_only"
        t["verdict_reason"] = f"cdp: no form widgets on page; applyLinks={r.get('applyLinks')}"

# also CDP-probe cursor as reference row
print("  CDP probe: cursor (reference) → cursor.com/careers/forward-deployed-engineer")
try:
    cursor_probe = render_probe("https://cursor.com/careers/forward-deployed-engineer")
except Exception as e:
    cursor_probe = {"error": str(e)}
data["reference"] = {
    "cursor": {
        "publicWebsite": "https://www.cursor.com",
        "customJobsPageUrl": "https://cursor.com/careers",
        "embed_pattern": "publicWebsite/careers/<role-slug>",
        "cdp_probe": cursor_probe,
        "verdict": "embed_form_inlined_clean" if cursor_probe.get("hasResumeInput") else "unknown",
    }
}

# recompute summary
data["summary"] = {
    "total": len(data["tenants"]),
    "embed_form_inlined_clean": sum(1 for r in data["tenants"] if r["verdict"]=="embed_form_inlined_clean"),
    "embed_form_inlined_captcha": sum(1 for r in data["tenants"] if r["verdict"]=="embed_form_inlined_captcha"),
    "jd_page_only_links_to_ashby": sum(1 for r in data["tenants"] if r["verdict"]=="jd_page_only_links_to_ashby"),
    "jd_page_only": sum(1 for r in data["tenants"] if r["verdict"]=="jd_page_only"),
    "no_embed": sum(1 for r in data["tenants"] if r["verdict"].startswith("no_embed")),
    "gql_failed": sum(1 for r in data["tenants"] if r["verdict_reason"]=="gql_failed"),
}

with open(sweep_path,"w") as f: json.dump(data, f, indent=2)
print(f"\nUpdated {sweep_path}")
print("Summary:", json.dumps(data["summary"], indent=2))
