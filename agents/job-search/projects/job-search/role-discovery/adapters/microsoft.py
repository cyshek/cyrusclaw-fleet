"""Microsoft Careers public search — Eightfold PCSX edition.

Cyrus's directive (2026-05-28): we want to discover Microsoft roles too
(he works there, but wants visibility for internal-mobility / tailoring).
Per workspace rules, MS gets the same `manual-apply discovery-only`
treatment as Google: never auto-applied (he's already an employee; any
internal apply goes through Microsoft's internal portal).

API:
  GET https://apply.careers.microsoft.com/api/pcsx/search
      ?domain=microsoft.com
      &query=<term>
      &location=United%20States
      &start=<offset>
      &num=<page-size>   # capped at 10 server-side, value ignored

Response shape: { "status": 200, "data": { "positions": [...], "count": N } }
Position fields used: id, displayJobId, name, locations[], postedTs, positionUrl

Old endpoint `gcsservices.careers.microsoft.com/search/api/v1/search` was
retired and now serves an SSL cert for a different host; their entire SPA
moved to apply.careers.microsoft.com on Eightfold's PCSX (Personalized
Careers Site eXperience) stack. The PCSX `/api/apply/v2/jobs` endpoint
requires a signed token we don't have; the `/api/pcsx/search` endpoint is
the public one the SPA uses for the listing grid and works anonymously
from any IP. Confirmed live 2026-05-29.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from core import Role, http_get


SEARCH_URL = "https://apply.careers.microsoft.com/api/pcsx/search"

SEARCH_TERMS = [
    "product manager",
    "program manager",
    "technical program manager",
    "sales engineer",
    "solutions engineer",
    "solutions architect",
    "customer engineer",
]

# Server returns up to 10 per page regardless of num=. Cap pagination so a
# single misbehaving term can't burn forever.
PAGE_SIZE = 10
MAX_PAGES_PER_TERM = 30  # 300 jobs/term ceiling
REQUEST_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://apply.careers.microsoft.com/careers",
}


def _fetch_page(term: str, start: int) -> dict:
    params = {
        "domain": "microsoft.com",
        "query": term,
        "location": "United States",
        "start": start,
        "num": PAGE_SIZE,
    }
    r = http_get(SEARCH_URL, headers=REQUEST_HEADERS, params=params, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"microsoft HTTP {r.status_code} (start={start}, term='{term}')")
    return r.json()


def _location_string(p: dict) -> str:
    locs = p.get("standardizedLocations") or p.get("locations") or []
    if not isinstance(locs, list):
        return ""
    # Dedup, preserve order; cap at 4 to keep cell readable.
    # MS uses bare "US" as their "Multiple Locations" shorthand;
    # `core.is_us_location` doesn't match that, so normalize it to
    # "United States" so the US filter keeps the row.
    seen, out = set(), []
    for loc in locs:
        if not isinstance(loc, str) or not loc:
            continue
        if loc.strip() == "US":
            loc = "United States"
        if loc not in seen:
            seen.add(loc)
            out.append(loc)
        if len(out) >= 4:
            break
    return "; ".join(out)


def _posted_at(p: dict) -> str:
    ts = p.get("postedTs") or p.get("creationTs")
    if not isinstance(ts, (int, float)):
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, ValueError, OSError):
        return ""


def _url_for(p: dict) -> str:
    # Prefer the SPA deep link the position itself advertises; fall back
    # to the canonical careers URL using displayJobId (the public req id
    # MS uses on its old careers site, still routable on the new one).
    pid = p.get("id")
    did = p.get("displayJobId")
    pos_url = p.get("positionUrl")
    if pos_url and isinstance(pos_url, str) and pos_url.startswith("http"):
        return pos_url
    if pid:
        return f"https://jobs.careers.microsoft.com/global/en/job/{did or pid}"
    return ""


def fetch(company: str = "Microsoft", slug: str = "", **_) -> List[Role]:
    seen: dict[str, dict] = {}
    for term in SEARCH_TERMS:
        try:
            start = 0
            for _ in range(MAX_PAGES_PER_TERM):
                data = _fetch_page(term, start=start)
                positions = ((data.get("data") or {}).get("positions") or [])
                if not positions:
                    break
                new_this_page = 0
                for p in positions:
                    key = str(p.get("id") or p.get("displayJobId") or "")
                    if not key or key in seen:
                        continue
                    seen[key] = p
                    new_this_page += 1
                # PCSX returns same trailing page when start >= count, so
                # bail when no new items.
                if new_this_page == 0:
                    break
                start += PAGE_SIZE
        except RuntimeError as e:
            print(f"  [microsoft] '{term}' failed: {e}")

    out: List[Role] = []
    for _, p in seen.items():
        out.append(Role(
            company="Microsoft",
            title=p.get("name", "") or "",
            location=_location_string(p),
            exp_required="exp:unstated",
            url=_url_for(p),
            posted_at=_posted_at(p),
            source="microsoft",
            raw={"jobId": p.get("id"), "displayJobId": p.get("displayJobId"),
                 "manual_apply_only": True},
        ))
    return out
