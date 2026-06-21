#!/usr/bin/env python3
"""Quick batch submit script - preps + submits GH roles."""
import sqlite3, os, re, subprocess, json, sys, time
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

# Load env
env_file = Path.home() / ".openclaw/.env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
os.environ["ENABLE_CAPSOLVER"] = "1"

DB = SCRIPT_DIR.parent / "tracker.db"
SUBMITTED_DIR = SCRIPT_DIR.parent / "applications" / "submitted"
OUTPUT_DIR = SCRIPT_DIR / "output"
VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
TODAY = "2026-06-21"

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def run_cmd(cmd, timeout=300, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)

def prep_role(role_id, dry_run=False):
    cmd = [str(VENV_PY), "inline_submit.py", "--role-id", str(role_id)]
    if dry_run:
        cmd.append("--dry-run")
    rc, out, err = run_cmd(cmd, timeout=400)
    combined = out + err
    log(f"  [prep] rc={rc} tail={combined[-200:]}")
    return rc, combined

def get_slug(role_id):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT source_key FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    if not row:
        return None
    sk = row[0] or ""
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", sk)
    if m:
        return m.group(1) + "-" + m.group(2)
    m = re.search(r"ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", sk, re.I)
    if m:
        org = re.sub(r"[^a-z0-9]+", "-", m.group(1).lower()).strip("-")
        return org + "-" + m.group(2)
    return None

def is_ashby(role_id):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT source_key FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    if row and row[0]:
        return "ashbyhq" in row[0]
    return False

def submit_gh(slug):
    plan_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    if not plan_path.exists():
        return False, "no plan"
    rc, out, err = run_cmd([str(VENV_PY), "_gh_submit.py", str(plan_path)], timeout=180)
    combined = out + err
    log(f"  [gh_submit] rc={rc} tail={combined[-300:]}")
    kws = ["confirmation", "submitted", "thank you", "success", "application received", "SUBMITTED"]
    success = any(kw.lower() in combined.lower() for kw in kws)
    return success, combined

def submit_ashby(slug):
    plan_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    if not plan_path.exists():
        return False, "no plan"
    rc, out, err = run_cmd([str(VENV_PY), "_ashby_runner.py", str(plan_path)], timeout=200)
    combined = out + err
    log(f"  [ashby] rc={rc} tail={combined[-300:]}")
    kws = ["FormSubmitSuccess", "EXIT_0", "SUBMITTED", "submitted successfully", "thank you for applying"]
    success = any(kw in combined for kw in kws)
    return success, combined

def mark_applied(role_id, method="auto"):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE roles SET status=\x27applied\x27, applied_by=?, applied_on=?, prep_status=\x27submitted\x27 WHERE id=?", (method, TODAY, role_id))
    conn.commit()
    conn.close()
    log(f"  [db] role {role_id} -> applied")

def write_status(slug, role_id, extra=""):
    sf = SUBMITTED_DIR / slug / "STATUS.md"
    if sf.parent.exists():
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        sf.write_text(f"STATUS: SUBMITTED\nsubmitted_at: {ts}\nsubmitted_by: auto\napplied_on: {TODAY}\nrole_id: {role_id}\n\n{extra}\n")

submitted = []
failed = []

role_ids = [int(x) for x in sys.argv[1:] if x.isdigit()]
if not role_ids:
    print("Usage: python3 batch_submit_today.py <role_id1> <role_id2> ...")
    sys.exit(1)

log(f"Batch submit {len(role_ids)} roles: {role_ids}")

for role_id in role_ids:
    log(f"\n=== Role {role_id} ===")
    ashby = is_ashby(role_id)
    ats_name = "ashby" if ashby else "gh"
    log(f"  ATS: {ats_name}")

    # 1. Prep
    rc, output = prep_role(role_id)
    if rc not in (0,):
        if rc == -1:
            log(f"  SKIP: prep timed out for {role_id}")
        else:
            log(f"  SKIP: prep failed rc={rc} for {role_id}")
        failed.append((role_id, "prep-failed"))
        continue

    # 2. Get slug + verify PREP-READY
    slug = get_slug(role_id)
    if not slug:
        log(f"  SKIP: no slug for {role_id}")
        failed.append((role_id, "no-slug"))
        continue

    status_file = SUBMITTED_DIR / slug / "STATUS.md"
    if not status_file.exists() or "PREP-READY" not in status_file.read_text():
        log(f"  SKIP: no PREP-READY for {slug}")
        failed.append((role_id, "no-prep-ready"))
        continue

    # 3. Submit
    if ashby:
        success, result = submit_ashby(slug)
    else:
        success, result = submit_gh(slug)

    if success:
        mark_applied(role_id, "auto")
        write_status(slug, role_id)
        submitted.append(role_id)
        log(f"  SUCCESS: {slug}")
    else:
        log(f"  FAILED: {slug}")
        failed.append((role_id, "submit-failed"))

log(f"\n=== RESULTS ===")
log(f"Submitted ({len(submitted)}): {submitted}")
log(f"Failed ({len(failed)}): {failed}")
