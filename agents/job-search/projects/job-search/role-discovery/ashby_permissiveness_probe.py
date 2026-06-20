"""Click Submit on each tenant's /application page WITHOUT filling anything.
Classify the response:
  - spam-flag text -> server-side spam policy fires BEFORE field validation (STRICT)
  - form-validation text -> server validates fields first (PERMISSIVE — worth a real attempt)
  
Also: try with a CapSolver-injected token first, since some pages won't even call submit without a token.
"""
import json, urllib.request, time, subprocess, sys, os
from websocket import create_connection

PORT=18801; HTTP=f"http://127.0.0.1:{PORT}"
PY = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.venv/bin/python3"
SOLVER = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/solve_recaptcha_v3.py"
SITEKEY = "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"

TENANTS = [
    ("Cohere", 597, "https://jobs.ashbyhq.com/cohere/929b6c8e-a47c-4512-bb17-99fa9581f23e/application"),
    ("Sierra", 854, "https://jobs.ashbyhq.com/sierra/422cb7bb-ab03-447b-808c-6d72f59bbd2f/application"),
    ("Attio", 967, "https://jobs.ashbyhq.com/attio/d48617ff-be9b-41cd-aff7-3ad2f826ca74/application"),
    ("Mercor", 1237, "https://jobs.ashbyhq.com/mercor/9c546843-035f-4400-9d0d-d5de5f7205ff/application"),
    ("Blaxel", 1360, "https://jobs.ashbyhq.com/blaxel/4acea42a-589d-42b1-949e-d4ec4b8907a2/application"),
    ("NeuralConcept", 1365, "https://jobs.ashbyhq.com/neuralconcept/b37daf93-77bf-4428-ad02-f39df3917035/application"),
    ("Encord", 1618, "https://jobs.ashbyhq.com/encord/9f97576a-5381-4839-a7cf-ebfa82089a63/application"),
    ("Profound", 1621, "https://jobs.ashbyhq.com/profound/b076c997-0ba3-4d3c-9dc9-ad0b3ed49b05/application"),
    ("Meticulous", 1622, "https://jobs.ashbyhq.com/meticulous/e4f7bc5d-1aac-4ed7-a8c3-b4f96002d416/application"),
    # Reference: known strict
    ("Baseten_REF", 944, "https://jobs.ashbyhq.com/baseten/54c83823-574e-40ad-9cff-a57acff0ffe6/application"),
    # Reference: known permissive
    ("Skydio_REF", 862, "https://jobs.ashbyhq.com/skydio/d73ae64d-5877-4ab6-ad42-0224702f3fba/application"),
]

env = os.environ.copy(); env["ENABLE_CAPSOLVER"] = "1"

def solve_one(page_url):
    cmd = [PY, SOLVER, "--stdin",
           "--fallback-sitekey", SITEKEY,
           "--page-url", page_url,
           "--action", "job_apply",
           "--min-score", "0.7"]
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

INJECT_JS_TPL = """((token) => {
  const ids=['g-recaptcha-response','g-recaptcha-response-100000'];
  for (const id of ids) {
    let el=document.getElementById(id);
    if (!el){ el=document.createElement('textarea'); el.id=id; el.name=id; el.style.display='none'; document.body.appendChild(el); }
    el.value = token;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  return true;
})(__TOKEN__)"""

CLICK_SUBMIT_JS = """(() => {
  const btn = [...document.querySelectorAll('button')].find(b => /submit application/i.test((b.textContent||'').trim()));
  if (!btn) return {ok: false, reason: 'no submit btn'};
  btn.click();
  return {ok: true, btnText: btn.textContent.slice(0,40)};
})()"""

OUTCOME_JS = """(() => {
  const t = document.body.innerText || '';
  // Check for various Ashby response patterns
  return {
    spam: /spam|flagged/i.test(t),
    success: /thanks for applying|application has been received|successfully submitted/i.test(t),
    formInvalid: /please complete|please fill|is required|please select|field is required|please enter|missing/i.test(t),
    errorBanner: /couldn't submit|cannot submit|unable to submit|something went wrong/i.test(t),
    title: document.title, url: location.href,
    excerpt: t.slice(0, 500),
  };
})()"""

results = {}
for name, rid, url in TENANTS:
    print(f"\n=== {name} (id={rid}) ===")
    # Solve captcha first (since some tenants gate the submit click on token presence)
    print("  solving captcha...")
    tok = solve_one(url)
    if not tok:
        print("  no token; skipping"); continue
    print(f"  token len={len(tok)}")
    # Open page
    tab = open_tab(url)
    cdp = CDP(tab['webSocketDebuggerUrl'])
    cdp.send('Page.enable'); cdp.send('Runtime.enable')
    time.sleep(7)
    # Inject token
    r = cdp.send('Runtime.evaluate', {'expression': INJECT_JS_TPL.replace('__TOKEN__', json.dumps(tok)), 'returnByValue': True, 'timeout': 5000})
    # Try click submit
    r = cdp.send('Runtime.evaluate', {'expression': CLICK_SUBMIT_JS, 'returnByValue': True, 'timeout': 5000})
    print(f"  click submit: {r.get('result',{}).get('result',{}).get('value', {})}")
    time.sleep(6)
    # Outcome
    r = cdp.send('Runtime.evaluate', {'expression': OUTCOME_JS, 'returnByValue': True, 'timeout': 5000})
    out = r.get('result',{}).get('result',{}).get('value', {})
    classification = (
        "SPAM-STRICT" if out.get('spam')
        else ("SUCCESS!" if out.get('success')
              else ("PERMISSIVE-form-validation" if out.get('formInvalid')
                    else ("UNKNOWN-error" if out.get('errorBanner') else "UNKNOWN")))
    )
    print(f"  >> {classification}  spam={out.get('spam')} fmtErr={out.get('formInvalid')} errBan={out.get('errorBanner')}")
    print(f"     excerpt: {out.get('excerpt','')[:200]}")
    results[name] = {'id': rid, 'url': url, 'classification': classification, **out}
    try: urllib.request.urlopen(f"{HTTP}/json/close/{tab['id']}")
    except: pass

open('/tmp/tenant_perm_probe_results.json','w').write(json.dumps(results, indent=2, default=str))
print('\n\nWrote /tmp/tenant_perm_probe_results.json')
print('\n=== SUMMARY ===')
for k, v in results.items():
    print(f"  {k}: {v.get('classification')}")
