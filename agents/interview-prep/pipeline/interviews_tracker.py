"""
interviews_tracker.py -- [DISABLED 2026-06-23]

FORMERLY: wrote new interview signals into tracker.db `interviews` table, then
re-rendered the XLSX and posted to #job-search.

DISABLED per job-search directive (2026-06-23): Cyrus now maintains the Interviews
sheet in Cyrus_Job_Tracker.xlsx MANUALLY. render_xlsx.py preserves that sheet as-is
on every re-render. interview-prep must NOT write the interviews table or trigger an
XLSX re-render. nightly_scan.py no longer imports/calls process_signals(); it is
notify-only. This module is retained for reference + the safe read helpers only.
If re-enabling write-back is ever wanted, coordinate with job-search first.
"""

_WRITE_DISABLED = True

import sqlite3
import subprocess
import datetime
import os

TRACKER_DB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
RENDER_SCRIPT = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/render_xlsx.py"
RENDER_VENV = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.venv/bin/python"
RENDER_CWD = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search"
XLSX_PATH = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/Cyrus_Job_Tracker.xlsx"
INTERVIEW_CHANNEL = "1513393827904360558"  # #interview-agent — all interview updates go here


def lookup_role_id(db, company, role_hint=None):
    """Find role_id from roles table by company + optional role hint."""
    company_exact = (company or "").strip()
    rows = db.execute(
        "SELECT id, company, role FROM roles WHERE company = ? ORDER BY applied_on DESC",
        (company_exact,)
    ).fetchall()
    if not rows:
        rows = db.execute(
            "SELECT id, company, role FROM roles WHERE company LIKE ? ORDER BY applied_on DESC",
            (f"%{company_exact}%",)
        ).fetchall()
    if not rows:
        return None
    if role_hint and len(rows) > 1:
        rh = role_hint.lower()
        for r in rows:
            if rh in (r["role"] or "").lower():
                return r["id"]
    return rows[0]["id"]


def is_already_tracked(db, company, interview_date):
    """Check if an interview row already exists for this company+date."""
    rows = db.execute(
        "SELECT id FROM interviews WHERE company = ? AND interview_date = ?",
        (company, interview_date)
    ).fetchall()
    return len(rows) > 0


def insert_interview(signal, tracker_row):
    """Insert a new row into the interviews table. Returns True if inserted, False if already exists."""
    company = (signal.get("company_guess") or "").strip()
    role_hint = signal.get("role_guess")
    interview_date = signal.get("date", "")[:10]  # YYYY-MM-DD
    interview_type = "calendar" if signal.get("source") == "calendar" else "email"
    notes = signal.get("subject", "")[:200]

    if not company:
        print(f"[interviews_tracker] Skipping — no company name")
        return False

    db = sqlite3.connect(TRACKER_DB)
    db.row_factory = sqlite3.Row

    try:
        if is_already_tracked(db, company, interview_date):
            print(f"[interviews_tracker] Already tracked: {company} on {interview_date}")
            return False

        role_id = lookup_role_id(db, company, role_hint)
        role = (tracker_row.get("role") if tracker_row else None) or role_hint or ""
        jd_url = (tracker_row.get("jd_url") if tracker_row else None) or ""
        applied_on = (tracker_row.get("applied_on") if tracker_row else None) or ""
        added_on = datetime.date.today().isoformat()

        db.execute(
            """INSERT INTO interviews
               (role_id, company, role, jd_url, applied_on, interview_type, interview_date, outcome, notes, added_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (role_id, company, role, jd_url, applied_on, interview_type, interview_date, notes, added_on)
        )
        db.commit()
        print(f"[interviews_tracker] Inserted: {company} / {role} on {interview_date}")
        return True
    finally:
        db.close()


def render_and_upload(signals_inserted):
    """Re-render the XLSX and post to #job-search."""
    if not signals_inserted:
        print("[interviews_tracker] Nothing inserted — skipping render")
        return

    print("[interviews_tracker] Rendering XLSX...")
    result = subprocess.run(
        [RENDER_VENV, RENDER_SCRIPT],
        cwd=RENDER_CWD,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[interviews_tracker] Render FAILED: {result.stderr[:300]}")
        return
    print("[interviews_tracker] Render OK")

    if not os.path.exists(XLSX_PATH):
        print(f"[interviews_tracker] XLSX not found at {XLSX_PATH}")
        return

    print("[interviews_tracker] Uploading to #job-search...")
    up = subprocess.run(
        ["openclaw", "message", "send",
         "--channel", "discord",
         "-t", f"channel:{INTERVIEW_CHANNEL}",
         "-m", f"📋 Interview tracker updated — {signals_inserted} new interview(s) added. Rebuilding Cyrus_Job_Tracker.xlsx...",
         "--media", XLSX_PATH],
        capture_output=True, text=True
    )
    if up.returncode != 0:
        print(f"[interviews_tracker] Upload FAILED: {up.stderr[:200]}")
    else:
        print("[interviews_tracker] Uploaded OK")


def process_signals(signals_with_tracker):
    """[DISABLED 2026-06-23] No-op. Sheet is Cyrus-owned; do not write DB / re-render."""
    if _WRITE_DISABLED:
        print("[interviews_tracker] DISABLED — skipping interviews-table write + XLSX render "
              "(Cyrus owns the Interviews sheet). No-op.")
        return 0
    inserted = 0
    for item in signals_with_tracker:
        sig = item["signal"]
        tr = item.get("tracker_row")
        if insert_interview(sig, tr):
            inserted += 1
    render_and_upload(inserted)
    return inserted
