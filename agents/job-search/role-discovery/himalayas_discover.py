"""Himalayas keyword-discovery: find NET-NEW employers hiring our TARGET roles
(PM / TPM / Solutions Engineer / Solutions Architect / Sales Engineer / etc.)
by crawling the public Himalayas jobs API, then verify each net-new company has
a public Greenhouse / Ashby / Lever board (via the proven slug-probe), and emit
ready-to-merge companies.yaml entries (deduped against the existing list).

WHY Himalayas (and not Wellfound / YC Work-at-a-Startup):
  - Wellfound is DataDome-walled (403, IP-bound) over plain HTTP.
  - YC WaaS /jobs + /companies require login and 406/404 a non-browser UA.
  - himalayas.app/jobs/api is a fully-open JSON endpoint (~105k jobs) that
    exposes companyName, companySlug, title, seniority, and locationRestrictions
    -- everything a keyword-discovery pass needs, with no auth and no captcha.
    It satisfies the P2 intent ("net-new companies, NOT IP-walled like LinkedIn")
    even though it was not one of the two example sources in the brief.

PIPELINE (mirrors yc_discover.py so the codebase stays consistent):
  1. fetch    -- paginate the Himalayas API (offset-walk; the API caps `limit`
                 at 20 rows/request) and cache to output/himalayas_jobs.json.
  2. parse    -- pull (title, companyName, companySlug, seniority, locations).
  3. keyword  -- keep ONLY rows whose title passes the LIVE classifier KEEP gate
                 (jd_llm_classifier.title_has_target_role AND no
                 extract_title_skip hit) so we never surface senior / FDE / SWE /
                 people-manager titles. Optional --us-only drops rows whose
                 locationRestrictions are present and contain no US/Americas/remote
                 signal.
  4. dedup    -- drop companies already in companies.yaml (by normalized name).
  5. probe    -- for each remaining net-new company, reuse
                 bulk_discover_slugs.probe()/slug_variants() to verify a real
                 public GH/Ashby/Lever board exists (we only emit companies we can
                 actually crawl with an existing adapter).
  6. emit     -- write output/himalayas_discover_hits.json + print merge-ready
                 YAML. NEVER blind-merges: --apply is required to append, and even
                 then it backs up companies.yaml first.

Usage:
  .venv/bin/python himalayas_discover.py --max-jobs 600          # crawl 600 jobs, probe, print YAML (dry)
  .venv/bin/python himalayas_discover.py --us-only --max-jobs 2000
  .venv/bin/python himalayas_discover.py --max-jobs 600 --apply  # also append verified new entries

Idempotent: never adds a company whose name (case-insensitive) OR resolved
adapter+slug already exists in companies.yaml.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml

ROOT = Path(__file__).parent
YAML_PATH = ROOT / "companies.yaml"
API_URL = "https://himalayas.app/jobs/api"
CACHE = ROOT / "output" / "himalayas_jobs.json"
HITS_OUT = ROOT / "output" / "himalayas_discover_hits.json"

# The Himalayas API ignores values of `limit` above this; it returns at most
# 20 rows per request regardless. We offset-walk in PAGE_SIZE steps.
PAGE_SIZE = 20
# Himalayas' WAF 403s a *detailed* desktop-Chrome UA string but serves a bare
# "Mozilla/5.0" fine (verified 2026-06-09). Keep this minimal.
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Reuse the proven board-probe + slug-variant logic.
from bulk_discover_slugs import probe, slug_variants  # noqa: E402
# Reuse the LIVE classifier KEEP gate so discovery and classification agree on
# what a target role is (single source of truth -- no second keyword list to
# drift out of sync).
from jd_llm_classifier import title_has_target_role, extract_title_skip  # noqa: E402
from yc_discover import _norm_name, load_existing  # noqa: E402
# Reuse the shared staffing/recruiter blocklist so Himalayas discovery drops the
# same staffing-agency middlemen the LinkedIn pipeline does (single source of
# truth -- no second list to drift).
from staffing_blocklist import is_staffing_firm  # noqa: E402

# Himalayas leaks a literal "name" placeholder as companyName on a non-trivial
# slice of rows (~10% in sampled crawls); these are junk and must never become a
# company entry. Matched case-insensitively after strip.
_PLACEHOLDER_NAMES = {"name", "company", "company name", "n/a", "none", "-"}

# Location tokens that count as "US-eligible" when locationRestrictions is set.
_US_TOKENS = (
    "united states", "usa", "u.s.", "us-", "america", "americas",
    "north america", "remote", "worldwide", "anywhere", "global",
)


def fetch_jobs(max_jobs: int, *, force: bool = False,
               sleep: float = 0.5) -> List[dict]:
    """Offset-walk the Himalayas API up to `max_jobs` rows; cache the result.

    The cache is keyed only by existence (not by max_jobs) -- a larger crawl
    overwrites a smaller one. Pass force=True to re-fetch.
    """
    if CACHE.exists() and not force:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if isinstance(cached, list) and len(cached) >= max_jobs:
                return cached[:max_jobs]
        except Exception:
            pass

    jobs: List[dict] = []
    offset = 0
    total = None
    consecutive_429 = 0
    while len(jobs) < max_jobs:
        try:
            r = requests.get(API_URL, headers=HEADERS,
                             params={"limit": PAGE_SIZE, "offset": offset},
                             timeout=20)
            if r.status_code == 429:
                # Himalayas rate-limits ~150 pages in; back off and retry a few
                # times before giving up so a big crawl doesn't truncate early.
                consecutive_429 += 1
                if consecutive_429 > 5:
                    print(f"[himalayas] gave up after {consecutive_429} 429s "
                          f"at offset={offset}", file=sys.stderr)
                    break
                backoff = min(30.0, 2.0 * (2 ** (consecutive_429 - 1)))
                print(f"[himalayas] 429 at offset={offset}; backoff {backoff:.0f}s "
                      f"(try {consecutive_429}/5)", file=sys.stderr)
                time.sleep(backoff)
                continue
            consecutive_429 = 0
            r.raise_for_status()
            payload = r.json()
        except Exception as e:  # pragma: no cover - network guard
            print(f"[himalayas] fetch error at offset={offset}: {e}",
                  file=sys.stderr)
            break
        batch = payload.get("jobs") or []
        if total is None:
            total = payload.get("totalCount")
        if not batch:
            break
        jobs.extend(batch)
        offset += len(batch)
        if total is not None and offset >= total:
            break
        time.sleep(sleep)

    jobs = jobs[:max_jobs]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(jobs), encoding="utf-8")
    print(f"[himalayas] fetched {len(jobs)} jobs (api total={total})",
          file=sys.stderr)
    return jobs


def is_us_eligible(job: dict) -> bool:
    """True if the role is US-eligible. If locationRestrictions is empty we treat
    the role as unrestricted (eligible); otherwise at least one restriction must
    look US/Americas/remote-friendly."""
    locs = job.get("locationRestrictions") or []
    if not locs:
        return True
    blob = " ".join(str(x) for x in locs).lower()
    return any(tok in blob for tok in _US_TOKENS)


def keyword_match(job: dict) -> bool:
    """Apply the LIVE classifier KEEP gate to the job title."""
    title = job.get("title") or ""
    if not title_has_target_role(title):
        return False
    # extract_title_skip returns a skip-keyword for senior/FDE/SWE/manager titles
    # that should NOT enter our queue; None means KEEP.
    if extract_title_skip(title) is not None:
        return False
    return True


def select_companies(jobs: List[dict], *, us_only: bool
                     ) -> Dict[str, dict]:
    """Filter jobs to target roles (+ optional US) and collapse to a unique
    company map: norm_name -> {name, slug(from himalayas), sample_title, n}."""
    companies: Dict[str, dict] = {}
    for job in jobs:
        if not keyword_match(job):
            continue
        if us_only and not is_us_eligible(job):
            continue
        name = (job.get("companyName") or "").strip()
        if not name:
            continue
        # Drop Himalayas' literal "name"/placeholder companyName leakage.
        if name.lower() in _PLACEHOLDER_NAMES:
            continue
        # Drop staffing/recruiter middlemen (opaque apply path, stale reposts).
        if is_staffing_firm(name):
            continue
        key = _norm_name(name)
        if not key:
            continue
        entry = companies.setdefault(key, {
            "name": name,
            "himalayas_slug": (job.get("companySlug") or "").strip(),
            "sample_title": job.get("title"),
            "n_target_roles": 0,
        })
        entry["n_target_roles"] += 1
    return companies


def discover_for(company: dict) -> Optional[Dict]:
    """Probe a single company for a public GH/Ashby/Lever board. Prefers the
    Himalayas slug, then name-derived variants. Returns a merge-ready dict or
    None (mirrors yc_discover.discover_for)."""
    name = company.get("name") or ""
    variants: List[str] = []
    if company.get("himalayas_slug"):
        variants.append(str(company["himalayas_slug"]).lower())
    variants += slug_variants(name)
    seen, ordered = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            ordered.append(v)

    best = None
    for adapter in ("greenhouse", "ashby", "lever"):
        for v in ordered:
            r = probe(adapter, v)
            if r and (best is None or r[2] > best[2]):
                best = r
        if best:
            break
    if not best:
        return None
    a, s, n = best
    return {"name": name, "adapter": a, "slug": s, "jobs": n,
            "himalayas_slug": company.get("himalayas_slug"),
            "sample_title": company.get("sample_title"),
            "n_target_roles": company.get("n_target_roles", 0)}


def run(max_jobs: int, us_only: bool, apply: bool, workers: int,
        force_fetch: bool) -> List[Dict]:
    jobs = fetch_jobs(max_jobs, force=force_fetch)
    companies = select_companies(jobs, us_only=us_only)
    existing_names, existing_slugs = load_existing(YAML_PATH)

    todo = [c for k, c in companies.items() if k not in existing_names]
    print(f"[himalayas] target-role companies={len(companies)} | "
          f"new-by-name={len(todo)} | probing boards...", file=sys.stderr)

    hits: List[Dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(discover_for, c): c for c in todo}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                r = None
            if not r:
                continue
            pair = f"{r['adapter']}/{r['slug']}"
            if pair in existing_slugs:
                continue  # already covered under a different name
            existing_slugs.add(pair)
            hits.append(r)
            print(f"  HIT {r['name']:28s} -> {pair} ({r['jobs']} jobs) "
                  f"[{r['n_target_roles']} target role(s) on himalayas]",
                  file=sys.stderr, flush=True)

    hits.sort(key=lambda x: (x["adapter"], -x["jobs"], x["name"].lower()))
    HITS_OUT.parent.mkdir(parents=True, exist_ok=True)
    HITS_OUT.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    print(f"\n=== {len(hits)} NET-NEW verified companies (Himalayas-sourced) ===",
          file=sys.stderr)
    for r in hits:
        print(f"  - {{ name: \"{r['name']}\", adapter: {r['adapter']}, "
              f"slug: {r['slug']} }}  # himalayas, {r['jobs']} jobs, "
              f"e.g. {r['sample_title']!r}")

    if apply and hits:
        _append_to_yaml(hits)
        print(f"\nAPPLIED: appended {len(hits)} entries to {YAML_PATH.name}",
              file=sys.stderr)
    elif apply and not hits:
        print("\nAPPLY requested but 0 hits -- nothing appended.",
              file=sys.stderr)
    return hits


def _append_to_yaml(hits: List[Dict]) -> None:
    """Append verified entries to companies.yaml. Handles both a top-level list
    and the repo's actual {companies: [...]} wrapper. Backs up first."""
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or []
    if isinstance(raw, dict) and isinstance(raw.get("companies"), list):
        target = raw["companies"]
        container = raw
    elif isinstance(raw, list):
        target = raw
        container = raw
    else:
        raise SystemExit(
            "companies.yaml is neither a list nor {companies: [...]}; aborting.")
    bak = YAML_PATH.with_suffix(".yaml.bak.himalayas")
    bak.write_text(YAML_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    for r in hits:
        target.append({"name": r["name"], "adapter": r["adapter"],
                       "slug": r["slug"],
                       "note": "himalayas-auto-discovered"})
    YAML_PATH.write_text(
        yaml.safe_dump(container, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-jobs", type=int, default=600,
                    help="max jobs to crawl from the Himalayas API")
    ap.add_argument("--us-only", action="store_true",
                    help="drop roles whose locationRestrictions exclude US/remote")
    ap.add_argument("--apply", action="store_true",
                    help="append verified hits to companies.yaml (backs up first)")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--force-fetch", action="store_true")
    a = ap.parse_args()
    run(a.max_jobs, a.us_only, a.apply, a.workers, a.force_fetch)


if __name__ == "__main__":
    main()
