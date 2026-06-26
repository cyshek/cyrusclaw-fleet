#!/usr/bin/env python3
"""Dispatch PREP-READY applications from the 2026-06-26 new company crawl batch."""
import os, re, sqlite3, subprocess, sys, time, json
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

env_file = Path.home() / ".openclaw/.env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

CDP = "http://127.0.0.1:18800"
RESI_CDP = "http://127.0.0.1:19223"
os.environ["JOBSEARCH_CDP"] = CDP
os.environ["ENABLE_CAPSOLVER"] = "1"

DB = SCRIPT_DIR.parent / "tracker.db"
SUBMITTED_DIR = SCRIPT_DIR.parent / "applications" / "submitted"
OUTPUT_DIR = SCRIPT_DIR / "output"
VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

LOG_PATH = SCRIPT_DIR / "dispatch_prep_ready_20260626.log"
log_fh = open(LOG_PATH, "a")

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_fh.write(line + "\n")
    log_fh.flush()

def run_cmd(cmd, timeout=300, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:\n        return -2, "", str(e)

def get_role_id_from_slug(slug):
    status_f = SUBMITTED_DIR / slug / "STATUS.md"
    if status_f.exists():
        m = re.search(r"role_id:\s*(\d+)", status_f.read_text())
        if m:\n            return int(m.group(1))\n    return None\n\ndef mark_applied(role_id, slug, method="auto"):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by=?, applied_on=?, prep_status='submitted' WHERE id=?",
        (method, TODAY, role_id)
    )
    conn.commit()
    conn.close()
    log(f"  [db] role {role_id} ({slug}) -> submitted")

def write_submitted_status(slug, role_id, confirmation="", extra=""):
    status_f = SUBMITTED_DIR / slug / "STATUS.md"
    if status_f.parent.exists():
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        content = f"SUBMITTED -- {ts}\n\nsubmitted_by: auto\napplied_on: {TODAY}\nrole_id: {role_id}\n"
        if confirmation:
            content += f"confirmation_text: {confirmation[:300]}\n"
        content += "\n" + extra
        status_f.write_text(content)

GREENHOUSE_SLUGS = [
    "anduril-5174111007",
    "anduril-5174533007",
    "anduril-5160396007",
    "axon-7773731003",
    "pure-storage-8023953",
    "axon-7651705003",
    "braze-7977103",
]

GH_IFRAME_SLUGS = [
    "waymo-8028573",
    "databricks-8609617002",
    "esri-5091854007",
    "esri-5151689007",
]

ASHBY_SLUGS = [
    "langchain-5ac59bcb-0245-4a82-bab0-0ebdeae07ccd",
    "anyscale-52167dfd-c1b0-4e8a-b64c-b5710e176535",
]

LEVER_SLUGS = [
    "pointclickcare-708c41cf",
]

results = {"submitted": [], "blocked": [], "failed": []}

def check_status(slug):
    status_f = SUBMITTED_DIR / slug / "STATUS.md"
    if not status_f.exists():
        return None, "no STATUS.md"
    text = status_f.read_text()
    if "SUBMITTED" in text:
        return "submitted", text
    if "PREP-READY" in text:
        return "prep-ready", text
    return "unknown", text

def submit_gh(slug):
    plan_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    if not plan_path.exists():
        return False, f"no plan at {plan_path}"
    st, text = check_status(slug)
    if st == "submitted":
        return True, "already submitted"
    if st != "prep-ready":
        return False, f"status={st}: {text[:100]}"
    log(f"  [gh_submit] submitting {slug}")
    rc, out, err = run_cmd([str(VENV_PY), "_gh_submit.py", str(plan_path)], timeout=180)
    combined = out + err
    log(f"  [gh_submit] rc={rc} tail={combined[-400:]}")
    kws = ['confirmation', 'success', 'submitted', 'thank you', 'application received',
           'we have received', 'your application', "You've applied", "SUBMITTED"]
    success = any(kw.lower() in combined.lower() for kw in kws)
    return success, combined

def submit_ashby(slug, cdp=None):
    if cdp is None:
        cdp = CDP
    plan_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    if not plan_path.exists():
        return False, f"no plan at {plan_path}"
    st, text = check_status(slug)
    if st == "submitted":
        return True, "already submitted"
    if st != "prep-ready":
        return False, f"status={st}: {text[:100]}"
    log(f"  [ashby] submitting {slug} via {cdp}")
    extra = {"JOBSEARCH_CDP": cdp}
    rc, out, err = run_cmd([str(VENV_PY), "_ashby_runner.py", str(plan_path)], timeout=200, extra_env=extra)
    combined = out + err
    log(f"  [ashby] rc={rc} tail={combined[-400:]}")
    kws = ['FormSubmitSuccess', 'EXIT_0', 'SUBMITTED', 'application received',
           'submitted successfully', 'thank you for applying', 'successfully submitted']
    success = any(kw in combined for kw in kws)
    return success, combined

def submit_lever(slug):
    plan_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    if not plan_path.exists():
        return False, f"no plan at {plan_path}"
    st, text = check_status(slug)
    if st == "submitted":
        return True, "already submitted"
    if st != "prep-ready":
        return False, f"status={st}: {text[:100]}"
    log(f"  [lever] submitting {slug}")
    rc, out, err = run_cmd([str(VENV_PY), "_lever_runner.py", str(plan_path)], timeout=200)
    combined = out + err
    log(f"  [lever] rc={rc} tail={combined[-400:]}")
    kws = ['success', 'submitted', 'thank you', 'confirmation', 'application received', 'SUBMITTED']
    success = any(kw.lower() in combined.lower() for kw in kws)
    return success, combined


log(f"\n{'='*50}\nGREENHOUSE BATCH ({len(GREENHOUSE_SLUGS)} roles)\n{'='*50}")
for slug in GREENHOUSE_SLUGS:
    log(f"\n--- GH: {slug} ---")
    role_id = get_role_id_from_slug(slug)
    success, output = submit_gh(slug)
    if success:
        if role_id:
            mark_applied(role_id, slug)
        write_submitted_status(slug, role_id or 0, confirmation=output[:200])
        results["submitted"].append((slug, "greenhouse"))
        log(f"  SUCCESS: {slug}")
    else:
        log(f"  FAILED: {slug}: {output[:200]}")
        results["failed"].append((slug, "greenhouse", output[:200]))
    time.sleep(2)

log(f"\n{'='*50}\nGH_IFRAME BATCH ({len(GH_IFRAME_SLUGS)} roles)\n{'='*50}")
for slug in GH_IFRAME_SLUGS:
    log(f"\n--- GH_IFRAME: {slug} ---")
    role_id = get_role_id_from_slug(slug)
    success, output = submit_gh(slug)  # GH iframe still uses _gh_submit.py
    if success:
        if role_id:
            mark_applied(role_id, slug)
        write_submitted_status(slug, role_id or 0, confirmation=output[:200])
        results["submitted"].append((slug, "gh_iframe"))
        log(f"  SUCCESS: {slug}")
    else:
        log(f"  FAILED: {slug}: {output[:200]}")
        results["failed"].append((slug, "gh_iframe", output[:200]))
    time.sleep(2)

log(f"\n{'='*50}\nASHBY BATCH ({len(ASHBY_SLUGS)} roles)\n{'='*50}")
for slug in ASHBY_SLUGS:
    log(f"\n--- ASHBY: {slug} ---")
    role_id = get_role_id_from_slug(slug)
    success, output = submit_ashby(slug)
    if not success:
        log(f"  Retrying with residential proxy for {slug}")
        success, output = submit_ashby(slug, cdp=RESI_CDP)
    if success:
        if role_id:
            mark_applied(role_id, slug)
        write_submitted_status(slug, role_id or 0, confirmation=output[:200])
        results["submitted"].append((slug, "ashby"))
        log(f"  SUCCESS: {slug}")
    else:
        log(f"  FAILED: {slug}: {output[:200]}")
        results["failed"].append((slug, "ashby", output[:200]))
    time.sleep(2)

log(f"\n{'='*50}\nLEVER BATCH ({len(LEVER_SLUGS)} roles)\n{'='*50}")
for slug in LEVER_SLUGS:
    log(f"\n--- LEVER: {slug} ---")
    role_id = get_role_id_from_slug(slug)
    success, output = submit_lever(slug)
    if success:
        if role_id:
            mark_applied(role_id, slug)
        write_submitted_status(slug, role_id or 0, confirmation=output[:200])
        results["submitted"].append((slug, "lever"))
        log(f"  SUCCESS: {slug}")
    else:
        log(f"  FAILED: {slug}: {output[:200]}")
        results["failed"].append((slug, "lever", output[:200]))
    time.sleep(2)

log(f"\n{'='*50}\nFINAL RESULTS\n{'='*50}")
log(f"Submitted ({len(results['submitted'])}): {[s for s,_ in results['submitted']]}")
log(f"Failed ({len(results['failed'])}): {[s[:50] for s,_,__ in results['failed']]}")

conn = sqlite3.connect(DB)
rows = conn.execute("SELECT COUNT(*), status FROM roles GROUP BY status ORDER BY COUNT(*) DESC;").fetchall()
conn.close()
log("DB Counts:")
for count, status in rows:
    log(f"  {count:4d}  {status or 'open'}")

log_fh.close()
