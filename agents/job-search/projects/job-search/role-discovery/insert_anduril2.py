#!/usr/bin/env python3
"""Insert missing Anduril GH roles into tracker.db and stage PREP-READY STATUS.md."""

import glob
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

WORKSPACE = "/home/azureuser/.openclaw/agents/job-search/workspace"
ROLE_DISCOVERY = os.path.join(WORKSPACE, "projects/job-search/role-discovery")
DB_PATH = os.path.join(WORKSPACE, "projects/job-search/tracker.db")
APPLICATIONS_DIR = os.path.join(WORKSPACE, "applications")
PLAN_GLOB = os.path.join(ROLE_DISCOVERY, "output/inline-plan-anduril-*.json")
DRYRUN_DIR = os.path.join(WORKSPACE, "applications/dryrun")
SUBMITTED_DIR = os.path.join(APPLICATIONS_DIR, "submitted")

NOW_TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY = "2026-06-23"


def main():
    plan_paths = sorted(glob.glob(PLAN_GLOB))
    print(f"Found {len(plan_paths)} plan files")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    staged = 0
    skipped_applied = 0
    errors = []

    for plan_path in plan_paths:
        basename = os.path.basename(plan_path)
        m = re.match(r"inline-plan-(anduril-(\d+))\.json", basename)
        if not m:\n+            errors.append(f"Could not parse slug from {plan_path}")
            continue
        slug = m.group(1)
        jid = m.group(2)

        with open(plan_path) as fh:
            plan = json.load(fh)

        url = plan.get("url", "")
        pdf_path = plan.get("pdf_path_local", "")
        cover_answers = plan.get("cover_answers", {})

        # Find dryrun spec
        dryrun_files = glob.glob(os.path.join(DRYRUN_DIR, f"andurilindustries-{jid}.json"))
        if not dryrun_files:
            dryrun_files = glob.glob(os.path.join(DRYRUN_DIR, f"*anduril*{jid}*.json"))

        job_title = f"Anduril Role {jid}"
        if dryrun_files:
            with open(dryrun_files[0]) as fh:
                dryrun = json.load(fh)
            job_title = dryrun.get("job_title", dryrun.get("title", job_title))
        else:
            errors.append(f"No dryrun spec for jid={jid}, slug={slug}")

        # Check existing
        cur.execute("SELECT id, applied_by, applied_on FROM roles WHERE app_url=?", (url,))
        row = cur.fetchone()

        if row:
            role_id, applied_by, applied_on = row
            if applied_by:
                skipped_applied += 1
                print(f"  SKIP (already applied): {slug} -> id={role_id}, applied_by={applied_by}")
            else:
                print(f"  EXISTING (not applied): {slug} -> id={role_id}, title={job_title!r}")
        else:
            cur.execute(
                """INSERT INTO roles (company, role, app_url, source_key, status, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, '', ?, ?)""",
                ("Anduril", job_title, url, url, TODAY, TODAY),
            )
            conn.commit()
            role_id = cur.lastrowid
            inserted += 1
            print(f"  INSERT: {slug} -> id={role_id}, title={job_title!r}")

        # Stage STATUS.md
        submitted_dir = os.path.join(SUBMITTED_DIR, slug)
        os.makedirs(submitted_dir, exist_ok=True)
        status_path = os.path.join(submitted_dir, "STATUS.md")

        if os.path.exists(status_path):
            with open(status_path) as fh:
                existing = fh.read()
            if "SUBMITTED" in existing or "submitted" in existing.lower():
                print(f"  STATUS.md exists (SUBMITTED), not overwriting")
                staged += 1
                continue

        cover_str = json.dumps(cover_answers, indent=2) if cover_answers else "{}"
        status_content = (
            f"PREP-READY — {NOW_TS}\n\n"
            f"role_id: {role_id}\n"
            f"slug:    {slug}\n"
            f"plan:    {os.path.abspath(plan_path)}\n"
            f"pdf:     {pdf_path}\n"
            f"cover:   {cover_str}\n"
        )

        with open(status_path, "w") as fh:
            fh.write(status_content)
        staged += 1
        print(f"  STAGED: {status_path}")

    conn.close()

    print()
    print("=" * 50)
    print(f"SUMMARY: inserted={inserted}, staged={staged}, skipped_already_applied={skipped_applied}")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
