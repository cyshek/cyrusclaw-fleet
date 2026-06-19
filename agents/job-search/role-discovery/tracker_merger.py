"""Merge discovered roles JSON into tracker.db (SQLite-backed).

Logic:
- For each discovered role:
    - source_key (normalize_url) already in DB → update last_seen, backfill posted_on,
      preserve cyrus-edited fields (status, applied_*, cyrus_notes).
    - new → INSERT with status='' (empty = open queue).
- Auto-close: rows with status='' AND no applied_by AND a verifiable URL that
  no longer appears in fresh data → status='closed' with flags annotation.
  Conservative — same guards as before (skip linkedin/indeed; require company
  was successfully scanned with fetched > 0).

Companies skipped from auto-close (no successful scan this run) keep their
existing rows untouched.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from tracker_db import connect, normalize_url, today, DB_PATH
try:
    from staffing_blocklist import is_staffing_firm
except ImportError:  # pragma: no cover - safety guard
    def is_staffing_firm(_):
        return False

POSTED_RE = re.compile(r"posted:(\d{4}-\d{2}-\d{2})")

_TITLE_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm_title(t: str) -> str:
    return _TITLE_NORM_RE.sub(" ", (t or "").lower()).strip()


def _norm_company(c: str) -> str:
    c = (c or "").lower().strip()
    for noise in (" inc.", " inc", " labs", ".io", ".ai", " technologies",
                  " tech", " platform", " ai", ","):
        c = c.replace(noise, " ")
    return re.sub(r"\s+", " ", c).strip()


def role_to_db_row(r: dict) -> dict:
    url = r.get("url", "")
    posted = (r.get("posted_at") or "")[:10] or None
    source = r.get("source", "") or ""
    # LinkedIn-discovery rows: use stable linkedin:<job_id> source_key when
    # the row could not be resolved to a known ATS (source still 'linkedin').
    # If resolved (source 'linkedin:greenhouse' etc), use the ATS URL via
    # normalize_url so it can dedup against the same job from the curated
    # ATS adapter.
    if source == "linkedin":
        # raw is dropped at to_dict() time so we have to reconstruct the
        # job_id from the URL.
        job_id = None
        m = re.search(r"/jobs/view/[^/?]*?-(\d{8,})", url)
        if m:
            job_id = m.group(1)
        if not job_id:
            m2 = re.search(r"(\d{9,})", url)
            job_id = m2.group(1) if m2 else None
        src_key = f"linkedin:{job_id}" if job_id else normalize_url(url)
    elif source == "jobright":
        # JobRight discovery rows: app_url is a jobright.ai/jobs/info/<id>
        # wrapper (24-hex Mongo ObjectId). Use a stable `jobright:<jobId>`
        # source_key (mirrors the linkedin:<job_id> precedent) so re-runs
        # dedupe idempotently. raw is dropped at to_dict() time, so the jobId
        # is recovered from the wrapper URL.
        m = re.search(r"/jobs/info/([0-9a-fA-F]{24})", url)
        src_key = f"jobright:{m.group(1)}" if m else normalize_url(url)
    else:
        src_key = normalize_url(url)
    return dict(
        source_key=src_key,
        company=r["company"],
        role=r["title"],
        level=None,
        loc=r.get("location") or None,
        exp_req=r.get("exp_required") or "exp:unstated",
        jd_url=url or None,
        app_url=url or None,
        posted_on=posted,
        flags=(f"posted:{posted}" if posted else None),
        _source=source,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles-json", help="Discovered roles JSON (default: latest in output/)")
    args = ap.parse_args()

    if not args.roles_json:
        out_dir = HERE / "output"
        candidates = sorted(out_dir.glob("*-roles.json"))
        if not candidates:
            sys.exit("No roles JSON found in output/.")
        args.roles_json = str(candidates[-1])

    roles_json = json.loads(Path(args.roles_json).read_text(encoding="utf-8"))
    print(f"Loaded {len(roles_json)} discovered roles from {args.roles_json}")

    # Load meta for auto-close scoping
    meta_path = Path(args.roles_json).with_name(
        Path(args.roles_json).stem.replace("-roles", "-meta") + ".json"
    )
    company_fetched: dict[str, int] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for s in meta.get("successes", []):
            company_fetched[s["company"].lower()] = s.get("fetched", 0)
        print(f"Loaded meta: {len(company_fetched)} companies scanned successfully")
    else:
        print(f"WARN: no meta at {meta_path} — auto-close disabled this run")

    conn = connect()
    cur = conn.cursor()

    # Index existing rows by source_key
    cur.execute("SELECT id, source_key, status, applied_by, flags, posted_on FROM roles WHERE source_key IS NOT NULL")
    existing = {r["source_key"]: dict(r) for r in cur.fetchall()}
    print(f"Loaded {len(existing)} existing rows from {DB_PATH}")

    # Index existing rows by (norm_company, norm_title) for cross-source dedup.
    cur.execute("SELECT id, source_key, company, role FROM roles")
    existing_ct: dict[tuple[str, str], dict] = {}
    for r in cur.fetchall():
        ct = (_norm_company(r["company"]), _norm_title(r["role"]))
        # Prefer non-linkedin rows as the canonical entry for this (co, title)
        prev = existing_ct.get(ct)
        if prev is None or (str(prev["source_key"] or "").startswith("linkedin:")
                            and not str(r["source_key"] or "").startswith("linkedin:")):
            existing_ct[ct] = dict(r)

    fresh_keys: set[str] = set()
    inserted_keys: set[str] = set()  # keys INSERTed this run (dedupe within the discovered JSON)
    inserted = 0
    matched = 0
    backfilled_posted = 0
    linkedin_dropped = 0

    stamp = today()
    for r in roles_json:
        row = role_to_db_row(r)
        key = row["source_key"]
        if not key:
            continue
        fresh_keys.add(key)
        if key in inserted_keys:
            # Duplicate source_key within the SAME discovered JSON (already
            # inserted moments ago this run) -> skip to avoid UNIQUE collision.
            continue
        if key in existing:
            matched += 1
            ex = existing[key]
            # Backfill posted_on if missing
            if not ex.get("posted_on") and row["posted_on"]:
                cur.execute(
                    "UPDATE roles SET posted_on=?, last_seen=?, flags=COALESCE(NULLIF(flags,''), ?) WHERE id=?",
                    (row["posted_on"], stamp, row["flags"], ex["id"]),
                )
                backfilled_posted += 1
            else:
                cur.execute("UPDATE roles SET last_seen=? WHERE id=?", (stamp, ex["id"]))
            continue
        # Cross-source dedup for LinkedIn-discovery rows: if (company, title)
        # already exists from any source, skip the LinkedIn duplicate.
        if (row.get("_source") or "").startswith("linkedin"):
            ct = (_norm_company(row["company"]), _norm_title(row["role"]))
            if ct in existing_ct and not str(existing_ct[ct]["source_key"] or "").startswith("linkedin:"):
                linkedin_dropped += 1
                continue
        # Cross-source backfill: if (company, title) already exists from any
        # non-JobRight source but has no posted_on, and this JobRight row has
        # one, backfill it. Then skip the duplicate insert. (2026-06-14)
        if (row.get("_source") or "").startswith("jobright"):
            ct = (_norm_company(row["company"]), _norm_title(row["role"]))
            if ct in existing_ct:
                ex_ct = existing_ct[ct]
                if not ex_ct.get("posted_on") and row.get("posted_on"):
                    cur.execute(
                        "UPDATE roles SET posted_on=?, last_seen=? WHERE id=?",
                        (row["posted_on"], stamp, ex_ct["id"]),
                    )
                    backfilled_posted += 1
                continue  # skip insert regardless — row already exists
        # Staffing-firm safety net (in case adapter didn't drop it).
        # Insert as status='skip' rather than '' so it stays out of any queue.
        _is_staffing = is_staffing_firm(row["company"])
        # INSERT new
        flags = row["flags"]
        if (row.get("_source") or "").startswith("linkedin"):
            base = flags or ""
            flags = (base + " manual-apply").strip() if "manual-apply" not in base else base
            if ":" in (row.get("_source") or ""):  # resolved to ATS
                flags = flags.replace("manual-apply", "").strip() or None
        # Discovery-only adapters: never auto-apply. Cyrus rule 2026-05-28
        # for Google — we want roles in the tracker so he can ask for a
        # tailored resume, but auto-submit must skip them. The
        # `manual-apply` tag is the same signal already used elsewhere,
        # and `inline_submit.pick_batch` won't match google.com URLs
        # anyway. Keep this list small and explicit.
        # 2026-05-29: added openai per Cyrus — he'll handle OpenAI apps himself.
        # 2026-06-01: added uber per Cyrus — discover + hold for referral, he
        # routes through a friend; never auto-apply (custom careers API, no ATS).
        # 2026-06-08: Cyrus REMOVED the uber auto-manual-apply lock ("get rid of
        # the auto submit lock"). Uber is no longer force-tagged manual-apply/
        # discovery-only here. NOTE: Uber still has NO standard ATS (custom
        # careers API behind CSRF/Akamai), so the inline submit pipeline cannot
        # POST to it — Uber rows are applied via live-browser drive or prepped
        # for manual, not auto-submitted. Lock removal != auto-submit capability.
        # 2026-06-01: added bytedance + tiktok — referral-hold.
        # 2026-06-15: RESCINDED hold for bytedance + tiktok (Cyrus directive).
        #   Both now auto-apply via _tiktok_runner.py (same as Uber rescind 2026-06-08).
        # 2026-06-11: added jobright — DISCOVERY-ONLY source. JobRight's
        # public feed only exposes a jobright.ai/jobs/info/<id> WRAPPER URL
        # (the real ATS URL is behind their authed /swan/* API, out of scope).
        # These rows are a freshness/discovery signal; auto-submit must skip
        # them, so tag manual-apply + discovery-only (the burndown queue
        # excludes BLOCKED/manual-apply rows). See adapters/jobright.py.
        if (row.get("_source") or "") in {"google", "microsoft", "openai", "jobright"}:
            base = flags or ""
            if "manual-apply" not in base:
                flags = (base + " manual-apply").strip()
            if "discovery-only" not in (flags or ""):
                flags = ((flags or "") + " discovery-only").strip()
        # JobRight rows carry ONLY a jobright.ai/jobs/info/<id> wrapper URL (no
        # ATS host), so inline_submit.pick_batch already can't select them. But
        # the sequential_burndown queue keys purely on status=''/applied/prep —
        # it does NOT filter on flags or URL — so a freshly-inserted status=''
        # jobright row WOULD be picked up and waste a doomed attempt. Insert
        # jobright as status='manual-apply' (a non-empty status, like the 138
        # existing manual-apply rows) so it is excluded from EVERY status=''
        # queue immediately, while staying visible to Cyrus as a discovery hit.
        # Scoped to jobright only to avoid changing the other discovery-only
        # sources' established status='' behavior.
        _discovery_status = "manual-apply" if (row.get("_source") or "") == "jobright" else None
        if _is_staffing:
            base = flags or ""
            if "staffing-firm" not in base:
                flags = (base + " staffing-firm").strip()
        cur.execute(
            """INSERT INTO roles
               (source_key, company, role, level, loc, exp_req, jd_url, app_url,
                status, flags, applied_by, applied_on, cyrus_notes,
                posted_on, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, row["company"], row["role"], row["level"], row["loc"],
             row["exp_req"], row["jd_url"], row["app_url"],
             ("skip" if _is_staffing else (_discovery_status or "")), flags, None, None, None,
             row["posted_on"], stamp, stamp),
        )
        existing_ct[(_norm_company(row["company"]), _norm_title(row["role"]))] = {
            "id": None, "source_key": key, "company": row["company"], "role": row["role"],
        }
        inserted_keys.add(key)
        inserted += 1

    # Auto-close: was '' status, never applied, didn't show up this run
    closed = 0
    cur.execute("""SELECT id, source_key, company FROM roles
                   WHERE COALESCE(status,'')=''
                     AND applied_by IS NULL
                     AND source_key IS NOT NULL""")
    for r in cur.fetchall():
        key = r["source_key"]
        if key in fresh_keys:
            continue
        url_lower = key.lower()
        if any(d in url_lower for d in ("linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com")):
            continue
        if key.startswith("linkedin:"):
            # LinkedIn-discovery rows: never auto-close from another adapter's
            # crawl. They'd only auto-close from a fresh LinkedIn crawl that
            # didn't see the same job_id, which today is not implemented.
            continue
        if key.startswith("noref:"):
            continue
        if key.startswith("jobright:"):
            # JobRight discovery rows: never auto-close from another adapter's
            # crawl (same rationale as linkedin). They'd only auto-close from a
            # fresh JobRight crawl that didn't re-list the same jobId; the
            # jobright source_key won't appear in another company's fresh_keys,
            # and a company-name collision must not silently close them.
            continue
        if company_fetched.get(r["company"].lower(), 0) <= 0:
            continue
        cur.execute(
            """UPDATE roles SET status='closed',
                                flags=TRIM(COALESCE(flags,'') || ' auto-closed:' || ?)
               WHERE id=?""",
            (stamp, r["id"]),
        )
        closed += 1

    # Persist company_scans
    for co, n in company_fetched.items():
        cur.execute(
            "INSERT INTO company_scans(company,last_scan,fetched,status) VALUES(?,?,?,?) "
            "ON CONFLICT(company) DO UPDATE SET last_scan=excluded.last_scan, fetched=excluded.fetched",
            (co, stamp, n, "ok"),
        )

    conn.commit()
    conn.close()

    print(f"\nResults:")
    print(f"  Already in DB (matched):        {matched}")
    print(f"  Brand-new rows inserted:        {inserted}")
    print(f"  posted_on backfills:            {backfilled_posted}")
    print(f"  LinkedIn dups dropped (co+ttl): {linkedin_dropped}")
    print(f"  Auto-closed (no longer listed): {closed}")


if __name__ == "__main__":
    main()
