#!/usr/bin/env python3
"""Backfill posted_on from JobRight raw feed into tracker.db for existing rows
that have no posted_on date (e.g. Google roles found via direct crawl).

Usage:
    python backfill_jobright_dates.py
"""
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from adapters.jobright import crawl as jr_crawl  # noqa

DB_PATH = HERE.parent / "tracker.db"


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def main() -> None:
    print("[backfill_jobright_dates] Fetching raw JobRight feed...")
    raw_roles = jr_crawl()  # all 347, unfiltered
    print(f"[backfill_jobright_dates] {len(raw_roles)} raw roles fetched")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Load existing rows that have no posted_on
    cur.execute(
        "SELECT id, company, role FROM roles WHERE (posted_on IS NULL OR posted_on='') "
        "AND status != 'closed'"
    )
    no_date_rows = {(_norm(r["company"]), _norm(r["role"])): r["id"] for r in cur.fetchall()}
    print(f"[backfill_jobright_dates] {len(no_date_rows)} existing rows have no posted_on")

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    backfilled = 0
    for role in raw_roles:
        if not role.posted_at:
            continue
        key = (_norm(role.company), _norm(role.title))
        row_id = no_date_rows.get(key)
        if row_id:
            cur.execute(
                "UPDATE roles SET posted_on=? WHERE id=? AND (posted_on IS NULL OR posted_on='')",
                (role.posted_at, row_id),
            )
            if cur.rowcount:
                backfilled += 1
                print(f"  backfilled id={row_id} {role.company} | {role.title} -> {role.posted_at}")

    con.commit()
    con.close()
    print(f"[backfill_jobright_dates] Done. Backfilled posted_on for {backfilled} rows.")


if __name__ == "__main__":
    main()
