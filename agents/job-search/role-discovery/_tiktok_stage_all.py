#!/usr/bin/env python3
"""Batch-stage TikTok JDs (serial, browser-bound) then emit a tasks file with
family classification for the parallel tailor stage. tiktok-scale 2026-06-02."""
import subprocess, sys, re
from pathlib import Path
ROOT='/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
VP=ROOT+'/role-discovery/.venv/bin/python'

def fam(title):
    t=title.lower()
    if 'technical program manager' in t or 'tpm' in t: return 'tpm'
    if 'program manager' in t or 'pgm' in t: return 'pgm'
    return 'pm'

rows=[l.strip().split('|',2) for l in Path('/tmp/tiktok_roles.txt').read_text().splitlines() if l.strip()]
tasks=[]
for rid, jid, title in rows:
    jd=Path(ROOT)/'applications'/'queued'/f'tiktok-{jid}'/'JD.md'
    if not (jd.exists() and len(jd.read_text())>200):
        r=subprocess.run([VP, ROOT+'/role-discovery/_tiktok_fetch_jd.py', jid, title],
                         capture_output=True, text=True)
        print(f"fetch {rid}/{jid}: {r.stdout.strip()} {r.stderr.strip()[:100]}")
    else:
        print(f"skip-fetch {rid}/{jid}: JD already staged")
    tasks.append(f"{rid}|{jid}|{fam(title)}|{title}")
Path('/tmp/tiktok_tasks.txt').write_text('\n'.join(tasks)+'\n')
print(f"\nDONE. {len(tasks)} tasks -> /tmp/tiktok_tasks.txt")
