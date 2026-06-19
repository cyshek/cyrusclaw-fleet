#!/usr/bin/env python3
"""Serial TikTok referral submit driver. For each task line (rid|jid|fam|title):
run _tiktok_runner.py --job-id <jid> --resume <tailored pdf>, parse classify=,
update tracker.db on submitted. tiktok-scale 2026-06-02."""
import subprocess, sys, re, sqlite3, datetime, time
from pathlib import Path
ROOT='/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
VP=ROOT+'/role-discovery/.venv/bin/python'
DB=ROOT+'/tracker.db'
TODAY=datetime.date.today().isoformat()

import os
TASKFILE=os.environ.get('TIKTOK_TASKS','/tmp/tiktok_tasks2.txt')
tasks=[l.strip().split('|',3) for l in Path(TASKFILE).read_text().splitlines() if l.strip()]
# allow resume from a start index
start=int(sys.argv[1]) if len(sys.argv)>1 else 0
limit=int(sys.argv[2]) if len(sys.argv)>2 else len(tasks)
tasks=tasks[start:start+limit]

def mark(rid, status, note):
    c=sqlite3.connect(DB); cur=c.cursor()
    if status=='applied':
        cur.execute("UPDATE roles SET status='applied', applied_by='agent', applied_on=?, "
                    "agent_notes=? WHERE id=?", (TODAY, note, rid))
    else:
        cur.execute("UPDATE roles SET status=?, agent_notes=? WHERE id=?", (status, note, rid))
    c.commit(); c.close()

results=[]
for rid, jid, fam, title in tasks:
    # idempotent: skip roles already applied (don't re-submit / re-hit already-applied)
    c0=sqlite3.connect(DB); st=c0.execute("SELECT status FROM roles WHERE id=?",(rid,)).fetchone(); c0.close()
    if st and st[0]=='applied':
        print(f"### {rid}/{jid} already applied -> skip"); results.append((rid,jid,'ALREADY-DONE')); continue
    pdf=f"{ROOT}/applications/queued/tiktok-{jid}/Cyrus_Shekari_Resume_tiktok_{jid}_v2.pdf"
    if not Path(pdf).exists():
        print(f"### {rid}/{jid} NO-PDF skip"); results.append((rid,jid,'no-pdf')); continue
    print(f"\n### {rid}/{jid} [{fam}] {title[:50]} ###", flush=True)
    try:
        p=subprocess.run([VP, ROOT+'/role-discovery/_tiktok_runner.py',
                          '--brand','tiktok','--job-id',jid,'--resume',pdf],
                         capture_output=True, text=True, timeout=240)
        out=p.stdout+p.stderr
        rc=p.returncode
    except subprocess.TimeoutExpired as e:
        out=(e.stdout or '')+(e.stderr or '') if isinstance(e.stdout,str) else 'timeout'
        rc=-1
        out=str(out)+"\nclassify=blocked reason=runner-timeout"
    cls=re.search(r'classify=(\S+)', out)
    reason=re.search(r'reason=(\S+)', out)
    cls=cls.group(1) if cls else f'rc{rc}-noclass'
    reason=reason.group(1) if reason else ''
    print(out[-900:], flush=True)
    if cls in ('submitted','already-applied','submitted-via-history'):
        verb = {'submitted':'SUBMITTED via referral',
                'already-applied':'ALREADY APPLIED (on file)',
                'submitted-via-history':'SUBMITTED via referral (history-confirmed)'}[cls]
        note=f"tiktok-referral-submit {TODAY}: {verb}"
        mark(rid,'applied',note); results.append((rid,jid,cls.upper()))
        print(f">>> {rid} MARKED applied ({cls})")
    else:
        note=f"tiktok-referral-submit {TODAY}: BLOCKED ({cls} {reason})".strip()
        mark(rid,'blocked',note); results.append((rid,jid,f'blocked:{cls}:{reason}'))
        print(f">>> {rid} BLOCKED {cls} {reason}")
    time.sleep(2)

print("\n===== SUMMARY =====")
sub=[r for r in results if r[2] in ('SUBMITTED','ALREADY-APPLIED','SUBMITTED-VIA-HISTORY')]
print(f"SUBMITTED: {len(sub)}/{len(results)}")
for r in results: print('  ',r)
