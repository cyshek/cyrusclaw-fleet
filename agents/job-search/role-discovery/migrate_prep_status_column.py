#!/usr/bin/env python3
"""migrate_prep_status_column.py — idempotent.

Adds `prep_status TEXT` to roles table if not present.

Values used:
  NULL          — no manual-ready packet
  'manual_ready'— prep complete, waiting for Cyrus to click Submit by hand
                  (currently only Workday roles)
  'submitted'   — Cyrus marked it submitted (manual flow can flip this; future)

`applied_by` / `applied_on` semantics unchanged: still mean "auto-submitted by
the pipeline" (or hand-set by Cyrus). prep_status is orthogonal.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "tracker.db"


def main() -> int:
    conn = sqlite3.connect(DB)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(roles)").fetchall()}
    changed = False
    if "prep_status" not in cols:
        conn.execute("ALTER TABLE roles ADD COLUMN prep_status TEXT")
        changed = True
        print("added column: prep_status")
    if "prep_path" not in cols:
        # Optional: store the applications/submitted/<slug>/ path for the xlsx link.
        conn.execute("ALTER TABLE roles ADD COLUMN prep_path TEXT")
        changed = True
        print("added column: prep_path")
    conn.commit()
    conn.close()
    if not changed:
        print("no changes (columns already present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
