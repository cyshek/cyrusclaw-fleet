#!/usr/bin/env python3
"""Idempotent ALTER TABLE adding 6 LLM-classifier columns to roles.

Backs up tracker.db to tracker.db.bak.YYYYMMDD-llm-classifier before mutating.
Safe to run multiple times.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "tracker.db"

NEW_COLS = [
    ("llm_classified_at", "TEXT"),
    ("llm_yoe_required", "INTEGER"),
    ("llm_is_people_manager", "INTEGER"),
    ("llm_seniority", "TEXT"),
    ("llm_fit_score", "INTEGER"),
    ("llm_reason", "TEXT"),
]


def main() -> int:
    if not DB.exists():
        print(f"ERR tracker.db missing: {DB}", file=sys.stderr)
        return 2

    con = sqlite3.connect(DB)
    existing = {r[1] for r in con.execute("PRAGMA table_info(roles)").fetchall()}
    missing = [(n, t) for (n, t) in NEW_COLS if n not in existing]

    if not missing:
        print("OK all 6 LLM columns already present; nothing to do.")
        con.close()
        return 0

    # Backup first
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    bak = DB.with_suffix(f".db.bak.{stamp}-llm-classifier")
    if not bak.exists():
        shutil.copy2(DB, bak)
        print(f"OK backed up tracker.db -> {bak.name}")
    else:
        print(f"OK backup already exists: {bak.name}")

    for name, typ in missing:
        con.execute(f"ALTER TABLE roles ADD COLUMN {name} {typ}")
        print(f"  + added {name} {typ}")
    con.commit()
    con.close()
    print(f"OK migration complete; {len(missing)} columns added.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
