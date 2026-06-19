"""LinkedIn → ATS resolver.

Goal (per BACKLOG.md 2026-05-23 P1): for each LinkedIn-discovered row in
tracker.db, resolve the off-site ATS URL so it can flow through the normal
auto-apply pipeline (greenhouse/ashby/lever/workday adapters).

Reality (2026-05-23): the anonymous LinkedIn surface DOES NOT expose the
off-site apply URL. We probed extensively:

- `/jobs/view/<id>` page (browser-rendered): the "Apply" button is wrapped
  in a `contextual-sign-in-modal`; the actual off-site URL is loaded only
  after authentication. The page text contains the strings
  `apply-link-offsite` / `apply-link-onsite` (signal of off-site vs Easy
  Apply) but NO URL. Anti-bot fingerprinting fires (`uc=scraping` in
  li.protechts.net beacon).
- `/jobs-guest/jobs/api/jobPosting/<id>` (the endpoint the static adapter
  uses): same — exposes the offsite/onsite signal but no URL.
- Clicking the Apply button anonymously: dispatches the sign-in modal,
  no popup, no redirect, no URL leak.
- Tried alternate endpoints (`/apply`, `/applyExternal`, `/applyOffsite`,
  `/applyRedirect`): all 404.

Resolution requires either:
1. LinkedIn auth cookies (out of scope — anonymous-only per task rules)
2. Paid scraping API (money decision — escalate to Cyrus)
3. Click-through with auth session (same as #1)

**What this script DOES do as a fallback:**

Classify each LinkedIn row by whether it's `apply-link-offsite` (external
ATS exists, just hidden behind LinkedIn auth) vs `apply-link-onsite` (Easy
Apply only — there is NO external URL, the application lives entirely
inside LinkedIn and is fundamentally unreachable without LinkedIn auth).

Updates:
- Easy-Apply-only rows: set `status='skip'`, `flags='linkedin-easy-apply'`,
  `cyrus_notes='Easy Apply only - no external URL exists; needs LinkedIn auth'`.
  These are NOT recoverable without LinkedIn auth.
- Offsite rows: set `flags='linkedin-offsite-unresolved'`,
  `cyrus_notes='Off-site ATS exists but URL hidden behind LinkedIn auth wall'`.
  These ARE recoverable if/when we get a LinkedIn auth path.
- Failed fetches: leave row untouched.

Run:
  .venv/bin/python linkedin_ats_resolver.py            # full run
  .venv/bin/python linkedin_ats_resolver.py --limit 50 # probe
  .venv/bin/python linkedin_ats_resolver.py --dry-run  # no DB writes
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tracker_db import connect, today  # noqa: E402

DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/144.0.0.0 Safari/537.36")

# Rate limit between LinkedIn fetches (seconds). LinkedIn aggressively flags scraping.
RATE_LIMIT_SEC = 1.6

# 429 backoff
MAX_429_RETRIES = 3

OFFSITE_RX = re.compile(r"apply-link-offsite|apply-button__offsite", re.I)
ONSITE_RX = re.compile(r"apply-link-onsite", re.I)
# ATS URL patterns (same as adapters/linkedin.py)
ATS_PATTERNS = [
    ("greenhouse",
     re.compile(r"https?://(?:boards|job-boards)\.greenhouse\.io/[^\s\"'<>\\]+", re.I)),
    ("greenhouse_iframe",
     re.compile(r"https?://[a-z0-9.\-]+/careers?/jobs?/[0-9]+\?gh_jid=\d+", re.I)),
    ("ashby",
     re.compile(r"https?://jobs\.ashbyhq\.com/[^\s\"'<>\\]+", re.I)),
    ("lever",
     re.compile(r"https?://jobs\.lever\.co/[^\s\"'<>\\]+", re.I)),
    ("workday",
     re.compile(r"https?://[a-z0-9.\-]*myworkdayjobs\.com/[^\s\"'<>\\]+", re.I)),
    ("smartrecruiters",
     re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/[^\s\"'<>\\]+", re.I)),
]


def extract_job_id(url: str, source_key: str) -> Optional[str]:
    """Pull job id from source_key (preferred) or URL fallback."""
    if source_key and source_key.startswith("linkedin:"):
        rest = source_key[len("linkedin:"):]
        if rest.isdigit():
            return rest
    m = re.search(r"/jobs/view/[^?]*?-(\d{8,})", url or "")
    if m:
        return m.group(1)
    m = re.search(r"(\d{9,})", url or "")
    return m.group(1) if m else None


def classify_page(html: str) -> tuple[str, Optional[tuple[str, str]]]:
    """Return ('offsite'|'onsite'|'unknown', resolved_ats_or_None).

    resolved_ats_or_None = (ats_name, ats_url) if a real external URL is
    embedded in the HTML, else None.
    """
    # First check: did we find a real external URL? (almost never happens
    # anonymously, but if LinkedIn ever changes their mind we'll catch it)
    for ats_name, pat in ATS_PATTERNS:
        m = pat.search(html)
        if m:
            return ("resolved", (ats_name, m.group(0).rstrip("\")'<>")))
    # Otherwise check the offsite/onsite signal
    if OFFSITE_RX.search(html):
        return ("offsite", None)
    if ONSITE_RX.search(html):
        return ("onsite", None)
    return ("unknown", None)


def run(limit: Optional[int] = None, dry_run: bool = False, verbose: bool = False, all_open_linkedin: bool = False) -> dict:
    conn = connect()
    cur = conn.cursor()
    if all_open_linkedin:
        # Broader: every open + unapplied row whose app_url points at linkedin.com,
        # regardless of source_key shape or flags. Matches 2026-05-25 burndown intent.
        rows = cur.execute(
            """SELECT id, source_key, company, role, jd_url, app_url, status, flags
               FROM roles
               WHERE (status IS NULL OR status = '')
                 AND applied_by IS NULL
                 AND app_url LIKE '%linkedin.com%'
               ORDER BY id"""
        ).fetchall()
    else:
        rows = cur.execute(
            """SELECT id, source_key, company, role, jd_url, app_url, status, flags
               FROM roles
               WHERE source_key LIKE 'linkedin:%'
                 AND (status IS NULL OR status = '' OR status NOT IN ('closed','skip','rejected'))
                 AND (flags LIKE '%manual-apply%' OR flags IS NULL)
               ORDER BY id"""
        ).fetchall()
    print(f"[resolver] {len(rows)} candidate LinkedIn rows", file=sys.stderr)
    if limit:
        rows = rows[:limit]
        print(f"[resolver] limited to {len(rows)}", file=sys.stderr)

    stats = {
        "scanned": 0,
        "fetch_failed": 0,
        "resolved": 0,            # actual external URL extracted (rare/zero)
        "offsite_unresolved": 0,  # external exists but URL hidden behind auth
        "easy_apply": 0,
        "unknown": 0,
        "deduped": 0,
        "ats_breakdown": {},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Pre-build dedup helper: (norm_company, norm_title) -> existing curated row id
    sys.path.insert(0, str(HERE / "adapters"))
    from linkedin import _norm_company, _norm_title  # noqa: E402

    curated_idx: dict[tuple[str, str], int] = {}
    for r in cur.execute(
        """SELECT id, company, role, source_key FROM roles
           WHERE source_key NOT LIKE 'linkedin:%' AND source_key IS NOT NULL"""
    ).fetchall():
        curated_idx.setdefault((_norm_company(r[1]), _norm_title(r[2])), r[0])

    stamp = today()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        for i, row in enumerate(rows):
            rid = row["id"]
            sk = row["source_key"]
            url = row["app_url"] or row["jd_url"] or ""
            jid = extract_job_id(url, sk)
            if not jid:
                if verbose:
                    print(f"  [{rid}] no job id from sk={sk!r} url={url!r}", file=sys.stderr)
                stats["fetch_failed"] += 1
                continue

            stats["scanned"] += 1
            detail_url = DETAIL_URL.format(job_id=jid)
            html = None
            for attempt in range(MAX_429_RETRIES + 1):
                try:
                    resp = page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
                    if resp and resp.status == 429:
                        wait = 5 * (attempt + 1)
                        if verbose:
                            print(f"  [{rid}] 429, sleeping {wait}s", file=sys.stderr)
                        time.sleep(wait); continue
                    if not resp or resp.status != 200:
                        if verbose:
                            print(f"  [{rid}] HTTP {resp.status if resp else '?'}", file=sys.stderr)
                        break
                    page.wait_for_timeout(300)
                    html = page.content()
                    break
                except PWTimeoutError:
                    if verbose:
                        print(f"  [{rid}] timeout attempt {attempt}", file=sys.stderr)
                    continue
                except Exception as e:
                    if verbose:
                        print(f"  [{rid}] err {e}", file=sys.stderr)
                    break

            if not html:
                stats["fetch_failed"] += 1
                time.sleep(RATE_LIMIT_SEC)
                continue

            kind, resolved = classify_page(html)
            new_flags = None
            new_status = None
            new_notes = None
            new_app_url = None
            new_source_key = None

            if resolved:
                ats_name, ats_url = resolved
                stats["resolved"] += 1
                stats["ats_breakdown"][ats_name] = stats["ats_breakdown"].get(ats_name, 0) + 1
                # Dedup check: does (company, title) already exist as a curated row?
                ct = (_norm_company(row["company"]), _norm_title(row["role"]))
                if ct in curated_idx:
                    # Close this LinkedIn row as deduped
                    new_status = "closed"
                    new_notes = f"auto: deduped to curated ATS row #{curated_idx[ct]} (resolved to {ats_name})"
                    new_flags = f"linkedin-resolved-deduped:{ats_name}"
                    stats["deduped"] += 1
                    if verbose:
                        print(f"  [{rid}] RESOLVED+DEDUPED -> {ats_name} (curated row #{curated_idx[ct]})", file=sys.stderr)
                else:
                    new_app_url = ats_url
                    new_flags = f"linkedin-resolved:{ats_name}"
                    new_source_key = f"{ats_name}:linkedin:{jid}"
                    # Mark for normal ATS dispatch
                    if verbose:
                        print(f"  [{rid}] RESOLVED -> {ats_name} {ats_url[:80]}", file=sys.stderr)
            elif kind == "offsite":
                stats["offsite_unresolved"] += 1
                # Preserve existing posted: prefix in flags if present
                existing = row["flags"] or ""
                posted_prefix = ""
                m = re.match(r"(posted:\d{4}-\d{2}-\d{2} )", existing)
                if m:
                    posted_prefix = m.group(1)
                new_flags = f"{posted_prefix}linkedin-offsite-unresolved"
                new_notes = "Off-site ATS exists but URL hidden behind LinkedIn auth wall (anonymous resolver can't see it). Will retry when auth/paid-resolver path lands."
            elif kind == "onsite":
                stats["easy_apply"] += 1
                new_status = "skip"
                existing = row["flags"] or ""
                posted_prefix = ""
                m = re.match(r"(posted:\d{4}-\d{2}-\d{2} )", existing)
                if m:
                    posted_prefix = m.group(1)
                new_flags = f"{posted_prefix}linkedin-easy-apply"
                new_notes = "Easy Apply only - no external URL exists. Application lives inside LinkedIn; requires LinkedIn auth + browser flow."
            else:
                stats["unknown"] += 1
                if verbose:
                    print(f"  [{rid}] unknown classification (no offsite/onsite signal)", file=sys.stderr)

            if not dry_run and (new_flags or new_status or new_notes or new_app_url or new_source_key):
                # Build dynamic UPDATE
                sets = ["last_seen = ?"]
                vals = [stamp]
                if new_flags is not None:
                    sets.append("flags = ?"); vals.append(new_flags)
                if new_status is not None:
                    sets.append("status = ?"); vals.append(new_status)
                if new_notes is not None:
                    sets.append("agent_notes = ?"); vals.append(new_notes)
                if new_app_url is not None:
                    sets.append("app_url = ?"); vals.append(new_app_url)
                if new_source_key is not None:
                    # Check collision first
                    coll = cur.execute(
                        "SELECT id FROM roles WHERE source_key = ? AND id != ?",
                        (new_source_key, rid),
                    ).fetchone()
                    if coll:
                        # very rare — leave source_key alone, just update other fields
                        if verbose:
                            print(f"  [{rid}] source_key {new_source_key} collides w/ {coll[0]}; keeping original", file=sys.stderr)
                    else:
                        sets.append("source_key = ?"); vals.append(new_source_key)
                vals.append(rid)
                cur.execute(f"UPDATE roles SET {', '.join(sets)} WHERE id = ?", vals)

            # Commit every 25 rows so a crash doesn't lose everything
            if (i + 1) % 25 == 0:
                if not dry_run:
                    conn.commit()
                if verbose or (i + 1) % 50 == 0:
                    print(f"  [progress] {i+1}/{len(rows)} scanned={stats['scanned']} "
                          f"resolved={stats['resolved']} offsite={stats['offsite_unresolved']} "
                          f"easy={stats['easy_apply']} unknown={stats['unknown']} fail={stats['fetch_failed']}",
                          file=sys.stderr)

            time.sleep(RATE_LIMIT_SEC)

        browser.close()

    if not dry_run:
        conn.commit()
    conn.close()

    stats["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Limit row count (for probes)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write to tracker.db")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--all-open-linkedin", action="store_true",
                    help="Broaden query: every open+unapplied row whose app_url has linkedin.com")
    args = ap.parse_args()
    stats = run(limit=args.limit, dry_run=args.dry_run, verbose=args.verbose,
                all_open_linkedin=args.all_open_linkedin)
    print("\n=== LinkedIn ATS Resolver Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
