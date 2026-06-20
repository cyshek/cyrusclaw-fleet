"""Eightfold PCSX public jobs API adapter (reusable across Eightfold tenants).

Many large employers run their careers site on Eightfold's "Personalized
Careers Site eXperience" (PCSX) stack. The public listing grid the SPA uses
is the v2 jobs endpoint:

  GET https://<host>/api/apply/v2/jobs
      ?domain=<domain>
      &query=<term>
      &start=<offset>
      &num=<page-size>

Response shape: { ..., "positions": [...], "count": N }
Position fields used: id, name/posting_name, location, locations[],
display_job_id, ats_job_id, canonicalPositionUrl, t_update/t_create,
department, work_location_option.

This adapter is NOT Netflix-hardcoded. The Eightfold `domain` + `host` are
passed in via companies.yaml opts so the same code serves any Eightfold
tenant:
    Netflix  -> domain=netflix.com, host=explore.jobs.netflix.net

(Microsoft also runs Eightfold but via the `/api/pcsx/search` variant on
apply.careers.microsoft.com; that tenant keeps its dedicated `microsoft.py`
adapter. This one targets the `/api/apply/v2/jobs` listing API which Netflix
serves anonymously. Confirmed live 2026-06-08, count≈215.)
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List
import time

from core import Role, http_get


# Search terms mirror the qualifying-title families so we surface the same
# role classes the title gate keeps. Eightfold does fuzzy matching, so a
# handful of broad terms is enough; dedupe by position id across terms.
SEARCH_TERMS = [
    "product manager",
    "program manager",
    "technical program manager",
    "solutions engineer",
    "sales engineer",
    "solutions architect",
    "customer engineer",
]

PAGE_SIZE = 10  # server caps num=10 regardless of request
# Hard ceiling on total page fetches across ALL terms so a misbehaving tenant
# can't burn forever. 300 fetches * 10 = up to 3000 position-reads, plenty for
# a ~215-job board with 7 terms.
MAX_TOTAL_FETCHES = 300
MAX_PAGES_PER_TERM = 40  # 400 jobs/term ceiling

REQUEST_HEADERS = {
    "Accept": "application/json",
}


def _fetch_page(host: str, domain: str, term: str, start: int) -> dict:
    url = f"https://{host}/api/apply/v2/jobs"
    params = {
        "domain": domain,
        "query": term,
        "start": start,
        "num": PAGE_SIZE,
    }
    headers = dict(REQUEST_HEADERS)
    headers["Referer"] = f"https://{host}/careers"
    r = http_get(url, headers=headers, params=params, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(
            f"eightfold[{host}] HTTP {r.status_code} (start={start}, term='{term}')"
        )
    return r.json()


def _location_string(p: dict) -> str:
    """Join the position's location list, deduped, capped at 4 slots.

    Eightfold formats each location as "City,State,Country" with no spaces
    after commas (e.g. "Los Gatos,California,United States of America").
    core.is_us_location matches on "united states" / city / ", XX" state
    code, so the raw Eightfold strings already pass for US roles. We leave
    them as-is (just normalize comma spacing for readability) and join with
    "; " which is one of core's multi-location separators.
    """
    locs = p.get("locations")
    if not isinstance(locs, list) or not locs:
        single = p.get("location")
        locs = [single] if isinstance(single, str) and single else []
    seen, out = set(), []
    for loc in locs:
        if not isinstance(loc, str) or not loc.strip():
            continue
        # "City,State,Country" -> "City, State, Country" (readability only;
        # does not affect the US matcher which is substring/regex based).
        norm = ", ".join(part.strip() for part in loc.split(",") if part.strip())
        # Eightfold's remote shorthand "USA - Remote" / "USA Remote" has a
        # bare leading "USA" that core.is_us_location does NOT match (its US
        # markers require " usa" with a leading space or "(usa)"). Normalize
        # the leading token to "United States" so genuine US-remote roles pass
        # the gate, mirroring microsoft.py's bare-"US" normalization. We only
        # touch a leading USA token to avoid mangling "...United States...".
        low = norm.lower()
        if low == "usa" or low.startswith("usa -") or low.startswith("usa,") \
                or low.startswith("usa "):
            norm = "United States" + norm[3:]
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
        if len(out) >= 4:
            break
    return "; ".join(out)


def _posted_at(p: dict) -> str:
    ts = p.get("t_update") or p.get("t_create")
    if not isinstance(ts, (int, float)):
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, ValueError, OSError):
        return ""


def _url_for(host: str, p: dict) -> str:
    """Stable application/posting URL for the position."""
    canon = p.get("canonicalPositionUrl")
    if isinstance(canon, str) and canon.startswith("http"):
        return canon
    pid = p.get("id")
    if pid:
        return f"https://{host}/careers/job/{pid}"
    return ""


def fetch(company: str, slug: str = "", **opts) -> List[Role]:
    """Paginate the Eightfold v2 jobs API for an Eightfold tenant.

    opts (from companies.yaml) carry the tenant identity so this adapter is
    reusable:
        domain : Eightfold domain query param (e.g. "netflix.com")
        host   : Eightfold host (e.g. "explore.jobs.netflix.net")

    Falls back to deriving from `slug` if opts not given:
        slug "netflix.com|explore.jobs.netflix.net" or just a host.
    """
    domain = opts.get("domain") or ""
    host = opts.get("host") or ""
    # Backstop: allow slug to carry "domain|host" or a bare host.
    if (not domain or not host) and slug:
        if "|" in slug:
            d, h = slug.split("|", 1)
            domain = domain or d.strip()
            host = host or h.strip()
        elif "." in slug and "/" not in slug:
            host = host or slug.strip()
    if not host:
        raise RuntimeError(
            f"eightfold[{company}]: no host (set opts host=... in companies.yaml)"
        )
    if not domain:
        # Domain often == registrable part of host's parent; safest to require
        # it explicitly, but fall back to host so a single-arg config still runs.
        domain = host

    seen: dict[str, dict] = {}
    total_fetches = 0
    declared_count = None

    for term in SEARCH_TERMS:
        if total_fetches >= MAX_TOTAL_FETCHES:
            break
        try:
            start = 0
            for _ in range(MAX_PAGES_PER_TERM):
                if total_fetches >= MAX_TOTAL_FETCHES:
                    break
                data = _fetch_page(host, domain, term, start=start)
                total_fetches += 1
                if declared_count is None:
                    c = data.get("count")
                    if isinstance(c, int):
                        declared_count = c
                positions = data.get("positions") or []
                if not positions:
                    break
                new_this_page = 0
                for p in positions:
                    key = str(p.get("id") or p.get("ats_job_id")
                              or p.get("display_job_id") or "")
                    if not key or key in seen:
                        continue
                    seen[key] = p
                    new_this_page += 1
                # Eightfold returns the trailing page repeatedly once
                # start >= count, so stop when a full page yields nothing new.
                if new_this_page == 0:
                    break
                start += PAGE_SIZE
                # Polite jitter between page fetches.
                time.sleep(0.3 + 0.5 * (total_fetches % 2) * 0.5)
        except RuntimeError as e:
            print(f"  [eightfold:{host}] '{term}' failed: {e}")

    out: List[Role] = []
    for _, p in seen.items():
        title = p.get("name") or p.get("posting_name") or ""
        out.append(Role(
            company=company,
            title=title,
            location=_location_string(p),
            exp_required="exp:unstated",  # listing API carries no JD text/YOE
            url=_url_for(host, p),
            posted_at=_posted_at(p),
            source="eightfold",
            raw={
                "id": p.get("id"),
                "display_job_id": p.get("display_job_id"),
                "ats_job_id": p.get("ats_job_id"),
                "department": p.get("department"),
                "eightfold_host": host,
            },
        ))
    return out
