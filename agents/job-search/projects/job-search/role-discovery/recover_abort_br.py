#!/usr/bin/env python3
"""
Recover ABORT-BULLET-REWRITER STATUS.md files where the v2 PDF already exists.
Rewrites STATUS.md to PREP-READY pointing at the inline plan so drain_prep_ready
can pick them up.
"""
import re
from pathlib import Path
from datetime import datetime, timezone

SUBMITTED = Path("../applications/submitted")
OUTPUT = Path("output")

recovered = []
skipped = []

for status_file in sorted(SUBMITTED.glob("*/STATUS.md")):
    txt = status_file.read_text(errors='ignore')
    if not txt.startswith("ABORT-BULLET-REWRITER"):
        continue
    workdir = status_file.parent
    slug = workdir.name

    # Extract role_id
    m = re.search(r'role_id:\s*(\d+)', txt)
    if not m:
        skipped.append((slug, "no role_id"))
        continue
    role_id = int(m.group(1))

    # Find any v2 PDF in workdir
    pdfs = list(workdir.glob("*_v2.pdf"))
    if not pdfs:
        skipped.append((slug, "no v2 PDF"))
        continue
    if pdfs[0].stat().st_size < 1024:
        skipped.append((slug, f"tiny PDF {pdfs[0].stat().st_size}b"))
        continue

    # Find the inline plan
    plan_candidates = list(OUTPUT.glob(f"inline-plan-{slug}.json"))
    if not plan_candidates:
        plan_candidates = list(OUTPUT.glob(f"inline-plan-{slug[:30]}*.json"))
    if not plan_candidates:
        skipped.append((slug, "no inline plan"))
        continue
    plan_path = plan_candidates[0].resolve()

    # Write PREP-READY STATUS.md
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_status = (
        f"PREP-READY — {now}\n\n"
        f"role_id: {role_id}\n"
        f"plan: {plan_path}\n"
        f"pdf: {pdfs[0].resolve()}\n"
        f"recovered_from: ABORT-BULLET-REWRITER (v2 PDF already present)\n"
    )
    status_file.write_text(new_status)
    recovered.append((slug, role_id, str(pdfs[0].name)))
    print(f"  RECOVERED: {slug} (role={role_id}) — {pdfs[0].name}")

print(f"\nDone: {len(recovered)} recovered, {len(skipped)} skipped")
for s, r in skipped:
    print(f"  SKIP: {s} — {r}")
