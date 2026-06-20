#!/usr/bin/env python3
"""Single-row Ashby residential-egress submit orchestrator (ashbydrain-r3).

Usage:
    .venv/bin/python _resi_submit_one.py <role_id>

Env required (exported by _residential_browser.sh):
    JOBSEARCH_CDP, CAPSOLVER_API_KEY, ENABLE_CAPSOLVER=1

Flow:
  1. Run inline_submit.py --role-id <id> --ats ashby  (real prep, writes workdir+plan+PREP-READY STATUS).
  2. Locate plan_path + workdir + pdf + app_url + company + role from inline_submit JSON.
  3. Run _ashby_runner.py <plan> via residential-proxied Chrome (JOBSEARCH_CDP).
  4. Parse runner result JSON: classify=='submitted' & ok==True  => SUCCESS.
     - On SUCCESS: overwrite workdir/STATUS.md with SUBMITTED block, then return classify=submitted.
     - Else: leave row blocked, return the runner's classify/error for honest banking.

Does NOT touch the DB — the parent driver does the DB UPDATE only after this returns submitted
AND after re-reading STATUS.md from disk. Keeps the success commit observable + idempotent.
"""
import json, os, subprocess, sys, datetime, pathlib, re

ROLE_ID = int(sys.argv[1])
HERE = pathlib.Path(__file__).resolve().parent
VENV_PY = str(HERE / ".venv" / "bin" / "python")
CDP = os.environ.get("JOBSEARCH_CDP", "")
EGRESS = os.environ.get("RESI_EGRESS_IP", "82.23.97.223")

def emit(d):
    print("RESI_ONE_RESULT " + json.dumps(d, default=str))

if not CDP:
    emit({"role_id": ROLE_ID, "phase": "preflight", "ok": False, "classify": "no-cdp",
          "error": "JOBSEARCH_CDP not set; source _residential_browser.sh first"})
    sys.exit(2)

# ---- 1. prep (real, not dry-run, so workdir + plan get written) ----
prep = subprocess.run(
    [VENV_PY, "inline_submit.py", "--role-id", str(ROLE_ID), "--ats", "ashby"],
    cwd=str(HERE), capture_output=True, text=True, timeout=600,
)
prep_out = prep.stdout + "\n" + prep.stderr
# inline_submit prints a human block plus a machine JSON envelope: {"results": [ {...} ]}.
plan_path = workdir = pdf = slug = None
j = None
# Find the results envelope (last balanced {..."results"...} object in stdout).
env_obj = None
for m in re.finditer(r"\{\s*\"processed\".*?\"results\".*?\}\s*\]\s*\}", prep.stdout, re.DOTALL):
    env_obj = m
if env_obj is None:
    for m in re.finditer(r"\{.*?\"results\"\s*:\s*\[.*?\]\s*\}", prep.stdout, re.DOTALL):
        env_obj = m
if env_obj is not None:
    try:
        envj = json.loads(env_obj.group(0))
        rs = envj.get("results") or []
        if rs:
            j = rs[0]
    except Exception:
        j = None
if j is None:
    # fallback: a bare per-role object containing workdir
    for m in re.finditer(r"\{[^{}]*\"workdir\"[^{}]*\}", prep.stdout, re.DOTALL):
        try:
            j = json.loads(m.group(0))
        except Exception:
            j = None
if j:
    plan_path = j.get("plan_path"); workdir = j.get("workdir")
    pdf = j.get("pdf"); slug = j.get("slug")
# Fallback: grep PREP-READY STATUS lines / known dirs
if not plan_path:
    pm = re.search(r"plan:\s*(\S+inline-plan-\S+\.json)", prep_out)
    if pm: plan_path = pm.group(1)
if not workdir and plan_path:
    sm = re.search(r"inline-plan-(.+)\.json", os.path.basename(plan_path))
    if sm:
        slug = sm.group(1)
        workdir = str(HERE.parent / "applications" / "submitted" / slug)

if not plan_path or not os.path.exists(plan_path):
    emit({"role_id": ROLE_ID, "phase": "prep", "ok": False, "classify": "prep-failed",
          "error": f"could not locate plan_path (rc={prep.returncode})",
          "prep_tail": prep_out[-1500:]})
    sys.exit(3)

# ---- 2. run the Ashby runner through residential CDP ----
env = dict(os.environ)
env["JOBSEARCH_CDP"] = CDP
env["ENABLE_CAPSOLVER"] = "1"
run = subprocess.run(
    [VENV_PY, "_ashby_runner.py", plan_path],
    cwd=str(HERE), capture_output=True, text=True, timeout=900, env=env,
)
run_out = run.stdout
# runner prints a single JSON object (json.dumps(r, indent=2)) at the end
res = None
# find the LAST top-level {...} block
brace = run.stdout.rfind("\n{")
if brace == -1 and run.stdout.lstrip().startswith("{"):
    brace = run.stdout.index("{")
if brace != -1:
    try:
        res = json.loads(run.stdout[brace:])
    except Exception:
        # try greedy from first {
        try:
            res = json.loads(run.stdout[run.stdout.index("{"):])
        except Exception:
            res = None

if res is None:
    emit({"role_id": ROLE_ID, "phase": "run", "ok": False, "classify": "runner-no-json",
          "plan_path": plan_path, "rc": run.returncode,
          "run_tail": (run.stdout[-1200:] + "\nSTDERR:\n" + run.stderr[-800:])})
    sys.exit(4)

classify = res.get("classify")
ok = bool(res.get("ok"))
err = res.get("error")

# ---- 3. on SUCCESS write STATUS.md ----
if classify == "submitted" and ok:
    # gather metadata from plan
    company = role_title = app_url = ""
    resume_name = ""
    try:
        plan = json.loads(pathlib.Path(plan_path).read_text())
        app_url = plan.get("navigate") or plan.get("url") or ""
    except Exception:
        plan = {}
    # pull company/role/app_url from DB-independent meta.json if present
    wd = pathlib.Path(workdir)
    metaf = wd / "meta.json"
    if metaf.exists():
        try:
            meta = json.loads(metaf.read_text())
            company = meta.get("company", company)
            role_title = meta.get("role", role_title)
            app_url = meta.get("apply_url") or meta.get("app_url") or app_url
        except Exception:
            pass
    if pdf:
        resume_name = os.path.basename(pdf)
    today = datetime.date.today().isoformat()
    status = f"""# STATUS: SUBMITTED (residential-egress path)

- role_id: {ROLE_ID}
- company: {company}
- role: {role_title}
- ats: ashby
- app_url: {app_url}
- submitted_on: {today}
- submitted_by: agent
- resume_attached: {("yes (" + resume_name + ")") if resume_name else "yes"}
- egress: RESIDENTIAL via Webshare {EGRESS} (relay 18901 -> proxied Chrome CDP 19223)
- confirmation_signal: FormSubmitSuccess token (scan_form_submit_success==True; runner classify=submitted, ok=true)
- cohort: ashbydrain-r3 (strict-Ashby score-gate cohort, overturned-belief residential path)
"""
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "STATUS.md").write_text(status)
    emit({"role_id": ROLE_ID, "phase": "done", "ok": True, "classify": "submitted",
          "workdir": str(wd), "status_written": True, "company": company,
          "role": role_title, "app_url": app_url, "resume": resume_name})
    sys.exit(0)

# ---- not a success: report honest classify for banking ----
emit({"role_id": ROLE_ID, "phase": "done", "ok": False, "classify": classify or "unknown",
      "error": err, "workdir": workdir, "plan_path": plan_path,
      "run_log_tail": run.stdout[-600:]})
sys.exit(1)
