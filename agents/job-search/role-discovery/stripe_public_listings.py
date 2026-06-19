#!/usr/bin/env python3
"""
stripe_public_listings.py — resolver from Stripe's public Greenhouse board.

Background
----------
Stripe runs a fully public Greenhouse board at
`https://boards-api.greenhouse.io/v1/boards/stripe/jobs` (~500 jobs as of
2026-05-24). The GH `id` is the same numeric token that Stripe surfaces in
its `data-ghid` / `ghJobPostId` markers and in `?gh_jid=<id>` query strings.

Stripe also exposes per-role pages at three known shapes:

  * Apply URL (the wrapper that loads the GH embed):
      https://stripe.com/jobs/listing/<slug>/<gh_jid>/apply
  * Listing detail (JD):
      https://stripe.com/jobs/listing/<slug>/<gh_jid>
  * Search-with-gh_jid (301 -> listing detail):
      https://stripe.com/jobs/search?gh_jid=<gh_jid>

The slug Stripe uses is NOT in the GH API — it's derived from the title or
read off `absolute_url`. The GH API's `absolute_url` for stripe jobs points
at `stripe.com/jobs/search?gh_jid=<id>`, which 301s to the slugged page.

LinkedIn-side tracker rows are keyed by LinkedIn JIDs (10-digit) which are
UNRELATED to Stripe gh_jid. The only signal we have is title + (location,
city/region). This script does a fuzzy match.

Output
------
Writes `applications/dryrun/_stripe-public-listings.json` with:

  {
    "fetched_at": "<iso>",
    "total_active": <int>,
    "listings": [
        {"gh_jid": "7901987", "title": "...", "loc": "...", "slug": "...",
         "apply_url": "https://stripe.com/jobs/listing/<slug>/<id>/apply",
         "search_url": "https://stripe.com/jobs/search?gh_jid=<id>",
         "gh_api_url": ".../boards/stripe/jobs/<id>"},
        ...
    ]
  }

CLI
---

  python stripe_public_listings.py                 # refresh cache only
  python stripe_public_listings.py --resolve       # also fuzzy-match tracker open Stripe rows
  python stripe_public_listings.py --resolve --apply
                                                    # ... and update tracker.db (after backup)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT  # projects/job-search
WORKSPACE = ROOT.parent.parent  # workspace root
TRACKER = PROJ / "tracker.db"
DRYRUN = PROJ / "applications" / "dryrun"
CACHE = DRYRUN / "_stripe-public-listings.json"

GH_BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/stripe/jobs"

# Map from a city/state token in LinkedIn loc -> a normalized location keyword
# that appears in the Stripe GH job's `location.name`.
LOC_TOKENS = {
    "san francisco": ["sf", "san francisco", "south san francisco"],
    "seattle": ["sea", "seattle"],
    "new york": ["ny", "nyc", "new york"],
    "chicago": ["chicago"],
    "remote": ["remote"],
}


def fetch_stripe_listings(timeout: int = 30) -> dict:
    r = requests.get(GH_BOARD_URL, timeout=timeout)
    r.raise_for_status()
    return r.json()


def derive_slug(title: str) -> str:
    """Derive Stripe's slug from a role title.

    Stripe's slugs lowercase the title, strip punctuation, and replace runs of
    non-alphanumeric chars with single '-'. Smoke-tested on
    `account-executive-enterprise-germany/7825578` and matches Stripe's pages.
    """
    s = title.lower()
    # Replace common ampersand
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def build_listing(job: dict) -> dict:
    gh_jid = str(job["id"])
    title = job["title"]
    loc = (job.get("location") or {}).get("name", "") or ""
    slug = derive_slug(title)
    return {
        "gh_jid": gh_jid,
        "title": title,
        "loc": loc,
        "slug": slug,
        "apply_url": f"https://stripe.com/jobs/listing/{slug}/{gh_jid}/apply",
        "listing_url": f"https://stripe.com/jobs/listing/{slug}/{gh_jid}",
        "search_url": f"https://stripe.com/jobs/search?gh_jid={gh_jid}",
        "gh_api_url": f"https://boards-api.greenhouse.io/v1/boards/stripe/jobs/{gh_jid}",
        "gh_embed_url": f"https://job-boards.greenhouse.io/embed/job_app?for=stripe&token={gh_jid}",
    }


def refresh_cache(verbose: bool = True) -> dict:
    if verbose:
        print(f"[stripe-listings] fetching {GH_BOARD_URL}", file=sys.stderr)
    data = fetch_stripe_listings()
    jobs = data.get("jobs") or []
    listings = [build_listing(j) for j in jobs]
    out = {
        "fetched_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_active": len(listings),
        "listings": listings,
    }
    DRYRUN.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, indent=2))
    if verbose:
        print(f"[stripe-listings] cached {len(listings)} listings -> {CACHE}", file=sys.stderr)
    return out


def load_cache(stale_hours: int = 24, refresh_if_stale: bool = True) -> dict:
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text())
            ts = dt.datetime.fromisoformat(d["fetched_at"].rstrip("Z"))
            age = (dt.datetime.utcnow() - ts).total_seconds() / 3600
            if age < stale_hours or not refresh_if_stale:
                return d
        except Exception:
            pass
    return refresh_cache()


# --- matching -----------------------------------------------------------------

def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t.lower())).strip()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def loc_overlap(li_loc: str, stripe_loc: str) -> bool:
    li = li_loc.lower()
    sl = stripe_loc.lower()
    for canonical, tokens in LOC_TOKENS.items():
        if any(t in li for t in tokens) and any(t in sl for t in tokens):
            return True
    return False


def fuzzy_match(
    tracker_row: dict, listings: List[dict], min_score: float = 0.78
) -> List[dict]:
    """Return ranked listing matches for a tracker row (best-first)."""
    candidates: List[tuple] = []
    for lst in listings:
        score = title_similarity(tracker_row["role"], lst["title"])
        if score < min_score:
            continue
        bonus = 0.0
        # location bonus if any city token overlaps
        if tracker_row.get("loc") and loc_overlap(tracker_row["loc"], lst["loc"]):
            bonus += 0.10
        # exact-title bonus
        if norm_title(tracker_row["role"]) == norm_title(lst["title"]):
            bonus += 0.05
        candidates.append((score + bonus, score, lst))
    candidates.sort(key=lambda x: -x[0])
    return [
        {"score": round(s, 3), "title_score": round(ts, 3), **lst}
        for s, ts, lst in candidates
    ]


# --- tracker integration ------------------------------------------------------

def get_open_stripe_rows() -> List[dict]:
    c = sqlite3.connect(TRACKER)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        """SELECT id, source_key, company, role, loc, jd_url, app_url, status, applied_by, agent_notes
           FROM roles
           WHERE company='Stripe' AND status='' AND applied_by IS NULL
           ORDER BY id"""
    ).fetchall()
    return [dict(r) for r in rows]


def backup_tracker(tag: str = "stripe-resolver") -> Path:
    today = dt.date.today().strftime("%Y%m%d")
    bak = TRACKER.with_suffix(f".db.bak.{today}-{tag}")
    if not bak.exists():
        shutil.copy2(TRACKER, bak)
    return bak


def apply_matches(matches: List[dict], dry_run: bool = False) -> List[dict]:
    """For each tracker row with a unique high-confidence match, update jd_url + app_url.

    Skips rows with ambiguous (multiple) matches or no match.
    Returns the list of update actions.
    """
    actions: List[dict] = []
    if not dry_run:
        backup_tracker()
    c = sqlite3.connect(TRACKER)
    try:
        for m in matches:
            row = m["row"]
            cands = m["candidates"]
            if len(cands) != 1:
                continue
            top = cands[0]
            apply_url = top["apply_url"]
            listing_url = top["listing_url"]
            action = {
                "id": row["id"],
                "role": row["role"],
                "from_jd": row["jd_url"],
                "from_app": row["app_url"],
                "to_jd": listing_url,
                "to_app": apply_url,
                "gh_jid": top["gh_jid"],
                "score": top["score"],
            }
            actions.append(action)
            if not dry_run:
                # Preserve the LinkedIn URL as a note in agent_notes (idempotent: only add a marker
                # if there's no `linkedin_url_pre_stripe_resolver=` marker yet AND the current jd_url
                # is a LinkedIn URL (otherwise we'd be saving a stale value on rerun).
                cur = c.execute(
                    "SELECT agent_notes FROM roles WHERE id=?", (row["id"],)
                ).fetchone()
                existing_notes = (cur[0] or "") if cur else ""
                marker_key = "linkedin_url_pre_stripe_resolver="
                new_notes = existing_notes
                if (
                    marker_key not in existing_notes
                    and row["jd_url"]
                    and "linkedin.com" in row["jd_url"]
                ):
                    marker = f"{marker_key}{row['jd_url']}"
                    sep = "" if not existing_notes else "\n"
                    new_notes = f"{existing_notes}{sep}{marker}"
                c.execute(
                    """UPDATE roles
                       SET jd_url=?, app_url=?, agent_notes=?
                       WHERE id=?""",
                    (listing_url, apply_url, new_notes, row["id"]),
                )
        if not dry_run:
            c.commit()
    finally:
        c.close()
    return actions


# --- CLI ----------------------------------------------------------------------

def cmd_resolve(verbose: bool, apply: bool) -> dict:
    data = load_cache(refresh_if_stale=True)
    listings = data["listings"]
    rows = get_open_stripe_rows()
    matches = []
    for row in rows:
        cands = fuzzy_match(row, listings)
        # Promote a single confident match: top is exact-title (>=1.10) AND clearly ahead of #2.
        # Norm-equal titles get +0.05; loc-overlap gets +0.10. So exact-title+loc -> 1.15.
        # If top.title_score == 1.0 (exact normalized title match) treat as unique.
        if cands and cands[0].get("title_score", 0) >= 0.999:
            cands = [cands[0]]
        matches.append({"row": row, "candidates": cands})

    # console report
    print(f"== Stripe public-listings resolver ==", file=sys.stderr)
    print(f"  cache: {CACHE} ({data['total_active']} active listings, fetched {data['fetched_at']})", file=sys.stderr)
    print(f"  open Stripe tracker rows: {len(rows)}", file=sys.stderr)
    print(file=sys.stderr)
    summary = {"resolved": [], "ambiguous": [], "unmatched": []}
    for m in matches:
        row = m["row"]
        cands = m["candidates"]
        header = f"id={row['id']} {row['role']!r} loc={row['loc']!r}"
        if len(cands) == 1:
            top = cands[0]
            print(f"[OK] {header}", file=sys.stderr)
            print(f"     -> {top['title']!r} loc={top['loc']!r}  score={top['score']}  gh_jid={top['gh_jid']}", file=sys.stderr)
            print(f"     -> {top['apply_url']}", file=sys.stderr)
            summary["resolved"].append({"id": row["id"], "gh_jid": top["gh_jid"], "score": top["score"]})
        elif len(cands) > 1:
            print(f"[AMBIGUOUS] {header}  ({len(cands)} candidates)", file=sys.stderr)
            for c in cands[:4]:
                print(f"     ? {c['title']!r} loc={c['loc']!r}  score={c['score']}  gh_jid={c['gh_jid']}", file=sys.stderr)
            summary["ambiguous"].append({"id": row["id"], "count": len(cands), "top_gh_jids": [c["gh_jid"] for c in cands[:5]]})
        else:
            print(f"[NO MATCH] {header}", file=sys.stderr)
            summary["unmatched"].append({"id": row["id"], "role": row["role"], "loc": row["loc"]})

    result = {
        "matches": [
            {"row": m["row"], "candidates": m["candidates"]} for m in matches
        ],
        "summary": summary,
    }

    if apply:
        actions = apply_matches(matches, dry_run=False)
        print(file=sys.stderr)
        print(f"[apply] backed up tracker.db; updated {len(actions)} rows", file=sys.stderr)
        for a in actions:
            print(f"  id={a['id']} jd_url -> {a['to_jd']}", file=sys.stderr)
        result["applied_updates"] = actions

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="force refresh cache")
    ap.add_argument("--resolve", action="store_true", help="match against tracker open Stripe rows")
    ap.add_argument("--apply", action="store_true", help="with --resolve, also update tracker.db (jd_url+app_url)")
    ap.add_argument("--json", action="store_true", help="emit JSON of result")
    args = ap.parse_args()

    if args.refresh:
        refresh_cache()
    if args.resolve:
        res = cmd_resolve(verbose=True, apply=args.apply)
        if args.json:
            print(json.dumps(res, indent=2, default=str))
    elif not args.refresh:
        # default: refresh + print summary
        data = refresh_cache()
        print(json.dumps({"total_active": data["total_active"], "cache": str(CACHE)}, indent=2))


if __name__ == "__main__":
    main()
