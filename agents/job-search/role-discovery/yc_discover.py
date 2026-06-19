"""YC breadth discovery: feed the public yc-oss company dataset through the
proven ATS slug-probe logic to find NET-NEW employers with a public
Greenhouse / Ashby / Lever board, then emit ready-to-merge companies.yaml
entries (deduped against the existing list).

No auth, no rabbit-hole: yc-oss publishes the full YC directory as static JSON
(name, slug, website, status, isHiring, regions). We filter to Active+hiring
(optionally US-region), then reuse bulk_discover_slugs.probe()/slug_variants()
to verify a real board exists.

Usage:
  .venv/bin/python yc_discover.py --limit 200          # probe first 200 hiring cos (dry, prints YAML)
  .venv/bin/python yc_discover.py --us-only --limit 0  # all US hiring cos
  .venv/bin/python yc_discover.py --apply              # append verified new entries to companies.yaml

Idempotent: never adds a company whose name (case-insensitive) OR resolved
adapter+slug already exists in companies.yaml.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml

ROOT = Path(__file__).parent
YAML_PATH = ROOT / "companies.yaml"
YC_ALL_URL = "https://yc-oss.github.io/api/companies/all.json"
CACHE = ROOT / "output" / "yc_all.json"

# Reuse the proven probe logic.
from bulk_discover_slugs import probe, slug_variants  # noqa: E402


def fetch_yc(force: bool = False) -> List[dict]:
    """Load the yc-oss directory (cached to output/yc_all.json)."""
    if CACHE.exists() and not force:
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    r = requests.get(YC_ALL_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    return data


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_existing(yaml_path: Path = YAML_PATH) -> Tuple[set, set]:
    """Return (existing normalized-names, existing adapter+slug pairs)."""
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or []
    comps = raw if isinstance(raw, list) else list(
        (raw.get("companies") or {}).values() if isinstance(raw.get("companies"), dict)
        else (raw.get("companies") or [])
    )
    names, slugs = set(), set()
    for c in comps:
        if not isinstance(c, dict):
            continue
        if c.get("name"):
            names.add(_norm_name(c["name"]))
        a, s = c.get("adapter"), c.get("slug")
        if a and s:
            slugs.add(f"{a}/{s}")
    return names, slugs


def select_hiring(data: List[dict], us_only: bool, ignore_hiring_flag: bool = False) -> List[dict]:
    out = []
    for x in data:
        if x.get("status") != "Active":
            continue
        # isHiring is self-reported and lags reality; with ignore_hiring_flag
        # we keep all Active cos and let the live ATS probe (which only keeps
        # boards that actually return jobs) do the real filtering.
        if not ignore_hiring_flag and not x.get("isHiring"):
            continue
        if us_only and not any(
            "America" in (r or "") for r in (x.get("regions") or [])
        ):
            continue
        out.append(x)
    return out


def discover_for(company: dict) -> Optional[Dict]:
    """Probe a single YC company. Prefers its authoritative yc slug, then
    name-derived variants. Returns a merge-ready dict or None."""
    name = company.get("name") or ""
    variants: List[str] = []
    if company.get("slug"):
        variants.append(str(company["slug"]).lower())
    variants += slug_variants(name)
    seen, ordered = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            ordered.append(v)

    best = None
    for adapter in ("greenhouse", "ashby", "lever"):
        for v in ordered:
            r = probe(adapter, v)
            if r and (best is None or r[2] > best[2]):
                best = r
        if best:
            break
    if not best:
        return None
    a, s, n = best
    return {"name": name, "adapter": a, "slug": s, "jobs": n,
            "website": company.get("website"), "batch": company.get("batch")}


def run(limit: int, us_only: bool, apply: bool, workers: int,
        force_fetch: bool, ignore_hiring_flag: bool = False) -> List[Dict]:
    data = fetch_yc(force=force_fetch)
    hiring = select_hiring(data, us_only, ignore_hiring_flag=ignore_hiring_flag)
    existing_names, existing_slugs = load_existing(YAML_PATH)
    # Skip companies already in yaml by name before probing (save requests).
    todo = [c for c in hiring if _norm_name(c.get("name", "")) not in existing_names]
    if limit and limit > 0:
        todo = todo[:limit]
    print(f"YC hiring(Active{'+US' if us_only else ''})={len(hiring)} | "
          f"new-by-name={len(todo)} | probing...", file=sys.stderr)

    hits: List[Dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(discover_for, c): c for c in todo}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                r = None
            if not r:
                continue
            pair = f"{r['adapter']}/{r['slug']}"
            if pair in existing_slugs:
                continue  # already covered under a different name
            existing_slugs.add(pair)
            hits.append(r)
            print(f"  HIT {r['name']:28s} -> {pair} ({r['jobs']} jobs)",
                  file=sys.stderr, flush=True)

    hits.sort(key=lambda x: (x["adapter"], -x["jobs"], x["name"].lower()))
    out = ROOT / "output" / "yc_discover_hits.json"
    out.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    print(f"\n=== {len(hits)} NET-NEW verified YC companies ===", file=sys.stderr)
    for r in hits:
        print(f"  - {{ name: \"{r['name']}\", adapter: {r['adapter']}, "
              f"slug: {r['slug']} }}  # yc {r.get('batch','')}, {r['jobs']} jobs")

    if apply and hits:
        _append_to_yaml(hits)
        print(f"\nAPPLIED: appended {len(hits)} entries to {YAML_PATH.name}",
              file=sys.stderr)
    return hits


def _append_to_yaml(hits: List[Dict]) -> None:
    """Append verified entries to companies.yaml. Handles both a top-level
    list and the repo's actual ``{companies: [...]}`` wrapper."""
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or []
    if isinstance(raw, dict) and isinstance(raw.get("companies"), list):
        target = raw["companies"]
        container = raw
    elif isinstance(raw, list):
        target = raw
        container = raw
    else:
        raise SystemExit(
            "companies.yaml is neither a list nor {companies: [...]}; aborting apply.")
    bak = YAML_PATH.with_suffix(".yaml.bak.yc")
    bak.write_text(YAML_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    for r in hits:
        target.append({"name": r["name"], "adapter": r["adapter"],
                       "slug": r["slug"], "note": f"yc-auto-discovered {r.get('batch','')}".strip()})
    YAML_PATH.write_text(
        yaml.safe_dump(container, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200,
                    help="max companies to probe (0 = all)")
    ap.add_argument("--us-only", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="append verified hits to companies.yaml")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--force-fetch", action="store_true")
    ap.add_argument("--ignore-hiring-flag", action="store_true",
                    help="keep all Active cos (not just isHiring); live probe filters")
    a = ap.parse_args()
    run(a.limit, a.us_only, a.apply, a.workers, a.force_fetch,
        ignore_hiring_flag=a.ignore_hiring_flag)


if __name__ == "__main__":
    main()
