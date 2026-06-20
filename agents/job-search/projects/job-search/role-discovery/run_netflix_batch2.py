#!/usr/bin/env python3
"""
Netflix Eightfold Batch 2 — sequential submission script.
Roles: 2875, 2870, 1394, 1539

Usage:
  JOBSEARCH_CDP=http://127.0.0.1:19223 .venv/bin/python run_netflix_batch2.py
"""
import json
import os
import sys
import sqlite3
import subprocess
import time
import shutil
from datetime import date

# Workspace root
WORKSPACE = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../.."))
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "tracker.db")
SUBMITTED_DIR = os.path.join(WORKSPACE, "applications", "submitted")
QUEUED_DIR = os.path.join(WORKSPACE, "projects", "job-search", "applications", "queued")

TODAY = "2026-06-14"

ROLES = [
    {
        "id": 2875,
        "slug": "netflix-2875",
        "pid": "790315885533",
        "resume": os.path.join(QUEUED_DIR, "netflix-2875", "Cyrus_Shekari_Resume_netflix_2875_v2.pdf"),
    },
    {
        "id": 2870,
        "slug": "netflix-2870",
        "pid": "790313094223",
        "resume": os.path.join(QUEUED_DIR, "netflix-2870", "Cyrus_Shekari_Resume_netflix_2870_v2.pdf"),
    },
    {
        "id": 1394,
        "slug": "netflix-1394",
        "pid": "790315659551",
        "resume": os.path.join(QUEUED_DIR, "netflix-1394", "Cyrus_Shekari_Resume_netflix_1394_v2.pdf"),
    },
    {
        "id": 1539,
        "slug": "netflix-1539",
        "pid": "790315245289",
        "resume": os.path.join(QUEUED_DIR, "netflix-1539", "Cyrus_Shekari_Resume_netflix_1539_v2.pdf"),
    },
]


def write_status_md(submitted_dir, role, result, resume_path):
    """Write STATUS.md to submitted dir."""
    os.makedirs(submitted_dir, exist_ok=True)
    enc_id = result.get("enc_id", "unknown")
    conf = result.get("confirmation", {})
    status_content = f"""# Netflix Role {role['id']} — SUBMITTED

pid: {role['pid']}
enc_id: {enc_id}
submitted_by: auto-residential
applied_on: {TODAY}
resume_attached: tailored ({os.path.basename(resume_path)})
confirmation: {json.dumps(conf, indent=2)}
"""
    with open(os.path.join(submitted_dir, "STATUS.md"), "w") as f:\n        f.write(status_content)\n    print(f"[{role['id']}] STATUS.md written to {submitted_dir}")


def update_db(role_id, status="applied", block_reason=None):
    """Update tracker DB."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if status == "applied":
            conn.execute(
                "UPDATE roles SET status='applied', applied_by='auto', applied_on=? WHERE id=?",
                (TODAY, role_id),
            )
            print(f"[{role_id}] DB: status=applied applied_on={TODAY}")
        elif block_reason:
            conn.execute(
                "UPDATE roles SET block_reason=? WHERE id=?",
                (block_reason, role_id),
            )
            print(f"[{role_id}] DB: block_reason set")
        conn.commit()
    finally:
        conn.close()


def run_role(role):
    """Run a single role through the eightfold runner."""
    role_id = role["id"]
    resume = role["resume"]
    print(f"\n{'='*60}")
    print(f"[{role_id}] Starting submission")
    print(f"[{role_id}] Resume: {resume}")
    
    if not os.path.exists(resume):
        print(f"[{role_id}] ERROR: Resume not found: {resume}")
        return {"status": "error", "error": f"resume not found: {resume}"}
    
    resume_size = os.path.getsize(resume)
    print(f"[{role_id}] Resume size: {resume_size} bytes")
    if resume_size < 1000:
        print(f"[{role_id}] ERROR: Resume too small, might be corrupted")
        return {"status": "error", "error": "resume too small"}

    # Import the runner
    sys.path.insert(0, HERE)
    import importlib
    import _eightfold_runner as runner
    importlib.reload(runner)

    # Load personal info
    personal_info_path = os.path.join(HERE, "personal-info.json")
    with open(personal_info_path) as f:\n        personal_info = json.load(f)\n\n    # Get apply_url from DB\n    conn = sqlite3.connect(DB_PATH)\n    row = conn.execute("SELECT app_url FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    if not row or not row[0]:
        print(f"[{role_id}] ERROR: No app_url in DB")
        return {"status": "error", "error": "no app_url"}
    
    apply_url = row[0]
    print(f"[{role_id}] apply_url: {apply_url}")

    # Run
    start_t = time.time()
    result = runner.run_eightfold(
        role_id=role_id,
        apply_url=apply_url,
        personal_info=personal_info,
        resume_pdf_path=resume,
        dry_run=False,
    )
    elapsed = time.time() - start_t
    print(f"[{role_id}] Result ({elapsed:.1f}s): {result}")
    return result


def main():
    print(f"Netflix Eightfold Batch 2 — {TODAY}")
    print(f"CDP URL: {os.environ.get('JOBSEARCH_CDP', 'NOT SET')}")
    print(f"DB: {DB_PATH}")
    
    results = {}
    
    for role in ROLES:
        role_id = role["id"]
        try:
            result = run_role(role)
            status = result.get("status", "error")
            results[role_id] = result

            if status == "submitted":
                # Write STATUS.md
                submitted_dir = os.path.join(SUBMITTED_DIR, f"netflix-{role_id}")
                write_status_md(submitted_dir, role, result, role["resume"])
                # Update DB
                update_db(role_id, status="applied")
                print(f"[{role_id}] ✅ SUBMITTED")
                
            elif status == "already_applied":
                print(f"[{role_id}] ℹ️ ALREADY APPLIED")
                # Still mark in DB
                update_db(role_id, status="applied")
                
            elif status == "closed":
                print(f"[{role_id}] ⛔ CLOSED")
                update_db(role_id, block_reason="BLOCKED 2026-06-14: eightfold-req-closed")
                
            elif status == "blocked":
                err = result.get("error", "captcha/other")
                print(f"[{role_id}] 🚫 BLOCKED: {err}")
                update_db(role_id, block_reason=f"BLOCKED 2026-06-14: {err[:100]}")
                
            else:
                err = result.get("error", "unknown")
                print(f"[{role_id}] ❌ FAILED: {err}")
                update_db(role_id, block_reason=f"BLOCKED 2026-06-14: {err[:100]}")
                
        except Exception as ex:
            import traceback
            print(f"[{role_id}] EXCEPTION: {ex}")
            traceback.print_exc()
            results[role_id] = {"status": "error", "error": str(ex)}
        
        # Brief pause between roles
        print(f"[{role_id}] Sleeping 3s before next role...")
        time.sleep(3)
    
    print("\n" + "="*60)
    print("BATCH SUMMARY:")
    for role in ROLES:
        r = results.get(role["id"], {})
        print(f"  {role['id']}: {r.get('status', 'N/A')} — {r.get('error', r.get('enc_id', ''))}")
    
    return results


if __name__ == "__main__":
    main()
