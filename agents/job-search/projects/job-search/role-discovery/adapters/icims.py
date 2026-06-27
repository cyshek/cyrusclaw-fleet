"""iCIMS Attract (Jibe) jobs API adapter.

Discovery endpoint:
  GET https://{icims_client_code}.jibeapply.com/api/jobs
      ?keyword=&location=&pagesize=10&page=N&internal=false&activelanguagetag=en-us

Notes:
  - API returns ALL roles regardless of keyword param (keyword is ignored server-side)
  - Returns exactly 10 jobs/page; totalCount is authoritative page-count driver
  - apply_url shape: https://<host>.icims.com/jobs/<req_id>/login
"""
from __future__ import annotations

import re
import sys
import time
from typing import List

from core import Role, http_get, parse_experience, strip_html

# Client-side title filter — keep only roles matching these patterns.
# iCIMS API ignores the keyword param and returns ALL roles every time,
# so we must filter client-side.
TITLE_KEEP_RE = re.compile(
    r"\b("
    r"product.{0,4}manager"
    r"|program.{0,4}manager"
    r"|technical.{0,4}program"
    r"|solutions.{0,4}(engineer|architect)"
    r"|sales.{0,4}engineer"
    r"|customer.{0,4}engineer"
    r"|solutions.{0,4}consultant"
    r"|APM\b|TPM\b|PgM\b|EPM\b"
    r")\b",
    re.IGNORECASE,
)

# jibeapply API always returns exactly 10 items/page regardless of pagesize
API_PAGE_SIZE = 10
RATE_LIMIT_SLEEP = 0.3   # seconds between pages
HARD_CAP = 5000          # safety cap on total raw fetch


def _fetch_all_raw(client_code: str) -> List[dict]:
    """Fetch all roles for a tenant via pagination.

    Keyword is intentionally left empty — the API ignores it and returns all
    roles regardless. Fetching once avoids 7x duplicate pagination.
    """
    base_url = f"https://{client_code}.jibeapply.com/api/jobs"
    results: List[dict] = []
    page = 1
    total: int | None = None

    while True:
        params = {
            "keyword": "",
            "location": "",
            "pagesize": API_PAGE_SIZE,
            "page": page,
            "internal": "false",
            "activelanguagetag": "en-us",
        }
        r = http_get(base_url, params=params)
        if r.status_code != 200:
            raise RuntimeError(
                f"icims[{client_code}] HTTP {r.status_code} page={page}"
            )
        data = r.json()

        # totalCount is authoritative; lock the max seen
        page_total = data.get("totalCount")
        if isinstance(page_total, int) and page_total > 0:
            if total is None or page_total > total:
                total = page_total

        jobs_batch = data.get("jobs") or []
        for j in jobs_batch:
            # Standard response wraps each job under a "data" key
            job_data = j.get("data") if isinstance(j, dict) and "data" in j else j
            results.append(job_data)

        fetched = len(results)

        if not jobs_batch:
            break  # empty page — exhausted
        if total is not None and fetched >= total:
            break  # fetched everything totalCount promised
        if fetched >= HARD_CAP:
            break  # safety cap
        if len(jobs_batch) < API_PAGE_SIZE:
            break  # short page — last page

        page += 1
        time.sleep(RATE_LIMIT_SLEEP)

    return results


def fetch(company: str, slug: str, **opts) -> List[Role]:
    """Main adapter entry point — called by REGISTRY["icims"].

    Expects ``icims_client_code`` in opts (e.g. "amd", "siriusxmradio").
    Falls back to slug if icims_client_code not provided.
    """
    client_code = opts.get("icims_client_code") or slug
    if not client_code:
        raise ValueError(f"icims adapter for {company!r}: missing icims_client_code")

    try:
        raw_jobs = _fetch_all_raw(client_code)
    except Exception as e:
        print(f"[icims] {company}/{client_code} fetch error: {e}", file=sys.stderr)
        return []

    seen_req_ids: set[str] = set()
    out: List[Role] = []

    for job in raw_jobs:
        # --- Deduplicate by req_id ---
        req_id = str(job.get("req_id") or "").strip()
        if not req_id or req_id in seen_req_ids:
            continue
        seen_req_ids.add(req_id)

        # --- Filter: US-only, must be applyable, exclude internal ---
        if job.get("internal", False):
            continue
        if not job.get("applyable", False):
            continue
        cc = (job.get("country_code") or job.get("country") or "").upper().strip()
        if cc not in ("US", "USA", "UNITED STATES"):
            continue

        # --- Title filter (client-side, since API ignores keyword) ---
        title = (job.get("title") or "").strip()
        if not TITLE_KEEP_RE.search(title):
            continue

        # --- Build location string ---
        city = (job.get("city") or "").strip()
        state = (job.get("state") or "").strip()
        full_loc = (job.get("full_location") or job.get("location_name") or "").strip()
        if full_loc:
            # Deduplicate semicolon-separated locations (API repeats locations for multi-loc roles)
            seen_locs: list[str] = []
            for part in full_loc.split(";"):
                p = part.strip()
                if p and p not in seen_locs:
                    seen_locs.append(p)
            location = "; ".join(seen_locs)
        elif city and state:
            location = f"{city}, {state}"
        elif city:
            location = city
        elif state:
            location = state
        else:
            location = "US"

        # --- Description ---
        desc_raw = job.get("description") or ""
        desc = strip_html(desc_raw) if "<" in desc_raw else desc_raw

        # --- apply_url from API (ends in /login; runner handles it) ---
        apply_url = (job.get("apply_url") or "").strip()

        # --- Posted date: ISO prefix ---
        posted_raw = job.get("posted_date") or job.get("update_date") or ""
        posted_at = str(posted_raw)[:10] if posted_raw else ""

        out.append(Role(
            company=company,
            title=title,
            location=location,
            exp_required=parse_experience(desc),
            url=apply_url,
            posted_at=posted_at,
            source="icims",
            raw={
                "req_id": req_id,
                "client_code": client_code,
                "employment_type": job.get("employment_type"),
                "department": job.get("department"),
            },
        ))

    return out
