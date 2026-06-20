"""Lever public postings API.

URL: https://api.lever.co/v0/postings/{slug}?mode=json
"""
from __future__ import annotations
from typing import List
from datetime import datetime
from core import Role, http_get, parse_experience, strip_html


def fetch(company: str, slug: str, **_) -> List[Role]:
    url = f"https://api.lever.co/v0/postings/{slug}"
    r = http_get(url, params={"mode": "json"})
    if r.status_code != 200:
        raise RuntimeError(f"lever[{slug}] HTTP {r.status_code}")
    data = r.json()
    out: List[Role] = []
    for j in data:
        cat = j.get("categories") or {}
        loc = cat.get("location") or ""
        all_locs = j.get("allLocations") or []
        if all_locs:
            loc = " | ".join(all_locs[:5])
        desc = strip_html((j.get("descriptionPlain") or "") + " " + " ".join(
            (l.get("text", "") if isinstance(l, dict) else "") for l in (j.get("lists") or [])
        ))
        ts = j.get("createdAt")
        posted = ""
        if ts:
            try:
                posted = datetime.utcfromtimestamp(ts / 1000).date().isoformat()
            except Exception:
                pass
        out.append(Role(
            company=company,
            title=j.get("text", ""),
            location=loc,
            exp_required=parse_experience(desc),
            url=j.get("hostedUrl", ""),
            posted_at=posted,
            source="lever",
            raw={"id": j.get("id")},
        ))
    return out
