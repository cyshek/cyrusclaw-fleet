"""Uber Careers public search API — discovery-only.

Cyrus's directive (2026-06-01): KEEP DISCOVERING Uber roles (so the tracker
has them and Cyrus can tailor a resume / route a referral), but NEVER
auto-apply. Uber has no standard ATS; it runs a custom careers API. Like the
google adapter, uber-sourced rows are tagged `manual-apply` by tracker_merger
and the careers URL pattern (uber.com/careers/list/...) is not matched by
inline_submit's ATS regexes, so it's double-locked out of any auto-submit.

Data source (curl-friendly from the Azure VM, no Akamai on this endpoint):
  POST https://www.uber.com/api/loadSearchJobsResults?localeCode=en
  headers: Content-Type: application/json, x-csrf-token: x
  body:    {"params":{"query":"<term>"},"page":0,"limit":50}
  -> data.results[] each carries: id, title, location{city,...},
     description (FULL JD text incl. quals), updatedDate.
NOTE: the per-job detail page (uber.com/careers/list/<id>) is 406/Akamai via
curl, but the SEARCH endpoint returns full JD text, so we never need it.
"""
from __future__ import annotations
from typing import List
from core import Role, http_post_json, parse_experience, strip_html

SEARCH_URL = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"

# Title families we discover. The crawler's core/tracker_merger applies the
# title/location/YOE gating downstream (same as every other adapter), so we
# cast a slightly wide net here and let the shared filters trim it.
SEARCH_TERMS = [
    "Product Manager",
    "Program Manager",
    "Technical Program Manager",
    "Product Manager II",
    "Associate Product Manager",
]

LIMIT = 50            # results per query page
MAX_PAGES = 4        # safety cap; Uber paginates `limit` per page
_HEADERS = {"x-csrf-token": "x"}


def _fetch_page(term: str, page: int) -> list:
    body = {"params": {"query": term}, "page": page, "limit": LIMIT}
    r = http_post_json(SEARCH_URL, body, headers=_HEADERS, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"uber HTTP {r.status_code} (page={page}, term='{term}')")
    try:
        return r.json().get("data", {}).get("results", []) or []
    except Exception as e:
        raise RuntimeError(f"uber JSON parse failed (term='{term}'): {e}")


def fetch(company: str, slug: str = "", **_) -> List[Role]:
    seen: dict = {}
    for term in SEARCH_TERMS:
        for page in range(MAX_PAGES):
            results = _fetch_page(term, page)
            if not results:
                break
            for j in results:
                rid = j.get("id")
                if rid is None or rid in seen:
                    continue
                seen[rid] = j
            if len(results) < LIMIT:
                break  # last page for this term

    out: List[Role] = []
    for rid, j in seen.items():
        loc = (j.get("location") or {}).get("city", "") or ""
        region = (j.get("location") or {}).get("region", "") or ""
        if region and loc:
            loc = f"{loc}, {region}"
        desc = strip_html(j.get("description", "") or "")
        out.append(Role(
            company=company,
            title=j.get("title", "") or "",
            location=loc,
            exp_required=parse_experience(desc),
            url=f"https://www.uber.com/careers/list/{rid}/",
            posted_at=(j.get("updatedDate") or "")[:10],
            source="uber",
            raw={"id": rid},
        ))
    return out
