#!/usr/bin/env python3
"""Fetch JDs for Netflix Eightfold roles and write to queued dirs."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from jd_llm_classifier import fetch_jd_eightfold

roles = [
    (2875, 'https://explore.jobs.netflix.net/careers/job/790315885533', 'Finance Program Manager'),
    (2870, 'https://explore.jobs.netflix.net/careers/job/790313094223', 'Product Manager, Enterprise Developer Enablement'),
    (1394, 'https://explore.jobs.netflix.net/careers/job/790315659551', 'Product Manager, Content Intelligence'),
    (1539, 'https://explore.jobs.netflix.net/careers/job/790315245289', 'Support Solutions Engineer (L5), Graph Search'),
]

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'applications', 'queued'))

for role_id, url, title in roles:
    try:
        jd = fetch_jd_eightfold(url)
        slug = f'netflix-{role_id}'
        outdir = os.path.join(BASE, slug)
        os.makedirs(outdir, exist_ok=True)
        jd_path = os.path.join(outdir, 'JD.md')
        with open(jd_path, 'w') as f:\n            f.write(jd)\n        print(f'OK {role_id}: {len(jd)} chars -- {title}')
        print(jd[:300])
        print('---')
    except Exception as e:\n        print(f'FAIL {role_id}: {e}')
