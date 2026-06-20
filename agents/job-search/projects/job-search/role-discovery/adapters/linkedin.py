"""LinkedIn guest jobs-search discovery adapter.

Uses LinkedIn's public guest endpoint (no auth required):
  https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
    ?keywords=<kw>&location=<loc>&f_TPR=r604800&start=<offset>

Crawls a configurable matrix of (keyword × location) combos and emits Role
records with `source` = 'linkedin' and url = the LinkedIn job-view URL.

Best-effort ATS resolution: for each LinkedIn result we fetch the public
jobPosting detail HTML once and look for off-site apply URLs to a known ATS
(greenhouse / ashby / lever / workday / smartrecruiters). If found we rewrite
the URL so downstream auto-apply (`inline_submit.py`) can pick it up.
Otherwise the URL stays as the LinkedIn page and we annotate raw.flags with
'manual-apply' so the merger / consumer can tell.

Rate limit: 1 req/sec serialized. Retries on 429 with exponential backoff.

Smoke test (fast health-check, no DB writes, exits non-zero if 0 roles):
    python adapters/linkedin.py --smoke      # canonical, warning-free
    python -m adapters.linkedin --smoke      # also works; runpy emits a benign
                                             #   'found in sys.modules' RuntimeWarning
                                             #   because adapters/__init__.py eagerly
                                             #   imports this module for REGISTRY.
Full crawl + tracker.db dedup report (heavy ~155s):
    python adapters/linkedin.py --full [--insert]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

# Make `core` importable when run as module from role-discovery dir
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import (  # noqa: E402
    Role,
    DEFAULT_HEADERS,
    is_qualifying_title,
    is_us_location,
    is_qualifying_experience,
    parse_experience,
    strip_html,
)
from staffing_blocklist import is_staffing_firm  # noqa: E402

SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

DEFAULT_KEYWORDS = [
    "product manager",
    "technical program manager",
    "sales engineer",
    "solutions engineer",
    "solutions architect",
    "forward deployed engineer",
]

DEFAULT_LOCATIONS = [
    "United States",
    "San Francisco Bay Area",
    "New York City Metropolitan Area",
    "Seattle, WA",
]

# r604800 = last 7 days. r86400 = last 24h. r2592000 = last 30 days.
DEFAULT_TPR = "r604800"

# How many pages per (kw, loc) combo to try (LinkedIn gives ~10 per page).
MAX_PAGES_PER_COMBO = 4

# Rate limit between any LinkedIn HTTP calls (seconds).
RATE_LIMIT_SEC = 1.1

# Max 429 retries.
MAX_429_RETRIES = 3

# ATS resolution: turning this on costs ~1s per unique job. In practice the
# static guest jobPosting HTML almost NEVER contains the off-site apply URL
# (LinkedIn loads it client-side via JS), so the success rate is near 0.
# Left as opt-in; weekly crawl runs with resolve_ats=False by default.
DEFAULT_RESOLVE_ATS = False

# JobPostingId regex against the LinkedIn URL.
JOB_ID_RE = re.compile(r"/jobs/view/[^/?]*?-(\d{8,})(?:[/?]|$)")
JOB_ID_FALLBACK_RE = re.compile(r"jobPosting:(\d{8,})")

# ATS host signatures we care about.
ATS_PATTERNS = [
    ("greenhouse",         re.compile(r"https?://(?:boards|job-boards)\.greenhouse\.io/[^\s\"'<>]+", re.I)),
    ("greenhouse_iframe",  re.compile(r"https?://[a-z0-9.\-]+/careers?/jobs?/[0-9]+\?gh_jid=\d+", re.I)),
    ("ashby",              re.compile(r"https?://jobs\.ashbyhq\.com/[^\s\"'<>]+", re.I)),
    ("lever",              re.compile(r"https?://jobs\.lever\.co/[^\s\"'<>]+", re.I)),
    ("workday",            re.compile(r"https?://[a-z0-9.\-]*myworkdayjobs\.com/[^\s\"'<>]+", re.I)),
    ("smartrecruiters",    re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/[^\s\"'<>]+", re.I)),
]


# ---------- single shared session w/ rate limit ----------

_session = requests.Session()
_session.headers.update(DEFAULT_HEADERS)
_session.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
_last_call_ts = [0.0]
_detail_cache: dict[str, Optional[tuple[str, str]]] = {}


def _throttled_get(url: str, params: Optional[dict] = None, timeout: int = 25) -> requests.Response:
    """GET with serialized 1.1s rate-limit + 429 backoff."""
    for attempt in range(MAX_429_RETRIES + 1):
        elapsed = time.time() - _last_call_ts[0]
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        _last_call_ts[0] = time.time()
        try:
            r = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= MAX_429_RETRIES:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "0") or "0") or (5 * (attempt + 1))
            time.sleep(wait)
            continue
        return r
    return r  # type: ignore[return-value]


# ---------- card parsing ----------

def _extract_job_id(url: str) -> Optional[str]:
    if not url:
        return None
    m = JOB_ID_RE.search(url)
    if m:
        return m.group(1)
    # Fallback to data-entity-urn embedded
    m2 = JOB_ID_FALLBACK_RE.search(url)
    if m2:
        return m2.group(1)
    # Some hrefs end with -<digits>?... — looser fallback
    m3 = re.search(r"(\d{9,})", url)
    return m3.group(1) if m3 else None


def _parse_search_cards(html: str) -> List[dict]:
    """Return list of dicts with company, title, location, url, posted_at, job_id."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("li")
    out: List[dict] = []
    for li in items:
        card = li.find("div", class_=re.compile(r"base-card"))
        if not card:
            continue
        title_el = card.find(["h3"], class_=re.compile(r"base-search-card__title"))
        company_el = card.find(["h4"], class_=re.compile(r"base-search-card__subtitle"))
        loc_el = card.find(class_=re.compile(r"job-search-card__location"))
        link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
        time_el = card.find("time")

        if not title_el or not link_el:
            continue

        title = title_el.get_text(strip=True)
        company = company_el.get_text(strip=True) if company_el else ""
        location = loc_el.get_text(strip=True) if loc_el else ""
        href = link_el.get("href", "")
        # Strip query string
        clean_url = href.split("?")[0] if href else ""
        # Try datetime attr first, then urn
        posted = ""
        if time_el and time_el.get("datetime"):
            posted = time_el["datetime"][:10]
        job_id = _extract_job_id(href)
        if not job_id:
            urn = card.get("data-entity-urn", "") or ""
            m = JOB_ID_FALLBACK_RE.search(urn)
            if m:
                job_id = m.group(1)
        if not job_id or not title or not company:
            continue
        out.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "url": clean_url or f"https://www.linkedin.com/jobs/view/{job_id}",
            "posted_at": posted,
        })
    return out


# ---------- detail / ATS resolution ----------

def _fetch_detail_and_resolve(job_id: str) -> Optional[tuple[str, str, str]]:
    """Returns (ats_name, ats_url, jd_text) or None if no ATS found.

    Cached by job_id.
    """
    if job_id in _detail_cache:
        cached = _detail_cache[job_id]
        if cached is None:
            return None
        ats_name, ats_url = cached
        return (ats_name, ats_url, "")  # text dropped after caching

    url = DETAIL_URL.format(job_id=job_id)
    try:
        r = _throttled_get(url)
    except Exception:
        _detail_cache[job_id] = None
        return None
    if r.status_code != 200 or not r.text:
        _detail_cache[job_id] = None
        return None
    html = r.text
    # Search ATS patterns in raw HTML (covers both rendered href and JSON-embedded).
    for ats_name, pat in ATS_PATTERNS:
        m = pat.search(html)
        if m:
            ats_url = m.group(0).rstrip("\")'<>")
            _detail_cache[job_id] = (ats_name, ats_url)
            return (ats_name, ats_url, strip_html(html))
    _detail_cache[job_id] = None
    return None


# ---------- public crawl ----------

def crawl(
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
    locations: Iterable[str] = DEFAULT_LOCATIONS,
    tpr: str = DEFAULT_TPR,
    max_pages_per_combo: int = MAX_PAGES_PER_COMBO,
    resolve_ats: bool = DEFAULT_RESOLVE_ATS,
    verbose: bool = False,
) -> List[Role]:
    """Crawl LinkedIn guest search and return Role list (unfiltered)."""
    raw_cards: dict[str, dict] = {}  # job_id -> card
    keywords = list(keywords)
    locations = list(locations)
    for kw in keywords:
        for loc in locations:
            for page in range(max_pages_per_combo):
                params = {
                    "keywords": kw,
                    "location": loc,
                    "f_TPR": tpr,
                    "start": page * 25,
                }
                try:
                    r = _throttled_get(SEARCH_URL, params=params)
                except Exception as e:
                    if verbose:
                        print(f"  [linkedin] err kw={kw!r} loc={loc!r} pg={page}: {e}", file=sys.stderr)
                    break
                if r.status_code != 200:
                    if verbose:
                        print(f"  [linkedin] HTTP {r.status_code} kw={kw!r} loc={loc!r} pg={page}", file=sys.stderr)
                    break
                cards = _parse_search_cards(r.text)
                if not cards:
                    break
                added = 0
                for c in cards:
                    if c["job_id"] not in raw_cards:
                        raw_cards[c["job_id"]] = c
                        added += 1
                if verbose:
                    print(f"  [linkedin] kw={kw!r:35} loc={loc!r:35} pg={page}: {len(cards):2} cards (+{added} new)")
                if added == 0:
                    break

    if verbose:
        print(f"  [linkedin] total unique cards from search: {len(raw_cards)}")

    roles: List[Role] = []
    dropped_staffing = 0
    for job_id, c in raw_cards.items():
        # Drop staffing-firm / recruiter / IT-services postings up front.
        # See `role-discovery/staffing_blocklist.py` for the curated list.
        if is_staffing_firm(c["company"]):
            dropped_staffing += 1
            if verbose:
                print(f"  [linkedin] dropped (staffing-firm): {c['company']} | {c['title']}")
            continue
        ats_name = None
        ats_url = None
        jd_text = ""
        if resolve_ats:
            res = _fetch_detail_and_resolve(job_id)
            if res:
                ats_name, ats_url, jd_text = res
        # Use ATS URL if resolved, else LinkedIn URL
        final_url = ats_url or c["url"]
        exp = parse_experience(jd_text) if jd_text else "exp:unstated"
        flags = "manual-apply" if not ats_name else f"linkedin-resolved:{ats_name}"
        roles.append(Role(
            company=c["company"],
            title=c["title"],
            location=c["location"],
            exp_required=exp,
            url=final_url,
            posted_at=c["posted_at"],
            source=f"linkedin:{ats_name}" if ats_name else "linkedin",
            raw={
                "job_id": job_id,
                "linkedin_url": c["url"],
                "ats": ats_name,
                "flags": flags,
            },
        ))
    if verbose and dropped_staffing:
        print(f"  [linkedin] dropped {dropped_staffing} staffing-firm cards before role build")
    return roles


# ---------- adapter entrypoint (used by run.py) ----------

def fetch(company: str, slug: str, **opts) -> List[Role]:
    """Adapter signature for run.py.

    Treats this entry as a SOURCE rather than a single company. The
    `companies.yaml` entry should be:

      - name: LinkedIn
        adapter: linkedin
        slug: ""
        keywords: [optional list]
        locations: [optional list]
        tpr: r604800
        resolve_ats: true

    Returns all roles found across the keyword × location matrix.
    """
    keywords = opts.get("keywords") or DEFAULT_KEYWORDS
    locations = opts.get("locations") or DEFAULT_LOCATIONS
    tpr = opts.get("tpr") or DEFAULT_TPR
    resolve_ats = opts.get("resolve_ats", DEFAULT_RESOLVE_ATS)
    pages = int(opts.get("max_pages_per_combo", MAX_PAGES_PER_COMBO))
    return crawl(
        keywords=keywords,
        locations=locations,
        tpr=tpr,
        max_pages_per_combo=pages,
        resolve_ats=resolve_ats,
        verbose=opts.get("verbose", False),
    )


# ---------- dedup helpers (used by smoke test + tracker integration) ----------

_TITLE_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm_title(t: str) -> str:
    return _TITLE_NORM_RE.sub(" ", t.lower()).strip()


def _norm_company(c: str) -> str:
    c = c.lower().strip()
    # Strip common noise (mirrors gmail_response_scanner heuristic).
    for noise in (" inc.", " inc", " labs", ".io", ".ai", " technologies", " tech",
                  " platform", " ai", ",", "  "):
        c = c.replace(noise, " ")
    return re.sub(r"\s+", " ", c).strip()


def existing_company_titles(conn) -> set[tuple[str, str]]:
    cur = conn.cursor()
    cur.execute("SELECT company, role FROM roles")
    return {(_norm_company(r[0]), _norm_title(r[1])) for r in cur.fetchall()}


# ---------- smoke test / health-check ----------

def _smoke(verbose: bool = False) -> int:
    """Fast health-check: actually exercise the live guest endpoint, print a
    count + 3-role sample, and return a NON-ZERO exit code if zero roles come
    back (so a real future breakage — endpoint block, parser drift, IP-429 —
    is caught instead of silently passing).

    Read-only: does NOT touch tracker.db. Uses a tiny 2-combo matrix, 1 page
    each, so it finishes in a few seconds rather than the full ~155s crawl.
    For the heavy tracker-dedup variant use `--full`.
    """
    print("=== LinkedIn adapter smoke test (health-check) ===")
    # Tiny matrix: 2 keyword/location combos, 1 page each.
    probes = [
        ("product manager", "United States"),
        ("technical program manager", "San Francisco Bay Area"),
    ]
    print(f"Probing {len(probes)} keyword/location combo(s), 1 page each "
          f"(read-only, no DB writes)")
    t0 = time.time()
    all_roles: List[Role] = []
    per_combo: List[tuple[str, str, int]] = []
    for kw, loc in probes:
        roles = crawl(keywords=[kw], locations=[loc], verbose=verbose,
                      resolve_ats=False, max_pages_per_combo=1)
        per_combo.append((kw, loc, len(roles)))
        all_roles.extend(roles)
    dt = time.time() - t0

    for kw, loc, n in per_combo:
        print(f"  {kw!r:32} @ {loc!r:28} -> {n:3} roles")
    print(f"\nTotal roles returned: {len(all_roles)} in {dt:.1f}s")

    # Sample of 3: company | title | location | url
    print("\nSample (up to 3):")
    for r in all_roles[:3]:
        print(f"  {r.company} | {r.title} | {r.location} | {r.url}")

    if not all_roles:
        print("\nFAIL: zero roles returned from the live guest endpoint. "
              "The crawl is BROKEN (endpoint block / IP-429 / parser drift / "
              "layout change). Investigate before relying on LinkedIn discovery.",
              file=sys.stderr)
        return 1
    print("\nPASS: live guest endpoint returned roles, parser is healthy.")
    return 0


def _smoke_full(insert: bool, verbose: bool) -> None:
    print("=== LinkedIn adapter smoke test ===")
    # Smaller matrix for the smoke test to keep wall-clock reasonable.
    kws = DEFAULT_KEYWORDS
    locs = DEFAULT_LOCATIONS
    print(f"Matrix: {len(kws)} keywords x {len(locs)} locations, {MAX_PAGES_PER_COMBO} pages/combo")
    print(f"Max LinkedIn calls: search={len(kws) * len(locs) * MAX_PAGES_PER_COMBO} + detail per unique job")
    t0 = time.time()
    roles = crawl(keywords=kws, locations=locs, verbose=verbose, resolve_ats=False,
                  max_pages_per_combo=MAX_PAGES_PER_COMBO)
    dt = time.time() - t0
    print(f"\nDiscovered: {len(roles)} raw roles in {dt:.1f}s")
    # Filter
    qual = [r for r in roles
            if is_qualifying_title(r.title)
            and is_qualifying_experience(r.exp_required)
            and is_us_location(r.location)]
    print(f"After title/exp/US filters: {len(qual)}")

    # ATS-resolution breakdown
    by_source: dict[str, int] = {}
    for r in qual:
        by_source[r.source] = by_source.get(r.source, 0) + 1
    print("Source breakdown:")
    for s, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {s:30} {n}")

    # Tracker dedup
    from tracker_db import connect, normalize_url, today  # noqa
    conn = connect()
    existing_ct = existing_company_titles(conn)
    existing_keys = {r[0] for r in conn.execute(
        "SELECT source_key FROM roles WHERE source_key IS NOT NULL"
    ).fetchall()}

    new_rows = 0
    dup_by_company_title = 0
    dup_by_source_key = 0
    inserted_rows = 0
    stamp = today()
    cur = conn.cursor()

    for r in qual:
        ct_key = (_norm_company(r.company), _norm_title(r.title))
        if ct_key in existing_ct:
            dup_by_company_title += 1
            continue
        # source_key for linkedin: stable across runs
        src_key = f"linkedin:{r.raw.get('job_id')}"
        if src_key in existing_keys:
            dup_by_source_key += 1
            continue
        new_rows += 1
        if not insert:
            continue
        cur.execute(
            """INSERT INTO roles
               (source_key, company, role, level, loc, exp_req, jd_url, app_url,
                status, flags, applied_by, applied_on, cyrus_notes,
                posted_on, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (src_key, r.company, r.title, None, r.location, r.exp_required,
             r.raw.get("linkedin_url"), r.url, "",
             r.raw.get("flags") or "manual-apply",
             None, None, None,
             r.posted_at or None, stamp, stamp),
        )
        existing_keys.add(src_key)
        existing_ct.add(ct_key)
        inserted_rows += 1
    if insert:
        conn.commit()
    conn.close()

    print(f"\nDedup vs tracker.db ({len(existing_keys)} existing source_keys, "
          f"{len(existing_ct)} existing (company,title) pairs):")
    print(f"  Skipped (company+title already tracked elsewhere): {dup_by_company_title}")
    print(f"  Skipped (linkedin source_key already inserted):    {dup_by_source_key}")
    print(f"  Would-insert / Inserted:                           {new_rows} / {inserted_rows}")

    # Dump JSON sample
    sample_path = Path("/tmp/linkedin_smoke_sample.json")
    sample_path.write_text(json.dumps(
        [{**r.to_dict(), "flags": r.raw.get("flags"), "ats": r.raw.get("ats")} for r in qual[:25]],
        indent=2,
    ))
    print(f"\nSample (first 25 qualifying) dumped to {sample_path}")


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="Fast health-check: live-fetch a tiny matrix, print count+sample, "
                         "exit non-zero if zero roles (no DB writes)")
    ap.add_argument("--full", action="store_true",
                    help="Full crawl + tracker.db dedup report (heavy, ~155s)")
    ap.add_argument("--insert", action="store_true", help="With --full: also insert into tracker.db")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.full:
        _smoke_full(insert=args.insert, verbose=args.verbose)
    elif args.smoke:
        sys.exit(_smoke(verbose=args.verbose))
    else:
        roles = crawl(verbose=args.verbose)
        print(json.dumps([{**asdict(r), "raw": r.raw} for r in roles[:5]], indent=2, default=str))
        print(f"\nTotal: {len(roles)}")


if __name__ == "__main__":
    _main()
