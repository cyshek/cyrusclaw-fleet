#!/usr/bin/env python3
"""Insert missing Anduril GH plan JSONs into tracker.db and write PREP-READY STATUS.md."""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone

BASE = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search")
RDIR = BASE / "role-discovery"
DB = BASE / "tracker.db"
OUTPUT = RDIR / "output"
SUBMITTED = RDIR / "applications" / "submitted"
DRYRUN = BASE / "applications" / "dryrun"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")

db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row

inserted = 0
staged = 0
skipped = 0

for plan_f in sorted(OUTPUT.glob("inline-plan-anduril-*.json")):
    slug = plan_f.stem.replace("inline-plan-", "")
    m = re.search(r'anduril-(\d+)', slug)
    if not m:
        print(f"SKIP no jid: {slug}")
        continue
    jid = m.group(1)
    url = f"https://job-boards.greenhouse.io/andurilindustries/jobs/{jid}"

    # Skip if already applied
    row = db.execute("SELECT id, applied_by FROM roles WHERE app_url=? OR app_url LIKE ?",
                     (url, f"%/jobs/{jid}%")).fetchone()
    if row and row["applied_by"]:
        skipped += 1
        print(f"SKIP already applied: {slug}")
        continue

    # Get job title from dryrun spec
    spec_f = DRYRUN / f"andurilindustries-{jid}.json"
    job_title = "Unknown Role"
    if spec_f.exists():
        spec = json.loads(spec_f.read_text())
        job_title = spec.get("job_title") or "Unknown Role"

    # Insert if missing
    if not row:
        db.execute(
            "INSERT INTO roles (source_key, company, role, app_url, status, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            (url, "Anduril", job_title, url, "", NOW[:10], NOW[:10])
        )
        db.commit()
        row = db.execute("SELECT id FROM roles WHERE app_url=?", (url,)).fetchone()
        role_id = row["id"]
        inserted += 1
        print(f"INSERTED id={role_id}: {job_title}")
    else:
        role_id = row["id"]

    # Read plan to get pdf path
    plan = json.loads(plan_f.read_text())
    pdf = plan.get("pdf_path_local", "")
    cover = plan.get("cover_answers", "")

    # Patch role_id into plan if missing
    if "role_id" not in plan:
        plan["role_id"] = role_id
        plan_f.write_text(json.dumps(plan, ensure_ascii=False))

    # Write PREP-READY STATUS.md
    workdir = SUBMITTED / slug
    status_f = workdir / "STATUS.md"
    if status_f.exists():
        first = status_f.read_text().split("\n")[0]
        if any(x in first for x in ("SUBMITTED", "ABORT", "BLOCKED")):
            skipped += 1
            continue
    workdir.mkdir(exist_ok=True)
    status_f.write_text(
        f"PREP-READY — {NOW}\n\nrole_id: {role_id}\nslug:    {slug}\n"
        f"plan:    {plan_f}\npdf:     {pdf}\ncover:   {cover}\n"
    )
    staged += 1
    print(f"STAGED: {slug} (id={role_id}) — {job_title}")

db.close()
print(f"\nInserted: {inserted} | Staged: {staged} | Skipped: {skipped}")
