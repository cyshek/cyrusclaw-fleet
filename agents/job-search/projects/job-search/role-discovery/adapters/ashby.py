"""Ashby public job board API.

URL: https://api.ashbyhq.com/posting-api/job-board/{slug}
"""
from __future__ import annotations
from typing import List
from core import Role, http_get, parse_experience, strip_html


def fetch(company: str, slug: str, **_) -> List[Role]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    r = http_get(url, params={"includeCompensation": "false"})
    if r.status_code != 200:
        raise RuntimeError(f"ashby[{slug}] HTTP {r.status_code}")
    data = r.json()
    out: List[Role] = []
    for j in data.get("jobs", []):
        loc = j.get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        sec_locs = j.get("secondaryLocations") or []
        if sec_locs:
            extras = []
            for s in sec_locs:
                if isinstance(s, dict):
                    nm = s.get("location") or s.get("name") or ""
                    if nm:
                        extras.append(nm)
                elif isinstance(s, str):
                    extras.append(s)
            if extras:
                loc = loc + " | " + " | ".join(extras)
        desc = strip_html(j.get("descriptionHtml") or j.get("descriptionPlain") or "")
        out.append(Role(
            company=company,
            title=j.get("title", ""),
            location=loc,
            exp_required=parse_experience(desc),
            url=j.get("jobUrl", ""),
            posted_at=(j.get("publishedAt") or "")[:10],
            source="ashby",
            raw={"id": j.get("id")},
        ))
    return out
