"""SmartRecruiters public postings API.

URL: https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0

Response schema:
  {"offset": N, "limit": N, "totalFound": N, "content": [...]}
  Each posting: id, name (title), location {city, region, country, remote, hybrid,
                fullLocation}, releasedDate, experienceLevel, typeOfEmployment

Job page URL: https://jobs.smartrecruiters.com/{CompanySlug}/{id}
  (stable without the title slug suffix)

source_key: "smartrecruiters:{id}"  (handled in tracker_merger)

US filter: location.country == "us" OR location.remote == True
  SmartRecruiters uses ISO-3166-1 alpha-2 codes (lowercase).
"""
from __future__ import annotations

import time
from typing import List

from core import Role, http_get, parse_experience

_PAGE_SIZE = 100
_MAX_PAGES = 5   # cap at 500 results per company
_SLEEP = 0.3     # polite delay between pages


def _is_us_or_remote(loc: dict) -> bool:
    """Return True if the posting is in the US or flagged remote."""
    if not loc:
        return False
    if loc.get("remote"):
        return True
    country = (loc.get("country") or "").lower().strip()
    return country in ("us", "usa", "united states")


def _build_url(company_slug: str, posting_id) -> str:
    """Build the public SmartRecruiters job page URL."""
    return f"https://jobs.smartrecruiters.com/{company_slug}/{posting_id}"


def fetch(company: str, slug: str, **_) -> List[Role]:
    """Fetch US/remote postings from SmartRecruiters for the given company slug.

    Args:
        company: Human-readable company name.
        slug: SmartRecruiters company identifier (case-sensitive, e.g. "Workato").

    Returns:
        List of Role objects filtered to US + remote postings.
        Returns empty list on HTTP errors (does not raise).
    """
    base_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    out: List[Role] = []
    offset = 0

    for _ in range(_MAX_PAGES):
        try:
            r = http_get(base_url, params={"limit": _PAGE_SIZE, "offset": offset})
        except Exception:
            break
        if r.status_code != 200:
            break
        data = r.json()
        items = data.get("content") or []
        if not items:
            break

        for j in items:
            loc = j.get("location") or {}
            if not _is_us_or_remote(loc):
                continue

            posting_id = j.get("id", "")
            loc_parts = [
                loc.get("city"),
                loc.get("region"),
                loc.get("country", "").upper() or None,
            ]
            loc_str = ", ".join(p for p in loc_parts if p)
            if loc.get("remote"):
                loc_str = (loc_str + " (Remote)").strip() if loc_str else "Remote"

            # Build stable public job page URL
            job_url = _build_url(slug, posting_id) if posting_id else ""

            out.append(Role(
                company=company,
                title=j.get("name", ""),
                location=loc_str,
                exp_required="exp:unstated",  # SR list API does not expose YOE
                url=job_url,
                posted_at=(j.get("releasedDate") or "")[:10],
                source="smartrecruiters",
                raw={"id": str(posting_id), "sr_slug": slug},
            ))

        total = data.get("totalFound", 0)
        offset += len(items)
        if offset >= total or len(items) < _PAGE_SIZE:
            break
        time.sleep(_SLEEP)

    return out
