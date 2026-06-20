"""Greenhouse public job board API.

URL: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
"""
from __future__ import annotations
from typing import List
from core import Role, http_get, parse_experience, strip_html


def fetch(company: str, slug: str, **_) -> List[Role]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    r = http_get(url, params={"content": "true"})
    if r.status_code != 200:
        raise RuntimeError(f"greenhouse[{slug}] HTTP {r.status_code}")
    data = r.json()
    out: List[Role] = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        desc = strip_html(j.get("content", ""))
        out.append(Role(
            company=company,
            title=j.get("title", ""),
            location=loc,
            exp_required=parse_experience(desc),
            url=j.get("absolute_url", ""),
            posted_at=(j.get("updated_at") or j.get("first_published") or "")[:10],
            source="greenhouse",
            raw={"id": j.get("id")},
        ))
    return out
