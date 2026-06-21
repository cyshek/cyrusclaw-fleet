"""Remotive remote job board API.

URL: https://remotive.com/api/remote-jobs?category={slug}&limit=200

Supported slugs: product, management-finance, sales, customer-support, etc.
Each returned job has id, title, company_name, url, candidate_required_location, tags.

Location filter: pass-through when candidate_required_location contains "USA",
"US", "Worldwide", "Americas" (broadly US-accessible), or is empty.
Classifier applies title/experience gates downstream.

source_key: remotive:<job_id>  (handled in tracker_merger)
"""
from __future__ import annotations
from typing import List
from core import Role, http_get, parse_experience, strip_html

# Remotive uses integer IDs
_US_TOKENS = {"USA", "US", "Worldwide", "Americas", "North America", "World"}


def _is_us_accessible(location: str) -> bool:
    """Return True if the location field suggests the role accepts US applicants."""
    if not location:
        return True  # unspecified = worldwide
    loc_upper = location.upper()
    # Direct substring matches
    for token in ("USA", "WORLDWIDE", "AMERICAS", "NORTH AMERICA"):
        if token in loc_upper:
            return True
    # "US" standalone — avoid matching "AUSTRALIA", "RUSSIA", etc.
    import re
    if re.search(r"\bUS\b", location):
        return True
    return False


def fetch(company: str, slug: str, **kwargs) -> List[Role]:
    """Fetch jobs from Remotive for the given category slug.

    Args:
        company: Human-readable name (e.g. "Remotive (product)") — not used for API call.
        slug: Remotive category name, e.g. "product", "management-finance", "sales".
    """
    limit = kwargs.get("limit", 200)
    url = "https://remotive.com/api/remote-jobs"
    r = http_get(url, params={"category": slug, "limit": limit})
    if r.status_code != 200:
        raise RuntimeError(f"remotive[{slug}] HTTP {r.status_code}")
    data = r.json()
    jobs = data.get("jobs", [])

    out: List[Role] = []
    for j in jobs:
        loc = j.get("candidate_required_location") or ""
        if not _is_us_accessible(loc):
            continue  # skip non-US roles early to reduce noise

        job_id = j.get("id", "")
        desc = strip_html(j.get("description") or "")
        posted = (j.get("publication_date") or "")[:10]

        out.append(Role(
            company=j.get("company_name") or company,
            title=j.get("title", ""),
            location=loc or "Remote",
            exp_required=parse_experience(desc),
            url=j.get("url", ""),
            posted_at=posted,
            source="remotive",
            raw={"id": job_id, "slug": slug},
        ))
    return out
