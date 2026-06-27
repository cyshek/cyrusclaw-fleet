#!/usr/bin/env python3
"""Batch TikTok referral submitter — 2026-06-27.

Iterates all open TikTok/ByteDance tracker roles and submits via _tiktok_runner.py.
Writes STATUS.md + updates tracker.db on success.
"""
import sqlite3
import subprocess
import sys
import os
from pathlib import Path
from datetime import date

ROOT = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
VENV = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.venv/bin/python3'
RUNNER = f'{ROOT}/role-discovery/_tiktok_runner.py'
DB = f'{ROOT}/tracker.db'
BASE_RESUME = f'{ROOT}/resume/Cyrus_Shekari_Resume.pdf'
QUEUED = Path(f'{ROOT}/applications/queued')
SUBMITTED_DIR = Path(f'{ROOT}/applications/submitted')
TODAY = date.today().isoformat()


def get_resume(job_id: str) -> str:
    """Return tailored resume if available, else base."""
    qd = QUEUED / f'tiktok-{job_id}'
    if qd.exists():
        pdfs = sorted(qd.glob('*.pdf'))
        if pdfs:
            return str(pdfs[0])
    return BASE_RESUME


def write_status_md(role_id: int, job_id: str, brand: str, role_name: str, outcome: str, notes: str = ''):
    slug = f'{brand}-{role_id}'
    out_dir = SUBMITTED_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    status_text = f"""# {brand.title()} {role_id} — {role_name}

**Status:** SUBMITTED
**Date:** {TODAY}
**Submitted by:** auto (_tiktok_runner.py)
**Job ID:** {job_id}
**Confirmation:** Redirect to /referral/tiktok/resume/applied + "We have received your resume."
**Notes:** {outcome}{' | ' + notes if notes else ''}
"""
    (out_dir / 'STATUS.md').write_text(status_text)
    print(f"  [status] STATUS.md written -> {out_dir / 'STATUS.md'}")


def mark_submitted(conn, role_id: int, job_id: str, brand: str, role_name: str, outcome: str):
    write_status_md(role_id, job_id, brand, role_name, outcome)
    c = conn.cursor()
    c.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=? WHERE id=?",
        (TODAY, role_id)
    )
    conn.commit()
    print(f"  [db] role {role_id} -> submitted, applied_on={TODAY}")


def mark_blocked(conn, role_id: int, reason: str):
    c = conn.cursor()
    c.execute(
        "UPDATE roles SET status='blocked', block_reason=?, agent_notes=? WHERE id=?",
        (reason, f'tiktok-runner {TODAY}: {reason}', role_id)
    )
    conn.commit()
    print(f"  [db] role {role_id} -> blocked ({reason})")


def run_runner(brand: str, job_id: str, resume: str):
    """Run _tiktok_runner.py and return (exit_code, stdout)."""
    cmd = [VENV, RUNNER, '--brand', brand, '--job-id', job_id, '--resume', resume]
    env = os.environ.copy()
    env['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
        cwd=f'{ROOT}/role-discovery'
    )
    stdout = result.stdout + result.stderr
    return result.returncode, stdout


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    c = conn.cursor()
    c.execute("""
        SELECT id, company, role, app_url
        FROM roles
        WHERE status='open'
          AND (app_url LIKE '%tiktok%' OR app_url LIKE '%bytedance%' OR app_url LIKE '%lifeattiktok%')
        ORDER BY id
    """)
    rows = list(c.fetchall())
    print(f"\n{'='*60}")
    print(f"TikTok Batch Submit -- {TODAY}")
    print(f"Total open roles: {len(rows)}")
    print(f"{'='*60}\n")

    submitted = []
    already_applied = []
    closed = []
    blocked = []

    for i, row in enumerate(rows, 1):
        role_id = row['id']
        role_name = row['role']
        app_url = row['app_url']
        brand = 'bytedance' if 'bytedance' in app_url else 'tiktok'

        # Extract job_id from URL
        if '/position/' in app_url:
            job_id = app_url.split('/position/')[-1].split('/')[0]
        else:
            print(f"\n[{i}/{len(rows)}] SKIP role {role_id}: can't extract job_id from {app_url}")
            mark_blocked(conn, role_id, 'no-job-id-in-url')
            blocked.append((role_id, role_name, 'no-job-id-in-url'))
            continue

        resume = get_resume(job_id)
        resume_flag = 'TAILORED' if 'queued' in resume else 'BASE'

        print(f"\n[{i}/{len(rows)}] role {role_id} | {role_name[:55]}")
        print(f"  brand={brand} job_id={job_id} resume={resume_flag}")

        try:
            rc, out = run_runner(brand, job_id, resume)
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 180s")
            mark_blocked(conn, role_id, 'timeout-180s')
            blocked.append((role_id, role_name, 'timeout'))
            continue
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            mark_blocked(conn, role_id, f'exception:{e}')
            blocked.append((role_id, role_name, str(e)))
            continue

        # Print abbreviated output
        for line in out.splitlines():
            if any(k in line for k in ['classify', 'SUCCESS', 'FAIL', 'blocked', 'ERROR', 'runner', 'login', 'submit', 'already', 'workauth']):
                print(f"  > {line}")

        # Parse outcome from runner output
        if 'classify=already-applied' in out:
            outcome = 'already-applied (on file)'
            print(f"  -> ALREADY APPLIED (already on file)")
            already_applied.append((role_id, role_name))
            mark_submitted(conn, role_id, job_id, brand, role_name, outcome)
        elif 'classify=submitted' in out or 'classify=submitted-via-history' in out:
            outcome = 'submitted'
            print(f"  -> SUBMITTED")
            submitted.append((role_id, role_name))
            mark_submitted(conn, role_id, job_id, brand, role_name, outcome)
        elif rc == 0:
            print(f"  -> SUBMITTED (rc=0) ")
            submitted.append((role_id, role_name))
            mark_submitted(conn, role_id, job_id, brand, role_name, 'rc=0')
        elif 'login failed' in out.lower() or 'login-failed' in out:
            reason = 'login-failed'
            print(f"  -> BLOCKED: {reason}")
            mark_blocked(conn, role_id, reason)
            blocked.append((role_id, role_name, reason))
        elif 'closed' in out.lower() or '404' in out or 'not found' in out.lower():
            reason = 'role-closed-404'
            print(f"  -> CLOSED/404")
            mark_blocked(conn, role_id, reason)
            closed.append((role_id, role_name))
        else:
            # Extract reason from classify line
            reason = 'unknown'
            for line in out.splitlines():
                if 'classify=blocked' in line:
                    reason = line.split('reason=')[-1].strip() if 'reason=' in line else 'submit-failed'
                    break
                if 'classify=' in line:
                    reason = line.split('classify=')[-1].strip()
                    break
            if reason == 'unknown' and rc != 0:
                reason = f'rc={rc}'
            print(f"  -> BLOCKED: {reason}")
            mark_blocked(conn, role_id, reason)
            blocked.append((role_id, role_name, reason))

    conn.close()

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE -- {TODAY}")
    print(f"  SUBMITTED:       {len(submitted)}")
    print(f"  ALREADY_APPLIED: {len(already_applied)}")
    print(f"  CLOSED/404:      {len(closed)}")
    print(f"  BLOCKED:         {len(blocked)}")
    print(f"{'='*60}\n")

    if submitted:
        print("Submitted:")
        for rid, rname in submitted:
            print(f"  {rid} {rname[:60]}")

    if already_applied:
        print("\nAlready applied:")
        for rid, rname in already_applied:
            print(f"  {rid} {rname[:60]}")

    if blocked:
        print("\nBlocked:")
        for item in blocked:
            rid, rname = item[0], item[1]
            reason = item[2] if len(item) > 2 else ''
            print(f"  {rid} {rname[:50]} | {reason}")

    return len(submitted) + len(already_applied), len(blocked)


if __name__ == '__main__':
    submitted, blocked = main()
    sys.exit(0 if submitted > 0 or blocked == 0 else 1)
