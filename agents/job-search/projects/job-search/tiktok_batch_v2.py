#!/usr/bin/env python3
"""Batch TikTok referral submitter - sequential, one role at a time."""
import sqlite3
import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import date

ROOT = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
VENV = ROOT + '/role-discovery/.venv/bin/python3'
RUNNER = ROOT + '/role-discovery/_tiktok_runner.py'
DB = ROOT + '/tracker.db'
BASE_RESUME = ROOT + '/resume/Cyrus_Shekari_Resume.pdf'
QUEUED = Path(ROOT + '/applications/queued')
SUBMITTED_DIR = Path(ROOT + '/applications/submitted')
TODAY = date.today().isoformat()
LOG_FILE = f'/tmp/tiktok_batch_{TODAY}.log'


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:\n        f.write(line + '\n')\n\n\ndef get_resume(job_id):
    qd = QUEUED / f'tiktok-{job_id}'
    if qd.exists():
        pdfs = sorted(qd.glob('*.pdf'))
        if pdfs:
            return str(pdfs[0])
    return BASE_RESUME


def write_status_md(role_id, job_id, brand, role_name, outcome):
    slug = f'{brand}-{role_id}'
    out_dir = SUBMITTED_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f"# {brand.title()} {role_id} - {role_name}\n\n"
        f"**Status:** SUBMITTED\n"
        f"**Date:** {TODAY}\n"
        f"**Submitted by:** auto (_tiktok_runner.py)\n"
        f"**Job ID:** {job_id}\n"
        f"**Confirmation:** {outcome}\n"
    )
    (out_dir / 'STATUS.md').write_text(text)
    log(f"  STATUS.md -> {out_dir}/STATUS.md")


def mark_submitted_db(role_id, job_id, brand, role_name, outcome):
    write_status_md(role_id, job_id, brand, role_name, outcome)
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            "UPDATE roles SET status='submitted', applied_by='auto', applied_on=? WHERE id=?",
            (TODAY, role_id)
        )
        conn.commit()
    finally:
        conn.close()
    log(f"  DB: role {role_id} -> submitted")


def mark_blocked_db(role_id, reason):
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            "UPDATE roles SET status='blocked', block_reason=?, agent_notes=? WHERE id=?",
            (reason, f'tiktok-runner {TODAY}: {reason}', role_id)
        )
        conn.commit()
    finally:
        conn.close()
    log(f"  DB: role {role_id} -> blocked ({reason})")


def run_one(brand, job_id, resume):
    cmd = [VENV, RUNNER, '--brand', brand, '--job-id', job_id, '--resume', resume]
    env = os.environ.copy()
    env['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
            env=env, cwd=ROOT + '/role-discovery'
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, 'TIMEOUT'
    except Exception as e:\n        return -2, f'EXCEPTION: {e}'


def get_open_roles():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, company, role, app_url FROM roles
        WHERE status='open'
          AND (app_url LIKE '%tiktok%' OR app_url LIKE '%bytedance%' OR app_url LIKE '%lifeattiktok%')
        ORDER BY id
    """)
    rows = list(c.fetchall())
    conn.close()
    return rows


def main():
    rows = get_open_roles()
    log(f"TikTok Batch Submit -- {TODAY} -- {len(rows)} open roles")

    submitted = []
    already_applied = []
    blocked_list = []

    for i, row in enumerate(rows, 1):
        role_id = row['id']
        role_name = row['role']
        app_url = row['app_url']
        brand = 'bytedance' if 'bytedance' in app_url else 'tiktok'

        if '/position/' in app_url:
            job_id = app_url.split('/position/')[-1].split('/')[0]
        else:
            log(f"\n[{i}/{len(rows)}] SKIP {role_id}: no job_id in URL")
            mark_blocked_db(role_id, 'no-job-id-in-url')
            blocked_list.append((role_id, role_name, 'no-job-id'))
            continue

        resume = get_resume(job_id)
        resume_flag = 'TAILORED' if 'queued' in resume else 'BASE'
        log(f"\n[{i}/{len(rows)}] role={role_id} brand={brand} resume={resume_flag}")
        log(f"  Title: {role_name[:70]}")

        rc, out = run_one(brand, job_id, resume)

        for line in out.splitlines():
            if any(k in line for k in ['classify', 'SUCCESS', 'runner', 'login', 'work-auth', 'submit', 'already', 'TIMEOUT', 'EXCEPTION', 'Error', 'error', 'blocked']):
                log(f"    {line}")

        if rc == -1 or 'TIMEOUT' in out:
            log(f"  -> TIMEOUT")
            mark_blocked_db(role_id, 'timeout-180s')
            blocked_list.append((role_id, role_name, 'timeout'))
        elif rc == -2:
            log(f"  -> EXCEPTION")
            mark_blocked_db(role_id, 'exception')
            blocked_list.append((role_id, role_name, 'exception'))
        elif 'classify=already-applied' in out:
            log(f"  -> ALREADY APPLIED (treating as submitted)")
            already_applied.append((role_id, role_name))
            mark_submitted_db(role_id, job_id, brand, role_name, 'already-applied (on file)')
        elif 'classify=submitted' in out or 'classify=submitted-via-history' in out:
            log(f"  -> SUBMITTED")
            submitted.append((role_id, role_name))
            mark_submitted_db(role_id, job_id, brand, role_name, 'Redirect /applied + We have received your resume')
        elif rc == 0:
            log(f"  -> SUBMITTED (rc=0)")
            submitted.append((role_id, role_name))
            mark_submitted_db(role_id, job_id, brand, role_name, 'rc=0')
        else:
            reason = f'rc={rc}'
            for line in out.splitlines():
                if 'classify=blocked' in line:
                    reason = line.split('reason=')[-1].strip() if 'reason=' in line else 'submit-failed'
                    break
                elif 'classify=' in line and 'dryrun' not in line:
                    reason = line.split('classify=')[-1].strip()
                    break
            log(f"  -> BLOCKED: {reason}")
            mark_blocked_db(role_id, reason)
            blocked_list.append((role_id, role_name, reason))

        time.sleep(2)

    # Re-render XLSX
    log("\nRunning render_xlsx.py...")
    try:
        r = subprocess.run([VENV, ROOT + '/role-discovery/render_xlsx.py'],
                           timeout=120, capture_output=True)
        log(f"render_xlsx done (rc={r.returncode})")
    except Exception as e:\n        log(f"render_xlsx failed: {e}")

    log(f"\n=== BATCH COMPLETE ===")
    log(f"  SUBMITTED:       {len(submitted)}")
    log(f"  ALREADY_APPLIED: {len(already_applied)}")
    log(f"  BLOCKED:         {len(blocked_list)}")
    log(f"  TOTAL:           {len(submitted)+len(already_applied)+len(blocked_list)}")

    if submitted:
        log("\nSubmitted:")
        for rid, rname in submitted:
            log(f"  {rid} {rname[:60]}")
    if already_applied:
        log("\nAlready applied:")
        for rid, rname in already_applied:
            log(f"  {rid} {rname[:60]}")
    if blocked_list:
        log("\nBlocked:")
        for item in blocked_list:
            log(f"  {item[0]} {item[1][:50]} | {item[2] if len(item)>2 else ''}")

    return len(submitted) + len(already_applied), len(blocked_list)


if __name__ == '__main__':
    main()
