"""Rippling-hosted job board (ats.rippling.com).

URL: https://ats.rippling.com/<board-slug>/jobs

Background (chain_027, 2026-05-29 → rippling-adapter-2026-05-30):
  Hammerspace careers page embeds Rippling via:
    <div id="rr-job-board" data-job-board-id="hammerspace">
  + JS embed from `ats.rippling.com`. The real board lives at
  https://ats.rippling.com/<slug>/jobs.

  Direct REST API calls to `ats.rippling.com/api/...` for board listing are
  Cloudflare-protected against anonymous JSON clients. BUT the page-served
  HTML at the `/jobs` index includes a full `__NEXT_DATA__` script with the
  entire job list dehydrated. Path:
    data.props.pageProps.dehydratedState.queries[0].state.data.items
  Each item: {id, name, url, department, locations: [{country, countryCode,
  state, city, workplaceType, name}], language}.

  Per-job JD detail at `/<slug>/jobs/<uuid>` similarly carries
  `__NEXT_DATA__` with `apiData.jobPost.description` (sectioned HTML).

  No paging required for boards up to 20 roles. Larger boards need
  pageSize/page handling — not yet wired (no example tenant >20 roles).

The 'slug' field in companies.yaml maps to the Rippling board id (e.g.
'hammerspace'). The `host` field is optional and ignored — included for
forward compat if Rippling ever splits boards across hosts.
"""
from __future__ import annotations

import json
import re
from typing import Any, List

from core import Role, http_get, parse_experience, strip_html


_NEXT_DATA_RX = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _extract_next_data(html: str) -> dict[str, Any]:
    """Pull and parse the __NEXT_DATA__ JSON blob from a Next.js page."""
    m = _NEXT_DATA_RX.search(html)
    if not m:
        raise RuntimeError("rippling: no __NEXT_DATA__ in page HTML")
    return json.loads(m.group(1))


def _fetch_listing(slug: str) -> list[dict]:
    """Return the dehydrated `items` list from a board's `/jobs` page."""
    url = f"https://ats.rippling.com/{slug}/jobs"
    r = http_get(url, headers={"Accept": "text/html"})
    if r.status_code != 200:
        raise RuntimeError(f"rippling[{slug}] listing HTTP {r.status_code}")
    data = _extract_next_data(r.text)
    queries = (
        data.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [])
    )
    items: list[dict] = []
    for q in queries:
        key = q.get("queryKey") or []
        # The "job-posts" query is the listing; "locations" / "departments"
        # are unrelated.
        if isinstance(key, list) and "job-posts" in key:
            d = (q.get("state") or {}).get("data") or {}
            items = d.get("items") or []
            break
    # Fallback: first query that has items[]
    if not items:
        for q in queries:
            d = (q.get("state") or {}).get("data") or {}
            its = d.get("items") if isinstance(d, dict) else None
            if its:
                items = its
                break
    return items


def _fetch_jd_text(slug: str, job_id: str) -> tuple[str, str]:
    """Fetch a single JD page and return (title, full-text JD).

    Returns ("", "") if the page is missing/unauthorized rather than
    raising — the caller can still build a Role from the listing alone.
    """
    url = f"https://ats.rippling.com/{slug}/jobs/{job_id}"
    try:
        r = http_get(url, headers={"Accept": "text/html"})
        if r.status_code != 200:
            return "", ""
        data = _extract_next_data(r.text)
        api = (
            data.get("props", {})
                .get("pageProps", {})
                .get("apiData", {})
        )
        jp = api.get("jobPost") or {}
        desc = jp.get("description") or {}
        parts: list[str] = []
        # Standard sections, in display order. The schema is stable across
        # tenants verified (Hammerspace). All sections are HTML.
        for section in ("company", "role", "responsibilities", "requirements",
                        "benefits", "additionalInformation", "additional"):
            v = desc.get(section)
            if isinstance(v, str) and v.strip():
                parts.append(strip_html(v))
            elif isinstance(v, dict):
                # Some tenants nest under {value: "..."} or sectioned dicts.
                inner = v.get("value") if "value" in v else None
                if isinstance(inner, str) and inner.strip():
                    parts.append(strip_html(inner))
        # Belt-and-suspenders: if no standard sections found, fall back to
        # any string-valued top-level key.
        if not parts:
            for k, v in desc.items():
                if isinstance(v, str) and v.strip():
                    parts.append(strip_html(v))
        title = jp.get("name") or ""
        return title.strip(), "\n\n".join(parts)
    except Exception:
        return "", ""


def _format_location(item: dict) -> str:
    """Build a human-readable location string from a listing item.

    The listing JSON sometimes shows `workplaceCountry: None` at the
    top level but each entry in `locations[]` carries `country`,
    `countryCode`, `state`, `city`, `workplaceType`. Build something
    parseable by core.is_us_location().
    """
    locs = item.get("locations") or []
    parts: list[str] = []
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        # If the location has a free-text `name` field, prefer that for
        # display ("Remote (TX, US)") but ALSO include the structured
        # country/state so is_us_location() can match.
        name = (loc.get("name") or "").strip()
        city = loc.get("city")
        state = loc.get("state")
        country = loc.get("country") or ""
        wt = (loc.get("workplaceType") or "").upper()

        segments = [s for s in (city, state, country) if s]
        canonical = ", ".join(segments).strip(", ")
        if wt == "REMOTE":
            canonical = (canonical + " (Remote)").strip()
        if name and name != canonical:
            parts.append(f"{name} [{canonical}]" if canonical else name)
        elif canonical:
            parts.append(canonical)
        elif name:
            parts.append(name)
    return " | ".join(parts)


def fetch(company: str, slug: str, *, fetch_jd: bool = False, **_) -> List[Role]:
    """List all open postings on the given Rippling board.

    Args:
      company: display name (must match tracker.md "Company" column).
      slug:    Rippling board id (path segment in `ats.rippling.com/<slug>/jobs`).
      fetch_jd: when True, pull each job's detail page to get the full JD
                body for experience parsing. Slower (1 extra HTTP/job) — leave
                off for bulk crawls and let jd_llm_classifier handle it lazily.
    """
    items = _fetch_listing(slug)
    out: List[Role] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        jid = it.get("id") or ""
        if not jid:
            continue
        title = (it.get("name") or "").strip()
        url = it.get("url") or f"https://ats.rippling.com/{slug}/jobs/{jid}"
        loc = _format_location(it)
        posted = (it.get("createdOn") or it.get("publishedAt") or "")[:10]

        desc_text = ""
        if fetch_jd:
            _t, desc_text = _fetch_jd_text(slug, jid)

        out.append(Role(
            company=company,
            title=title,
            location=loc,
            exp_required=parse_experience(desc_text),
            url=url,
            posted_at=posted,
            source="rippling",
            raw={"id": jid, "slug": slug,
                 "department": (it.get("department") or {}).get("name", "")},
        ))
    return out
