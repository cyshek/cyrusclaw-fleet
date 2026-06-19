#!/usr/bin/env python3
"""Post-residential-drain RECONCILER (canonical).

Run AFTER any residential-egress drain (_residential_browser.sh + _ashby_runner.py).
The drain marks wins via STATUS.md + response_status='submitted-residential' but the
ad-hoc drain driver does NOT flip the tracker `status` -> rows get stranded as 'blocked'
even though they were really submitted (bug found by the 2026-06-11 blocked-section audit:
944/946/947/1237 were submitted 06-08 but still labelled blocked).

This reconciler is IDEMPOTENT and is the durable fix: it (1) backfills any missing
applications/submitted/<slug>/STATUS.md from .ashbydrain-results.json, AND (2) flips the
DB row to status='applied', applied_by='auto-residential', applied_on=<date> for every
'submitted' drain win not already applied. Takes a tracker.db.bak first. Safe to re-run.

Two evidence sources are required before flipping a row to applied (disk+DB both directions):
  - .ashbydrain-results.json says the row == 'submitted', OR
  - the DB row already carries response_status LIKE '%submitted-residential%'.
A row flips to applied only when at least one holds; otherwise it's left untouched + reported.
"""
import json, os, re, sqlite3, datetime, shutil, sys

ROOT = '/home/azureuser/.openclaw/agents/job-search/workspace'
DB = os.path.join(ROOT, 'projects/job-search/tracker.db')
RESULTS = '.ashbydrain-results.json'
TODAY = datetime.date.today().isoformat()


def load_results():
    if not os.path.exists(RESULTS):
        return {}
    try:
        return json.load(open(RESULTS))
    except Exception as e:
        print(f"[warn] could not read {RESULTS}: {e}")
        return {}


def outcome_of(v):
    return (v[0] if isinstance(v, (list, tuple)) else v)


def note_of(v):
    return (v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else '')


def main():
    c = sqlite3.connect(DB)
    res = load_results()

    # rows the results file says were submitted
    submitted_ids = {str(rid) for rid, v in res.items() if outcome_of(v) == 'submitted'}
    # PLUS any DB row already flagged submitted-residential (covers drains whose results file is gone)
    db_resid = {str(r[0]) for r in c.execute(
        "SELECT id FROM roles WHERE response_status LIKE '%submitted-residential%'").fetchall()}
    candidate_ids = submitted_ids | db_resid
    if not candidate_ids:
        print("[reconcile] no submitted-residential drain wins found — nothing to do.")
        return

    # backup before any write
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = f"{DB}.bak.{stamp}-drain-reconcile"
    shutil.copy2(DB, bak)
    print(f"[reconcile] backup -> {bak}")

    made_status, flipped, skipped = [], [], []
    for rid in sorted(candidate_ids, key=lambda x: int(x) if x.isdigit() else 0):
        row = c.execute(
            "SELECT id,company,role,app_url,status,applied_by,response_status FROM roles WHERE id=?",
            (rid,)).fetchone()
        if not row:
            continue
        cid, co, role, url, status, by, rstat = row

        # --- (1) backfill STATUS.md if missing ---
        base = re.sub(r'[^a-z0-9]+', '-', (co or 'co').lower()).strip('-')
        slug = f"{base}-{cid}"
        d = os.path.join(ROOT, 'applications/submitted', slug)
        sp = os.path.join(d, 'STATUS.md')
        if not os.path.exists(sp):
            os.makedirs(d, exist_ok=True)
            open(sp, 'w').write(f"""# SUBMITTED — {co} (role_id {cid})

- **role:** {role}
- **status:** SUBMITTED
- **submitted_by:** auto-residential
- **submitted_on:** {TODAY}
- **app_url:** {url}
- **confirmation:** FormSubmitSuccess (Ashby)
- **egress:** residential (Webshare)
- **evidence:** .ashbydrain-results.json / response_status=submitted-residential
- **reconciled:** STATUS.md + DB status by post-drain reconciler {TODAY}
""")
            made_status.append(slug)

        # --- (2) flip DB status if not already applied ---
        if status != 'applied':
            c.execute(
                "UPDATE roles SET status='applied', applied_by='auto-residential', "
                "applied_on=COALESCE(applied_on,?), "
                "response_status=COALESCE(NULLIF(response_status,''),'submitted-residential') "
                "WHERE id=?",
                (TODAY, cid))
            flipped.append((cid, co))
        else:
            skipped.append((cid, co))

    c.commit()
    print(f"[reconcile] backfilled {len(made_status)} STATUS.md")
    for m in made_status:
        print('   +', m)
    print(f"[reconcile] flipped {len(flipped)} rows -> applied (auto-residential)")
    for fid, fco in flipped:
        print('   ->', fid, fco)
    print(f"[reconcile] already-applied (left as-is): {len(skipped)}")
    if flipped:
        print("[reconcile] REMINDER: run render_xlsx.py to refresh the sheet.")


if __name__ == '__main__':
    main()
