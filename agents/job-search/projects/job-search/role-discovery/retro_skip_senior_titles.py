#!/usr/bin/env python3
"""
retro_skip_senior_titles.py — one-shot retro-pass for the senior-title skip layer.

Iterates all OPEN roles in tracker.db (no applied_by, status NOT in
skip/closed/none/scan-blocked, prep_status IS NULL) and flips any whose
title matches core.has_senior_title() to status='skip' with a 'senior-title'
flag appended.

Backs up tracker.db before --apply. --dry-run is the default.

Usage:
    .venv/bin/python retro_skip_senior_titles.py --dry-run
    .venv/bin/python retro_skip_senior_titles.py --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent  # projects/job-search
DB_PATH = PROJECT / "tracker.db"
RESULT_PATH = PROJECT / "applications" / "_senior-title-retro-skips.json"

sys.path.insert(0, str(HERE))
from core import has_senior_title, SENIOR_TITLE_RE  # noqa: E402


SKIP_STATUSES = {"skip", "closed", "none", "scan-blocked"}


def select_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute("""
        SELECT id, company, role, loc, exp_req, status, flags, applied_by,
               agent_notes, prep_status, app_url, jd_url
          FROM roles
         WHERE applied_by IS NULL
           AND (prep_status IS NULL OR prep_status='')
    """).fetchall()
    out = []
    for r in rows:
        st = (r["status"] or "").lower()
        if st in SKIP_STATUSES:
            continue
        out.append(r)
    return out


# Words that, when combined with a senior-keyword, suggest the role is NOT a
# senior IC/PM track and should be flagged for manual review rather than
# auto-skipped. e.g. "Group Engagement Manager" (customer-success), "Partner
# Manager" (channel partnerships), "Partner Engineer" (solutions partner-eng).
BORDERLINE_TOKENS = (
    "engagement",
    "channel",
    "alliance",
    "alliances",
    "partnerships",
    "ecosystem",
    "success",  # "Partner Success Manager"
)


def is_borderline(title: str) -> tuple[bool, str]:
    """Detect borderline matches that might be channel/CS roles, not senior IC/PM."""
    if not title:
        return False, ""
    t = title.lower()
    for tok in BORDERLINE_TOKENS:
        if tok in t:
            return True, tok
    # "Group" + words that aren't engineering/product/eng-mgr-y
    return False, ""


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="Preview matches without writing (default).")
    g.add_argument("--apply", action="store_true",
                   help="Commit changes to tracker.db after backup.")
    args = ap.parse_args()

    apply_mode = bool(args.apply)
    if apply_mode:
        args.dry_run = False

    if not DB_PATH.exists():
        print(f"ERROR: tracker.db not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    candidates = select_candidates(conn)
    print(f"[scan] {len(candidates)} open roles to evaluate")

    matched = []
    borderline = []
    for r in candidates:
        if not has_senior_title(r["role"]):
            continue
        m = SENIOR_TITLE_RE.search(r["role"] or "")
        keyword = m.group(0) if m else ""
        bord, btok = is_borderline(r["role"])
        rec = {
            "id": r["id"],
            "company": r["company"],
            "role": r["role"],
            "loc": r["loc"],
            "exp_req": r["exp_req"],
            "status": r["status"],
            "flags": r["flags"],
            "matched_keyword": keyword,
            "borderline_token": btok if bord else None,
        }
        if bord:
            borderline.append(rec)
        else:
            matched.append(rec)

    # Sort for stable output
    matched.sort(key=lambda x: (x["company"].lower(), x["id"]))
    borderline.sort(key=lambda x: (x["company"].lower(), x["id"]))

    print(f"[match] {len(matched)} clean senior-title matches")
    print(f"[borderline] {len(borderline)} borderline (flagged for review, NOT skipped)")
    print()
    print("== Sample of first 10 clean matches ==")
    for rec in matched[:10]:
        print(f"  id={rec['id']:>5}  [{rec['matched_keyword']:<15}]  {rec['company']:<20}  {rec['role']}")
    if borderline:
        print()
        print("== Borderline cases (NOT applied; review manually) ==")
        for rec in borderline:
            print(f"  id={rec['id']:>5}  [{rec['matched_keyword']:<15}]  ({rec['borderline_token']})  {rec['company']:<20}  {rec['role']}")

    if not apply_mode:
        print()
        print("[dry-run] No changes written. Re-run with --apply to commit.")
        # Still write a preview to a temp file for reference
        preview_path = PROJECT / "applications" / "_senior-title-retro-skips.preview.json"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dry_run": True,
            "matched_count": len(matched),
            "borderline_count": len(borderline),
            "matched": matched,
            "borderline": borderline,
        }, indent=2) + "\n")
        print(f"[dry-run] preview written to {preview_path}")
        return

    # --apply path
    backup = DB_PATH.with_suffix(
        f".db.bak.{datetime.now().strftime('%Y%m%d')}-senior-title"
    )
    # If backup already exists (re-run same day), tack on a unique suffix
    if backup.exists():
        backup = DB_PATH.with_suffix(
            f".db.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}-senior-title"
        )
    shutil.copy2(DB_PATH, backup)
    print(f"[backup] tracker.db -> {backup}")

    today = datetime.now().strftime("%Y-%m-%d")
    note = f"skipped by senior-title guard {today}"

    flipped_ids = []
    cur = conn.cursor()
    for rec in matched:
        rid = rec["id"]
        # Fetch current values for safe merge
        cur.execute("SELECT flags, agent_notes FROM roles WHERE id=?", (rid,))
        row = cur.fetchone()
        if not row:
            continue
        cur_flags = (row["flags"] or "").strip()
        cur_notes = (row["agent_notes"] or "").strip()
        # flags: comma-separated; avoid double-adding
        flag_set = {f.strip() for f in cur_flags.split(",") if f.strip()}
        flag_set.add("senior-title")
        new_flags = ",".join(sorted(flag_set))
        new_notes = (cur_notes + ("\n" if cur_notes else "") + note).strip()
        cur.execute("""
            UPDATE roles
               SET status='skip',
                   flags=?,
                   agent_notes=?
             WHERE id=?
        """, (new_flags, new_notes, rid))
        flipped_ids.append(rid)
    conn.commit()
    print(f"[apply] flipped {len(flipped_ids)} roles to status='skip'")

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applied": True,
        "backup_path": str(backup),
        "flipped_count": len(flipped_ids),
        "flipped_ids": flipped_ids,
        "matched": matched,
        "borderline_count": len(borderline),
        "borderline": borderline,
    }, indent=2) + "\n")
    print(f"[apply] result written to {RESULT_PATH}")


if __name__ == "__main__":
    main()
