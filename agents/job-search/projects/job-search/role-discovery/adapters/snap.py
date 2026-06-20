"""Snap Inc. careers public JSON API.

Snap runs a proprietary careers SPA (careers.snap.com) backed by a public
Elasticsearch-style JSON endpoint, with apply handled on Workday
(wd1.myworkdaysite.com/recruiting/snapchat/snap/...). No standard ATS, so it
needs this custom adapter.

Data source (curl-friendly, ~136 jobs full feed, no keyword param honored —
returns everything, filter client-side just like Atlassian):
  GET https://careers.snap.com/api/jobs
  -> {"body":[{"_source":{id,title,primary_location,offices[],absolute_url,
       department,role,employment_type}}]}
The list rows carry NO JD text / YOE, so exp_required is left unstated (the
crawler's gate keeps unstated-exp roles; title/location filters still apply).
"""
from __future__ import annotations
from typing import List
from core import Role, http_get

JOBS_URL = "https://careers.snap.com/api/jobs"


def _loc(src: dict) -> str:
    pl = src.get("primary_location") or ""
    offices = src.get("offices") or []
    if pl:
        # promote primary_location to a "City, State" form if offices match
        for o in offices:
            full = o.get("location", "")
            if full.lower().startswith(pl.lower()):
                return full
        return pl
    return offices[0].get("location", "") if offices else ""


def fetch(company: str, slug: str = "", **_) -> List[Role]:
    r = http_get(JOBS_URL, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"snap HTTP {r.status_code}")
    data = r.json()
    out: List[Role] = []
    for j in data.get("body", []):
        s = j.get("_source", {}) or {}
        title = s.get("title", "") or ""
        if not title:
            continue
        out.append(Role(
            company=company,
            title=title,
            location=_loc(s),
            exp_required="",  # list API exposes no JD text → unstated
            url=s.get("absolute_url", "") or "",
            posted_at="",
            source="snap",
            raw={"id": s.get("id"), "dept": s.get("departments") or s.get("role")},
        ))
    return out
