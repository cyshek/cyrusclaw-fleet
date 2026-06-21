"""Himalayas remote jobs API adapter.

API: https://himalayas.app/jobs/api/search
Docs: https://himalayas.app/api
No auth required. Max 20/request. Cache 24h — one call per crawl only.

source_key: himalayas:<guid>  (handled in tracker_merger)
"""
from __future__ import annotations

import time
import re
from datetime import datetime, timezone
from typing import List

from core import Role, http_get, parse_experience, strip_html

_BASE_URL = "https://himalayas.app/jobs/api/search"
_PAGE_SIZE = 20
_SLEEP_BETWEEN_PAGES = 0.5  # seconds — be polite

# Accepted employment types
_FULL_TIME_TYPES = {"Full Time", "Full-Time", "Full_Time"}

# Location strings that indicate US-accessible roles
_US_LOCATION_TOKENS = {"United States", "Worldwide"}


def _is_us_accessible(location_restrictions: list) -> bool:
    """Return True if locationRestrictions allows US applicants.

    Empty/null = no restriction = worldwide = OK.
    Non-empty must contain 'United States' or 'Worldwide'.
    """
    if not location_restrictions:
        return True  # no restriction → worldwide
    for loc in location_restrictions:
        if loc in _US_LOCATION_TOKENS:
            return True
    return False


def _is_full_time(employment_type: str) -> bool:
    """Return True if employment type is Full Time (not Intern/Part Time/Contractor)."""
    if not employment_type:
        return True  # unknown → don't filter
    # Normalize: strip spaces, lower for comparison
    et = employment_type.strip()
    return et in _FULL_TIME_TYPES or "full" in et.lower() and "time" in et.lower()


def _parse_pub_date(pub_date) -> str:
    """Convert pubDate (unix timestamp int or ISO string) to YYYY-MM-DD."""
    if not pub_date:
        return ""
    if isinstance(pub_date, (int, float)):
        try:
            return datetime.fromtimestamp(int(pub_date), tz=timezone.utc).date().isoformat()
        except Exception:
            return ""
    if isinstance(pub_date, str):
        return pub_date[:10]
    return ""


def _extract_guid(job: dict) -> str:
    """Extract a stable identifier from the job's guid or applicationLink."""
    guid = job.get("guid") or job.get("applicationLink") or ""
    # Use the full URL as the guid (it's already a stable unique URL on himalayas)
    return guid


def fetch(company: str, slug: str, **kwargs) -> List[Role]:
    """Fetch jobs from Himalayas for the given search query.

    Args:
        company: Human-readable name (e.g. "Himalayas (PM)") — not used for API call.
        slug: Search query, e.g. "product manager", "solutions engineer".

    Returns:
        List of Role objects, filtered to US-accessible full-time roles.
    """
    out: List[Role] = []
    offset = 0
    total_count = None

    while True:
        params = {
            "q": slug,
            "country": "US",
            "worldwide": "true",
            "limit": _PAGE_SIZE,
            "offset": offset,
        }
        r = http_get(_BASE_URL, params=params)
        if r.status_code != 200:
            raise RuntimeError(f"himalayas[{slug}] HTTP {r.status_code}")

        data = r.json()

        # Capture total count on first page
        if total_count is None:
            total_count = data.get("totalCount", 0)

        jobs = data.get("jobs", [])
        if not jobs:
            break

        for j in jobs:
            # Filter: employment type must be Full Time
            emp_type = j.get("employmentType") or ""
            if not _is_full_time(emp_type):
                continue

            # Filter: location must be US-accessible
            loc_restrictions = j.get("locationRestrictions") or []
            if not _is_us_accessible(loc_restrictions):
                continue

            # Build location string
            if loc_restrictions:
                location = ", ".join(loc_restrictions)
            else:
                location = "Remote"

            # Parse description for experience
            desc = strip_html(j.get("description") or "")
            exp_req = parse_experience(desc)

            # Stable unique ID (guid = full URL on himalayas)
            guid = _extract_guid(j)

            # Post date
            posted_at = _parse_pub_date(j.get("pubDate"))

            out.append(Role(
                company=j.get("companyName") or company,
                title=j.get("title", ""),
                location=location,
                exp_required=exp_req,
                url=j.get("applicationLink") or j.get("guid") or "",
                posted_at=posted_at,
                source="himalayas",
                raw={
                    "guid": guid,
                    "categories": j.get("categories") or [],
                },
            ))

        offset += len(jobs)

        # Stop if we've fetched all results
        if total_count is not None and offset >= total_count:
            break
        if len(jobs) < _PAGE_SIZE:
            break

        time.sleep(_SLEEP_BETWEEN_PAGES)

    return out
