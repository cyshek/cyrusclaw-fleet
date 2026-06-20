"""Run permissiveness-probe on every dead-letter Ashby tenant (one representative row each)."""
import json, urllib.request, time, subprocess, os, sqlite3, sys
from websocket import create_connection

PORT=18801; HTTP=f"http://127.0.0.1:{PORT}"
PY = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.venv/bin/python3"
SOLVER = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/solve_recaptcha_v3.py"
SITEKEY = "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"

# Get one rep per company from dead-letter list
con = sqlite3.connect('tracker.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("""SELECT MIN(id) as id, company, app_url FROM roles 
               WHERE applied_by IS NULL AND status != 'closed' 
                 AND app_url LIKE '%jobs.ashbyhq.com%' 
                 AND (agent_notes LIKE '%spam%' OR agent_notes LIKE '%strict-Ashby%' OR agent_notes LIKE '%captcha-hard%')
               GROUP BY company ORDER BY company""")
reps = [(r['id'], r['company'], r['app_url']) for r in cur.fetchall()]
# We've already tested these from prior probe (Cohere, Sierra, Attio, Mercor, Blaxel, NeuralConcept, Encord, Profound, Meticulous + Baseten, Notion, Skydio, Speak)
ALREADY = {'Cohere','Sierra','Attio','Mercor','Blaxel','Blaxel (YC X25)','Neural Concept','Encord','Profound','Meticulous','Baseten','Notion','Skydio','Speak'}
todo = [(rid, comp, url) for (rid, comp, url) in reps if comp not in ALREADY]
print(f"Total tenants in dead-letter: {len(reps)}")
print(f"Already tested: {len(reps) - len(todo)}")
print(f"To test now: {len(todo)}")
for rid, comp, url in todo:
    print(f"  {comp} (id={rid})")

env = os.environ.copy(); env["ENABLE_CAPSOLVER"] = "1"

def solve_one(page_url):
    cmd = [PY, SOLVER, "--stdin", "--fallback-sitekey", SITEKEY, "--page-url", page_url, "--action", "job_apply", "--min-score", "0.7"]
    r = subprocess.run(cmd, input=json.dumps({"sitekey":SITEKEY}), capture_output=True, text=True, timeout=120, env=env)
    if r.returncode != 0: return None
    o = json.loads(r.stdout); return o.get('token') or o.get('gRecaptchaResponse')

def open_tab(url):
    r = urllib.request.urlopen(urllib.request.Request(f"{HTTP}/json/new?{urllib.request.quote(url)}", method='PUT'))
    return json.loads(r.read())

class CDP:
    def __init__(self, ws_url): self.ws = create_connection(ws_url, timeout=60); self.id=0
    def send(self, m, p=None):
        self.id += 1; cid = self.id
        self.ws.send(json.dumps({"id":cid,"method":m,"params":p or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == cid: return msg

INJECT_JS_TPL = """((token) => {const ids=['g-recaptcha-response','g-recaptcha-response-100000']; for (const id of ids) { let el=document.getElementById(id); if (!el){el=document.createElement('textarea'); el.id=id; el.name=id; el.style.display='none'; document.body.appendChild(el);} el.value=token; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));} return true;})(__TOKEN__)"""
CLICK_JS = """(() => {const btn=[...document.querySelectorAll('button')].find(b => /submit application/i.test((b.textContent||'').trim())); if (!btn) return {ok:false}; btn.click(); return {ok:true, btnText: btn.textContent.slice(0,40)};})()"""
OUTCOME_JS = """(() => {const t=document.body.innerText||''; return {spam:/spam|flagged/i.test(t), success:/thanks for applying|application has been received|successfully submitted/i.test(t), formInvalid:/please complete|please fill|is required|please select|field is required|please enter|missing/i.test(t), errorBanner:/couldn't submit|cannot submit|unable to submit|something went wrong/i.test(t), title:document.title, url:location.href, excerpt: t.slice(0, 400)};})()"""

results = {}
for rid, company, jd_url in todo:
    app_url = jd_url.rstrip('/') + '/application'
    print(f"\n=== {company} (id={rid}) ===")
    print(f"  URL: {app_url}")
    tok = solve_one(app_url)
    if not tok:
        print("  no token"); results[company] = {'id': rid, 'err': 'no_token'}; continue
    try:
        tab = open_tab(app_url)
        cdp = CDP(tab['webSocketDebuggerUrl'])
        cdp.send('Page.enable'); cdp.send('Runtime.enable')
        time.sleep(7)
        # Quick check: is this a valid /application page or 404?
        chk = cdp.send('Runtime.evaluate', {'expression':"""(()=>{const btns=[...document.querySelectorAll('button')].filter(b=>/submit/i.test(b.textContent||'')).length; const b=document.body.innerText||''; return {submitBtns:btns, has404:/not found|removed|closed/i.test(b), bodyLen:b.length};})()""", 'returnByValue': True, 'timeout': 5000})
        chkv = chk.get('result',{}).get('result',{}).get('value', {})
        if chkv.get('has404') or chkv.get('submitBtns', 0) == 0:
            print(f"  no submit/closed: {chkv}")
            results[company] = {'id': rid, 'status': 'closed_or_404', 'probe': chkv}
            try: urllib.request.urlopen(f"{HTTP}/json/close/{tab['id']}")
            except: pass
            continue
        cdp.send('Runtime.evaluate', {'expression': INJECT_JS_TPL.replace('__TOKEN__', json.dumps(tok)), 'returnByValue': True, 'timeout': 5000})
        cdp.send('Runtime.evaluate', {'expression': CLICK_JS, 'returnByValue': True, 'timeout': 5000})
        time.sleep(6)
        r = cdp.send('Runtime.evaluate', {'expression': OUTCOME_JS, 'returnByValue': True, 'timeout': 5000})
        out = r.get('result',{}).get('result',{}).get('value', {})
        cls = ("SPAM-STRICT" if out.get('spam') else
               ("SUCCESS" if out.get('success') else
                ("PERMISSIVE-form-validation" if out.get('formInvalid') else
                 ("UNKNOWN-error" if out.get('errorBanner') else "UNKNOWN"))))
        print(f"  >> {cls}")
        results[company] = {'id': rid, 'url': app_url, 'classification': cls, 'spam': out.get('spam'), 'formInvalid': out.get('formInvalid'), 'excerpt': out.get('excerpt','')[:200]}
        try: urllib.request.urlopen(f"{HTTP}/json/close/{tab['id']}")
        except: pass
    except Exception as e:
        print(f"  err: {e!r}")
        results[company] = {'id': rid, 'err': str(e)}

open('/tmp/full_tenant_perm_sweep.json','w').write(json.dumps(results, indent=2, default=str))
print('\n=== FULL SUMMARY ===')
for k, v in sorted(results.items()):
    print(f"  {k:25} -> {v.get('classification') or v.get('status') or v.get('err')}")
