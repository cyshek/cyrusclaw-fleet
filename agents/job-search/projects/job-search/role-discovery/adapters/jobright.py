"""JobRight.ai public fresh-roles discovery adapter (DISCOVERY-ONLY).

Harvests jobright.ai's PUBLIC, unauthenticated `/remote-jobs/<category>` pages.
Each page is a Next.js document whose `<script id="__NEXT_DATA__">` embeds
`props.pageProps.defaultData` = ~30 fully-populated, newest-first job objects.
No login / cookie required.

=== DISCOVERY-ONLY (read this) ===
Every public listing's `applyLink` is a `https://jobright.ai/jobs/info/<id>`
WRAPPER, never a direct ATS URL (100% of sampled rows). The real ATS URL sits
behind JobRight's authenticated `/swan/*` API (401 anon) and is OUT OF SCOPE
for this adapter. Therefore rows ingested here are a FRESHNESS / DISCOVERY
signal only — they are NOT auto-submittable. They are tagged
`manual-apply` + `discovery-only` by `tracker_merger` (jobright is in the
discovery-only source set there) so the auto-submit / burndown queue never
picks them up. See spike: projects/job-search/JOBRIGHT-SPIKE-2026-06-11.md.

Field map (per item):
  jobResult.jobId               -> 24-hex Mongo ObjectId (stable, used in source_key)
  jobResult.jobTitle            -> title
  companyResult.companyName     -> company  (NOTE: jobResult.companyName is EMPTY)
  jobResult.jobLocation         -> location
  jobResult.publishTime         -> posted_at (ISO UTC 'YYYY-MM-DD HH:MM:SS'); date part preserved
  jobResult.applyLink           -> url (the jobright.ai/jobs/info/<id> wrapper)
  jobResult.minYearsOfExperience-> experience floor (fallback: parse jobSummary)
  jobResult.isRemote/workModel/jobSeniority/h1BStatus/employmentType -> raw metadata

source_key: `jobright:<jobId>` (computed in tracker_merger from the wrapper URL,
mirroring the linkedin:<job_id> precedent) for idempotent dedup.

Smoke test (fast health-check, no DB writes, exits non-zero if 0 roles):
    python adapters/jobright.py --smoke      # canonical, warning-free
Full crawl preview (all categories, prints counts + sample, no DB writes):
    python adapters/jobright.py --full

Politeness: serialized GETs with a small inter-request delay + realistic UA.
Azure DC egress currently gets clean HTTP 200 (no Cloudflare/DataDome), but we
stay polite and back off on 429.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional

import requests

# Make `core` importable when run as module from role-discovery dir
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import (  # noqa: E402
    Role,
    DEFAULT_HEADERS,
    parse_experience,
    strip_html,
)

# Authoritative category slugs, derived from
#   https://jobright.ai/sitemap-remote-jobs.xml
# (enumerated 2026-06-11; the sitemap lists exactly these 12 category landing
# pages and no individual job slugs, so the category-page __NEXT_DATA__ is the
# harvest surface). Refreshable via `python adapters/jobright.py --slugs`.
DEFAULT_CATEGORY_SLUGS = [
    "business-finance-hr-legal",
    "customer-support-success",
    "data-ai",
    "hardware-embedded",
    "healthcare-life-sciences",
    "infrastructure-security",
    "manufacturing-industrial",
    "marketing-growth",
    "product-design",
    "public-sector-education",
    "sales-business-development",
    "software-engineering",
]

CATEGORY_URL = "https://jobright.ai/remote-jobs/{slug}"
SITEMAP_URL = "https://jobright.ai/sitemap-remote-jobs.xml"

# Politeness: serialized GETs, small delay between category fetches.
RATE_LIMIT_SEC = 1.2
MAX_429_RETRIES = 3

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
# 24-hex Mongo ObjectId inside the wrapper applyLink path.
JOBID_RE = re.compile(r"/jobs/info/([0-9a-fA-F]{24})")
SITEMAP_SLUG_RE = re.compile(r"remote-jobs/([a-z0-9-]+)")


# ---------- single shared session w/ rate limit ----------

_session = requests.Session()
_session.headers.update(DEFAULT_HEADERS)
_session.headers["Accept"] = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
)
_last_call_ts = [0.0]


def _throttled_get(url: str, timeout: int = 30) -> requests.Response:
    """GET with serialized rate-limit + 429 backoff."""
    last: Optional[requests.Response] = None
    for attempt in range(MAX_429_RETRIES + 1):
        elapsed = time.time() - _last_call_ts[0]
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        _last_call_ts[0] = time.time()
        try:
            r = _session.get(url, timeout=timeout)
        except requests.RequestException:
            if attempt >= MAX_429_RETRIES:
                raise
            time.sleep(2 ** attempt)
            continue
        last = r
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "0") or "0") or (5 * (attempt + 1))
            time.sleep(wait)
            continue
        return r
    return last  # type: ignore[return-value]


# ---------- parsing ----------

def extract_next_data(html: str) -> Optional[dict]:
    """Pull the __NEXT_DATA__ JSON blob out of a category page. Returns the
    parsed dict, or None if not present / unparseable."""
    if not html:
        return None
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (ValueError, TypeError):
        return None


def _job_id_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    m = JOBID_RE.search(url)
    return m.group(1) if m else None


def parse_jobs(next_data: dict) -> List[Role]:
    """Parse `props.pageProps.defaultData` into Role records.

    Pure / offline — no network. Used by both the live crawl and the unit
    tests (against a saved fixture).
    """
    if not next_data:
        return []
    try:
        items = next_data["props"]["pageProps"].get("defaultData", []) or []
    except (KeyError, TypeError, AttributeError):
        return []

    roles: List[Role] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        jr = it.get("jobResult") or {}
        cr = it.get("companyResult") or {}
        if not isinstance(jr, dict):
            continue

        apply_link = jr.get("applyLink") or ""
        # Strip tracking query so the wrapper URL (and source_key derived from
        # it) is stable across runs.
        clean_url = apply_link.split("?")[0] if apply_link else ""
        job_id = jr.get("jobId") or _job_id_from_url(clean_url)
        if not job_id:
            continue

        title = (jr.get("jobTitle") or "").strip()
        # Company name lives in companyResult.companyName; jobResult.companyName
        # is empty on these public pages (verified 30/30).
        company = (
            (cr.get("companyName") if isinstance(cr, dict) else "")
            or jr.get("companyName")
            or ""
        ).strip()
        if not title or not company:
            continue

        location = (jr.get("jobLocation") or "").strip()
        # publishTime is 'YYYY-MM-DD HH:MM:SS' (UTC). Keep the date for the
        # tracker's posted_on so RECENCY is preserved + queryable.
        publish_time = (jr.get("publishTime") or "").strip()
        posted_date = publish_time[:10] if publish_time else ""

        # Experience: prefer the structured field, fall back to JD-text parse.
        exp = "exp:unstated"
        min_yoe = jr.get("minYearsOfExperience")
        if isinstance(min_yoe, (int, float)) and min_yoe > 0:
            exp = f"exp:{int(min_yoe)}+yrs"
        else:
            summary = jr.get("jobSummary") or ""
            reqs = jr.get("requirements") or []
            if isinstance(reqs, list):
                summary = summary + "\n" + "\n".join(str(x) for x in reqs)
            exp = parse_experience(strip_html(summary)) if summary.strip() else "exp:unstated"

        roles.append(
            Role(
                company=company,
                title=title,
                location=location,
                exp_required=exp,
                # The jobright.ai/jobs/info/<id> WRAPPER. This is intentional:
                # discovery-only, not a direct ATS URL. tracker_merger tags it
                # manual-apply + discovery-only so it never enters the submit
                # queue.
                url=clean_url or f"https://jobright.ai/jobs/info/{job_id}",
                posted_at=posted_date,
                source="jobright",
                raw={
                    "job_id": job_id,
                    "publish_time": publish_time,
                    "publish_time_desc": jr.get("publishTimeDesc"),
                    "is_remote": jr.get("isRemote"),
                    "work_model": jr.get("workModel"),
                    "seniority": jr.get("jobSeniority"),
                    "min_yoe": min_yoe,
                    "h1b_status": jr.get("h1BStatus"),
                    "employment_type": jr.get("employmentType"),
                    "company_size": cr.get("companySize") if isinstance(cr, dict) else None,
                    "company_url": cr.get("companyURL") if isinstance(cr, dict) else None,
                    "company_linkedin": cr.get("companyLinkedinURL") if isinstance(cr, dict) else None,
                    "flags": "manual-apply discovery-only",
                },
            )
        )
    return roles


# ---------- public crawl ----------

def fetch_category(slug: str, verbose: bool = False) -> List[Role]:
    """Fetch + parse one category page. Returns Role list (unfiltered)."""
    url = CATEGORY_URL.format(slug=slug)
    try:
        r = _throttled_get(url)
    except Exception as e:  # network error
        if verbose:
            print(f"  [jobright] err slug={slug!r}: {e}", file=sys.stderr)
        return []
    if r.status_code != 200 or not r.text:
        if verbose:
            print(f"  [jobright] HTTP {r.status_code} slug={slug!r}", file=sys.stderr)
        return []
    data = extract_next_data(r.text)
    if data is None:
        if verbose:
            print(f"  [jobright] no __NEXT_DATA__ slug={slug!r}", file=sys.stderr)
        return []
    roles = parse_jobs(data)
    if verbose:
        newest = roles[0].raw.get("publish_time") if roles else "-"
        print(f"  [jobright] slug={slug!r:30} -> {len(roles):2} roles (newest publishTime={newest})")
    return roles


def crawl(
    slugs: Iterable[str] = DEFAULT_CATEGORY_SLUGS,
    verbose: bool = False,
) -> List[Role]:
    """Crawl all category pages and return a de-duplicated Role list (by jobId).

    Newest-first ordering within each category is preserved; cross-category
    dedupe keeps the first occurrence.
    """
    seen: dict[str, Role] = {}
    for slug in slugs:
        for role in fetch_category(slug, verbose=verbose):
            jid = role.raw.get("job_id")
            if jid and jid not in seen:
                seen[jid] = role
    return list(seen.values())


def fetch_category_slugs_live(verbose: bool = False) -> List[str]:
    """(Maintenance) Re-derive the category slugs from the live sitemap.

    Not used by the crawl (we keep the static list for determinism), but handy
    to detect when JobRight adds/removes a category. Returns [] on failure.
    """
    try:
        r = _throttled_get(SITEMAP_URL)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    slugs = sorted(set(SITEMAP_SLUG_RE.findall(r.text)))
    if verbose:
        print("live sitemap slugs:", slugs)
    return slugs


# ---------- adapter entrypoint (used by run.py) ----------

def fetch(company: str, slug: str, **opts) -> List[Role]:
    """Adapter signature for run.py.

    Treated as a SOURCE (not a single company), mirroring the linkedin adapter.
    companies.yaml entry:

      - name: JobRight
        adapter: jobright
        slug: ""
        # optional: slugs: [product-design, sales-business-development]

    Returns all roles found across the configured category slugs (unfiltered;
    run.py applies the title/exp/US filter, then tracker_merger tags every
    jobright row manual-apply + discovery-only).
    """
    slugs = opts.get("slugs") or DEFAULT_CATEGORY_SLUGS
    return crawl(slugs=slugs, verbose=opts.get("verbose", False))


# ---------- smoke test / health-check ----------

def _smoke(verbose: bool = False) -> int:
    """Fast health-check: live-fetch 1 category, print count + sample, return
    non-zero if zero roles (so a future breakage — page block, parser drift,
    IP-429 — is caught). Read-only: does NOT touch tracker.db."""
    print("=== JobRight adapter smoke test (health-check) ===")
    probe_slug = "product-design"
    print(f"Probing 1 category {probe_slug!r} (read-only, no DB writes)")
    t0 = time.time()
    roles = fetch_category(probe_slug, verbose=verbose)
    dt = time.time() - t0
    print(f"\nTotal roles returned: {len(roles)} in {dt:.1f}s")
    if roles:
        newest = roles[0].raw.get("publish_time")
        print(f"Newest publishTime: {newest}")
        print("\nSample (up to 3):")
        for r in roles[:3]:
            print(f"  {r.company} | {r.title} | {r.location} | posted={r.posted_at} | {r.url}")
    if not roles:
        print(
            "\nFAIL: zero roles from the live category page. Crawl is BROKEN "
            "(page block / IP-429 / parser drift / layout change). Investigate "
            "before relying on JobRight discovery.",
            file=sys.stderr,
        )
        return 1
    print("\nPASS: live category page returned roles, parser is healthy.")
    return 0


def _full(verbose: bool = False) -> None:
    """Full crawl preview across all categories. Prints counts + a sample, no
    DB writes (the weekly pipeline writes via run.py -> tracker_merger)."""
    print("=== JobRight full crawl preview ===")
    print(f"Categories: {len(DEFAULT_CATEGORY_SLUGS)}")
    t0 = time.time()
    roles = crawl(verbose=verbose)
    dt = time.time() - t0
    print(f"\nDiscovered: {len(roles)} unique roles (by jobId) in {dt:.1f}s")
    if roles:
        times = sorted((r.raw.get("publish_time") or "") for r in roles if r.raw.get("publish_time"))
        print(f"publishTime span: {times[0] if times else '-'}  ..  {times[-1] if times else '-'}")
        sample_path = Path("/tmp/jobright_full_sample.json")
        sample_path.write_text(
            json.dumps(
                [{**r.to_dict(), "job_id": r.raw.get("job_id"), "flags": r.raw.get("flags")} for r in roles[:25]],
                indent=2,
            )
        )
        print(f"Sample (first 25) dumped to {sample_path}")


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="Fast health-check: live-fetch 1 category, exit non-zero if zero roles (no DB writes)")
    ap.add_argument("--full", action="store_true",
                    help="Full crawl preview across all categories (no DB writes)")
    ap.add_argument("--slugs", action="store_true",
                    help="Print the category slugs derived from the live sitemap (maintenance)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.slugs:
        print(json.dumps(fetch_category_slugs_live(verbose=True), indent=2))
    elif args.full:
        _full(verbose=args.verbose)
    elif args.smoke:
        sys.exit(_smoke(verbose=args.verbose))
    else:
        roles = crawl(verbose=args.verbose)
        print(json.dumps([{**asdict(r), "raw": r.raw} for r in roles[:5]], indent=2, default=str))
        print(f"\nTotal: {len(roles)}")


if __name__ == "__main__":
    _main()
