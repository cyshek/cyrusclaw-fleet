"""LinkedIn offsite resolver — LEAN (tactic1 only: companies.yaml ATS-API title match).

Why lean: probing (2026-06-03) proved the LinkedIn guest jobPosting/jobs-view
endpoints DO NOT expose offsite apply URLs anonymously from this VM — they serve
the sign-in-wall variant and 429 after ~4 requests. And the v2 careers-page
domain-guess tactic hangs on dead hosts (connect timeouts x hundreds). So the
only fast+reliable anonymous path is: for companies we KNOW the ATS slug for
(companies.yaml), hit the ATS public board API and fuzzy-match the role title.

Reuses helpers from linkedin_ats_resolver_v2 (do not duplicate logic).

CLI:
  .venv/bin/python _li_offsite_lean.py --dry-run            # report table, no writes
  .venv/bin/python _li_offsite_lean.py --apply              # writes app_url + agent_notes
"""
from __future__ import annotations
import argparse, sqlite3, sys, time, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tracker_db import DB_PATH  # noqa
import linkedin_ats_resolver_v2 as v2  # noqa

# 2026-06-03: broadened from `source_key LIKE 'linkedin%'` (which MISSED rows
# whose source_key is the full https://...linkedin.com URL, e.g. Notion 758,
# Snowflake 871 — ~36 resolvable rows were silently excluded) to keying purely
# off the LinkedIn app_url. Still excludes terminal statuses. NOTE: 'skip' is
# excluded to respect intentional FDE/blocklist skips — if a legit role got
# wrongly swept to skip, fix the row's status, don't loosen this.
OPEN_SQL = (
    "SELECT id, company, role, jd_url, app_url, flags, agent_notes "
    "FROM roles WHERE app_url LIKE '%linkedin.com%' "
    "AND applied_by IS NULL AND status NOT IN ('applied','submitted','skip','closed') "
    "ORDER BY id"
)


def resolve_row(row):
    res = v2.Resolution(role_id=row["id"], company=row["company"], role_title=row["role"])
    try:
        v2.tactic1_companies_yaml(res)
    except Exception as e:
        res.error = f"tactic1 err: {e}"
    # High-confidence gate for OFFSITE apply: a loose match (e.g. "Solutions
    # Engineer Startups" -> "IT Solutions Engineer", j=0.67) would point the
    # applicant at the WRONG req. Require near-exact title match to commit.
    APPLY_MIN_JACCARD = 0.85
    if res.ats_url and res.jaccard < APPLY_MIN_JACCARD:
        res.error = f"low-confidence j={res.jaccard:.2f} matched={res.matched_title!r} (held back)"
        res.ats_url = None
    return res


def update_flags(flags: str, ats_kind: str) -> str:
    parts = [p for p in (flags or "").replace(";", " ").split() if p]
    parts = [p for p in parts if p != "linkedin-offsite-unresolved"]
    if "manual-apply" not in parts:
        parts.append("manual-apply")
    tag = f"ats-{ats_kind}"
    if tag not in parts:
        parts.append(tag)
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default="/tmp/li_lean_report.json")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(OPEN_SQL).fetchall()
    print(f"[lean] open linkedin-url rows: {len(rows)}  mode={'APPLY' if args.apply else 'DRY-RUN'}")

    results = []
    # serial — ATS APIs are fast; keeps us polite & avoids thread hangs
    for r in rows:
        res = resolve_row(r)
        results.append((r, res))
        flag = "RESOLVED" if res.ats_url else "no"
        print(f"  {r['id']:5} | {r['company'][:24]:24} | {r['role'][:42]:42} | {flag:8} | {res.ats_kind or '':14} | {res.ats_url or ''}")

    resolved = [(r, x) for r, x in results if x.ats_url]
    print(f"\n=== {len(resolved)}/{len(rows)} resolved ({100*len(resolved)//max(1,len(rows))}%) ===")
    bykind = {}
    for _, x in resolved:
        bykind[x.ats_kind] = bykind.get(x.ats_kind, 0) + 1
    for k, n in sorted(bykind.items(), key=lambda z: -z[1]):
        print(f"  {k:16} {n}")

    json.dump(
        [{"id": r["id"], "company": r["company"], "role": r["role"], "resolved": bool(x.ats_url),
          "new_app_url": x.ats_url, "ats": x.ats_kind, "matched": x.matched_title, "jaccard": round(x.jaccard, 3)}
         for r, x in results],
        open(args.out, "w"), indent=2)
    print(f"wrote {args.out}")

    if args.apply and resolved:
        stamp = "2026-06-03"
        n = 0
        for r, x in resolved:
            orig = r["app_url"]
            note = (r["agent_notes"] or "").rstrip()
            sep = "\n" if note else ""
            note += f"{sep}LINKEDIN-OFFSITE-RESOLVED {stamp} via companies.yaml ats={x.ats_kind} jaccard={x.jaccard:.2f} | original: {orig}"
            newflags = update_flags(r["flags"], x.ats_kind)
            conn.execute("UPDATE roles SET app_url=?, agent_notes=?, flags=? WHERE id=?",
                         (x.ats_url, note, newflags, r["id"]))
            n += 1
        conn.commit()
        print(f"APPLIED: updated {n} rows")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
