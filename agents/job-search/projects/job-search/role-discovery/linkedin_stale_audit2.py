#!/usr/bin/env python3
"""LinkedIn stale-req audit - fixed URL regex."""
import sqlite3, re, time, sys, requests
from datetime import datetime

DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
RATE = 1.0
BATCH = 50
TODAY = datetime.now().strftime("%Y-%m-%d")
NOTE = " | [" + TODAY + "] LinkedIn closed/expired verification"

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "text/html,*/*"}

def get_li_id(url):
    # LinkedIn job URLs: /jobs/view/<title-slug>-<JOBID>
    patterns = [r'-(\d{7,12})(?:/|$)', r'currentJobId=(\d+)', r'/jobs/view/(\d{7,12})(?:/|$)']
    for pat in patterns:
        m = re.search(pat, url)
        if m: return m.group(1)
    return None

def is_closed_req(li_id):
    try:
        r = requests.get("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/" + li_id, headers=HDRS, timeout=8)
        if r.status_code != 200: return True
        b = r.text
        if "No longer accepting" in b: return True
        if '"closed":true' in b or '"closed": true' in b: return True
        if len(b.strip()) < 100: return True
        return False
    except Exception as e:
        print("  ERR " + li_id + ": " + str(e), flush=True)
        return False

def commit_batch(conn, ids):
    if not ids: return
    ph = ",".join(["?"] * len(ids))
    conn.execute("UPDATE roles SET status='blocked', block_reason='req-closed', agent_notes=COALESCE(agent_notes,'') || ? WHERE id IN (" + ph + ")", [NOTE] + ids)
    conn.commit()

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, app_url FROM roles WHERE status='blocked' AND app_url LIKE '%linkedin.com/jobs%' AND (block_reason IS NULL OR block_reason='') AND first_seen < datetime('now','-30 days') ORDER BY id").fetchall()
    total = len(rows)
    print("=== LinkedIn Stale Audit: " + str(total) + " rows ===", flush=True)
    closed_ids, live, skipped, pending = [], 0, 0, []
    for i, row in enumerate(rows, 1):
        rid, url = row["id"], row["app_url"]
        li_id = get_li_id(url)
        if not li_id:
            print("[" + str(i) + "/" + str(total) + "] id=" + str(rid) + " SKIP no-id", flush=True)
            skipped += 1
            continue
        print("[" + str(i) + "/" + str(total) + "] id=" + str(rid) + " li=" + li_id, end=" ", flush=True)
        if is_closed_req(li_id):
            print("CLOSED", flush=True)
            closed_ids.append(rid)
            pending.append(rid)
        else:
            print("live", flush=True)
            live += 1
        if len(pending) >= BATCH:
            commit_batch(conn, pending)
            print("*** batch committed " + str(len(pending)), flush=True)
            pending = []
        if i < total: time.sleep(RATE)
    if pending:
        commit_batch(conn, pending)
        print("*** final batch " + str(len(pending)), flush=True)
    conn.close()
    print("\n=== DONE ===")
    print("Total:   " + str(total))
    print("Closed:  " + str(len(closed_ids)))
    print("Live:    " + str(live))
    print("Skipped: " + str(skipped))
    return len(closed_ids)

if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
