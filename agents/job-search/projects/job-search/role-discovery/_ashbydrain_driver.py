#!/usr/bin/env python3
"""Ashby residential-drain serial driver. Runs the proven residential path per
role, parses runner classify, banks confirmed submits, logs blocks. SOLE worker."""
import sqlite3, os, re, json, subprocess, sys, time, datetime, glob

ROOT='/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
RD=os.path.join(ROOT,'role-discovery')
DB=os.path.join(ROOT,'tracker.db')
SUB=os.path.join(ROOT,'applications','submitted')
OUT=os.path.join(RD,'output')
PY=os.path.join(RD,'.venv','bin','python3')
CDP=os.environ.get('JOBSEARCH_CDP','http://127.0.0.1:19223')
PER_ROLE_TIMEOUT=460  # ~7.5 min hard cap per role

WORK=[597,836,938,967,968,970,971,1235,1361,1362,1382,1385,
      1134,1359,1387,1388,1389,1390,1391,756,1397,1015,1112,1119,1124,1126]
WORK=sorted(set(WORK))

def now(): return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def today(): return datetime.date.today().isoformat()

def slug_uuid(u):
    m=re.match(r'https?://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]+)',u or '')
    if not m: return None,None
    return m.group(1), m.group(2)

def find_plan(uuid):
    if not uuid: return None
    g=glob.glob(os.path.join(OUT,f'inline-plan-*{uuid}.json'))
    return g[0] if g else None

def find_submit_dir(uuid):
    if not uuid: return None
    for d in os.listdir(SUB):
        if d.endswith(uuid): return os.path.join(SUB,d)
    return None

TMP_UPLOADS='/tmp/openclaw/uploads'
import shutil
def stage_resume(plan, uuid):
    """Copy the plan's expected /tmp/openclaw/uploads resume PDF from the role's
    submitted/<slug>/ dir (where it actually persists). Returns staged path or None."""
    try:
        txt=open(plan).read()
    except Exception:
        return None
    tmps=set(re.findall(r'/tmp/openclaw/uploads/[^"\\ ]+\.pdf',txt))
    resume=[t for t in tmps if 'resume' in t.lower()]
    if not resume:
        return None
    target=resume[0]; base=os.path.basename(target)
    os.makedirs(TMP_UPLOADS,exist_ok=True)
    if os.path.exists(target):
        return target
    sd=find_submit_dir(uuid)
    src=os.path.join(sd,base) if sd else None
    if src and os.path.exists(src):
        shutil.copy2(src,target)
        print(f"  staged resume {base} <- submitted dir",flush=True)
        return target
    # fallback: any *Resume*.pdf in the submitted dir
    if sd:
        cands=sorted(glob.glob(os.path.join(sd,'*esume*.pdf')))
        if cands:
            shutil.copy2(cands[-1],target)
            print(f"  staged resume {os.path.basename(cands[-1])} -> {base} (fallback)",flush=True)
            return target
    print(f"  WARN: could not stage resume {base} (no source found)",flush=True)
    return None

def job_not_found(subresp):
    return bool(subresp) and bool(re.search(r'job not found|no longer accepting|position (is )?closed|not currently accepting',subresp,re.I))

def disk_already_submitted(uuid):
    sd=find_submit_dir(uuid)
    if not sd: return False
    sp=os.path.join(sd,'STATUS.md')
    if not os.path.exists(sp): return False
    up=open(sp).read().upper()
    return bool(re.search(r'STATUS:\s*SUBMITTED',up) or 'SUBMITTED ✅' in open(sp).read()
                or 'APPLICATION SUCCESS' in up or 'SUCCESSFULLY SUBMITTED' in up
                or 'FORMSUBMITSUCCESS' in up)

def run():
    c=sqlite3.connect(DB)
    results={}
    for rid in WORK:
        row=c.execute('SELECT id,company,role,app_url FROM roles WHERE id=?',(rid,)).fetchone()
        if not row:
            results[rid]=('skip','no-row'); continue
        _,comp,role,url=row
        org,uuid=slug_uuid(url)
        print(f"\n===== role {rid} {comp} | {role[:45]} =====",flush=True)
        print(f"  url={url}",flush=True)
        # idempotency: disk already submitted?
        if disk_already_submitted(uuid):
            print(f"  SKIP: disk already SUBMITTED",flush=True)
            results[rid]=('skip','already-submitted-disk'); continue
        plan=find_plan(uuid)
        if not plan:
            print(f"  no plan -> re-prep via inline_submit",flush=True)
            try:
                pr=subprocess.run([PY,'inline_submit.py','--role-id',str(rid),'--ats','ashby','--dry-run'],
                                  cwd=RD,capture_output=True,text=True,timeout=300)
                print(pr.stdout[-1500:],flush=True)
                if pr.returncode!=0: print("PREP STDERR:",pr.stderr[-800:],flush=True)
            except Exception as e:
                print(f"  prep failed: {e}",flush=True)
            plan=find_plan(uuid)
        if not plan:
            print(f"  STILL no plan -> BLOCK",flush=True)
            results[rid]=('block','no-plan-could-not-prep'); continue
        # stage the resume PDF the plan expects (persisted in submitted dir)
        stage_resume(plan, uuid)
        # run the residential submit
        env=dict(os.environ)
        env['JOBSEARCH_CDP']=CDP; env['ENABLE_CAPSOLVER']='1'
        t0=time.time()
        classify='error'; err=None; subresp=None; ok=False
        try:
            pr=subprocess.run([PY,'_ashby_runner.py',plan],cwd=RD,env=env,
                              capture_output=True,text=True,timeout=PER_ROLE_TIMEOUT)
            raw=pr.stdout
            # runner prints stderr logs + final JSON to stdout
            jstart=raw.rfind('\n{')
            if jstart<0 and raw.strip().startswith('{'): jstart=0
            try:
                j=json.loads(raw[jstart:]) if jstart>=0 else json.loads(raw)
            except Exception:
                # last resort: find last {...} block
                m=list(re.finditer(r'\{[\s\S]*\}',raw))
                j=json.loads(m[-1].group(0)) if m else {}
            classify=j.get('classify','?'); err=j.get('error'); ok=j.get('ok'); subresp=(j.get('submit_response') or '')[:400]
            print(f"  RUNNER classify={classify} ok={ok} err={err} ({time.time()-t0:.0f}s)",flush=True)
            if pr.stderr: print("  [stderr tail]",pr.stderr[-600:],flush=True)
        except subprocess.TimeoutExpired:
            classify='timeout'; err=f'per-role timeout {PER_ROLE_TIMEOUT}s'
            print(f"  TIMEOUT after {PER_ROLE_TIMEOUT}s",flush=True)
        except Exception as e:
            classify='error'; err=str(e)
            print(f"  ERROR {e}",flush=True)
        # detect already-applied surfaced by Ashby
        already = subresp and re.search(r'already (applied|submitted)|previously applied',subresp,re.I)
        if classify=='submitted':
            results[rid]=('submitted',subresp or 'FormSubmitSuccess')
        elif already:
            results[rid]=('skip',f'ashby-reports-already-applied')
        elif job_not_found(subresp):
            results[rid]=('block','closed-req: Ashby job-not-found/closed')
        else:
            reason=err or classify
            results[rid]=('block',f'{classify}: {reason}')
        # persist incremental result file
        with open(os.path.join(RD,'.ashbydrain-results.json'),'w') as f:
            json.dump({str(k):v for k,v in results.items()},f,indent=2)
    return results

if __name__=='__main__':
    cli=[int(x) for x in sys.argv[1:] if x.isdigit()]
    if cli:
        WORK=sorted(set(cli))
        print(f"WORK overridden from CLI: {WORK}",flush=True)
    r=run()
    print("\n\n===== FINAL =====",flush=True)
    for k in sorted(r): print(k,r[k],flush=True)
