#!/usr/bin/env python3
"""LinkedIn-stranded brute-force resolver — pure HTTP, no LinkedIn.

For each tracker.db row whose `app_url` is a LinkedIn job page and whose
company has a known ATS (via `_linkedin_stranded_ats_map.json`), this
script queries that company's public board API, fuzzy-matches the row's
title, and rewrites `app_url` (+ `source_key`, + `agent_notes`) to point
at the real ATS posting.

Independence from LinkedIn — LinkedIn is locked out (cookie throttled),
this resolver NEVER fetches a LinkedIn URL.

CLI:
    linkedin_stranded_brute_resolver.py [--limit N] [--apply]
                                        [--max-seconds N] [--role-id ID]
                                        [--per-row-seconds 30]
                                        [--map PATH]
                                        [--dry-run] [--db PATH] [--quiet]

Default is dry-run; pass --apply to commit DB writes.

Selection SQL (only LinkedIn-stranded, unapplied, open, not yet brute-resolved):
    status IN ('','blocked')
    AND (applied_by IS NULL OR applied_by='')
    AND app_url LIKE '%linkedin.com%'
    AND (agent_notes IS NULL OR agent_notes NOT LIKE '%LINKEDIN-BRUTE%')
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DEFAULT_DB = PROJ / "tracker.db"
DEFAULT_MAP = HERE / "_linkedin_stranded_ats_map.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_TIMEOUT = 12

# ---------------------------------------------------------------------------
# Dynamic ATS slug resolution (net-new fallback when the static map has no
# entry for a company). Reuses the proven bulk_discover_slugs probe so we don't
# hand-maintain _linkedin_stranded_ats_map.json forever -- every weekly crawl
# strands fresh LinkedIn rows whose company may have a public GH/Ashby/Lever
# board that simply isn't in the static map yet.
#
# SAFETY: a name->slug probe can collide on the WRONG company (e.g. "Epic"
# resolves to greenhouse/epicgames, but the row is Epic Systems healthcare).
# That is fine here because resolve_one() still runs best_match()'s conservative
# title-guard on whatever board we hand it -- a wrong company whose board lacks
# a matching title yields UNRESOLVED (no DB rewrite), never a false RESOLVED.
# So this fallback can only ADD correct resolutions, not manufacture wrong ones.
_DYNAMIC_CACHE: dict[str, Optional[dict]] = {}


def dynamic_ats_entry(company: str) -> Optional[dict]:
    """Probe a company name for a public GH/Ashby/Lever board and return a
    resolver-compatible ats_entry ({"ats": ..., "slug": ...}) or None.

    Memoized per company name (probing is the expensive part). Import is lazy so
    importing this module never hard-requires bulk_discover_slugs.
    """
    name = (company or "").strip()
    if not name:
        return None
    if name in _DYNAMIC_CACHE:
        return _DYNAMIC_CACHE[name]
    try:
        from bulk_discover_slugs import probe, slug_variants
    except Exception:
        _DYNAMIC_CACHE[name] = None
        return None
    entry: Optional[dict] = None
    for adapter in ("greenhouse", "ashby", "lever"):
        for v in slug_variants(name):
            try:
                hit = probe(adapter, v)
            except Exception:
                hit = None
            if hit:
                entry = {"ats": hit[0], "slug": hit[1], "dynamic": True}
                break
        if entry:
            break
    _DYNAMIC_CACHE[name] = entry
    return entry
DEFAULT_PER_ROW = 30
DEFAULT_MAX_SECONDS = 7200

FUZZY_THRESHOLD = 0.75  # difflib SequenceMatcher ratio cutoff

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_SENIORITY_RX = re.compile(
    r"\b(senior|sr|jr|junior|staff|principal|lead|head|chief|associate|"
    r"i{1,3}|iv|v|founding)\b",
    re.I,
)
_PUNCT_RX = re.compile(r"[^a-z0-9 ]+")
_WS_RX = re.compile(r"\s+")


def normalize_title(s: str) -> str:
    s = (s or "").lower()
    s = _PUNCT_RX.sub(" ", s)
    s = _SENIORITY_RX.sub(" ", s)
    # Common expansions
    s = re.sub(r"\bpm\b", "product manager", s)
    s = re.sub(r"\btpm\b", "technical program manager", s)
    s = re.sub(r"\bse\b", "solutions engineer", s)
    s = re.sub(r"\bsa\b", "solutions architect", s)
    s = re.sub(r"\bfde\b", "forward deployed engineer", s)
    s = _WS_RX.sub(" ", s).strip()
    return s


# Generic role tokens: a title made of ONLY these (after stop/seniority strip)
# is a non-distinctive stub. Two titles may match on a distinctive shared token,
# never on generic role words alone -- this is the guard that stops
# "Product Manager, Crypto" collapsing onto a bare "Product Manager" or
# "Sales Engineer" matching "Sales Manager".
_GENERIC_TOKENS = {
    "product", "program", "project", "manager", "management", "sales",
    "solutions", "solution", "engineer", "engineering", "architect",
    "technical", "associate", "customer", "strategy", "operations",
    "business", "analyst", "specialist", "director", "of", "and", "the",
    "for", "to", "in", "at", "on", "a", "an",
}


def significant_tokens(title: str) -> set[str]:
    """Normalized tokens of length>1 (seniority/abbrev already handled by
    normalize_title)."""
    return {t for t in normalize_title(title).split() if len(t) > 1}


def shared_distinctive_token(a: str, b: str) -> bool:
    """True iff a & b share at least one NON-generic token. The core anti-
    collision guard for the fuzzier overlap tier."""
    da = significant_tokens(a) - _GENERIC_TOKENS
    db = significant_tokens(b) - _GENERIC_TOKENS
    return bool(da & db)


def collision_guard_ok(target: str, candidate: str) -> bool:
    """Anti-collision gate shared by every best_match tier.

    A match is allowed only if EITHER:
      - target & candidate share a distinctive (non-generic) token
        ('Crypto', 'Networking', 'Verse', ...), OR
      - the target title is ENTIRELY generic ('Solutions Engineer',
        'Product Manager') -- it has no distinctive token to require -- AND
        the two titles are structurally the same role: equal after
        normalization, or one normalized title is a whole substring of the
        other (so a region/team SUFFIX is fine: 'Solutions Engineer' vs
        'Solutions Engineer, NAM', but 'Sales Engineer' vs 'Sales Manager'
        is rejected -- neither is a substring of the other).
    This lets legit generic-role variants resolve while still blocking
    generic-word collisions onto a DIFFERENT role.
    """
    if shared_distinctive_token(target, candidate):
        return True
    target_distinct = significant_tokens(target) - _GENERIC_TOKENS
    if target_distinct:
        # target HAS a distinctive token but candidate doesn't share it -> block
        return False
    # target is fully generic: require structural sameness
    na, nb = normalize_title(target), normalize_title(candidate)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def token_overlap(a: str, b: str) -> float:
    """Jaccard overlap of significant tokens (order-independent). Complements
    fuzzy_ratio, which is sequence-order sensitive and so under-scores legit
    reordered variants like 'Solutions Engineer, Cloud' vs
    'Cloud Solutions Engineer'."""
    ta, tb = significant_tokens(a), significant_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def fuzzy_ratio(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def location_overlap(a: str, b: str) -> bool:
    """Coarse: any 4+char alpha token in common (case-insensitive)."""
    if not a or not b:
        return False
    toks_a = {t for t in re.findall(r"[a-z]{4,}", a.lower())}
    toks_b = {t for t in re.findall(r"[a-z]{4,}", b.lower())}
    # Ignore very common location words
    common = {"states", "united", "remote", "area", "metro"}
    return bool((toks_a & toks_b) - common)


def title_substring_match(a: str, b: str) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


def is_linkedin_url(url: str) -> bool:
    if not url:
        return False
    return "linkedin.com" in url.lower()


# ---------------------------------------------------------------------------
# ATS API queries
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
    try:
        return requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    except Exception:
        return None


def http_post_json(url: str, body: dict, timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
    try:
        return requests.post(
            url, json=body,
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
            timeout=timeout,
        )
    except Exception:
        return None


def fetch_greenhouse_jobs(slug: str) -> tuple[list[dict], Optional[str]]:
    r = http_get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not r:
        return [], "network-error"
    if r.status_code != 200:
        return [], f"http-{r.status_code}"
    try:
        data = r.json()
    except Exception:
        return [], "json-error"
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "") if isinstance(j.get("location"), dict) else ""
        out.append({
            "title": j.get("title", ""),
            "location": loc,
            "url": j.get("absolute_url", ""),
            "id": j.get("id"),
        })
    return out, None


def fetch_ashby_jobs(slug: str) -> tuple[list[dict], Optional[str]]:
    r = http_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false")
    if not r:
        return [], "network-error"
    if r.status_code != 200:
        return [], f"http-{r.status_code}"
    try:
        data = r.json()
    except Exception:
        return [], "json-error"
    out = []
    for j in data.get("jobs", []):
        loc = j.get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        out.append({
            "title": j.get("title", ""),
            "location": loc,
            "url": j.get("jobUrl", ""),
            "id": j.get("id"),
        })
    return out, None


def fetch_lever_jobs(slug: str) -> tuple[list[dict], Optional[str]]:
    r = http_get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not r:
        return [], "network-error"
    if r.status_code != 200:
        return [], f"http-{r.status_code}"
    try:
        data = r.json()
    except Exception:
        return [], "json-error"
    out = []
    if isinstance(data, list):
        for j in data:
            cat = j.get("categories") or {}
            loc = cat.get("location") or ""
            out.append({
                "title": j.get("text", ""),
                "location": loc,
                "url": j.get("hostedUrl", ""),
                "id": j.get("id"),
            })
    return out, None


def fetch_workday_jobs(host: str, tenant: str, site: str, search_text: str = "") -> tuple[list[dict], Optional[str]]:
    """Workday paginates 20/page. We pull up to 200 jobs."""
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out = []
    offset = 0
    seen_ext = set()
    site_url_prefix = f"https://{host}/{site}"
    while offset < 200:
        body = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": search_text}
        r = http_post_json(url, body)
        if not r:
            return out, "network-error"
        if r.status_code != 200:
            if not out:
                return out, f"http-{r.status_code}"
            break
        try:
            data = r.json()
        except Exception:
            return out, "json-error"
        jobs = data.get("jobPostings", []) or []
        if not jobs:
            break
        for j in jobs:
            ext = j.get("externalPath") or ""
            if not ext or ext in seen_ext:
                continue
            seen_ext.add(ext)
            out.append({
                "title": j.get("title", ""),
                "location": j.get("locationsText", ""),
                "url": site_url_prefix + ext,
                "id": ext.rsplit("/", 1)[-1] if ext else "",
            })
        total = data.get("total", len(out))
        offset += len(jobs)
        if offset >= total:
            break
    return out, None


def fetch_jobs_for_ats(entry: dict, search_text: str = "") -> tuple[list[dict], Optional[str]]:
    """Dispatch to the right ATS fetcher. Returns (jobs, error)."""
    ats = entry.get("ats")
    if ats == "greenhouse":
        return fetch_greenhouse_jobs(entry["slug"])
    if ats == "ashby":
        return fetch_ashby_jobs(entry["slug"])
    if ats == "lever":
        return fetch_lever_jobs(entry["slug"])
    if ats == "workday":
        return fetch_workday_jobs(entry["host"], entry["tenant"], entry["site"], search_text)
    return [], f"unsupported-ats:{ats}"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def best_match(
    target_title: str, target_loc: str, jobs: list[dict],
    threshold: float = FUZZY_THRESHOLD,
    overlap_threshold: float = 0.7,
) -> tuple[Optional[dict], float, str]:
    """Return (best_job_dict, score, reason).

    Conservative by design -- a false RESOLVED rewrites the apply URL to the
    WRONG job, so every tier requires an anti-collision guard. Tiers (first
    win returns):
      1. fuzzy ratio >= threshold AND (location overlap OR title-substring)
         AND a shared DISTINCTIVE (non-generic) token. The distinctive-token
         clause is NEW (2026-06-11): it stops high-fuzzy generic collisions
         like 'Sales Engineer' vs 'Sales Manager' (share only 'sales') or
         'Product Manager, Crypto' vs a bare 'Product Manager'.
      2. token-overlap (Jaccard on significant tokens) >= overlap_threshold
         AND a shared distinctive token. NEW tier: catches legit REORDERED /
         suffixed variants that sequence-based fuzzy under-scores, e.g.
         'Solutions Engineer, Cloud Platform' vs 'Cloud Solutions Engineer'
         or 'Sr. Technical Solutions Engineer - West' vs
         'Technical Solutions Engineer'. Still collision-safe via the
         distinctive-token requirement.
      3. exact title-substring AND fuzzy >= 0.6 AND a shared distinctive token.
    The seniority strip + PM/TPM/SE/SA/FDE expansion in normalize_title already
    make 'Sr.'=='Senior' and 'PM'=='Product Manager' equivalent before any tier
    runs.
    """
    if not jobs:
        return None, 0.0, "no-jobs"

    candidates = []
    for j in jobs:
        score = fuzzy_ratio(target_title, j.get("title", ""))
        candidates.append((score, j))

    candidates.sort(key=lambda x: -x[0])
    best_score, best_job = candidates[0]

    # Tier 1: high fuzzy + (loc|substring) + collision guard
    if best_score >= threshold:
        loc_ok = location_overlap(target_loc, best_job.get("location", ""))
        title_sub = title_substring_match(target_title, best_job.get("title", ""))
        guard_ok = collision_guard_ok(target_title, best_job.get("title", ""))
        if (loc_ok or title_sub) and guard_ok:
            return best_job, best_score, (
                f"fuzzy>=th({best_score:.2f}) loc={loc_ok} sub={title_sub} guard=1"
            )
        if (loc_ok or title_sub) and not guard_ok:
            return None, best_score, (
                f"fuzzy>=th but generic-only collision (guard failed, "
                f"score={best_score:.2f})"
            )
        return None, best_score, f"fuzzy>=th but no loc/sub guard (score={best_score:.2f})"

    # Tier 2: order-independent token-overlap + collision guard
    best_ov = None
    best_ov_score = 0.0
    for _, j in candidates:
        ov = token_overlap(target_title, j.get("title", ""))
        if ov > best_ov_score and collision_guard_ok(target_title, j.get("title", "")):
            best_ov_score = ov
            best_ov = j
    if best_ov is not None and best_ov_score >= overlap_threshold:
        return best_ov, best_ov_score, f"token-overlap({best_ov_score:.2f}) guard=1"

    # Tier 3: exact title substring with looser fuzzy, still collision-guarded
    for score, j in candidates:
        if (score >= 0.6
                and title_substring_match(target_title, j.get("title", ""))
                and collision_guard_ok(target_title, j.get("title", ""))):
            return j, score, f"title-substring (score={score:.2f}) guard=1"

    return None, best_score, f"no-match (best={best_score:.2f})"


# ---------------------------------------------------------------------------
# Source key derivation (mirrors linkedin_resolver_pipeline.derive_source_key)
# ---------------------------------------------------------------------------

def derive_source_key(ats_url: str, ats_hint: Optional[str] = None) -> str:
    u = urlparse(ats_url)
    host = (u.netloc or "").lower()
    path = u.path or ""
    if "greenhouse.io" in host or "boards.greenhouse" in host or "job-boards.greenhouse" in host:
        m = re.search(r"/(?:embed/job_app\?for=|)([^/]+)/jobs/(\d+)", path)
        if m:
            return f"greenhouse:{m.group(1)}:{m.group(2)}"
        return f"greenhouse:unknown:{int(time.time())}"
    if "lever.co" in host:
        m = re.search(r"/([^/]+)/([0-9a-f-]+)", path)
        if m:
            return f"lever:{m.group(1)}:{m.group(2)}"
        return f"lever:unknown:{int(time.time())}"
    if "ashbyhq.com" in host:
        m = re.search(r"/([^/]+)/([0-9a-f-]+)", path)
        if m:
            return f"ashby:{m.group(1)}:{m.group(2)}"
        return f"ashby:unknown:{int(time.time())}"
    if "myworkdayjobs.com" in host:
        m = re.search(r"/job/[^/]+/[^/]+/([^/?_]+)", path)
        jid = m.group(1) if m else str(int(time.time()))
        tenant = host.split(".")[0]
        return f"workday:{tenant}:{jid}"
    return f"ats:{host}:{int(time.time())}"


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

# Statuses worth resolving: a LinkedIn URL with any of these statuses still
# lacks a real ATS/company apply URL. 'manual-apply' and 'queued' are added so
# the offsite-link/board-API resolution also runs against rows that were merely
# flagged for manual handling because their app_url is a linkedin.com page
# (they were never actually applied to — applied_by guard still excludes any
# real submission). Only ever EXPANDS the candidate pool; all guards below
# (applied_by, already-brute-noted, linkedin-url) are unchanged.
RESOLVABLE_STATUSES = ('', 'blocked', 'manual-apply', 'queued')
_STATUS_IN = ", ".join("'%s'" % s for s in RESOLVABLE_STATUSES)

SELECT_TARGETS_SQL = """
    SELECT id, company, role, loc, app_url
    FROM roles
    WHERE status IN (%s)
      AND (applied_by IS NULL OR applied_by = '')
      AND app_url LIKE '%%linkedin.com%%'
      AND (agent_notes IS NULL OR agent_notes NOT LIKE '%%LINKEDIN-BRUTE-DONE%%')
""" % _STATUS_IN
# IDEMPOTENCY (fixed 2026-06-11): the guard now excludes ONLY rows that
# TERMINALLY resolved (marker 'LINKEDIN-BRUTE-DONE', written for RESOLVED).
# It used to exclude ANY row carrying a 'LINKEDIN-BRUTE' note -- which
# PERMANENTLY locked out every NO-ATS / ERRORED / UNRESOLVED row, so once a
# company was missing from a stale map (NO-ATS) it was NEVER retried even after
# the map was fixed. Non-terminal outcomes now write a plain 'LINKEDIN-BRUTE'
# audit note WITHOUT '-DONE', so each weekly run re-attempts them against the
# freshly-rebuilt map / dynamic probe. RESOLVED rows are doubly safe: their
# app_url is rewritten off linkedin.com so the URL clause excludes them too.


def fetch_targets(con: sqlite3.Connection, limit: Optional[int], role_id: Optional[int]) -> list[tuple]:
    sql = SELECT_TARGETS_SQL
    params: list = []
    if role_id:
        sql += " AND id = ?"
        params.append(role_id)
    sql += " ORDER BY id"
    rows = con.execute(sql, params).fetchall()
    if limit:
        rows = rows[:limit]
    return rows


def backup_db(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = db_path.parent / f"{db_path.name}.bak.{stamp}-linkedin-brute-resolver"
    if not bak.exists():
        import shutil
        shutil.copy2(db_path, bak)
    return bak


def write_resolved(
    con: sqlite3.Connection, role_id: int, new_url: str, source_key: str,
    ats: str, slug_or_tenant: str, score: float, reason: str, linkedin_url: str,
    stamp: str,
) -> None:
    note = (
        f"LINKEDIN-BRUTE-DONE {stamp}: resolved via {ats}({slug_or_tenant}) "
        f"score={score:.2f} reason={reason} | original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?",
        (new_url, source_key, note, role_id),
    )


def write_unresolved(
    con: sqlite3.Connection, role_id: int, ats: str, reason: str,
    linkedin_url: str, stamp: str,
) -> None:
    note = (
        f"LINKEDIN-BRUTE {stamp}: UNRESOLVED | ATS={ats} reason={reason} | "
        f"original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET agent_notes=? WHERE id=?",
        (note, role_id),
    )


def write_errored(
    con: sqlite3.Connection, role_id: int, ats: str, err: str,
    linkedin_url: str, stamp: str,
) -> None:
    note = (
        f"LINKEDIN-BRUTE {stamp}: ERRORED | ATS={ats} error={err} | "
        f"original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET agent_notes=? WHERE id=?",
        (note, role_id),
    )


def write_no_ats(
    con: sqlite3.Connection, role_id: int, reason: str,
    linkedin_url: str, stamp: str,
) -> None:
    note = (
        f"LINKEDIN-BRUTE {stamp}: NO-ATS | reason={reason} | "
        f"original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET agent_notes=? WHERE id=?",
        (note, role_id),
    )


# ---------------------------------------------------------------------------
# Main resolver loop
# ---------------------------------------------------------------------------

def resolve_one(
    company: str, title: str, loc: str, ats_entry: dict,
    jobs_cache: dict[str, tuple[list[dict], Optional[str]]],
) -> tuple[str, Optional[dict], float, str]:
    """Return (outcome, job_dict, score, reason).
    outcome in {RESOLVED, UNRESOLVED, ERRORED}.
    """
    if not ats_entry or ats_entry.get("ats") == "UNKNOWN":
        return "NO-ATS", None, 0.0, ats_entry.get("reason", "no-ats-identified") if ats_entry else "no-entry"
    if ats_entry.get("skip"):
        return "NO-ATS", None, 0.0, f"yaml-skip:{ats_entry.get('skip_reason','')}"

    # Cache jobs per ATS-key so we don't re-fetch for every row at the same company
    cache_key = (
        f"{ats_entry.get('ats')}:{ats_entry.get('slug') or ats_entry.get('host')}"
    )
    if cache_key not in jobs_cache:
        jobs_cache[cache_key] = fetch_jobs_for_ats(ats_entry)
    jobs, err = jobs_cache[cache_key]

    if err:
        return "ERRORED", None, 0.0, err
    if not jobs:
        return "UNRESOLVED", None, 0.0, "no-jobs-on-board"

    best, score, reason = best_match(title, loc, jobs)
    if best:
        return "RESOLVED", best, score, reason
    return "UNRESOLVED", None, score, reason


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=DEFAULT_MAX_SECONDS)
    ap.add_argument("--per-row-seconds", type=int, default=DEFAULT_PER_ROW)
    ap.add_argument("--role-id", type=int, default=None)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--map", default=str(DEFAULT_MAP),
                    help="Path to _linkedin_stranded_ats_map.json (company→ATS)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    write_mode = args.apply and not args.dry_run
    log = (lambda *a, **k: None) if args.quiet else print

    db_path = Path(args.db)
    map_path = Path(args.map)
    if not db_path.exists():
        print(f"FATAL: db not found: {db_path}", file=sys.stderr)
        return 1
    if not map_path.exists():
        print(f"FATAL: ats map not found: {map_path}", file=sys.stderr)
        return 1

    mapping = json.loads(map_path.read_text()).get("mapping", {})
    log(f"[brute] ATS-map: {len(mapping)} companies "
        f"({sum(1 for v in mapping.values() if v.get('ats')!='UNKNOWN')} with known ATS)",
        flush=True)

    con = sqlite3.connect(args.db)
    targets = fetch_targets(con, args.limit or None, args.role_id)
    log(f"[brute] targets: {len(targets)} (mode={'APPLY' if write_mode else 'DRY-RUN'})", flush=True)

    if write_mode:
        bak = backup_db(db_path)
        log(f"[brute] backup written: {bak}", flush=True)

    stamp = datetime.now().strftime("%Y-%m-%d")
    start = time.time()
    counts = {"resolved": 0, "unresolved": 0, "errored": 0, "no_ats": 0, "non_linkedin_skip": 0}
    by_ats: dict[str, int] = {}
    by_unresolved_ats: dict[str, int] = {}
    samples: list[dict] = []
    jobs_cache: dict[str, tuple[list[dict], Optional[str]]] = {}

    for i, row in enumerate(targets, 1):
        if time.time() - start > args.max_seconds:
            log(f"[brute] time-budget exhausted at row {i-1}", flush=True)
            break
        rid, company, role_title, loc, app_url = row

        # Defensive: ensure URL is actually LinkedIn (idempotency guard)
        if not is_linkedin_url(app_url or ""):
            counts["non_linkedin_skip"] += 1
            continue

        ats_entry = mapping.get(company or "")
        outcome, job, score, reason = resolve_one(
            company or "", role_title or "", loc or "", ats_entry or {}, jobs_cache,
        )

        if outcome == "RESOLVED":
            new_url = job["url"]
            sk = derive_source_key(new_url, ats_entry.get("ats"))
            slug_or_tenant = ats_entry.get("slug") or ats_entry.get("tenant") or "?"
            counts["resolved"] += 1
            by_ats[ats_entry["ats"]] = by_ats.get(ats_entry["ats"], 0) + 1
            samples.append({
                "id": rid, "company": company, "role": role_title,
                "ats": ats_entry["ats"], "slug": slug_or_tenant,
                "score": round(score, 3), "reason": reason,
                "linkedin_url": app_url, "new_url": new_url,
            })
            if write_mode:
                write_resolved(
                    con, rid, new_url, sk, ats_entry["ats"], slug_or_tenant,
                    score, reason, app_url, stamp,
                )
            log(f"  [{i}] R {company} → {ats_entry['ats']}({slug_or_tenant}) {score:.2f}", flush=True)
        elif outcome == "UNRESOLVED":
            counts["unresolved"] += 1
            ats = (ats_entry or {}).get("ats", "?")
            by_unresolved_ats[ats] = by_unresolved_ats.get(ats, 0) + 1
            if write_mode:
                write_unresolved(con, rid, ats, reason, app_url, stamp)
            log(f"  [{i}] U {company} ({ats}) {reason}", flush=True)
        elif outcome == "ERRORED":
            counts["errored"] += 1
            ats = (ats_entry or {}).get("ats", "?")
            if write_mode:
                write_errored(con, rid, ats, reason, app_url, stamp)
            log(f"  [{i}] E {company} ({ats}) {reason}", flush=True)
        else:  # NO-ATS
            counts["no_ats"] += 1
            if write_mode:
                write_no_ats(con, rid, reason, app_url, stamp)
            log(f"  [{i}] N {company} {reason}", flush=True)

        # commit every 20 rows for blast-radius safety
        if write_mode and i % 20 == 0:
            con.commit()

    if write_mode:
        con.commit()
    con.close()

    summary = {
        "mode": "apply" if write_mode else "dry-run",
        "attempted": sum(counts.values()),
        **counts,
        "by_resolved_ats": by_ats,
        "by_unresolved_ats": by_unresolved_ats,
        "elapsed_sec": int(time.time() - start),
        "sample_resolved": samples[:5],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
