"""li_company_slug_resolver.py — grow companies.yaml from LinkedIn-source leads.

LinkedIn discovery surfaces real, actively-hiring companies but stores only the
LinkedIn URL. Many of those companies ALSO run a public Greenhouse/Ashby/Lever
board we could crawl directly every week — we just never resolved the slug.

This script:
  1. Pulls distinct company names from LinkedIn-source tracker rows.
  2. Drops any already in companies.yaml (normalized-name match).
  3. Filters noise: staffing firms (staffing_blocklist), company-blocklist
     (Google/MS/Amazon via jd_llm_classifier), and obvious big-corp names that
     won't run a startup ATS (heuristic, conservative).
  4. Probes each survivor through the PROVEN bulk_discover_slugs.probe()
     across Greenhouse/Ashby/Lever slug variants.
  5. Emits merge-ready yaml entries (and optionally appends with --apply).

Zero new infra — reuses the same slug-probe path yc_discover.py uses.

Usage:
  python li_company_slug_resolver.py --dry-run [--limit N] [--workers 12]
  python li_company_slug_resolver.py --apply  [--limit N]
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).parent
DB = ROOT.parent / "tracker.db"
YAML_PATH = ROOT / "companies.yaml"

from bulk_discover_slugs import probe, slug_variants  # noqa: E402

# Optional filters — import defensively so the script still runs if a module moves.
try:
    from staffing_blocklist import is_staffing_firm
except Exception:  # pragma: no cover
    def is_staffing_firm(_name: str) -> bool:
        return False

try:
    from jd_llm_classifier import company_is_blocked
except Exception:  # pragma: no cover
    def company_is_blocked(_name: str) -> bool:
        return False

# Conservative big-corp / non-startup-ATS heuristic. These almost never run a
# public Greenhouse/Ashby/Lever board; probing them just wastes requests and
# risks a wrong-slug false positive. Kept tight on purpose.
_BIGCORP_RE = re.compile(
    r"\b(corporation|incorporated|holdings|group|systems inc|industries|"
    r"manufacturing|bearing|steel|sheetmetal|electric co|insurance|bank|"
    r"financial services|consulting|solutions llc|services llc|llc|l\.l\.c)\b",
    re.I,
)
# Known mega-caps that have boards but NOT on these ATSes (skip to cut noise).
_MEGACAP = {
    "amd", "abbott", "acorns", "intel", "nvidia", "salesforce", "adobe",
    "paypal", "cisco", "oracle", "sap", "ibm", "dell", "hp", "hpe",
    "qualcomm", "broadcom", "texas instruments", "ge", "ge aerospace",
}
# Job-board AGGREGATORS / reposters — a board here is NOT a single employer; it
# cross-posts many companies' roles and would pollute the tracker. Skip by name.
_AGGREGATORS = {
    "jobgether", "jobright", "remoteok", "weworkremotely", "builtin",
    "otta", "wellfound", "angellist", "ziprecruiter", "lensa", "jobot",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_existing_names(yaml_path: Path = YAML_PATH) -> set:
    d = yaml.safe_load(yaml_path.read_text())
    cos = d if isinstance(d, list) else d.get("companies", d)
    names = set()
    for c in cos:
        if isinstance(c, dict) and c.get("name"):
            names.add(norm(c["name"]))
    return names


def li_source_companies(db: Path = DB) -> List[str]:
    c = sqlite3.connect(str(db))
    try:
        rows = c.execute(
            """SELECT DISTINCT company FROM roles
               WHERE (app_url LIKE '%linkedin.com%' OR source_key LIKE '%linkedin%')
                 AND company IS NOT NULL AND TRIM(company)!=''"""
        ).fetchall()
    finally:
        c.close()
    return sorted({r[0].strip() for r in rows})


def should_skip(name: str) -> Optional[str]:
    """Return a reason string if this company should be skipped, else None."""
    low = name.lower().strip()
    if len(norm(name)) < 2:
        return "too-short"
    if low in _MEGACAP:
        return "megacap"
    if norm(name) in {norm(a) for a in _AGGREGATORS}:
        return "aggregator"
    if is_staffing_firm(name):
        return "staffing"
    try:
        if company_is_blocked(name):
            return "company-blocked"
    except Exception:
        pass
    if _BIGCORP_RE.search(low):
        return "bigcorp-heuristic"
    return None


def discover_for(name: str) -> Optional[Dict]:
    """Probe one company across adapters/slug-variants. First hit wins."""
    variants = slug_variants(name)
    # Probe greenhouse + ashby + lever for each variant. Cheap HTTP, short timeout.
    for adapter in ("greenhouse", "ashby", "lever"):
        for slug in variants:
            hit = probe(adapter, slug)
            if hit:
                a, s, n = hit
                return {"name": name, "adapter": a, "slug": s, "jobs": n}
    return None


def run(limit: int, apply: bool, workers: int) -> List[Dict]:
    existing = load_existing_names()
    all_li = li_source_companies()
    candidates: List[str] = []
    skipped: Dict[str, int] = {}
    for name in all_li:
        if norm(name) in existing:
            continue
        reason = should_skip(name)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        candidates.append(name)
    if limit:
        candidates = candidates[:limit]

    print(f"[li-resolver] LinkedIn-source companies: {len(all_li)}", file=sys.stderr)
    print(f"[li-resolver] already in yaml: {len(all_li) - len(candidates) - sum(skipped.values())}",
          file=sys.stderr)
    print(f"[li-resolver] skipped (noise): {sum(skipped.values())} {skipped}", file=sys.stderr)
    print(f"[li-resolver] probing {len(candidates)} candidates "
          f"(workers={workers})...", file=sys.stderr)

    hits: List[Dict] = []
    seen_pairs = set()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(discover_for, n): n for n in candidates}
        for fut in as_completed(futs):
            done += 1
            if done % 50 == 0:
                print(f"[li-resolver]   {done}/{len(candidates)} probed, "
                      f"{len(hits)} hits", file=sys.stderr)
            try:
                r = fut.result()
            except Exception:
                r = None
            if not r:
                continue
            pair = f"{r['adapter']}/{r['slug']}"
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            hits.append(r)

    hits.sort(key=lambda r: (-r["jobs"], r["name"].lower()))
    print(f"\n[li-resolver] {len(hits)} NEW employer boards resolved:", file=sys.stderr)
    for r in hits:
        print(f"  - {{ name: \"{r['name']}\", adapter: {r['adapter']}, "
              f"slug: {r['slug']} }}  # li-resolved, {r['jobs']} jobs")

    if apply and hits:
        _append_to_yaml(hits)
        print(f"\n[li-resolver] APPENDED {len(hits)} entries to {YAML_PATH}",
              file=sys.stderr)
    elif hits:
        print(f"\n[li-resolver] DRY-RUN — re-run with --apply to append "
              f"{len(hits)} entries.", file=sys.stderr)
    return hits


def _append_to_yaml(hits: List[Dict]) -> None:
    d = yaml.safe_load(YAML_PATH.read_text())
    is_list = isinstance(d, list)
    cos = d if is_list else d.get("companies", d)
    existing_pairs = {f"{c.get('adapter')}/{c.get('slug')}" for c in cos
                      if isinstance(c, dict)}
    added = 0
    for r in hits:
        pair = f"{r['adapter']}/{r['slug']}"
        if pair in existing_pairs:
            continue
        cos.append({"name": r["name"], "adapter": r["adapter"],
                    "slug": r["slug"], "note": "li-resolved"})
        existing_pairs.add(pair)
        added += 1
    YAML_PATH.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
    print(f"[li-resolver] wrote {added} new entries.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=12)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(limit=args.limit, apply=args.apply, workers=args.workers)


if __name__ == "__main__":
    main()
