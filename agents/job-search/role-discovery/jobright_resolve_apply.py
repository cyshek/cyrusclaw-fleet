"""JobRight authed apply-URL resolver.

Resolves jobright.ai/jobs/info/<jobId> WRAPPER rows to their real ATS apply URLs
by calling the authenticated JobRight API:
  GET https://jobright.ai/swan/share/job/<jobId>
  Cookie: SESSION_ID=<session_id>

Response envelope (proven live):
  {"success":true,"errorCode":10000,"result":{"jobDetail":{"jobResult":{
    "jobId":"...","jobTitle":"...","originalUrl":"https://...","applyLink":"..."
  }}}}

On success, the resolved ATS URL replaces the wrapper app_url in tracker.db and
the row status is updated:
  - Known auto-submittable ATS host (greenhouse/ashby/lever/workday/rippling/
    bamboohr/smartrecruiters/workable/eightfold): status set to '' (enters the
    normal auto-submit burndown queue).
  - Unknown/unrecognized ATS host: status stays 'manual-apply' but app_url is
    updated to the real URL (better for manual review; still visible in tracker).

Cookie source (NEVER hardcoded):
  1. Env var JOBRIGHT_SESSION_ID
  2. File projects/job-search/.jobright-session (single line; gitignored)
  If neither is set, the script prints a clear message and exits cleanly.

CLI:
  python jobright_resolve_apply.py               # resolve all eligible rows
  python jobright_resolve_apply.py --limit N     # resolve at most N rows
  python jobright_resolve_apply.py --dry-run     # print what WOULD change, no writes
  python jobright_resolve_apply.py --job-id <id> # resolve a single jobId (24-hex)

Eligibility filter:
  WHERE source_key LIKE 'jobright:%'
    AND status='manual-apply'
    AND app_url LIKE 'https://jobright.ai/%'
  (Idempotent: already-resolved rows have a non-jobright.ai app_url, so they're
   automatically skipped.)

DB backup: tracker.db.bak.jobright-resolve-<timestamp> created BEFORE any writes.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

import requests

# ── paths ─────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
# role-discovery/jobright_resolve_apply.py → ONE level up = projects/job-search/
# (HERE is .../role-discovery; the project root is its parent).
PROJ_DIR = HERE.parent
# Canonical tracker.db lives at the PROJECT ROOT (projects/job-search/tracker.db),
# matching tracker_db.py and inline_submit.py. A stale 0-byte tracker.db can sit
# inside role-discovery/; pointing DB_PATH at HERE silently resolves to that empty
# file → "nothing to resolve". Always anchor to PROJ_DIR. (bugfix 2026-06-13)
DB_PATH = PROJ_DIR / "tracker.db"
SESSION_FILE = PROJ_DIR / ".jobright-session"

# ── API ───────────────────────────────────────────────────────────────────────
JOBRIGHT_API = "https://jobright.ai/swan/share/job/{job_id}"
RATE_LIMIT_SEC = 0.8     # polite inter-request delay
REQUEST_TIMEOUT = 15


# ── exceptions ────────────────────────────────────────────────────────────────
class JobRightAuthError(Exception):
    """Raised when the SESSION_ID cookie is rejected (401/403) or the API
    returns a session-expired / unauthorized error response."""


class JobRightResolveError(Exception):
    """Raised on network error, malformed response, or missing required fields."""


# ── ATS host classification ────────────────────────────────────────────────────
# Mirrors the logic in inline_submit.detect_ats() so we don't import that
# giant module (it pulls in browser tooling we don't need here).

_WORKDAY_RX = re.compile(r"https?://[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com/", re.I)
_RIPPLING_RX = re.compile(r"ats\.rippling\.com/", re.I)
_BAMBOOHR_RX = re.compile(r"[a-z0-9-]+\.bamboohr\.com/", re.I)

#: ATS (name, test-function) pairs for known auto-submittable hosts.
_AUTO_ATS_PATTERNS = [
    ("greenhouse",      lambda u: "greenhouse.io" in u),
    ("ashby",           lambda u: "ashbyhq.com" in u),
    ("lever",           lambda u: "lever.co" in u),
    ("workday",         lambda u: bool(_WORKDAY_RX.search(u))),
    ("rippling",        lambda u: bool(_RIPPLING_RX.search(u))),
    ("bamboohr",        lambda u: bool(_BAMBOOHR_RX.search(u))),
    ("smartrecruiters", lambda u: "smartrecruiters.com" in u),
    ("workable",        lambda u: "workable.com" in u),
    ("eightfold",       lambda u: "eightfold.ai" in u),
]


def classify_ats(url: str) -> str:
    """Return the ATS name if known/auto-submittable, else 'unknown'.

    >>> classify_ats("https://boards.greenhouse.io/acme/jobs/123")
    'greenhouse'
    >>> classify_ats("https://jobs.ashbyhq.com/co/abc-123")
    'ashby'
    >>> classify_ats("https://jobs.lever.co/co/abc")
    'lever'
    >>> classify_ats("https://acme.wd1.myworkdayjobs.com/jobs")
    'workday'
    >>> classify_ats("https://ats.rippling.com/acme/jobs/abc")
    'rippling'
    >>> classify_ats("https://acme.bamboohr.com/careers/123")
    'bamboohr'
    >>> classify_ats("https://app.smartrecruiters.com/acme/123")
    'smartrecruiters'
    >>> classify_ats("https://apply.workable.com/acme/j/abc")
    'workable'
    >>> classify_ats("https://acme.eightfold.ai/careers/")
    'eightfold'
    >>> classify_ats("https://www.amazon.jobs/")
    'unknown'
    >>> classify_ats("https://jobright.ai/jobs/info/abc")
    'unknown'
    >>> classify_ats("")
    'unknown'
    """
    u = url or ""
    for name, test in _AUTO_ATS_PATTERNS:
        if test(u):
            return name
    return "unknown"


# ── URL cleaning ───────────────────────────────────────────────────────────────

_UTM_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "ref", "source",
])


def strip_utm_params(url: str) -> str:
    """Remove UTM/tracking query params from a URL.

    Greenhouse ``?token=`` is PRESERVED — it carries the job token and is
    essential for the embed apply URL to route correctly.

    >>> u = strip_utm_params("https://boards.greenhouse.io/co/jobs/123?token=abc&utm_source=jobright")
    >>> "token=abc" in u and "utm_source" not in u
    True
    >>> strip_utm_params("https://www.amazon.jobs/en/jobs/123?utm_source=jobright&mode=job_posting")
    'https://www.amazon.jobs/en/jobs/123?mode=job_posting'
    >>> strip_utm_params("https://example.com/jobs")
    'https://example.com/jobs'
    >>> strip_utm_params("")
    ''
    """
    if not url:
        return url
    parsed = urlparse(url)
    if not parsed.query:
        return url
    qs = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in qs.items() if k.lower() not in _UTM_PARAMS}
    new_query = urlencode(sorted(cleaned.items()), doseq=True)
    return urlunparse(parsed._replace(query=new_query))


# ── cookie loading ─────────────────────────────────────────────────────────────

def load_session_id() -> Optional[str]:
    """Return the JobRight SESSION_ID from env var or session file.

    Priority: env var JOBRIGHT_SESSION_ID > file .jobright-session.
    Returns None if neither is set.
    """
    val = os.environ.get("JOBRIGHT_SESSION_ID", "").strip()
    if val:
        return val
    if SESSION_FILE.exists():
        val = SESSION_FILE.read_text(encoding="utf-8").strip()
        if val:
            return val
    return None


# ── core API call ─────────────────────────────────────────────────────────────

_session = requests.Session()
_last_call_ts = [0.0]


def resolve_apply_url(job_id: str, session_id: str) -> Optional[str]:
    """Resolve a JobRight jobId to its real ATS apply URL.

    Calls the authenticated /swan/share/job/<jobId> API.
    Returns the cleaned ATS URL, or None if the API returns success:false or
    the expected fields are missing.

    Raises:
        JobRightAuthError: on HTTP 401/403 or an auth-failure API error code.
        JobRightResolveError: on network error, non-200 HTTP, or parse failure.

    The returned URL has UTM params stripped; Greenhouse token= is preserved.
    """
    url = JOBRIGHT_API.format(job_id=job_id)
    headers = {
        "Cookie": f"SESSION_ID={session_id}",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://jobright.ai/jobs/info/{job_id}",
    }

    # Polite rate limit
    elapsed = time.time() - _last_call_ts[0]
    if elapsed < RATE_LIMIT_SEC:
        time.sleep(RATE_LIMIT_SEC - elapsed)
    _last_call_ts[0] = time.time()

    try:
        resp = _session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise JobRightResolveError(
            f"Network error fetching jobId={job_id}: {exc}"
        ) from exc

    if resp.status_code in (401, 403):
        raise JobRightAuthError(
            f"JobRight API returned HTTP {resp.status_code} for jobId={job_id}. "
            "SESSION_ID is expired or invalid. Re-export JOBRIGHT_SESSION_ID with a fresh cookie."
        )
    if resp.status_code != 200:
        raise JobRightResolveError(
            f"Unexpected HTTP {resp.status_code} from JobRight API for jobId={job_id}"
        )

    try:
        data = resp.json()
    except (ValueError, TypeError) as exc:
        raise JobRightResolveError(
            f"Non-JSON response from JobRight API for jobId={job_id}: {exc}"
        ) from exc

    # Auth-failure embedded in a 200 response (observed error codes)
    if data.get("errorCode") in (10001, 10002, 40100, 40101):
        raise JobRightAuthError(
            f"JobRight API errorCode={data.get('errorCode')} for jobId={job_id} "
            "— session rejected. Re-export JOBRIGHT_SESSION_ID with a fresh cookie."
        )

    if not data.get("success"):
        # success:false with no auth error = job not found / soft error
        return None

    try:
        job_result = data["result"]["jobDetail"]["jobResult"]
    except (KeyError, TypeError):
        return None

    # Prefer originalUrl (the raw upstream ATS URL), fall back to applyLink
    raw_url = (job_result.get("originalUrl") or "").strip()
    if not raw_url:
        raw_url = (job_result.get("applyLink") or "").strip()
    if not raw_url:
        return None

    # Guard: if the resolved URL is still a jobright.ai wrapper, the API didn't
    # give us a real URL (shouldn't happen when authed, but be defensive).
    if "jobright.ai" in raw_url:
        return None

    return strip_utm_params(raw_url)


# ── batch driver ───────────────────────────────────────────────────────────────

def _backup_db(db_path: Path) -> Path:
    """Create a timestamped backup of tracker.db before any writes."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = db_path.parent / f"tracker.db.bak.jobright-resolve-{stamp}"
    shutil.copy2(db_path, bak)
    print(f"[jobright-resolve] DB backed up → {bak}")
    return bak


def _eligible_rows(conn: sqlite3.Connection, limit: Optional[int] = None) -> list:
    """Select rows eligible for apply-URL resolution."""
    conn.row_factory = sqlite3.Row
    q = """
        SELECT id, source_key, company, role, app_url
        FROM roles
        WHERE source_key LIKE 'jobright:%'
          AND status = 'manual-apply'
          AND app_url LIKE 'https://jobright.ai/%'
        ORDER BY id ASC
    """
    if limit is not None:
        q += f" LIMIT {limit}"
    cur = conn.execute(q)
    return [dict(r) for r in cur.fetchall()]


def _extract_job_id(source_key: str) -> Optional[str]:
    """Extract jobId from 'jobright:<jobId>' source_key."""
    if source_key and source_key.startswith("jobright:"):
        return source_key[len("jobright:"):]
    return None


def run_batch(
    session_id: str,
    limit: Optional[int] = None,
    dry_run: bool = False,
    db_path: Optional[Path] = None,
) -> dict:
    """Run the batch resolver.  Returns a stats summary dict.

    Args:
        session_id: The JobRight SESSION_ID cookie value.
        limit: Max rows to process (None = all eligible).
        dry_run: If True, print what WOULD change without writing to DB.
        db_path: Path to tracker.db (defaults to the canonical location).
    """
    db_path = db_path or DB_PATH
    if not db_path.exists():
        raise FileNotFoundError(f"tracker.db not found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    rows = _eligible_rows(conn, limit=limit)
    conn.close()

    print(f"[jobright-resolve] Eligible rows: {len(rows)}")
    if not rows:
        print("[jobright-resolve] Nothing to resolve.")
        return {
            "eligible": 0, "resolved_auto": 0, "resolved_manual": 0,
            "failed": 0, "skipped": 0, "errors": [],
        }

    if not dry_run:
        _backup_db(db_path)

    stats: dict = {
        "eligible": len(rows),
        "resolved_auto": 0,    # ATS known → status set to ''
        "resolved_manual": 0,  # ATS unknown → url updated, status stays 'manual-apply'
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    conn = sqlite3.connect(str(db_path))

    for row in rows:
        role_id = row["id"]
        source_key = row["source_key"]
        job_id = _extract_job_id(source_key)
        if not job_id:
            print(f"  [skip] id={role_id}: malformed source_key={source_key!r}")
            stats["skipped"] += 1
            continue

        print(f"  [resolve] id={role_id} jobId={job_id} ({row['company']} — {row['role']})")

        try:
            real_url = resolve_apply_url(job_id, session_id)
        except JobRightAuthError as exc:
            print(f"  [AUTH-FAIL] {exc}", file=sys.stderr)
            print(
                "[jobright-resolve] Aborting: session expired — "
                "set a fresh JOBRIGHT_SESSION_ID.",
                file=sys.stderr,
            )
            conn.close()
            stats["errors"].append({"id": role_id, "error": "auth-fail", "detail": str(exc)})
            return stats
        except JobRightResolveError as exc:
            print(f"  [error] id={role_id}: {exc}", file=sys.stderr)
            stats["failed"] += 1
            stats["errors"].append({"id": role_id, "error": "resolve-error", "detail": str(exc)})
            continue

        if not real_url:
            print(f"  [no-url] id={role_id}: API returned no URL (job may be removed)")
            stats["failed"] += 1
            continue

        ats = classify_ats(real_url)
        if ats != "unknown":
            new_status = ""   # enters the auto-submit burndown queue
            label = f"ATS={ats} → status='' (queued for auto-submit)"
        else:
            new_status = "manual-apply"   # keep manual, but real URL for review
            label = f"ATS=unknown → url updated, stays manual-apply"

        print(f"    → {real_url}")
        print(f"    → {label}")

        if dry_run:
            print(
                f"    [dry-run] WOULD UPDATE id={role_id}: "
                f"app_url={real_url!r} status={new_status!r}"
            )
            if ats != "unknown":
                stats["resolved_auto"] += 1
            else:
                stats["resolved_manual"] += 1
            continue

        # Commit to DB
        conn.execute(
            "UPDATE roles SET app_url=?, status=? WHERE id=?",
            (real_url, new_status, role_id),
        )
        conn.commit()

        if ats != "unknown":
            stats["resolved_auto"] += 1
        else:
            stats["resolved_manual"] += 1

    conn.close()
    return stats


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def _main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Resolve JobRight wrapper app_urls to real ATS apply URLs.\n"
            "Requires JOBRIGHT_SESSION_ID env var or .jobright-session file."
        )
    )
    ap.add_argument(
        "--limit", type=int, default=None,
        help="Max number of rows to resolve (default: all eligible)",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print what WOULD change without writing to tracker.db",
    )
    ap.add_argument(
        "--job-id", type=str, default=None,
        help="Resolve a single jobId (24-hex) and print the result (no DB writes)",
    )
    ap.add_argument(
        "--db", type=str, default=None,
        help=f"Path to tracker.db (default: {DB_PATH})",
    )
    args = ap.parse_args()

    session_id = load_session_id()
    if not session_id:
        print(
            "[jobright-resolve] ERROR: No SESSION_ID available.\n"
            "\n"
            "  Option 1 — env var:\n"
            "    export JOBRIGHT_SESSION_ID='<your-session-id-value>'\n"
            "\n"
            f"  Option 2 — file (gitignored):\n"
            f"    echo '<value>' > {SESSION_FILE}\n"
            "\n"
            "  To get your SESSION_ID:\n"
            "    Log into jobright.ai → DevTools → Application → Cookies → SESSION_ID\n"
            "\n"
            "Exiting cleanly (no changes made).",
            file=sys.stderr,
        )
        sys.exit(0)   # clean exit — no cookie is the expected state during build

    db_path = Path(args.db) if args.db else DB_PATH

    # ── single-job mode ─────────────────────────────────────────────────────
    if args.job_id:
        try:
            real_url = resolve_apply_url(args.job_id, session_id)
        except JobRightAuthError as exc:
            print(f"[AUTH-FAIL] {exc}", file=sys.stderr)
            sys.exit(2)
        except JobRightResolveError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            sys.exit(1)

        if real_url:
            ats = classify_ats(real_url)
            print(f"jobId={args.job_id}")
            print(f"  resolved → {real_url}")
            print(f"  ATS      = {ats}")
            print(f"  queue    = {'auto-submit' if ats != 'unknown' else 'manual-apply'}")
        else:
            print(
                f"[no-url] jobId={args.job_id}: API returned no URL "
                "(job may be removed or not yet indexed)"
            )
        return

    # ── batch mode ──────────────────────────────────────────────────────────
    if args.dry_run:
        print("[jobright-resolve] DRY-RUN mode — no writes to tracker.db")

    try:
        stats = run_batch(
            session_id=session_id,
            limit=args.limit,
            dry_run=args.dry_run,
            db_path=db_path,
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"\n[jobright-resolve] Done — "
        f"eligible={stats['eligible']} "
        f"resolved_auto={stats['resolved_auto']} "
        f"resolved_manual={stats['resolved_manual']} "
        f"failed={stats['failed']} "
        f"skipped={stats.get('skipped', 0)}"
    )
    if args.dry_run:
        print("[jobright-resolve] DRY-RUN — nothing was written.")


if __name__ == "__main__":
    _main()
