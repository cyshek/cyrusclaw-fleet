"""LinkedIn → ATS URL resolver v2 (REAL — not a classifier).

Replaces the v1 "classifier" approach. For each LinkedIn-only row in
tracker.db, attempts the following ladder (stop at first success) to find
the actual ATS apply URL:

    Tactic 1: companies.yaml ATS native search
      - Greenhouse / Lever / Ashby: hit the public job-board JSON API,
        fuzzy-match by title.
      - Workday: POST CXS jobs search with the role title; many tenants
        require session cookies and will 401 — those we treat as
        tactic-failed and fall through.

    Tactic 2: company careers-page scrape
      - GET https://<domain>/careers (and /jobs as fallback), look for
        ATS embed URLs (greenhouse/lever/ashby/workday). For each ATS
        URL on the page, fetch its anchor text / nearest heading and
        fuzzy-match against the LinkedIn role title.

    Tactic 3: free web-search fallback
      - DuckDuckGo HTML + Bing both heavily rate-limit/block scripted
        access from this VM (verified 2026-05-25 — see notes). We try
        anyway with a single best-effort query but expect mostly empty.

    Tactic 4: LinkedIn JD scrape for embedded ATS URL
      - Anonymous LinkedIn jobPosting endpoint historically yields ~0%
        but is cheap; run last.

On success: UPDATE roles SET app_url='<ats-url>' WHERE id=?; append a
resolution note to `agent_notes` (NEVER cyrus_notes).
On failure: append BLOCKED line to agent_notes.

CLI:
    .venv/bin/python linkedin_ats_resolver_v2.py --dry-run --limit 5
    .venv/bin/python linkedin_ats_resolver_v2.py --limit 20
    .venv/bin/python linkedin_ats_resolver_v2.py --all --workers 4
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests
import yaml

# Make sibling modules importable
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "adapters"))

from tracker_db import DB_PATH  # noqa: E402

ROOT = HERE.parent
COMPANIES_YAML = HERE / "companies.yaml"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

HTTP_TIMEOUT = 20

# ATS host regexes used to find apply URLs in HTML.
ATS_PATTERNS = [
    ("greenhouse",      re.compile(r"https?://(?:boards|job-boards)\.greenhouse\.io/[A-Za-z0-9._\-/?=&]+", re.I)),
    ("greenhouse_embed",re.compile(r"https?://boards\.greenhouse\.io/embed/job_app\?[A-Za-z0-9=&_\-]+", re.I)),
    ("ashby",           re.compile(r"https?://jobs\.ashbyhq\.com/[A-Za-z0-9._\-/]+", re.I)),
    ("lever",           re.compile(r"https?://jobs\.lever\.co/[A-Za-z0-9._\-/]+", re.I)),
    ("workday",         re.compile(r"https?://[a-z0-9.\-]*myworkdayjobs\.com/[A-Za-z0-9._\-/]+/job/[A-Za-z0-9._\-/]+", re.I)),
    ("smartrecruiters", re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/[A-Za-z0-9._\-/]+", re.I)),
]

# Title fuzzy threshold — token-set Jaccard.
TITLE_MIN_JACCARD = 0.55

_session = requests.Session()
_session.headers.update(DEFAULT_HEADERS)


# ---------- text utils ----------

_TOK_RE = re.compile(r"[A-Za-z0-9]+")
_STOP = {"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "at", "with",
         "by", "as", "is", "it", "be", "remote", "us", "usa", "united", "states",
         "new", "york", "san", "francisco", "ca", "ny", "wa", "tx", "seattle"}


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in _TOK_RE.findall(s or "") if t.lower() not in _STOP and len(t) > 1}


def title_jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def title_coverage(role_title: str, page_title: str) -> float:
    """Fraction of the ROLE title's distinctive tokens present in the page title.
    Asymmetric on purpose: a job page title like 'Omnidian - Senior Product
    Manager, Residential Business' fully covers 'Senior Product Manager'
    (coverage 1.0) even though symmetric jaccard is only 0.5. Used by validation
    so longer/branded ATS page titles don't unfairly fail the match."""
    rt, pt = _tokens(role_title), _tokens(page_title)
    if not rt or not pt:
        return 0.0
    return len(rt & pt) / len(rt)


# ---------- companies.yaml ----------

def _load_companies() -> dict[str, dict]:
    with open(COMPANIES_YAML) as f:
        data = yaml.safe_load(f)
    out = {}
    for c in data.get("companies", []):
        out[c["name"].lower().strip()] = c
    return out


COMPANIES = _load_companies()


# ---------- result type ----------

@dataclass
class Resolution:
    role_id: int
    company: str
    role_title: str
    ats_url: Optional[str] = None
    ats_kind: Optional[str] = None
    tactic: Optional[str] = None  # which tactic succeeded
    matched_title: Optional[str] = None
    jaccard: float = 0.0
    error: Optional[str] = None
    attempted: list[str] = field(default_factory=list)


# ---------- Tactic 1: ATS native search ----------

def _gh_search(slug: str, query: str) -> list[tuple[str, str]]:
    """Return [(title, absolute_url), ...] for greenhouse board `slug`."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = _session.get(url, timeout=HTTP_TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    try:
        jobs = r.json().get("jobs", []) or []
    except Exception:
        return []
    return [(j.get("title", ""), j.get("absolute_url", "")) for j in jobs if j.get("absolute_url")]


def _lever_search(slug: str, query: str) -> list[tuple[str, str]]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = _session.get(url, timeout=HTTP_TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    try:
        jobs = r.json() or []
    except Exception:
        return []
    return [(j.get("text", ""), j.get("hostedUrl", "")) for j in jobs if j.get("hostedUrl")]


def _ashby_search(slug: str, query: str) -> list[tuple[str, str]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = _session.get(url, timeout=HTTP_TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    try:
        jobs = r.json().get("jobs", []) or []
    except Exception:
        return []
    out = []
    for j in jobs:
        title = j.get("title", "")
        url = j.get("jobUrl") or j.get("applyUrl") or ""
        if not url and j.get("id"):
            url = f"https://jobs.ashbyhq.com/{slug}/{j['id']}"
        if url:
            out.append((title, url))
    return out


def _workday_search(host: str, tenant: str, site: str, query: str) -> list[tuple[str, str]]:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query}
    try:
        r = _session.post(
            url,
            json=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Calypso-PageBlocked": "false",
            },
            timeout=HTTP_TIMEOUT,
        )
    except Exception:
        return []
    if r.status_code != 200:
        return []  # 401/404/422 are all common — yaml entry may be stale
    try:
        data = r.json()
    except Exception:
        return []
    out = []
    site_prefix = f"https://{host}/{site}"
    for j in data.get("jobPostings", []) or []:
        title = j.get("title", "")
        ext = j.get("externalPath", "")
        if ext:
            out.append((title, site_prefix + ext))
    return out


def tactic1_companies_yaml(res: Resolution) -> bool:
    res.attempted.append("yaml")
    entry = COMPANIES.get(res.company.lower().strip())
    if not entry:
        return False
    adapter = entry.get("adapter")
    slug = entry.get("slug") or ""
    candidates: list[tuple[str, str]] = []
    try:
        if adapter == "greenhouse" and slug:
            candidates = _gh_search(slug, res.role_title)
        elif adapter == "lever" and slug:
            candidates = _lever_search(slug, res.role_title)
        elif adapter == "ashby" and slug:
            candidates = _ashby_search(slug, res.role_title)
        elif adapter == "workday":
            host = entry.get("host"); tenant = entry.get("tenant"); site = entry.get("site")
            if host and tenant and site:
                candidates = _workday_search(host, tenant, site, res.role_title)
    except Exception as e:
        res.error = f"yaml-tactic err: {e}"
        return False
    if not candidates:
        return False
    # Fuzzy match
    best = max(candidates, key=lambda c: title_jaccard(res.role_title, c[0]))
    j = title_jaccard(res.role_title, best[0])
    if j >= TITLE_MIN_JACCARD:
        res.ats_url = best[1]
        res.ats_kind = adapter
        res.matched_title = best[0]
        res.jaccard = j
        res.tactic = "yaml"
        return True
    return False


# ---------- Tactic 2: company careers page scrape ----------

def _company_domain_guess(company: str) -> list[str]:
    """Return candidate domains for a company name."""
    base = re.sub(r"[^a-z0-9]+", "", company.lower())
    if not base:
        return []
    out = [f"{base}.com", f"{base}.io", f"{base}.ai"]
    # also try first-word
    first = re.sub(r"[^a-z0-9]+", "", company.split()[0].lower())
    if first and first != base:
        out.insert(0, f"{first}.com")
    return out


def _extract_ats_links(html: str) -> list[tuple[str, str]]:
    """Find all ATS URLs in HTML; return (ats_kind, url) list."""
    found = []
    for ats, pat in ATS_PATTERNS:
        for m in pat.finditer(html):
            url = m.group(0).rstrip("\"'<>),.;")
            found.append((ats, url))
    return found


def extract_offsite_ats_from_li_html(html: str) -> Optional[tuple[str, str]]:
    """Given raw LinkedIn guest jobPosting/job-view HTML, return the first real
    offsite ATS (kind, url) pair, or None.

    IMPORTANT (verified 2026-06-03 from this VM's egress IP): the anonymous
    LinkedIn guest endpoints (jobs-guest/jobs/api/jobPosting/<id> AND
    /jobs/view/<id>) serve a SIGN-IN-WALL variant that does NOT expose the
    offsite apply URL — the apply button is replaced by a cold-join/sign-in
    modal, and LinkedIn 429s after ~4 requests. So in practice this returns
    None for live LinkedIn HTML. It is retained because (a) it correctly
    extracts ATS links from any HTML that DOES contain them (e.g. a cached
    page or future un-walled response), and (b) it filters out linkedin.com
    signup/cold-join decoy links. A None here is the EXPECTED outcome for the
    guest endpoint today, not a bug. The reliable resolver is tactic1
    (companies.yaml ATS-API title match)."""
    if not html:
        return None
    for ats, url in _extract_ats_links(html):
        if "linkedin.com" in url:  # skip LinkedIn's own offsite-decoy links
            continue
        return (ats, url)
    return None


def _gh_jobs_index_for_slug(slug: str) -> dict[str, str]:
    """Return {normalized_url: title} for a greenhouse board."""
    out = {}
    for title, url in _gh_search(slug, ""):
        out[url] = title
    return out


def tactic2_careers_page(res: Resolution) -> bool:
    res.attempted.append("careers")
    domains = _company_domain_guess(res.company)
    for domain in domains[:2]:  # cap to first 2 guesses
        for path in ("/careers", "/jobs", "/company/careers", "/about/careers"):
            url = f"https://{domain}{path}"
            try:
                r = _session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            except Exception:
                continue
            if r.status_code != 200 or not r.text:
                continue
            links = _extract_ats_links(r.text)
            if not links:
                continue
            # Try to fuzzy match by inspecting target ATS pages or anchor text.
            # First: if any greenhouse/lever/ashby links exist, fetch the ATS
            # board for the slug and search by title.
            for ats_kind, ats_url in links:
                slug = _slug_from_ats_url(ats_kind, ats_url)
                if not slug:
                    continue
                candidates = []
                if ats_kind in ("greenhouse", "greenhouse_embed"):
                    candidates = _gh_search(slug, res.role_title)
                elif ats_kind == "lever":
                    candidates = _lever_search(slug, res.role_title)
                elif ats_kind == "ashby":
                    candidates = _ashby_search(slug, res.role_title)
                if not candidates:
                    continue
                best = max(candidates, key=lambda c: title_jaccard(res.role_title, c[0]))
                j = title_jaccard(res.role_title, best[0])
                if j >= TITLE_MIN_JACCARD:
                    res.ats_url = best[1]
                    res.ats_kind = ats_kind.replace("_embed", "")
                    res.matched_title = best[0]
                    res.jaccard = j
                    res.tactic = f"careers:{domain}{path}"
                    return True
    return False


_SLUG_RE = {
    "greenhouse":       re.compile(r"greenhouse\.io/([A-Za-z0-9_\-]+)"),
    "greenhouse_embed": re.compile(r"greenhouse\.io/embed/job_app\?for=([A-Za-z0-9_\-]+)"),
    "lever":            re.compile(r"jobs\.lever\.co/([A-Za-z0-9_\-]+)"),
    "ashby":            re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_\-]+)"),
}


def _slug_from_ats_url(ats_kind: str, url: str) -> Optional[str]:
    pat = _SLUG_RE.get(ats_kind)
    if not pat:
        return None
    m = pat.search(url)
    return m.group(1) if m else None


# ---------- Tactic 3: web-search via residential proxy (real) ----------

# Direct DDG/Bing from this VM's datacenter IP returns 202/challenge (verified
# 2026-05-25). Routing the SAME query through the residential proxy
# (RESIDENTIAL_PROXY, the egress 2captcha/li_at use) returns HTTP 200 with real
# results (verified 2026-06-05). So tactic3 is now LIVE when JOBSEARCH_SEARCH_PROXY
# (or RESIDENTIAL_PROXY) is set; otherwise it no-ops cleanly as before.

def _search_proxy() -> Optional[str]:
    raw = (os.environ.get("JOBSEARCH_SEARCH_PROXY")
           or os.environ.get("RESIDENTIAL_PROXY")
           or os.environ.get("PROXY_2CAPTCHA") or "").strip()
    if not raw:
        return None
    # normalize host:port:user:pass -> http://user:pass@host:port for requests
    if "://" in raw:
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, pw = parts
        return f"http://{user}:{pw}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{raw}"
    return f"http://{raw}"


_DDG_HREF_RE = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', re.I)

# Brave Search API (reliable, no IP roulette). Set BRAVE_SEARCH_API_KEY.
# Free "Data for Search" tier = 2,000 q/mo @ 1 q/s. Verified 2026-06-05: the
# top result for '<co> <title> greenhouse lever ashby' is the exact ATS posting.
# Falls back to proxy-scrape (Brave/Startpage HTML) only if no API key is set.
_SEARCH_ENGINES = [
    ("brave",     "https://search.brave.com/search",      "q"),
    ("startpage", "https://www.startpage.com/sp/search",  "query"),
    ("mojeek",    "https://www.mojeek.com/search",         "q"),
]

# Per-engine retry count to ride out throttled residential-proxy IP rotations.
SEARCH_RETRIES = 4

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_MIN_INTERVAL = 1.05  # free tier = 1 q/s; stay just under
_brave_last_call = [0.0]


def _brave_api_key() -> Optional[str]:
    return (os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip() or None


def _brave_api_urls(query: str, key: str) -> list[str]:
    """Query the Brave Search API; return the ranked list of result URLs (or [] on
    failure). Self-throttles to respect the free tier's 1 query/sec limit."""
    wait = _BRAVE_MIN_INTERVAL - (time.time() - _brave_last_call[0])
    if wait > 0:
        time.sleep(wait)
    try:
        r = requests.get(
            BRAVE_API_URL, params={"q": query, "count": 20},
            headers={"Accept": "application/json", "X-Subscription-Token": key},
            timeout=HTTP_TIMEOUT,
        )
    except Exception:
        return []
    finally:
        _brave_last_call[0] = time.time()
    if r.status_code == 429:  # rate-limited: back off once and retry
        time.sleep(1.5)
        try:
            r = requests.get(
                BRAVE_API_URL, params={"q": query, "count": 20},
                headers={"Accept": "application/json", "X-Subscription-Token": key},
                timeout=HTTP_TIMEOUT,
            )
            _brave_last_call[0] = time.time()
        except Exception:
            return []
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    return [x["url"] for x in data.get("web", {}).get("results", []) if x.get("url")]


def _search_html(query: str, proxy: str) -> str:
    """Proxy-scrape fallback (used only when no Brave API key is set). Runs `query`
    against each search engine through the residential proxy until one returns 200
    with ATS links in the body. Returns raw HTML or '' if all fail.

    The residential proxy rotates egress IP per connection and some rotations are
    rate-limited, so we RETRY each engine a few times. NOTE: scraping is FLAKY
    for batch use (Brave 429s the IP after ~5 q, Startpage intermittent) — the
    Brave API path above is strongly preferred.
    """
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    for _name, url, qparam in _SEARCH_ENGINES:
        for _attempt in range(SEARCH_RETRIES):
            try:
                r = requests.get(
                    url, params={qparam: query},
                    headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                    proxies={"http": proxy, "https": proxy}, timeout=HTTP_TIMEOUT,
                )
            except Exception:
                continue
            if r.status_code == 200 and r.text and _extract_ats_links(r.text):
                return r.text
    return ""


def tactic3_websearch(res: Resolution) -> bool:
    res.attempted.append("websearch")
    query = f'{res.company} {res.role_title} apply greenhouse lever ashby workday'
    candidates: list[tuple[str, str]] = []

    key = _brave_api_key()
    if key:
        # Preferred: Brave Search API — reliable, ranked, no IP games.
        for url in _brave_api_urls(query, key):
            candidates.extend(_extract_ats_links(url))
    else:
        # Fallback: flaky proxy-scrape (no-op cleanly if no proxy either).
        proxy = _search_proxy()
        if not proxy:
            return False
        html = _search_html(query, proxy)
        if html:
            candidates = _extract_ats_links(html)

    if not candidates:
        return False
    # Guard against cross-company false positives: the company name should appear
    # in the ATS URL slug (e.g. .../discord, .../omnidian/...). tactic3 only fires
    # after tactic1/2 fail, and the query is company-scoped, but a coverage-based
    # title match alone could otherwise accept a same-titled role at a DIFFERENT
    # company. Require a company-token in the URL when we can derive one.
    co_toks = {t for t in _tokens(res.company) if len(t) > 2}
    seen: set[str] = set()
    for ats_kind, url in candidates:
        if url in seen or "linkedin.com" in url:
            continue
        seen.add(url)
        url_l = url.lower()
        if co_toks and not any(t in url_l for t in co_toks):
            continue  # URL slug doesn't mention the company -> skip
        j = _validate_ats_url(ats_kind, url, res.role_title)
        if j >= TITLE_MIN_JACCARD:
            res.ats_url = url
            res.ats_kind = ats_kind.replace("_embed", "")
            res.jaccard = j
            res.matched_title = res.role_title
            res.tactic = "brave-api" if key else "websearch-proxy"
            return True
    return False


# ---------- Tactic 4: LinkedIn JD scrape ----------

_LI_ID_RE = re.compile(r"/jobs/view/[^/?]*?-(\d{8,})(?:[/?]|$)")


def tactic4_linkedin_jd(res: Resolution, jd_url: str) -> bool:
    res.attempted.append("linkedin")
    m = _LI_ID_RE.search(jd_url or "")
    if not m:
        return False
    jid = m.group(1)
    api = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
    try:
        r = _session.get(api, timeout=HTTP_TIMEOUT)
    except Exception:
        return False
    if r.status_code != 200 or not r.text:
        return False
    links = _extract_ats_links(r.text)
    if not links:
        return False
    # Take the first ATS link; we have no title to match against here, so
    # accept low confidence and rely on validation step.
    ats_kind, ats_url = links[0]
    # Optional: validate by fetching the ATS page and comparing title.
    j = _validate_ats_url(ats_kind, ats_url, res.role_title)
    if j >= TITLE_MIN_JACCARD:
        res.ats_url = ats_url
        res.ats_kind = ats_kind.replace("_embed", "")
        res.jaccard = j
        res.tactic = "linkedin-jd"
        return True
    return False


def _validate_ats_url(ats_kind: str, url: str, expected_title: str) -> float:
    """Fetch the ATS apply page, extract title-ish text, return jaccard.

    Try the residential proxy first when available (some ATS pages soft-block
    datacenter IPs); fall back to the bare default session."""
    text = ""
    proxy = _search_proxy()
    if proxy:
        try:
            rp = requests.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True,
                              headers=DEFAULT_HEADERS,
                              proxies={"http": proxy, "https": proxy})
            if rp.status_code == 200 and rp.text:
                text = rp.text
        except Exception:
            text = ""
    if not text:
        try:
            r = _session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        except Exception:
            return 0.0
        if r.status_code != 200 or not r.text:
            return 0.0
        text = r.text
    # Cheap title extraction
    m = re.search(r"<title[^>]*>([^<]{3,200})</title>", text, re.I)
    page_title = m.group(1) if m else ""
    # also <h1>
    m2 = re.search(r"<h1[^>]*>([^<]{3,200})</h1>", text, re.I)
    if m2:
        page_title += " " + m2.group(1)
    # Accept on EITHER symmetric jaccard OR role-title coverage (asymmetric):
    # branded ATS page titles ("<Co> - <Role>, <Team>") cover the role fully but
    # score low on jaccard. Return the stronger of the two as the confidence.
    j = title_jaccard(expected_title, page_title)
    cov = title_coverage(expected_title, page_title)
    return max(j, cov)


# ---------- main resolve ----------

def resolve_one(role: sqlite3.Row) -> Resolution:
    res = Resolution(
        role_id=role["id"],
        company=role["company"],
        role_title=role["role"],
    )
    try:
        if tactic1_companies_yaml(res):
            return res
        if tactic2_careers_page(res):
            return res
        if tactic3_websearch(res):
            return res
        if tactic4_linkedin_jd(res, role["jd_url"]):
            return res
    except Exception as e:
        res.error = f"unexpected: {e}"
    return res


# ---------- DB ----------

def _fetch_open_rows(conn: sqlite3.Connection, limit: Optional[int], role_ids: Optional[list[int]]):
    sql = (
        "SELECT id, company, role, jd_url, app_url, status, flags, agent_notes "
        "FROM roles WHERE jd_url LIKE '%linkedin.com%' "
        "AND (app_url IS NULL OR app_url='' OR app_url LIKE '%linkedin.com%') "
        "AND status NOT IN ('skip','closed','submitted')"
    )
    params: list = []
    if role_ids:
        sql += f" AND id IN ({','.join('?'*len(role_ids))})"
        params.extend(role_ids)
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql, params).fetchall()


def _append_agent_note(existing: Optional[str], line: str) -> str:
    base = (existing or "").rstrip()
    sep = "\n" if base else ""
    return f"{base}{sep}{line}"


def _apply_resolution(conn: sqlite3.Connection, row: sqlite3.Row, res: Resolution, stamp: str, dry: bool) -> None:
    if res.ats_url:
        note = (
            f"[{stamp}] linkedin-resolver-v2: resolved via {res.tactic}; "
            f"ats={res.ats_kind} jaccard={res.jaccard:.2f} matched={res.matched_title!r}"
        )
        new_notes = _append_agent_note(row["agent_notes"], note)
        if not dry:
            conn.execute(
                "UPDATE roles SET app_url=?, agent_notes=? WHERE id=?",
                (res.ats_url, new_notes, row["id"]),
            )
    else:
        note = (
            f"[{stamp}] linkedin-resolver-v2: BLOCKED tactics={','.join(res.attempted)}"
            + (f" err={res.error}" if res.error else "")
        )
        new_notes = _append_agent_note(row["agent_notes"], note)
        if not dry:
            conn.execute("UPDATE roles SET agent_notes=? WHERE id=?", (new_notes, row["id"]))


# ---------- CLI ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--role-id", type=int, action="append", dest="role_ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON report path")
    args = ap.parse_args()

    if not args.all and not args.limit and not args.role_ids:
        ap.error("specify --limit N, --all, or --role-id ID")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = _fetch_open_rows(conn, args.limit if not args.all else None, args.role_ids)
    print(f"[v2] candidate rows: {len(rows)}; workers={args.workers}; dry={args.dry_run}")

    results: list[Resolution] = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_to_row = {ex.submit(resolve_one, r): r for r in rows}
        for fut in concurrent.futures.as_completed(future_to_row):
            r = future_to_row[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = Resolution(role_id=r["id"], company=r["company"], role_title=r["role"], error=str(e))
            results.append(res)
            status = f"OK[{res.tactic}]" if res.ats_url else "BLOCK"
            print(f"  id={r['id']:4} {r['company'][:25]:25} | {r['role'][:50]:50} | {status} | {res.ats_url or ''}")

    stamp = time.strftime("%Y-%m-%d")
    by_id = {r["id"]: r for r in rows}
    for res in results:
        _apply_resolution(conn, by_id[res.role_id], res, stamp, args.dry_run)
    if not args.dry_run:
        conn.commit()
    conn.close()
    dt = time.time() - t0

    resolved = [r for r in results if r.ats_url]
    blocked = [r for r in results if not r.ats_url]
    by_tactic: dict[str, int] = {}
    for r in resolved:
        by_tactic[r.tactic or "?"] = by_tactic.get(r.tactic or "?", 0) + 1
    print()
    print(f"=== summary === ({dt:.1f}s)")
    print(f"  resolved: {len(resolved)} / {len(results)}  ({100*len(resolved)//max(1,len(results))}%)")
    print(f"  blocked:  {len(blocked)}")
    print(f"  by tactic:")
    for t, n in sorted(by_tactic.items(), key=lambda x: -x[1]):
        print(f"    {t:30} {n}")
    if args.dry_run:
        print("  (DRY RUN — no DB writes)")
    if args.out:
        Path(args.out).write_text(json.dumps([asdict(r) for r in results], indent=2))
        print(f"  wrote report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
