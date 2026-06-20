"""ByteDance + TikTok careers public API — discovery-only, referral-hold.

Cyrus has a REFERRAL (links + code CY6MGWW, stored in
projects/job-search/.referrals.json). So these go the "Uber way": discover +
email Cyrus the matches with HIS referral link, NEVER auto-apply (applying
without the referral would cost him the referral credit). tracker_merger tags
bytedance/tiktok rows manual-apply + discovery-only, and the referral email
step routes them to him.

Both brands share ONE backend. The unlock (found 2026-06-01 by capturing the
SPA's fetch) is two headers the careers SPA sends:
    website-path: en          (ByteDance)  /  tiktok  (TikTok)
    x-tt-env: boe_epam_api
Without them the endpoint returns 400 "invalid request".

  POST https://jobs.bytedance.com/api/v1/public/supplier/search/job/posts   (ByteDance)
  POST https://lifeattiktok.com/api/v1/public/supplier/search/job/posts     (TikTok)
  body: {"recruitment_id_list":[],"job_category_id_list":[],"subject_id_list":[],
         "location_code_list":[],"keyword":"<q>","limit":N,"offset":M}
  -> data.job_post_list[] each carries: id, code, title, description,
     requirement, recruit_type{en_name}, job_category{en_name}, city_info
     (nested code/en_name + parent chain up to country), vacancies.
Full JD text lives in description + requirement, so parse_experience works.
"""
from __future__ import annotations
from typing import List
from core import Role, http_post_json, parse_experience, strip_html

# (host, website-path header, public apply/detail base) per brand.
_BRANDS = {
    "bytedance": ("jobs.bytedance.com", "en",
                  "https://jobs.bytedance.com/en/position/{id}/detail"),
    "tiktok":    ("lifeattiktok.com", "tiktok",
                  "https://lifeattiktok.com/position/{id}/detail"),
}

SEARCH_TERMS = [
    "product manager",
    "program manager",
    "technical program manager",
    "product manager II",
]
LIMIT = 50
MAX_PAGES = 4


def _country(city_info: dict) -> str:
    """Walk the city_info parent chain to the country en_name."""
    node = city_info or {}
    last = ""
    while node:
        en = node.get("en_name") or ""
        if node.get("location_type") == 1 and en:
            return en
        last = en or last
        node = node.get("parent") or {}
    return last


def _loc(city_info: dict) -> str:
    ci = city_info or {}
    city = ci.get("en_name") or ""
    parent = ci.get("parent") or {}
    state = parent.get("en_name") if parent.get("location_type") == 2 else ""
    if city and state and state.lower() not in ("united states of america",):
        return f"{city}, {state}"
    return city or _country(ci)


def _fetch_brand(brand: str, company: str) -> List[Role]:
    host, wpath, apply_tpl = _BRANDS[brand]
    url = f"https://{host}/api/v1/public/supplier/search/job/posts"
    headers = {
        "accept-language": "en-US",
        "website-path": wpath,
        "x-tt-env": "boe_epam_api",
        "origin": f"https://{host}",
        "referer": f"https://{host}/",
    }
    seen: dict = {}
    for term in SEARCH_TERMS:
        for page in range(MAX_PAGES):
            body = {"recruitment_id_list": [], "job_category_id_list": [],
                    "subject_id_list": [], "location_code_list": [],
                    "keyword": term, "limit": LIMIT, "offset": page * LIMIT}
            r = http_post_json(url, body, headers=headers, timeout=45)
            if r.status_code != 200:
                raise RuntimeError(f"{brand} HTTP {r.status_code} (term='{term}')")
            data = (r.json() or {}).get("data") or {}
            jl = data.get("job_post_list") or []
            if not jl:
                break
            for j in jl:
                jid = j.get("id")
                if jid and jid not in seen:
                    seen[jid] = j
            if len(jl) < LIMIT:
                break

    out: List[Role] = []
    for jid, j in seen.items():
        # Skip internships — Cyrus wants full-time IC roles.
        rt = ((j.get("recruit_type") or {}).get("en_name") or "").lower()
        if "intern" in rt:
            continue
        jd = strip_html((j.get("description") or "") + "\n" + (j.get("requirement") or ""))
        out.append(Role(
            company=company,
            title=j.get("title", "") or "",
            location=_loc(j.get("city_info")),
            exp_required=parse_experience(jd),
            url=apply_tpl.format(id=jid),
            posted_at="",
            source=brand,
            raw={"id": jid, "code": j.get("code"),
                 "category": (j.get("job_category") or {}).get("en_name")},
        ))
    return out


def fetch_bytedance(company: str, slug: str = "", **_) -> List[Role]:
    return _fetch_brand("bytedance", company)


def fetch_tiktok(company: str, slug: str = "", **_) -> List[Role]:
    return _fetch_brand("tiktok", company)
