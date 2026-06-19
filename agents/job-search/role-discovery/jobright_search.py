"""JobRight.ai authed search adapter — personalized/company-specific job search.

Uses the authenticated `/swan/recommend/list/jobs` API endpoint with a session
cookie to search for roles by keyword (and optionally company), returning roles
with `publishTime` dates and REAL ATS `originalUrl` values (not wrappers).

This complements the public category-page crawl in `adapters/jobright.py`:
  - Public crawl: ~390 freshest roles across 12 categories, no auth, wrappers only.
  - Authed search: keyword+company targeted, real ATS URLs, personalized ranking.

=== API facts (mapped 2026-06-14) ===
Endpoint: GET /swan/recommend/list/jobs
Auth:      Cookie: SESSION_ID=<value>
Params:    keyword (str), pageSize (int, max=10 per test), pageIndex (int, 0-based)
Response:  {"success":true,"result":{"jobList":[...],"impId":"..."}}
Key field: jobResult.originalUrl — real ATS URL (greenhouse/ashby/lever/workday/etc.)
           *** This is the CRITICAL field the public surface withholds ***
Note:      pageSize >10 still returns 10 (server-side cap); paginate with pageIndex.

=== Session cookie ===
Load precedence (NEVER hardcoded):
  1. Env var JOBRIGHT_SESSION_ID
  2. File projects/job-search/.jobright-session (single line; gitignored)

=== CLI ===
  python jobright_search.py                                  # default: Google roles search
  python jobright_search.py --keyword "product manager"      # custom keyword
  python jobright_search.py --keyword "TPM" --pages 3        # 3 pages of results
  python jobright_search.py --ingest                         # search + insert new into tracker
  python jobright_search.py --dry-run                        # print what would be inserted, no writes
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

import requests

# ── paths ──────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
PROJ_DIR = HERE.parent
DB_PATH = PROJ_DIR / "tracker.db"
SESSION_FILE = PROJ_DIR / ".jobright-session"

# ── API ───────────────────────────────────────────────────────────────────────
SEARCH_URL = "https://jobright.ai/swan/recommend/list/jobs"
PAGE_SIZE = 10           # Server-side cap — larger values still return 10
RATE_LIMIT_SEC = 0.8     # polite inter-request delay
REQUEST_TIMEOUT = 15


# ── exceptions ────────────────────────────────────────────────────────────────
class JobRightAuthError(Exception):
    """Session cookie rejected (401/403) or API returned auth error."""


class JobRightSearchError(Exception):
    """Network error, malformed response, or API error."""


# ── data class ────────────────────────────────────────────────────────────────
@dataclass
class SearchResult:
    """One job from the authed search API."""
    job_id: str
    title: str
    company: str
    location: str
    publish_time: str        # 'YYYY-MM-DD HH:MM:SS' UTC
    original_url: str        # Real ATS URL (the key value this adapter unlocks)
    apply_link: str          # Alias / redirect URL from JobRight
    is_remote: bool
    work_model: str
    seniority: str
    min_yoe: Optional[float]
    employment_type: str
    salary_desc: str
    company_id: Optional[int]
    source_key: str          # 'jobright-search:<jobId>'

    @classmethod
    def from_api_item(cls, item: dict) -> Optional["SearchResult"]:
        """Parse one item from jobList. Returns None if required fields missing."""
        jr = item.get("jobResult") or {}
        cr = item.get("companyResult") or {}
        if not isinstance(jr, dict):
            return None

        job_id = jr.get("jobId") or ""
        if not job_id:
            return None

        title = (jr.get("jobTitle") or "").strip()
        company = (
            (cr.get("companyName") if isinstance(cr, dict) else "")
            or jr.get("companyName")
            or ""
        ).strip()
        if not title or not company:
            return None

        original_url = (jr.get("originalUrl") or "").strip()
        apply_link = (jr.get("applyLink") or "").strip()

        return cls(
            job_id=job_id,
            title=title,
            company=company,
            location=(jr.get("jobLocation") or "").strip(),
            publish_time=(jr.get("publishTime") or "").strip(),
            original_url=original_url,
            apply_link=apply_link,
            is_remote=bool(jr.get("isRemote")),
            work_model=(jr.get("workModel") or "").strip(),
            seniority=(jr.get("jobSeniority") or "").strip(),
            min_yoe=jr.get("minYearsOfExperience"),
            employment_type=(jr.get("employmentType") or "").strip(),
            salary_desc=(jr.get("salaryDesc") or "").strip(),
            company_id=cr.get("companyId") if isinstance(cr, dict) else None,
            source_key=f"jobright-search:{job_id}",
        )


# ── session cookie loading ────────────────────────────────────────────────────
def load_session_cookie() -> str:
    """Load SESSION_ID from env var or .jobright-session file.

    Raises RuntimeError if neither is available.
    Never reads/hardcodes any specific value.
    """
    val = os.environ.get("JOBRIGHT_SESSION_ID", "").strip()
    if val:
        return val
    if SESSION_FILE.exists():
        val = SESSION_FILE.read_text().strip()
        if val:
            return val
    raise RuntimeError(
        "No JobRight session cookie found. "
        "Set JOBRIGHT_SESSION_ID env var or write session value to "
        f"{SESSION_FILE}"
    )


# ── HTTP layer ────────────────────────────────────────────────────────────────
_session_obj: Optional[requests.Session] = None
_last_call_ts: float = 0.0


def _get_http_session(cookie: str) -> requests.Session:
    global _session_obj
    if _session_obj is None:
        _session_obj = requests.Session()
        _session_obj.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://jobright.ai/jobs",
        })
        _session_obj.cookies.set("SESSION_ID", cookie, domain="jobright.ai")
    return _session_obj


def _throttled_get(url: str, params: dict, cookie: str) -> requests.Response:
    """Rate-limited GET with 429 backoff."""
    global _last_call_ts
    sess = _get_http_session(cookie)
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        elapsed = time.time() - _last_call_ts
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        _last_call_ts = time.time()
        try:
            r = sess.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            last_exc = e
            if attempt >= 3:
                raise JobRightSearchError(f"Network error: {e}") from e
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "0") or "0") or (5 * (attempt + 1))
            time.sleep(wait)
            continue
        if r.status_code in (401, 403):
            raise JobRightAuthError(
                f"Session rejected (HTTP {r.status_code}). "
                "The SESSION_ID cookie may be expired — get a fresh one from Cyrus."
            )
        return r
    raise JobRightSearchError(f"Exhausted retries (last exc: {last_exc})")


# ── core search ──────────────────────────────────────────────────────────────
def search(
    keyword: str,
    cookie: str,
    page_index: int = 0,
    page_size: int = PAGE_SIZE,
) -> List[SearchResult]:
    """Single-page search. Returns list of SearchResult (may be empty)."""
    params = {
        "keyword": keyword,
        "pageSize": page_size,
        "pageIndex": page_index,
    }
    r = _throttled_get(SEARCH_URL, params, cookie)
    try:
        data = r.json()
    except ValueError:
        raise JobRightSearchError(
            f"Non-JSON response (HTTP {r.status_code}): {r.text[:200]}"
        )

    if not data.get("success"):
        raise JobRightSearchError(
            f"API error — success=false: errorCode={data.get('errorCode')} "
            f"errorMsg={data.get('errorMsg')!r}"
        )

    job_list = (data.get("result") or {}).get("jobList") or []
    results: List[SearchResult] = []
    for item in job_list:
        sr = SearchResult.from_api_item(item)
        if sr:
            results.append(sr)
    return results


def search_all_pages(
    keyword: str,
    cookie: str,
    max_pages: int = 3,
    page_size: int = PAGE_SIZE,
) -> List[SearchResult]:
    """Paginate through up to `max_pages` result pages, dedup by job_id."""
    seen: dict[str, SearchResult] = {}
    for page_idx in range(max_pages):
        page = search(keyword, cookie, page_index=page_idx, page_size=page_size)
        if not page:
            break  # Empty page — no more results
        for sr in page:
            if sr.job_id not in seen:
                seen[sr.job_id] = sr
        if len(page) < page_size:
            break  # Partial page — last page
    return list(seen.values())


# ── Google-role helper ────────────────────────────────────────────────────────
GOOGLE_KEYWORDS = [
    "Google product manager",
    "Google TPM technical program manager",
    "Google solutions engineer",
]


def search_google_roles(cookie: str, max_pages: int = 2) -> List[SearchResult]:
    """Search for Google-related PM/TPM/SE roles, dedup by job_id, sort publishTime DESC.

    Searches multiple keywords and deduplicates results. Returns combined list
    sorted newest first.
    """
    seen: dict[str, SearchResult] = {}
    for keyword in GOOGLE_KEYWORDS:
        results = search_all_pages(keyword, cookie, max_pages=max_pages)
        for sr in results:
            if sr.job_id not in seen:
                seen[sr.job_id] = sr
    return sorted(seen.values(), key=lambda x: x.publish_time or "", reverse=True)


# ── ATS detection ─────────────────────────────────────────────────────────────
_ATS_AUTO_HOSTS = {
    "greenhouse.io": "greenhouse",
    "ashbyhq.com": "ashby",
    "lever.co": "lever",
    "bamboohr.com": "bamboohr",
    "smartrecruiters.com": "smartrecruiters",
    "workable.com": "workable",
    "ats.rippling.com": "rippling",
}
_WORKDAY_HOST_RE = re.compile(r"https?://[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com/", re.I)


def _detect_ats(url: str) -> Optional[str]:
    """Return ATS name for known auto-submittable hosts, else None."""
    if not url:
        return None
    if _WORKDAY_HOST_RE.search(url):
        return "workday"
    for host, name in _ATS_AUTO_HOSTS.items():
        if host in url:
            return name
    return None


# ── classifier gate ───────────────────────────────────────────────────────────
def _classify_keep(result: SearchResult) -> bool:
    """Mirror jd_llm_classifier.py keyword gates (structural/title only).

    Keeps: PM/TPM/EPM/PgM/APM/Program/Project/Solutions Engineer/Architect/Customer Engineer.
    Skips: Senior/Staff/Lead/Principal/Director/VP/Head titles, pure SWE, FDE, etc.
    Returns True if role should be kept.
    """
    title = result.title.lower()

    # Hard skip: senior/leadership titles (mirrors classifier senior_title_re)
    senior_tokens = [
        "senior", " sr ", "sr.", "staff", "principal", "lead ",
        "director", "vp ", "vice president", "head of",
        "chief", "distinguished", "fellow",
    ]
    for tok in senior_tokens:
        if tok in title:
            return False

    # Skip: pure SWE/engineering titles
    eng_tokens = [
        "software engineer", "swe ", "frontend", "backend",
        "full-stack", "fullstack", "machine learning engineer",
        "ml engineer", "data engineer", "data scientist",
        "infrastructure engineer", "site reliability", "security engineer",
        "mobile engineer", "android engineer", "ios engineer",
    ]
    for tok in eng_tokens:
        if tok in title:
            return False

    # Keep: target roles
    keep_tokens = [
        "product manager", "program manager", "project manager",
        "tpm", "technical program", "epm", "pgm", "apm",
        "solutions engineer", "solutions architect", "customer engineer",
        "sales engineer", "forward deployed",
    ]
    for tok in keep_tokens:
        if tok in title:
            return True

    # Default: keep (let downstream classifier handle it)
    return True


# ── tracker insertion ─────────────────────────────────────────────────────────
def search_jobright(
    keywords: List[str],
    companies: Optional[List[str]] = None,
    cookie: Optional[str] = None,
    max_pages: int = 2,
    verbose: bool = False,
) -> List[SearchResult]:
    """Search multiple keywords, optionally filter by company name, dedup by job_id.

    Parameters
    ----------
    keywords:  list of keyword strings to search
    companies: if provided, only keep results whose company name matches one
               (case-insensitive substring match)
    cookie:    SESSION_ID value; if None, auto-loads from file/env
    max_pages: pages per keyword (each page = 10 results)
    verbose:   print progress

    Returns dedup'd list sorted publishTime DESC.
    """
    if cookie is None:
        cookie = load_session_cookie()

    seen: dict[str, SearchResult] = {}
    for kw in keywords:
        if verbose:
            print(f"  [jobright-search] keyword={kw!r}", file=sys.stderr)
        results = search_all_pages(kw, cookie, max_pages=max_pages)
        for sr in results:
            if sr.job_id not in seen:
                seen[sr.job_id] = sr
        if verbose:
            print(f"    -> {len(results)} results (total seen={len(seen)})", file=sys.stderr)

    all_results = list(seen.values())

    # Optional company filter
    if companies:
        co_lower = [c.lower() for c in companies]
        all_results = [
            sr for sr in all_results
            if any(co in sr.company.lower() for co in co_lower)
        ]

    # Sort newest first
    return sorted(all_results, key=lambda x: x.publish_time or "", reverse=True)


def ingest_to_tracker(
    results: List[SearchResult],
    db_path: Path = DB_PATH,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """Insert new-to-tracker roles from search results into tracker.db.

    Rules:
    - Skip if source_key already in tracker
    - Skip if _classify_keep returns False (senior/pure-SWE filter)
    - ATS URL = originalUrl if it's a real ATS host, else fallback to jobright wrapper
    - ATS-supported roles: status='' (enters burndown queue)
    - Other roles: status='manual-apply'
    - Backs up DB before writing (unless dry_run)

    Returns: {"inserted": N, "skipped_dup": N, "skipped_filter": N}
    """
    stats = {"inserted": 0, "skipped_dup": 0, "skipped_filter": 0}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Get existing source_keys for dedup
        existing = {
            row[0] for row in conn.execute(
                "SELECT source_key FROM roles WHERE source_key LIKE 'jobright-search:%'"
            )
        }
        # Also check for the same jobId in classic jobright source_key
        existing_jobs = {
            row[0] for row in conn.execute(
                "SELECT source_key FROM roles WHERE source_key LIKE 'jobright:%'"
            )
        }
        # Extract jobIds from classic source keys (format: jobright:<jobId>)
        existing_job_ids = {sk.split(":", 1)[1] for sk in existing_jobs if ":" in sk}

        to_insert: List[SearchResult] = []
        for sr in results:
            if sr.source_key in existing:
                stats["skipped_dup"] += 1
                continue
            if sr.job_id in existing_job_ids:
                # Already in tracker from public crawl
                stats["skipped_dup"] += 1
                continue
            if not _classify_keep(sr):
                stats["skipped_filter"] += 1
                if verbose:
                    print(f"  [filter] skip: {sr.company} | {sr.title}")
                continue
            to_insert.append(sr)

        if not to_insert:
            return stats

        if not dry_run:
            # Backup before writes
            ts = int(time.time())
            bak = db_path.parent / f"tracker.db.bak.jobright-search-{ts}"
            shutil.copy2(db_path, bak)

        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        inserted_rows = []

        for sr in to_insert:
            # Determine best URL
            ats_name = _detect_ats(sr.original_url)
            app_url = (
                sr.original_url
                if sr.original_url
                else f"https://jobright.ai/jobs/info/{sr.job_id}"
            )
            jd_url = f"https://jobright.ai/jobs/info/{sr.job_id}"

            # Status: auto-submit queue if recognized ATS, else manual-apply
            status = "" if ats_name else "manual-apply"

            # Level from seniority field
            level = sr.seniority or ""

            # Flags
            flags = (
                f"jobright-search ats:{ats_name}"
                if ats_name
                else "jobright-search manual-apply"
            )

            # Experience
            exp_req = (
                f"exp:{int(sr.min_yoe)}+yrs"
                if sr.min_yoe and sr.min_yoe > 0
                else "exp:unstated"
            )

            posted_on = sr.publish_time[:10] if sr.publish_time else None

            row = (
                sr.source_key,   # source_key
                sr.company,      # company
                sr.title,        # role
                level,           # level
                sr.location,     # loc
                exp_req,         # exp_req
                jd_url,          # jd_url
                app_url,         # app_url
                status,          # status
                flags,           # flags
                None,            # applied_by
                None,            # applied_on
                None,            # cyrus_notes
                "",              # agent_notes
                posted_on,       # posted_on
                now,             # first_seen
                now,             # last_seen
            )
            inserted_rows.append(row)

            if verbose or dry_run:
                action = "DRY-RUN" if dry_run else "INSERT"
                ats_label = ats_name or "manual"
                posted = sr.publish_time[:10] if sr.publish_time else "?"
                print(f"  [{action}] {sr.company} | {sr.title} | {ats_label} | {posted}")

        if not dry_run and inserted_rows:
            conn.executemany(
                """INSERT OR IGNORE INTO roles
                   (source_key, company, role, level, loc, exp_req,
                    jd_url, app_url, status, flags,
                    applied_by, applied_on, cyrus_notes, agent_notes,
                    posted_on, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                inserted_rows,
            )
            conn.commit()

        stats["inserted"] = len(inserted_rows)
        return stats

    finally:
        conn.close()


# ── __main__ ─────────────────────────────────────────────────────────────────
def _main():
    ap = argparse.ArgumentParser(
        description=(
            "JobRight authed search adapter — "
            "fetch personalized job results with real ATS URLs."
        )
    )
    ap.add_argument(
        "--keyword", default=None,
        help="Search keyword (default: runs Google role searches)"
    )
    ap.add_argument(
        "--pages", type=int, default=2,
        help="Max pages to fetch per keyword (default: 2)"
    )
    ap.add_argument(
        "--ingest", action="store_true",
        help="Insert new-to-tracker roles into tracker.db"
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="With --ingest: print what would be inserted, no DB writes"
    )
    ap.add_argument(
        "--limit", type=int, default=20,
        help="Max results to display (default: 20)"
    )
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    try:
        cookie = load_session_cookie()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.keyword:
        print(f"Searching keyword: {args.keyword!r} (max {args.pages} pages)")
        results = search_all_pages(args.keyword, cookie, max_pages=args.pages)
        results.sort(key=lambda x: x.publish_time or "", reverse=True)
    else:
        print("Searching Google roles (PM/TPM/SE)...")
        results = search_google_roles(cookie, max_pages=args.pages)

    print(f"\nTotal results (deduped): {len(results)}")
    print(f"Showing top {min(args.limit, len(results))}:\n")

    for i, sr in enumerate(results[:args.limit], 1):
        ats = _detect_ats(sr.original_url)
        url_label = f"[{ats}]" if ats else "[manual]"
        salary = f" | {sr.salary_desc}" if sr.salary_desc else ""
        posted = sr.publish_time[:10] if sr.publish_time else "?"
        title_short = sr.title[:50]
        print(
            f"{i:2}. {posted:>10}  "
            f"{sr.company:<30}  {title_short:<50}  "
            f"{url_label:<15}{salary}"
        )
        if args.verbose:
            print(f"     URL: {sr.original_url or '(no url)'}")

    if args.ingest:
        prefix = "DRY RUN — " if args.dry_run else ""
        print(f"\n{prefix}Ingesting into tracker.db...")
        stats = ingest_to_tracker(results, dry_run=args.dry_run, verbose=True)
        print(
            f"\nResult: inserted={stats['inserted']} "
            f"skipped_dup={stats['skipped_dup']} "
            f"skipped_filter={stats['skipped_filter']}"
        )
        if stats["inserted"] > 0 and not args.dry_run:
            print(
                "\nTip: run `python jobright_resolve_apply.py` "
                "to resolve any remaining wrappers."
            )


if __name__ == "__main__":
    _main()
