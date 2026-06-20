#!/usr/bin/env python3
"""backfill_workday_exp.py

For every open Workday role in tracker.db, fetch the JD via the CXS endpoint,
re-run parse_experience over the JD body, and update roles.exp_req if it
changes. Also logs people-management overreach matches (title or JD) into
applications/_overreach-backfill.json.

No browser. Pure HTTP. Skips rows where workday is in maintenance mode.
Idempotent.
"""
from __future__ import annotations
import json
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

from core import parse_experience, is_overreach  # noqa: E402
from workday_dryrun import parse_workday_url, fetch_workday_job  # noqa: E402

DB = PROJECT / "tracker.db"
LOG_PATH = PROJECT / "applications" / "_overreach-backfill.json"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, company, role, exp_req, app_url, jd_url
        FROM roles
        WHERE applied_on IS NULL
          AND (status IS NULL OR status='')
          AND (app_url LIKE '%myworkdayjobs.com%' OR jd_url LIKE '%myworkdayjobs.com%')
        ORDER BY id
    """).fetchall()
    print(f"open Workday rows: {len(rows)}")
    changes = []
    overreaches = []
    for r in rows:
        url = r["app_url"] or r["jd_url"]
        try:
            parts = parse_workday_url(url)
        except Exception as e:
            print(f"  [{r['id']}] URL parse failed: {e}")
            continue
        fetched = fetch_workday_job(parts, quiet=True)
        if fetched.get("maintenance_mode"):
            print(f"  [{r['id']}] maintenance mode, skip")
            continue
        if fetched.get("fetch_error"):
            print(f"  [{r['id']}] fetch error: {fetched['fetch_error']}")
            continue
        jd = fetched.get("jd_text") or ""
        if not jd or len(jd) < 200:
            print(f"  [{r['id']}] JD body too short ({len(jd)})")
            continue
        new_exp = parse_experience(jd)
        old_exp = r["exp_req"] or ""
        if new_exp != old_exp:
            print(f"  [{r['id']}] {r['company'][:20]} | {old_exp} -> {new_exp}")
            conn.execute("UPDATE roles SET exp_req=? WHERE id=?", (new_exp, r["id"]))
            changes.append({"role_id": r["id"], "company": r["company"],
                            "role": r["role"], "old": old_exp, "new": new_exp})
        ovr, reason = is_overreach(new_exp, jd, r["role"])
        if ovr:
            overreaches.append({"role_id": r["id"], "company": r["company"],
                                "role": r["role"], "exp_req": new_exp,
                                "reason": reason, "url": url})
        time.sleep(0.5)
    conn.commit()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_changes": len(changes),
        "n_overreaches": len(overreaches),
        "changes": changes,
        "overreaches": overreaches,
    }, indent=2) + "\n")
    print(f"\n{len(changes)} exp_req updates, {len(overreaches)} overreaches flagged")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()
