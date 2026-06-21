"""BambooHR public careers API adapter.

BambooHR is a per-company ATS: each company has a subdomain at
  https://{slug}.bamboohr.com/careers/list

The /careers/list endpoint returns JSON (no auth required):
  {"meta": {"totalCount": N}, "result": [...]}

Each job:
  id              -- numeric job opening ID
  jobOpeningName  -- role title
  departmentLabel -- department
  employmentStatusLabel -- "Full-Time", "Part-Time", etc.
  location        -- {"city": ..., "state": ...}  (company's configured label)
  atsLocation     -- {"country": ..., "state": ..., "province": ..., "city": ...}
                     (canonical ATS location; preferred for US filter)
  isRemote        -- null or bool
  locationType    -- "2" = on-site, "1" = remote (not always set)

Job apply URL: https://{slug}.bamboohr.com/careers/{id}

US filter: atsLocation.country in ("United States", "US", null/empty when isRemote)
           OR isRemote == true / locationType == "1"

source_key: "bamboohr:{slug}:{id}"  (handled in tracker_merger)
"""
from __future__ import annotations

from typing import List

from core import Role, http_get

_US_COUNTRIES = {"United States", "US", "USA"}


def _is_us_or_remote(job: dict) -> bool:
    """Return True if this job is US-based or remote."""
    # isRemote flag (not always set, but authoritative when True)
    if job.get("isRemote"):
        return True
    # locationType: "1" = remote, "2" = on-site
    if job.get("locationType") == "1":
        return True

    # atsLocation is the canonical structured location
    ats = job.get("atsLocation") or {}
    country = (ats.get("country") or "").strip()
    if country in _US_COUNTRIES:
        return True

    # Fallback to location.state (US states are identifiable)
    # Only use this when atsLocation.country is missing
    if not country:
        loc = job.get("location") or {}
        state = (loc.get("state") or "").strip()
        # If the state looks like a US state (not None/empty), assume US
        # (BambooHR's location.state is often "California", "New York", etc.)
        if state and len(state) > 1:
            # Heuristic: treat any non-empty state as US when atsLocation.country is absent
            return True

    return False


def _location_str(job: dict) -> str:
    """Build a human-readable location string."""
    ats = job.get("atsLocation") or {}
    loc = job.get("location") or {}

    city = ats.get("city") or loc.get("city") or ""
    state = ats.get("state") or ats.get("province") or loc.get("state") or ""
    country = ats.get("country") or ""

    parts = [p for p in [city, state, country] if p]
    base = ", ".join(parts) if parts else ""

    if job.get("isRemote") or job.get("locationType") == "1":
        return (base + " (Remote)").strip() if base else "Remote"
    return base or "Unknown"


def fetch(company: str, slug: str, **_) -> List[Role]:
    """Fetch US/remote job openings from BambooHR for the given company slug.

    Args:
        company: Human-readable company name.
        slug: BambooHR subdomain slug (e.g. "uphold" for uphold.bamboohr.com).

    Returns:
        List of Role objects filtered to US + remote openings.
        Returns empty list on HTTP errors or non-JSON responses (does not raise).
    """
    url = f"https://{slug}.bamboohr.com/careers/list"
    try:
        r = http_get(url, headers={"Accept": "application/json"})
    except Exception:
        return []

    if r.status_code != 200:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    out: List[Role] = []
    for j in data.get("result") or []:
        if not _is_us_or_remote(j):
            continue

        # Filter to full-time only
        emp_label = (j.get("employmentStatusLabel") or "").lower()
        if emp_label and "full" not in emp_label and "full-time" not in emp_label:
            if emp_label in ("part-time", "part time", "intern", "internship", "contract",
                             "temporary", "casual", "volunteer"):
                continue

        job_id = str(j.get("id", ""))
        title = j.get("jobOpeningName") or ""
        apply_url = f"https://{slug}.bamboohr.com/careers/{job_id}" if job_id else ""

        out.append(Role(
            company=company,
            title=title,
            location=_location_str(j),
            exp_required="exp:unstated",  # BambooHR list API does not expose YOE
            url=apply_url,
            posted_at="",  # not available in list API
            source="bamboohr",
            raw={"id": job_id, "slug": slug, "dept": j.get("departmentLabel")},
        ))

    return out
