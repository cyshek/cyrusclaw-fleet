"""Workable public widget API.

Workable is a per-company hosted ATS (like greenhouse/ashby/lever): there is no
global "search all Workable jobs" endpoint, so each Workable company must be
listed in companies.yaml with adapter=workable and slug=<account-slug>.

Jobs-list endpoint (public, no auth):
  https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true
    -> {"name", "description", "jobs": [{title, application_url, city, state,
        country, telecommuting, published_on, experience, function, ...}]}

The per-role `application_url` (.../j/<shortcode>/apply) is what
`_workable_runner.py` submits to. Workable apply forms are gated by a
Cloudflare Turnstile (token-accepting) which the 2Captcha stack clears
(proven live 2026-06-03: Last Call Media, Unusual Machines), so discovered
Workable roles are AUTO-SUBMITTABLE, not manual-only.

Smoke test:
    python adapters/workable.py --smoke   # uses a known-good slug, expects >=1 job
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Role, http_get, parse_experience, strip_html  # noqa: E402

WIDGET_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


def _location(j: dict) -> str:
    locs = j.get("locations") or []
    if locs:
        parts = []
        for l in locs[:5]:
            seg = ", ".join(x for x in (l.get("city"), l.get("region") or l.get("state"),
                                        l.get("country")) if x)
            if seg:
                parts.append(seg)
        if parts:
            base = " | ".join(parts)
            return base + (" (Remote)" if j.get("telecommuting") else "")
    seg = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
    if j.get("telecommuting"):
        seg = (seg + " (Remote)").strip() if seg else "Remote"
    return seg


def fetch(company: str, slug: str, **_) -> List[Role]:
    url = WIDGET_URL.format(slug=slug)
    r = http_get(url, params={"details": "true"})
    if r.status_code != 200:
        raise RuntimeError(f"workable[{slug}] HTTP {r.status_code}")
    data = r.json()
    out: List[Role] = []
    for j in data.get("jobs", []) or []:
        desc = strip_html(j.get("description") or "")
        # Workable also ships a coarse "experience" label (Associate/Mid/Senior);
        # prefer a parsed YOE from the description, fall back to 0 (unknown).
        exp = parse_experience(desc)
        apply_url = j.get("application_url") or j.get("url") or j.get("shortlink") or ""
        out.append(Role(
            company=company,
            title=j.get("title", ""),
            location=_location(j),
            exp_required=exp,
            url=apply_url,
            posted_at=(j.get("published_on") or j.get("created_at") or "")[:10],
            source="workable",
            raw={"shortcode": j.get("shortcode"), "code": j.get("code"),
                 "experience": j.get("experience"), "function": j.get("function")},
        ))
    return out


def _smoke() -> int:
    # Last Call Media is a known stable Workable account.
    try:
        roles = fetch("Last Call Media", "lastcallmedia")
    except Exception as e:
        print(f"SMOKE FAIL: {e}", file=sys.stderr)
        return 1
    print(f"workable smoke: {len(roles)} role(s) for lastcallmedia")
    for r in roles[:5]:
        print(f"  - {r.title} | {r.location} | {r.url}")
    return 0 if roles else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--slug", help="probe an arbitrary Workable account slug")
    a = ap.parse_args()
    if a.slug:
        for r in fetch(a.slug, a.slug):
            print(f"{r.title} | {r.location} | {r.url}")
    else:
        sys.exit(_smoke())
