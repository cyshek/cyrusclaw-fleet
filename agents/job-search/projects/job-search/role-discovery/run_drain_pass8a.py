#!/usr/bin/env python3
"""
Ashby residential drain pass 8A - sequential processor
Processes slugs one at a time, logs results, updates DB and STATUS.md
"""
import subprocess
import sqlite3
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
os.chdir(WORKDIR)

CAPSOLVER_KEY = open("../.capsolver-key").read().strip()
DB_PATH = "../tracker.db"

LOG_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"output/drain_ashby_pass8a_{LOG_TS}.log"

# Slugs to process (artie already done)
SLUGS = [
    "ashby-2fc178fc-fa92-463a-b788-1c66e3f32a00",
    "boom-b6f53406-66b9-45aa-bcd9-9adbf5436a26",
    "braintrust-8f7560d2-cfb1-4e3a-92d1-8e24b532d10c",
    "braintrust-e1bc9095-2460-4cf4-957f-ba076b6cb5ba",
    "cartesia-d45f51e9-e7eb-42c5-b986-d3b5d50454c5",
    "clera-a165ab9a-fb5f-4663-914b-9a7a5921966d",
    "cohere-1fa01a03-9253-4f62-8f10-0fe368b38cb9",
    "dust-4258daef-22e3-42cf-9de1-54bf500f5801",
    "duvoai-e2156092-50f1-4181-87fb-9e4bc299dde3",
    "e2b-a9ddb7bc-9cc7-43d2-8e46-9c8de4666a04",
    "forge-ca54fd9a-55eb-45ae-ba48-f666747a24e8",
    "handshake-c91b7ebf-2c69-4d91-809d-a30ea0b9dc18",
    "harper-a5e08fb7-a266-4aaf-a9df-a58a4787e292",
    "hyperbound-2781ed68-e7cc-48d8-b10f-1e9dd3c850db",
    "interface-aebdf0e6-599f-4e0a-b2c4-e19fb7f1d226",
    "inworld-ai-9aef36c8-55e5-4e05-b3a7-00992ad69647",
    "kombo-b2fa5229-f320-44a0-be22-edcfb42b024f",
    "langchain-b8dead31-212a-4b92-82a7-c42df16ae877",
    "legora-f3c0712a-f8e2-4dc1-8e83-23da7891a1c2",
    "litellm-c91a9f7c-310b-4ac3-b494-80874bc75568",
    "mach9-e09c4604-583b-424f-9526-9f62f42439de",
    "mondaycom-068bbb1e-ea53-46a9-8faf-cb48765ba9c6",
    "norm-ai-366d4079-4842-469d-a5e0-3cc891a136b4",
    "notion-10437426-14c8-4c45-8075-67959ce80393",
    "notion-a6a91521-87cd-41aa-b800-24dc8808d375",
]

results = {
    "submitted": [],
    "hard_recaptcha": [],
    "other_fail": [],
    "skipped": [],
}

def log(msg, file=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if file:
        file.write(line + "\n")
        file.flush()

def update_db(role_id, status, applied_by=None, block_reason=None):
    conn = sqlite3.connect(DB_PATH)
    if status == "submitted":
        conn.execute(
            "UPDATE roles SET status='submitted', applied_by=?, applied_on='2026-06-23', "
            "prep_status='submitted', response_status='submitted-residential' WHERE id=?",
            (applied_by or "auto-residential", role_id)
        )
    elif status == "blocked":
        conn.execute(
            "UPDATE roles SET status='blocked', block_reason=? WHERE id=?",
            (block_reason, role_id)
        )
    conn.commit()
    conn.close()

def update_status_md(status_file, new_first_line, extra_lines=None):
    content = Path(status_file).read_text()
    lines = content.split("\n")
    lines[0] = new_first_line
    if extra_lines:
        lines = [lines[0]] + extra_lines + lines[1:]
    Path(status_file).write_text("\n".join(lines))

with open(LOG_FILE, "w") as lf:
    log(f"=== Ashby Residential Drain Pass 8A ===", lf)
    log(f"Processing {len(SLUGS)} remaining slugs (artie already submitted)", lf)
    log("", lf)

    for i, slug in enumerate(SLUGS):
        status_file = f"applications/submitted/{slug}/STATUS.md"
        
        if not Path(status_file).exists():
            log(f"[{i+1}/{len(SLUGS)}] {slug}: ERROR - STATUS.md not found", lf)
            results["skipped"].append(slug)
            continue

        # Read plan and role_id
        content = Path(status_file).read_text()
        plan_match = re.search(r"^plan:\s+(\S+)", content, re.MULTILINE)
        role_match = re.search(r"^role_id:\s+(\d+)", content, re.MULTILINE)
        
        if not plan_match or not role_match:
            log(f"[{i+1}/{len(SLUGS)}] {slug}: ERROR - missing plan or role_id", lf)
            results["skipped"].append(slug)
            continue

        plan = plan_match.group(1)
        role_id = int(role_match.group(1))
        
        log(f"[{i+1}/{len(SLUGS)}] {slug} (role_id={role_id})", lf)
        log(f"  plan: {plan}", lf)
        
        env = os.environ.copy()
        env["CAPSOLVER_API_KEY"] = CAPSOLVER_KEY
        env["ENABLE_CAPSOLVER"] = "1"
        env["JOBSEARCH_CDP"] = "http://127.0.0.1:19223"
        
        result = subprocess.run(
            [".venv/bin/python3", "_ashby_runner.py", plan],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        
        output = result.stdout + result.stderr
        exit_code = result.returncode
        
        # Log last 20 lines of output
        output_lines = output.strip().split("\n")
        for line in output_lines[-20:]:
            log(f"  | {line}", lf)
        log(f"  exit_code={exit_code}", lf)
        
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if exit_code == 0:
            log(f"  => SUBMITTED ✓", lf)
            update_status_md(
                status_file,
                f"SUBMITTED — {now}",
                extra_lines=["submitted_by: auto-residential", "confirmed: true"]
            )
            update_db(role_id, "submitted")
            results["submitted"].append(slug)
        elif "RECAPTCHA_SCORE_BELOW_THRESHOLD" in output:
            log(f"  => HARD-RECAPTCHA ✗", lf)
            update_status_md(status_file, "BLOCKED-HARD-RECAPTCHA")
            update_db(role_id, "blocked", block_reason="ashby-hard-recaptcha:RECAPTCHA_SCORE_BELOW_THRESHOLD even via residential")
            results["hard_recaptcha"].append(slug)
        else:
            log(f"  => FAILED (exit {exit_code}) ✗", lf)
            update_status_md(status_file, f"FAILED-{exit_code}")
            results["other_fail"].append(slug)
        
        log("", lf)
        import time; time.sleep(3)

    # Summary
    log("=== SUMMARY ===", lf)
    log(f"Submitted:      {len(results['submitted'])} (+ 1 artie pre-run = {len(results['submitted'])+1} total)", lf)
    log(f"Hard-recaptcha: {len(results['hard_recaptcha'])}", lf)
    log(f"Other-fail:     {len(results['other_fail'])}", lf)
    log(f"Skipped:        {len(results['skipped'])}", lf)
    
    if results["submitted"]:
        log("Submitted slugs:", lf)
        for s in results["submitted"]:
            log(f"  {s}", lf)
    if results["hard_recaptcha"]:
        log("Hard-recaptcha slugs:", lf)
        for s in results["hard_recaptcha"]:
            log(f"  {s}", lf)
    if results["other_fail"]:
        log("Other-fail slugs:", lf)
        for s in results["other_fail"]:
            log(f"  {s}", lf)

print(f"\nLog: {LOG_FILE}")
print(f"submitted={len(results['submitted'])+1} hard_recaptcha={len(results['hard_recaptcha'])} other_fail={len(results['other_fail'])}")
