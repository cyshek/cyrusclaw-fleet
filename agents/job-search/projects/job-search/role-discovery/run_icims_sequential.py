#!/usr/bin/env python3
"""
run_icims_sequential.py — Run iCIMS roles one-by-one, log outcomes.
Designed to be run via nohup and monitored via tail -f.
"""
import subprocess
import sys
import os
import json
import time
import sqlite3
from pathlib import Path

WORKDIR = Path('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
DB_PATH = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db'
APPS_DIR = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted'
LOG_PATH = '/tmp/icims_sequential.log'
TODAY = time.strftime('%Y-%m-%d', time.gmtime())

# Remaining roles to run (excluding 3758, 3761, 3762 already done)
ROLES = [
    (3763, 'https://careers-amd.icims.com/jobs/87077/login'),
    (3764, 'https://careers-amd.icims.com/jobs/87117/login'),
    (3765, 'https://careers-amd.icims.com/jobs/86326/login'),
    (3766, 'https://careers-amd.icims.com/jobs/86904/login'),
    (3767, 'https://careers-amd.icims.com/jobs/86949/login'),
    (3768, 'https://careers-amd.icims.com/jobs/86687/login'),
    (3769, 'https://careers-amd.icims.com/jobs/86615/login'),
    (3770, 'https://careers-amd.icims.com/jobs/86479/login'),
    (3771, 'https://canadacareers-amd.icims.com/jobs/86384/login'),
    (3772, 'https://careers-amd.icims.com/jobs/86128/login'),
    (3773, 'https://careers-amd.icims.com/jobs/86406/login'),
    (3774, 'https://careers-amd.icims.com/jobs/79943/login'),
    (3775, 'https://careers-amd.icims.com/jobs/80554/login'),
    (3776, 'https://careers-amd.icims.com/jobs/84726/login'),
    (3777, 'https://careers-amd.icims.com/jobs/86014/login'),
    (3778, 'https://careers-amd.icims.com/jobs/85750/login'),
    (3779, 'https://careers-amd.icims.com/jobs/84929/login'),
    (3780, 'https://careers-amd.icims.com/jobs/84268/login'),
    (3781, 'https://careers-amd.icims.com/jobs/80409/login'),
    (3782, 'https://careers-amd.icims.com/jobs/80071/login'),
    (3783, 'https://careers-amd.icims.com/jobs/80274/login'),
    # SiriusXM remaining
    (3759, 'https://uscareers-siriusxmradio.icims.com/jobs/17398/login'),
    (3760, 'https://uscareers-siriusxmradio.icims.com/jobs/17393/login'),
    # Keysight
    (3787, 'https://careers-keysight.icims.com/jobs/53104/login'),
    (3788, 'https://careers-keysight.icims.com/jobs/51760/login'),
    (3789, 'https://careers-keysight.icims.com/jobs/50012/login'),
]

def log(msg):
    ts = time.strftime('%H:%M:%S', time.gmtime())
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + "
")

def db_update_submitted(role_id, applied_on=TODAY):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, prep_status='submitted', "
        "agent_notes=COALESCE(agent_notes,'')||' [uncertain-submit: hcaptcha-solved+apply-clicked " + TODAY + "]' "
        "WHERE id=?", (applied_on, role_id))
    con.commit()
    con.close()

def db_update_closed(role_id):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE roles SET status='closed', block_reason='req-closed', "
        "agent_notes=COALESCE(agent_notes,'')||' [closed " + TODAY + "]' WHERE id=?", (role_id,))
    con.commit()
    con.close()

def db_update_already_applied(role_id):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE roles SET status='submitted', applied_by='auto-icims', applied_on=?, prep_status='submitted', "
        "agent_notes=COALESCE(agent_notes,'')||' [already-applied " + TODAY + "]' WHERE id=?", (TODAY, role_id))
    con.commit()
    con.close()

def get_role_info(role_id):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT company, role, prep_path FROM roles WHERE id=?", (role_id,)).fetchone()
    con.close()
    return row or ('Unknown', 'Unknown', '')

def write_status(role_id, url, hcap, outcome):
    company, role, prep_path = get_role_info(role_id)
    slug = os.path.basename(prep_path) if prep_path else f'amd-{role_id}'
    d = Path(APPS_DIR) / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / 'STATUS.md').write_text(f"""SUBMITTED — {TODAY}

role_id: {role_id}
company: {company}
role: {role}
url: {url}
submitted_by: auto-icims (_icims_runner.py)
confirmation: {outcome}
hcaptcha_solve: {hcap}
resume_attached: iCIMS profile-apply (no file input)
exit_code: 3
""")
    log(f"  STATUS.md: {d}")

def run_role(role_id, url, attempt=1):
    log(f"=== Role {role_id}: {url} (attempt {attempt}) ===")
    env = os.environ.copy()
    env['JOBSEARCH_CDP'] = 'http://127.0.0.1:19223'
    
    runner = str(WORKDIR / '_icims_runner.py')
    venv_python = str(WORKDIR / '.venv/bin/python3')
    
    proc = subprocess.run(
        [venv_python, runner, '--url', url],
        cwd=str(WORKDIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=720,  # 12 min max per role
    )
    
    stdout = proc.stdout + proc.stderr
    log(f"  exit_code={proc.returncode}")
    
    # Parse JSON result
    result = {}
    for line in reversed(stdout.split('
')):
        line = line.strip()
        if line.startswith('{'):
            try:
                result = json.loads(line)
                break
            except:
                pass
    
    status = result.get('status', 'unknown')
    hcap = result.get('hcaptcha_solve', 'n/a')
    block = result.get('block_reason', '')
    log(f"  status={status} hcaptcha={hcap} block={block}")
    
    # Print last few lines of stdout for debugging
    tail = [l for l in stdout.split('
') if l.strip()][-5:]
    for line in tail:
        log(f"  > {line}")
    
    return proc.returncode, status, hcap, block

def main():
    log(f"=== iCIMS Sequential Run — {len(ROLES)} roles — {TODAY} ===")
    
    results = {'submitted': [], 'closed': [], 'already_applied': [], 'failed': [], 'skipped': []}
    
    for role_id, url in ROLES:
        # Check if already submitted
        con = sqlite3.connect(DB_PATH)
        row = con.execute("SELECT status FROM roles WHERE id=?", (role_id,)).fetchone()
        con.close()
        cur_status = row[0] if row else 'open'
        
        if cur_status in ('submitted', 'applied', 'closed'):
            log(f"SKIP role {role_id}: already {cur_status}")
            results['skipped'].append(role_id)
            continue
        
        try:
            code, status, hcap, block = run_role(role_id, url)
        except subprocess.TimeoutExpired:
            log(f"  TIMEOUT (>720s) — skipping")
            results['failed'].append((role_id, 'timeout'))
            time.sleep(3)
            continue
        except Exception as e:
            log(f"  EXCEPTION: {e}")
            results['failed'].append((role_id, str(e)))
            time.sleep(3)
            continue
        
        # Book the result
        if status == 'applied' or code == 0:
            log(f"  RESULT: SUBMITTED (confirmed)")
            db_update_submitted(role_id)
            write_status(role_id, url, hcap, 'confirmed')
            results['submitted'].append(role_id)
        elif code == 3 and hcap and 'twocaptcha' in hcap:
            log(f"  RESULT: UNCERTAIN-SUBMITTED (hcap solved, Apply clicked)")
            db_update_submitted(role_id)
            write_status(role_id, url, hcap, f'uncertain (hcaptcha-solved+apply-clicked)')
            results['submitted'].append(role_id)
        elif status == 'closed' or code == 6:
            log(f"  RESULT: CLOSED")
            db_update_closed(role_id)
            results['closed'].append(role_id)
        elif status == 'already_applied' or code == 7:
            log(f"  RESULT: ALREADY_APPLIED")
            db_update_already_applied(role_id)
            results['already_applied'].append(role_id)
        elif code == 2 and 'no-vendor' in block:
            log(f"  RESULT: HCAPTCHA_BLOCKED — will retry once")
            # Retry once after a delay
            time.sleep(30)
            code2, status2, hcap2, block2 = run_role(role_id, url, attempt=2)
            if code2 == 3 and hcap2 and 'twocaptcha' in hcap2:
                log(f"  RETRY SUCCESS: uncertain-submitted")
                db_update_submitted(role_id)
                write_status(role_id, url, hcap2, 'uncertain-retry')
                results['submitted'].append(role_id)
            elif code2 == 6:
                db_update_closed(role_id)
                results['closed'].append(role_id)
            else:
                log(f"  RETRY ALSO FAILED: exit={code2} status={status2}")
                results['failed'].append((role_id, f'hcaptcha-blocked-after-retry'))
        else:
            log(f"  RESULT: FAILED (exit={code} status={status})")
            results['failed'].append((role_id, f'exit{code}-{status}'))
        
        # Small pause between roles
        time.sleep(5)
    
    log(f"
=== FINAL RESULTS ===")
    log(f"Submitted ({len(results['submitted'])}): {results['submitted']}")
    log(f"Closed ({len(results['closed'])}): {results['closed']}")
    log(f"Already applied ({len(results['already_applied'])}): {results['already_applied']}")
    log(f"Failed ({len(results['failed'])}): {results['failed']}")
    log(f"Skipped ({len(results['skipped'])}): {results['skipped']}")
    
    return results

if __name__ == '__main__':
    main()
