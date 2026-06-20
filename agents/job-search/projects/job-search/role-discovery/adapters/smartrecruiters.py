"""SmartRecruiters public postings API.

URL: https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0
"""
from __future__ import annotations
from typing import List
from core import Role, http_get, parse_experience, strip_html


def fetch(company: str, slug: str, **_) -> List[Role]:
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    out: List[Role] = []
    offset = 0
    while True:
        r = http_get(url, params={"limit": 100, "offset": offset})
        if r.status_code != 200:
            raise RuntimeError(f"smartrecruiters[{slug}] HTTP {r.status_code}")
        data = r.json()
        items = data.get("content", []) or []
        for j in items:
            loc = j.get("location") or {}
            loc_str = ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")]))
            out.append(Role(
                company=company,
                title=j.get("name", ""),
                location=loc_str,
                exp_required="exp:unstated",  # not in list
                url=j.get("ref", ""),
                posted_at=(j.get("releasedDate") or "")[:10],
                source="smartrecruiters",
                raw={"id": j.get("id")},
            ))
        total = data.get("totalFound", len(out))
        offset += len(items)
        if not items or offset >= total or offset >= 500:
            break
    return out
