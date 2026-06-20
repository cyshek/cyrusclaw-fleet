#!/usr/bin/env python3
"""Batch submit 2026-06-16. Run from role-discovery/ directory."""
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

env_file = Path.home() / ".openclaw/.env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

DB = SCRIPT_DIR.parent / "tracker.db"
SUBMITTED_DIR = SCRIPT_DIR.parent / "applications" / "submitted"
OUTPUT_DIR = SCRIPT_DIR / "output"
VENV_PY = SCRIPT_DIR / ".venv" / "bin" / "python"
CDP = "http://127.0.0.1:18800"
RESI_CDP = "http://127.0.0.1:19223"
TODAY = "2026-06-16"

os.environ["JOBSEARCH_CDP"] = CDP
os.environ["ENABLE_CAPSOLVER"] = "1"

LOG_PATH = SCRIPT_DIR / ("batch_submit_" + TODAY + ".log")
log_fh = open(LOG_PATH, "a")


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = "[" + ts + "] " + msg
    print(line, flush=True)
    log_fh.write(line + "\n")
    log_fh.flush()


def run_cmd(cmd, timeout=300, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def url_to_slug(url):
    if not url:
        return None
    m = re.search(r'(?:greenhouse\.io|boards\.greenhouse\.io)/([^/]+)/jobs/(\d+)', url)
    if m:
        return m.group(1) + "-" + m.group(2)
    m = re.search(r'ashbyhq\.com/([^/]+)/([0-9a-f-]{36})', url, re.I)
    if m:
        org = re.sub(r'[^a-z0-9]+', '-', m.group(1).lower()).strip('-')
        return org + "-" + m.group(2)
    m = re.search(r'uber\.com/careers/list/(\d+)', url)
    if m:
        return "uber-" + m.group(1)
    m = re.search(r'for=([^&]+).*?token=(\d+)', url)
    if not m:
        m = re.search(r'token=(\d+).*?for=([^&]+)', url)
        if m:
            return m.group(2) + "-" + m.group(1)
    if m:
        return m.group(1) + "-" + m.group(2)
    m = re.search(r'//([a-z0-9-]+)\.wd\d+\.myworkdayjobs', url)
    tenant = m.group(1) if m else "workday"
    m2 = re.search(r'_(REQ-\d+)', url)
    if m2:
        return tenant + "-" + m2.group(1)
    return None


def get_role_url(role_id):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT source_key, app_url FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    if row:
        return row[0] or row[1] or ""
    return ""


def prep_role(role_id):
    log("  [prep] role " + str(role_id))
    rc, out, err = run_cmd([str(VENV_PY), "inline_submit.py", "--role-id", str(role_id)], timeout=480)
    if rc != 0:
        log("  [prep] rc=" + str(rc) + " err=" + err[-400:])

    url = get_role_url(role_id)
    slug = url_to_slug(url)

    if not slug:
        log("  [prep] FAIL: no slug for " + str(role_id))
        return None, None

    status_f = SUBMITTED_DIR / slug / "STATUS.md"
    if not status_f.exists():
        log("  [prep] STATUS.md missing: " + str(status_f))
        return slug, None

    status = status_f.read_text()
    if "PREP-READY" not in status:
        log("  [prep] not PREP-READY: " + status[:200])
        return slug, None

    plan_path = OUTPUT_DIR / ("inline-plan-" + slug + ".json")
    if not plan_path.exists():
        log("  [prep] plan missing: " + str(plan_path))
        return slug, None

    log("  [prep] OK " + slug)
    return slug, str(plan_path)


def submit_gh(slug, plan_path):
    log("  [gh_submit] " + slug)
    rc, out, err = run_cmd([str(VENV_PY), "_gh_submit.py", plan_path], timeout=150)
    combined = out + err
    log("  [gh_submit] rc=" + str(rc) + " tail=" + combined[-400:])
    kws = ['confirmation', 'success', 'submitted', 'thank you', 'application received',
           'we have received', 'your application', "You've applied"]
    success = any(kw.lower() in combined.lower() for kw in kws)
    return rc, success, combined


def submit_ashby(slug, plan_path, cdp=None):
    if cdp is None:
        cdp = CDP
    log("  [ashby] " + slug + " via " + cdp)
    extra = {"JOBSEARCH_CDP": cdp}
    rc, out, err = run_cmd([str(VENV_PY), "_ashby_runner.py", plan_path], timeout=200, extra_env=extra)
    combined = out + err
    log("  [ashby] rc=" + str(rc) + " tail=" + combined[-400:])
    kws = ['FormSubmitSuccess', 'EXIT_0', 'SUBMITTED', 'application received',
           'submitted successfully', 'thank you for applying', 'successfully submitted']
    success = any(kw in combined for kw in kws)
    return rc, success, combined


def start_residential():
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(("127.0.0.1", 19223))
        s.close()
        log("  [resi] already up on 19223")
        return True
    except Exception:
        pass
    log("  [resi] starting residential Chrome...")
    rc, out, err = run_cmd(["bash", "-c", "source _residential_browser.sh 2>&1"], timeout=30)
    log("  [resi] " + out[-300:])
    time.sleep(3)
    return True


def mark_applied(role_id, slug, method="auto"):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE roles SET status='applied', applied_by=?, applied_on=?, prep_status='submitted' WHERE id=?",
        (method, TODAY, role_id)
    )
    conn.commit()
    conn.close()
    log("  [db] role " + str(role_id) + " -> applied")


def write_submitted_status(slug, extra=""):
    status_f = SUBMITTED_DIR / slug / "STATUS.md"
    if status_f.parent.exists():
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        content = "SUBMITTED -- " + ts + "\n\nsubmitted_by: auto\napplied_on: " + TODAY + "\n\n" + extra
        status_f.write_text(content)


results = {"submitted": [], "blocked": [], "skipped": [], "failed_resi": []}


def process_gh(role_id):
    log("\n=== GH " + str(role_id) + " ===")
    slug, plan_path = prep_role(role_id)
    if not plan_path:
        results["blocked"].append((role_id, slug or "?", "prep-failed"))
        return

    rc, success, output = submit_gh(slug, plan_path)
    if not success:
        log("  [retry] " + slug)
        time.sleep(3)
        rc, success, output = submit_gh(slug, plan_path)

    if success:
        log("  SUBMITTED: " + slug)
        mark_applied(role_id, slug)
        write_submitted_status(slug, "output:\n" + output[-500:])
        results["submitted"].append((role_id, slug))
    else:
        log("  BLOCKED: " + slug + " rc=" + str(rc))
        results["blocked"].append((role_id, slug, "gh-fail rc=" + str(rc)))


def process_ashby(role_id, strict=False):
    log("\n=== Ashby " + str(role_id) + " strict=" + str(strict) + " ===")
    slug, plan_path = prep_role(role_id)
    if not plan_path:
        results["blocked"].append((role_id, slug or "?", "prep-failed"))
        return

    rc, success, output = submit_ashby(slug, plan_path, cdp=CDP)

    if not success:
        log("  [resi] standard failed, trying residential for " + slug)
        start_residential()
        time.sleep(2)
        rc, success, output = submit_ashby(slug, plan_path, cdp=RESI_CDP)

    if success:
        log("  SUBMITTED: " + slug)
        mark_applied(role_id, slug)
        write_submitted_status(slug, "output:\n" + output[-500:])
        results["submitted"].append((role_id, slug))
    else:
        log("  BLOCKED: " + slug + " rc=" + str(rc))
        results["blocked"].append((role_id, slug, "ashby-fail rc=" + str(rc)))
        if strict:
            results["failed_resi"].append((role_id, slug))


def process_workday(role_id):
    log("\n=== Workday " + str(role_id) + " ===")
    slug, plan_path = prep_role(role_id)
    if not plan_path:
        results["blocked"].append((role_id, slug or "?", "prep-failed"))
        return

    if slug:
        status_f = SUBMITTED_DIR / slug / "STATUS.md"
        if status_f.exists() and "MANUAL" in status_f.read_text():
            log("  [workday] PREP-READY-MANUAL - trying _workday_runner.py")
            rc, out, err = run_cmd([str(VENV_PY), "_workday_runner.py", plan_path], timeout=300)
            combined = out + err
            success = rc == 0 and any(kw in combined.lower() for kw in ['submitted', 'confirmation', 'success'])
            if success:
                log("  SUBMITTED (workday): " + slug)
                mark_applied(role_id, slug, "auto-workday")
                write_submitted_status(slug, combined[-500:])
                results["submitted"].append((role_id, slug))
                return
            else:
                log("  BLOCKED (workday runner): " + slug + " rc=" + str(rc))
                results["blocked"].append((role_id, slug, "workday-runner rc=" + str(rc)))
                return

    results["blocked"].append((role_id, slug or "?", "workday-manual-only"))


def process_uber(role_id):
    log("\n=== Uber " + str(role_id) + " ===")
    url = get_role_url(role_id)
    if not url:
        results["blocked"].append((role_id, "?", "no-url"))
        return

    slug = url_to_slug(url) or ("uber-" + str(role_id))
    (SUBMITTED_DIR / slug).mkdir(parents=True, exist_ok=True)
    prep_role(role_id)  # best-effort prep for PDF

    rc, out, err = run_cmd([str(VENV_PY), "_uber_apply.py", url], timeout=300)
    combined = out + err
    success = any(kw in combined.lower() for kw in [
        'careers/apply/success', 'application submitted', 'successfully applied'
    ])

    if success:
        log("  SUBMITTED (uber): " + slug)
        mark_applied(role_id, slug, "auto-uber")
        write_submitted_status(slug, combined[-500:])
        results["submitted"].append((role_id, slug))
    else:
        log("  BLOCKED (uber): " + slug + " rc=" + str(rc) + " out=" + combined[-300:])
        results["blocked"].append((role_id, slug, "uber-fail rc=" + str(rc)))


# ===========================
# BATCH PROCESSING
# ===========================
log("=" * 60)
log("BATCH SUBMIT 2026-06-16 start")
log("=" * 60)

GH_ROLES = [
    2923,   # Discord Solutions Architect
    2926,   # Anthropic Customer PM EBC
    2927,   # Anthropic PM GTM
    2928,   # Anthropic TPM Apps Platform
    2929,   # Anthropic TPM Databases
    2938,   # Databricks PM Product
    2939,   # Axon Solutions Architect
    2947,   # Arize AI Sales Engineer
    2949,   # Sigma Computing Solution Engineer
    2951,   # Anduril Production PM
    2961,   # ShipBob Area Mgr B2B
    2962,   # ShipBob Area Mgr D2C
    2963,   # Flip PM
    2964,   # AvePoint Solution Engineer
    2965,   # Pure Storage Materials PM
    2966,   # Pure Storage Tech Services Eng
    2967,   # ClickHouse Solutions Architect
    2972,   # Credera Adobe Workfront SA (GH embed)
    2973,   # Divergent AI Solutions Engineer
    2980,   # Baselayer Solutions Engineer
]

ASHBY_ROLES = [
    2956,   # Ashby Customer Education PM
    2957,   # Eight Sleep Eng PM Hardware
    2958,   # Snowflake Solution Engineer
    2959,   # Metriport Solutions Architect
    2960,   # Abundant Research PM
    2969,   # Fluidstack TPM Design & Engineering
    2970,   # Fluidstack TPM Data Center Design
    2971,   # Helion TPM Orion
    2982,   # Granted Growth PM
]

ASHBY_STRICT = [
    2950,   # Baseten TPM Infrastructure
    2954,   # Skydio Program Manager
    2930,   # OpenAI PM ChatGPT Healthcare
    2931,   # OpenAI GRC PM
]

WORKDAY_ROLES = [
    2935,   # ConocoPhillips PM Enterprise AI
]

UBER_ROLES = [
    2937,   # Uber PM Core Technologies
]

log("\n--- GH ROLES (" + str(len(GH_ROLES)) + ") ---")
for rid in GH_ROLES:
    process_gh(rid)
    time.sleep(1)

log("\n--- ASHBY STANDARD (" + str(len(ASHBY_ROLES)) + ") ---")
for rid in ASHBY_ROLES:
    process_ashby(rid, strict=False)
    time.sleep(1)

log("\n--- ASHBY STRICT/RESIDENTIAL (" + str(len(ASHBY_STRICT)) + ") ---")
for rid in ASHBY_STRICT:
    process_ashby(rid, strict=True)
    time.sleep(1)

log("\n--- WORKDAY (" + str(len(WORKDAY_ROLES)) + ") ---")
for rid in WORKDAY_ROLES:
    process_workday(rid)
    time.sleep(1)

log("\n--- UBER (" + str(len(UBER_ROLES)) + ") ---")
for rid in UBER_ROLES:
    process_uber(rid)
    time.sleep(1)

log("\n" + "=" * 60)
log("FINAL REPORT")
log("=" * 60)
log("SUBMITTED (" + str(len(results["submitted"])) + "): " + str(results["submitted"]))
log("BLOCKED (" + str(len(results["blocked"])) + "): " + str(results["blocked"]))
log("SKIPPED (" + str(len(results["skipped"])) + "): " + str(results["skipped"]))
log("RESI_FAILED: " + str(results["failed_resi"]))

log("\n[render_xlsx] regenerating...")
rc, out, err = run_cmd([str(VENV_PY), "render_xlsx.py"], timeout=60)
log("[render_xlsx] rc=" + str(rc) + " " + (out + err)[-200:])

log("ALL DONE")
log_fh.close()

print("\n\n=== SUMMARY ===")
print("submitted=" + str(len(results["submitted"])))
print("blocked=" + str(len(results["blocked"])))
print("skipped=" + str(len(results["skipped"])))
print("Submitted: " + str([r[1] for r in results["submitted"]]))
print("Blocked: " + str([(r[0], r[1], r[2]) for r in results["blocked"]]))
print("Resi-failed: " + str(results["failed_resi"]))
