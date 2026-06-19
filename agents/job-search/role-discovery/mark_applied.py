#!/usr/bin/env python3
"""Mark a role as manually applied in tracker.db.

Usage:
    mark_applied.py --id N [--method manual|easy-apply|other] [--notes "free text"]

Behavior:
    - Sets applied_by='Cyrus', applied_on=date('now') (UTC date), status='applied'
      (only flips status if it's currently NULL/empty/'open'/'queued').
    - Appends a timestamped line to agent_notes:
        "MANUAL-APPLY YYYY-MM-DD: method=<method> <notes>"
    - Makes a one-time backup of tracker.db on first write per day:
        tracker.db.bak.YYYYMMDD-manual-apply  (only if not already present)
    - Refuses to act if --id row is already applied_by!='' UNLESS --force.
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import shutil
import sqlite3
import sys

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "tracker.db"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", type=int, required=True, help="roles.id to mark applied")
    ap.add_argument(
        "--method",
        default="manual",
        help="method tag (manual|easy-apply|workday|other). Default: manual",
    )
    ap.add_argument("--notes", default="", help="optional free-text note")
    ap.add_argument("--db", default=DEFAULT_DB, help=f"tracker.db path (default {DEFAULT_DB})")
    ap.add_argument("--dry-run", action="store_true", help="show changes, don't write")
    ap.add_argument("--force", action="store_true", help="overwrite even if already applied")
    args = ap.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"FATAL: db not found: {db_path}", file=sys.stderr)
        return 2

    today = dt.date.today().isoformat()
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT id, company, role, status, applied_by, applied_on, agent_notes "
        "FROM roles WHERE id = ?",
        (args.id,),
    ).fetchone()

    if row is None:
        print(f"FATAL: no role with id={args.id}", file=sys.stderr)
        return 2

    if row["applied_by"] and not args.force:
        print(
            f"REFUSED: id={args.id} already applied_by={row['applied_by']!r} on "
            f"{row['applied_on']!r}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 3

    new_note_line = f"MANUAL-APPLY {today}: method={args.method}"
    if args.notes:
        new_note_line += f" {args.notes}"

    old_notes = row["agent_notes"] or ""
    new_notes = (old_notes + ("\n" if old_notes and not old_notes.endswith("\n") else "")) + new_note_line

    new_status = row["status"]
    if new_status in (None, "", "open", "queued", "blocked"):
        new_status = "applied"

    print("=" * 60)
    print(f"id          : {row['id']}")
    print(f"company     : {row['company']}")
    print(f"role        : {row['role']}")
    print(f"status      : {row['status']!r}  ->  {new_status!r}")
    print(f"applied_by  : {row['applied_by']!r}  ->  'Cyrus'")
    print(f"applied_on  : {row['applied_on']!r}  ->  {today!r}")
    print(f"agent_notes : append -> {new_note_line!r}")
    print("=" * 60)

    if args.dry_run:
        print("DRY RUN — no changes written.")
        return 0

    # Backup once per day
    bak = f"{db_path}.bak.{dt.date.today().strftime('%Y%m%d')}-manual-apply"
    if not os.path.exists(bak):
        shutil.copy2(db_path, bak)
        print(f"Backup created: {bak}")
    else:
        print(f"Backup already exists for today: {bak}")

    con.execute(
        "UPDATE roles SET status=?, applied_by=?, applied_on=?, agent_notes=? "
        "WHERE id=?",
        (new_status, "Cyrus", today, new_notes, args.id),
    )
    con.commit()
    con.close()
    print(f"OK: id={args.id} marked applied at {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
