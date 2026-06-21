"""RemoteOK job board API.

URL: https://remoteok.com/api?tag={slug}

Supported slugs: product-manager, technical-program-manager, program-manager,
                 solutions-engineer, solutions-architect, customer-success-manager

Note: The API returns a JSON array where the FIRST element is a legal-notice
dict (keys "legal"), not a job. Skip it. Subsequent elements are job objects.

Job fields: id (str), position (str), company (str), url (str), apply_url (str),
            tags (list), location (str), epoch (int), date (str), description (str)

source_key: remoteok:<job_id>  (handled in tracker_merger)
"""
from __future__ import annotations
from datetime import datetime
from typing import List
from core import Role, http_get, parse_experience, strip_html

_REMOTEOK_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"


def fetch(company: str, slug: str, **kwargs) -> List[Role]:
    """Fetch jobs from RemoteOK for the given tag slug.

    Args:
        company: Human-readable name (e.g. "RemoteOK (PM)") — not used for API call.
        slug: RemoteOK tag, e.g. "product-manager", "solutions-engineer".
    """
    url = f"https://remoteok.com/api?tag={slug}"
    r = http_get(url, headers={"User-Agent": _REMOTEOK_UA})
    if r.status_code != 200:
        raise RuntimeError(f"remoteok[{slug}] HTTP {r.status_code}")

    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"remoteok[{slug}] unexpected response type: {type(data)}")

    out: List[Role] = []
    for item in data:
        # Skip the legal notice dict (first element, has 'legal' key or no 'id')
        if not isinstance(item, dict):
            continue
        job_id = item.get("id")
        if not job_id or "legal" in item:
            continue

        # Location: RemoteOK reports "Remote" / "" / specific region
        loc = item.get("location") or "Remote"

        # Prefer apply_url; fall back to url
        apply_url = item.get("apply_url") or item.get("url", "")

        desc = strip_html(item.get("description") or "")

        # Date: prefer ISO date string; fall back to epoch
        posted = ""
        raw_date = item.get("date") or ""
        if raw_date and len(raw_date) >= 10:
            posted = raw_date[:10]
        elif item.get("epoch"):
            try:
                posted = datetime.utcfromtimestamp(int(item["epoch"])).date().isoformat()
            except Exception:
                pass

        out.append(Role(
            company=item.get("company") or company,
            title=item.get("position", ""),
            location=loc,
            exp_required=parse_experience(desc),
            url=apply_url,
            posted_at=posted,
            source="remoteok",
            raw={"id": str(job_id), "slug": slug},
        ))
    return out
