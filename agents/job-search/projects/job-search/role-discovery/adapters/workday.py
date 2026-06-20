"""Workday CXS jobs search API.

POST https://{host}/wday/cxs/{tenant}/{site}/jobs
Body: {"appliedFacets":{}, "limit":20, "offset":0, "searchText":"product"}

Need host, tenant, site per company. Example for Nvidia:
  host="nvidia.wd5.myworkdayjobs.com", tenant="nvidia", site="NVIDIAExternalCareerSite"
"""
from __future__ import annotations
from typing import List, Dict
from core import Role, http_post_json, parse_experience, strip_html, http_get


# Default search terms — Workday returns jobs matching any of these via separate calls
SEARCH_TERMS = [
    "product manager",
    "program manager",
    "technical program manager",
    "sales engineer",
    "solutions engineer",
    "solutions architect",
    "customer engineer",
]


def _fetch_one(host: str, tenant: str, site: str, search_text: str, page_size: int = 20) -> List[dict]:
    # Workday caps limit at 20.
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out = []
    offset = 0
    total = None  # authoritative total comes from the FIRST page only.
    HARD_CAP = 1000  # safety ceiling so a misbehaving tenant can't loop forever
    while True:
        body = {
            "appliedFacets": {},
            "limit": page_size,
            "offset": offset,
            "searchText": search_text,
        }
        r = http_post_json(url, body, headers={"X-Calypso-PageBlocked": "false"})
        if r.status_code != 200:
            raise RuntimeError(f"workday[{tenant}/{site}] HTTP {r.status_code} for '{search_text}'")
        data = r.json()
        jobs = data.get("jobPostings", []) or []
        out.extend(jobs)
        offset += len(jobs)
        # Some Workday tenants (e.g. Salesforce wd12) report the real `total`
        # ONLY on the first page (offset=0) and return total=0 on every page
        # thereafter. The old loop read `total` fresh each page, so on page 2
        # `offset(40) >= total(0)` tripped and it stopped at 40 jobs/term
        # (Salesforce was capped to ~8 kept roles). Lock the total from the
        # FIRST non-trivial response and never let a later total=0 shrink it.
        page_total = data.get("total")
        if isinstance(page_total, int) and page_total > 0 and (total is None or page_total > total):
            total = page_total
        # Stop conditions:
        #   - the page was empty/short (no more results), OR
        #   - we've reached the locked total, OR
        #   - safety hard cap.
        if not jobs or len(jobs) < page_size:
            break
        if total is not None and offset >= total:
            break
        if offset >= HARD_CAP:
            break
    return out


def fetch(company: str, slug: str, **opts) -> List[Role]:
    """slug is unused for Workday; opts must include 'host', 'tenant', 'site'."""
    host = opts["host"]
    tenant = opts["tenant"]
    site = opts["site"]
    locations_facet = opts.get("us_only", True)

    seen = {}
    for term in SEARCH_TERMS:
        try:
            for j in _fetch_one(host, tenant, site, term):
                ext = j.get("externalPath") or ""
                if not ext:
                    continue
                if ext in seen:
                    continue
                seen[ext] = j
        except RuntimeError as e:
            # one search term failed; continue
            print(f"  [workday {tenant}] '{term}' failed: {e}")

    out: List[Role] = []
    site_url_prefix = f"https://{host}/{site}"
    for ext, j in seen.items():
        title = j.get("title") or ""
        loc = j.get("locationsText") or ""
        url = site_url_prefix + ext
        # Workday list view doesn't include description; would need per-job fetch.
        # Skip per-job fetch for speed; rely on title-based filtering only.
        out.append(Role(
            company=company,
            title=title,
            location=loc,
            exp_required="exp:unstated",  # not in list view
            url=url,
            posted_at=(j.get("postedOn") or "")[:24],
            source="workday",
            raw={"externalPath": ext},
        ))
    return out
