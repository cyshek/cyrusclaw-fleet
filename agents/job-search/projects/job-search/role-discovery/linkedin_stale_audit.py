#!/usr/bin/env python3
"""
LinkedIn stale-req audit: check 456 blocked rows with no block_reason.
Marks closed reqs as req-closed, leaves live ones alone.
"""
import sqlite3
import re
import time
import sys
import requests
from datetime import datetime

DB_PATH = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
RATE_LIMIT_SEC = 1.0  # 1 req/sec max
BATCH_SIZE = 50
TODAY = datetime.now().strftime("%Y-%m-%d")
NOTE_SUFFIX = f" | [{TODAY}] LinkedIn closed/expired verification"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def extract_li_id(url: str):
    """Extract LinkedIn job ID from URL."""
    # /jobs/view/1234567890/
    m = re.search(r'/jobs/view/(\d+)', url)
    if m:
        return m.group(1)
    # currentJobId=1234567890
    m = re.search(r'currentJobId=(\d+)', url)
    if m:
        return m.group(1)
    # /jobs/.../1234567890
    m = re.search(r'linkedin\.com/jobs/[^?]*/(\d+)', url)
    if m:
        return m.group(1)
    # Last resort: any long digit sequence in URL
    m = re.search(r'[/?=](\d{8,12})(?:[/?&]|$)', url)
    if m:
        return m.group(1)
    return None


def check_posting(li_id: str) -> bool:
    """Returns True if posting is closed/unavailable."""
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{li_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return True  # non-200 = closed/removed
        body = resp.text
        if "No longer accepting" in body:
            return True
        if '"closed":true' in body or '"closed": true' in body:
            return True
        # Empty/minimal response = removed req
        if len(body.strip()) < 100:
            return True
        return False
    except Exception as e:
        print(f"    ERROR fetching {li_id}: {e}", flush=True)
        return False  # On error, be conservative — don't mark closed


def batch_update(conn, pending_batch: list):
    """Update a batch of IDs to req-closed."""
    if not pending_batch:
        return
    placeholders = ",".join("?" * len(pending_batch))
    conn.execute(
        f"""
        UPDATE roles SET
            status='blocked',
            block_reason='req-closed',
            agent_notes = COALESCE(agent_notes,'') || ?
        WHERE id IN ({placeholders})
        """,
        [NOTE_SUFFIX] + pending_batch,
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, app_url FROM roles
        WHERE status='blocked'
        AND app_url LIKE '%linkedin.com/jobs%'
        AND (block_reason IS NULL OR block_reason='')
        AND first_seen < datetime('now','-30 days')
        ORDER BY id
        """
    ).fetchall()

    total = len(rows)
    print(f"=== LinkedIn Stale Audit: {total} rows to check ===", flush=True)

    closed_ids = []
    live_count = 0
    skip_count = 0
    pending_batch = []

    for i, row in enumerate(rows, 1):
        role_id = row["id"]
        url = row["app_url"]
        li_id = extract_li_id(url)

        if not li_id:
            print(f"  [{i}/{total}] id={role_id} SKIP (no li_id from {url[:80]})", flush=True)
            skip_count += 1
            continue

        print(f"  [{i}/{total}] id={role_id} li_id={li_id} ...", end=" ", flush=True)

        is_closed = check_posting(li_id)

        if is_closed:
            print("CLOSED", flush=True)
            closed_ids.append(role_id)
            pending_batch.append(role_id)
        else:
            print("live", flush=True)
            live_count += 1

        # Batch commit every BATCH_SIZE
        if len(pending_batch) >= BATCH_SIZE:
            batch_update(conn, pending_batch)
            print(f"  *** Committed batch of {len(pending_batch)} closures ***", flush=True)
            pending_batch = []

        # Rate limit between requests
        if i < total:
            time.sleep(RATE_LIMIT_SEC)

    # Commit remaining
    if pending_batch:
        batch_update(conn, pending_batch)
        print(f"  *** Committed final batch of {len(pending_batch)} closures ***", flush=True)

    conn.close()

    print("\n=== AUDIT COMPLETE ===")
    print(f"Total checked  : {total}")
    print(f"Marked closed  : {len(closed_ids)}")
    print(f"Still live     : {live_count}")
    print(f"Skipped (no ID): {skip_count}")

    return len(closed_ids)


if __name__ == "__main__":
    n_closed = main()
    sys.exit(0)
