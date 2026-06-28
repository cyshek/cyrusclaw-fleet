#!/usr/bin/env python3
"""
Clean stale PREP-READY STATUS.md files where the DB already shows submitted/applied.
"""
import re
import sqlite3
from pathlib import Path

WORKSPACE = Path("/home/azureuser/.openclaw/agents/job-search/workspace")
APPS_DIR = WORKSPACE / "projects/job-search/applications/submitted"
DB_PATH = WORKSPACE / "projects/job-search/tracker.db"
TODAY = "2026-06-27"


def get_submitted_role_ids(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company, role, applied_by, applied_on
        FROM roles
        WHERE status IN ('submitted', 'applied')
        AND applied_by IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()
    return {row['id']: dict(row) for row in rows}


def find_prep_ready_status_files(apps_dir):
    results = []
    for status_file in Path(apps_dir).rglob("STATUS.md"):
        try:
            content = status_file.read_text()
            if "PREP-READY" in content:
                results.append((status_file, content))
        except Exception as e:
            print(f"  WARN: Could not read {status_file}: {e}")
    return results


def extract_role_id(content):
    m = re.search(r'role_id:\s*(\d+)', content)
    if m:
        return int(m.group(1))
    return None

def main():
    print(f"=== Stale PREP-READY Cleanup ({TODAY}) ===")
    submitted = get_submitted_role_ids(DB_PATH)
    print(f"DB: {len(submitted)} submitted/applied roles with applied_by set")

    prep_ready_files = find_prep_ready_status_files(APPS_DIR)
    print(f"Found {len(prep_ready_files)} PREP-READY STATUS.md files")

    cleaned = 0
    skipped_no_id = 0
    skipped_not_submitted = 0

    for status_file, content in prep_ready_files:
        role_id = extract_role_id(content)

        if role_id is None:
            print(f"  SKIP (no role_id): {status_file}")
            skipped_no_id += 1
            continue

        if role_id not in submitted:
            skipped_not_submitted += 1
            continue

        new_content = (
            "SUBMITTED\n\n"
            f"submitted_by: auto (stale-cleanup {TODAY})\n"
            f"role_id: {role_id}\n"
            "note: STATUS.md was stale PREP-READY; DB already showed submitted\n"
        )
        status_file.write_text(new_content)
        cleaned += 1
        db_info = submitted[role_id]
        print(f"  CLEANED role_id={role_id} ({db_info.get('company', '?')} / {db_info.get('role','?')}) -> {status_file.parent.name}")

    print("\n=== SUMMARY ===")
    print(f"Cleaned (DB=submitted, STATUS.md was stale): {cleaned}")
    print(f"Skipped (no role_id in STATUS.md):           {skipped_no_id}")
    print(f"Skipped (DB not submitted yet):               {skipped_not_submitted}")
    print(f"Total PREP-READY files found:                 {len(prep_ready_files)}")
    return cleaned


if __name__ == "__main__":
    main()
