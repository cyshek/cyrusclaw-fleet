#!/usr/bin/env python3
"""discover_companies.py - Discover new GH/Ashby job boards from YC batches + curated list."""

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import yaml

WORKSPACE = Path(__file__).parent
COMPANIES_YAML = WORKSPACE / "companies.yaml"

# Legacy YC API batch codes (20/batch hard limit)
YC_BATCHES = [
    "W18", "S18", "W19", "S19", "W20", "S20", "W21", "S21",
    "W22", "S22", "W23", "S23", "W24", "S24", "W25", "S25",
]

# Algolia batch names (full YC directory, all batches)
YC_ALGOLIA_BATCHES = [
    "Summer 2005", "Summer 2006", "Winter 2007", "Summer 2007",
    "Winter 2008", "Summer 2008", "Winter 2009", "Summer 2009",
    "Winter 2010", "Summer 2010", "Winter 2011", "Summer 2011",
    "Winter 2012", "Summer 2012", "Winter 2013", "Summer 2013",
    "Winter 2014", "Summer 2014", "Winter 2015", "Summer 2015",
    "Winter 2016", "Summer 2016", "Winter 2017", "Summer 2017",
    "Winter 2018", "Summer 2018", "Winter 2019", "Summer 2019",
    "Winter 2020", "Summer 2020", "Winter 2021", "Summer 2021",
    "Winter 2022", "Summer 2022", "Winter 2023", "Summer 2023",
    "Winter 2024", "Summer 2024", "Winter 2025", "Summer 2025",
    "Fall 2025", "Winter 2026", "Spring 2026", "Summer 2026", "Fall 2026",
]

# Algolia credentials (from ycombinator.com/companies page source)
_ALGOLIA_APP_ID = "45BWZJ1SGC"
_ALGOLIA_API_KEY = (
    "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4ZTU0ZD"
    "lhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21w"
    "YW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbi"
    "Z0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
)

# Curated supplemental list: (display_name, [slug_candidates])
CURATED = [
    ("Linear", ["linear"]),
    ("Loom", ["loom"]),
    ("Vercel", ["vercel"]),
    ("Railway", ["railway"]),
    ("Supabase", ["supabase"]),
    ("PlanetScale", ["planetscale"]),
    ("Neon", ["neon", "neondatabase"]),
    ("Turso", ["turso"]),
    ("Fly.io", ["fly-io", "flyio"]),
    ("Render", ["render"]),
    ("Perplexity", ["perplexity", "perplexityai"]),
    ("Mistral AI", ["mistral", "mistralai"]),
    ("Cohere", ["cohere"]),
    ("Together AI", ["togetherai", "together-ai", "together"]),
    ("Replicate", ["replicate"]),
    ("Anyscale", ["anyscale"]),
    ("Modal", ["modal"]),
    ("CoreWeave", ["coreweave"]),
    ("Lambda Labs", ["lambdalabs", "lambda-labs"]),
    ("RunPod", ["runpod"]),
    ("Vast.ai", ["vast-ai", "vastai"]),
    ("Hex", ["hex"]),
    ("Mode", ["mode"]),
    ("Sigma Computing", ["sigmacomputing", "sigma"]),
    ("Count", ["count"]),
    ("Lightdash", ["lightdash"]),
    ("Retool", ["retool"]),
    ("Airplane", ["airplane", "airplane-dev"]),
    ("Appsmith", ["appsmith"]),
    ("Budibase", ["budibase"]),
    ("Clerk", ["clerk"]),
    ("Stytch", ["stytch"]),
    ("WorkOS", ["workos"]),
    ("Auth0", ["auth0"]),
    ("Frontegg", ["frontegg"]),
    ("Brex", ["brex"]),
    ("Mercury", ["mercury"]),
    ("Ramp", ["ramp"]),
    ("Puzzle", ["puzzle"]),
    ("Fora", ["fora"]),
    ("Finaloop", ["finaloop"]),
    ("Middesk", ["middesk"]),
    ("Vanta", ["vanta"]),
    ("Drata", ["drata"]),
    ("Secureframe", ["secureframe"]),
    ("Tugboat Logic", ["tugboat-logic", "tugboatlogic"]),
    ("Deel", ["deel"]),
    ("Remote", ["remote"]),
    ("Oyster HR", ["oyster-hr", "oysterhr", "oyster"]),
    ("Multiplier", ["multiplier"]),
    ("Luma AI", ["luma", "lumaai"]),
    ("Synthesia", ["synthesia"]),
    ("HeyGen", ["heygen"]),
    ("ElevenLabs", ["elevenlabs"]),
    ("Cursor", ["cursor-so", "cursor", "anysphere"]),
    ("Codeium", ["codeium", "windsurf"]),
    ("Tabnine", ["tabnine"]),
    ("Sourcegraph", ["sourcegraph"]),
    ("dbt Labs", ["dbtlabs", "dbt-labs", "fishtown-analytics"]),
    ("Airbyte", ["airbyte"]),
    ("Fivetran", ["fivetran"]),
    ("Hightouch", ["hightouch"]),
    ("Census", ["census"]),
    ("Segment", ["segment"]),
    ("mParticle", ["mparticle"]),
    ("RudderStack", ["rudderstack"]),
    ("Grafana Labs", ["grafana", "grafanalabs"]),
    ("Datadog", ["datadoghq", "datadog"]),
    ("Honeycomb", ["honeycomb"]),
    ("Chronosphere", ["chronosphere"]),
    ("Temporal", ["temporal"]),
    ("Inngest", ["inngest"]),
    ("Trigger.dev", ["trigger-dev", "triggerdev"]),
    ("Conductor", ["conductor"]),
    ("Mintlify", ["mintlify"]),
    ("ReadMe", ["readme"]),
    ("GitBook", ["gitbook"]),
    ("Plain", ["plain"]),
    ("Intercom", ["intercom"]),
    ("Front", ["front"]),
    ("Gladly", ["gladly"]),
    ("Kustomer", ["kustomer"]),
    ("Pave", ["pave"]),
    ("Lattice", ["lattice"]),
    ("Leapsome", ["leapsome"]),
    ("Culture Amp", ["cultureamp", "culture-amp"]),
    ("BetterUp", ["betterup"]),
]

SLUG_NAME_MAP = {
    "weights & biases": ["wandb"],
    "scale ai": ["scaleai", "scale"],
    "hugging face": ["huggingface"],
    "y combinator": [],
}


def name_to_slugs(name: str) -> list:
    """Generate candidate slugs from a company name."""
    name_lower = name.lower()
    if name_lower in SLUG_NAME_MAP:
        specials = SLUG_NAME_MAP[name_lower]
        if not specials:
            return []
        base = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")
        return list(dict.fromkeys(specials + [base]))
    base = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")
    slugs = [base]
    nohyphen = base.replace("-", "")
    if nohyphen != base:
        slugs.append(nohyphen)
    for suffix in ["-inc", "-corp", "-ai", "-hq", "-labs", "-io", "-tech"]:
        if base.endswith(suffix):
            trimmed = base[: -len(suffix)]
            if trimmed and trimmed not in slugs:
                slugs.append(trimmed)
            trimmed_nh = nohyphen[: -len(suffix.replace("-", ""))]
            if trimmed_nh and trimmed_nh not in slugs:
                slugs.append(trimmed_nh)
    return list(dict.fromkeys(slugs))


def probe_gh(slug: str) -> bool:
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            timeout=6,
        )
        return r.status_code == 200
    except Exception:
        return False


def probe_ashby(slug: str) -> bool:
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            timeout=6,
        )
        return r.status_code == 200
    except Exception:
        return False


def load_existing():
    with open(COMPANIES_YAML) as f:
        data = yaml.safe_load(f)
    cos = data["companies"]
    gh_slugs = set(
        c["slug"] for c in cos if c.get("adapter") == "greenhouse" and c.get("slug")
    )
    ashby_slugs = set(
        c["slug"] for c in cos if c.get("adapter") == "ashby" and c.get("slug")
    )
    return data, cos, gh_slugs, ashby_slugs


def fetch_yc_algolia(batches=None):
    """Fetch full YC company list via Algolia (used by ycombinator.com/companies).

    Uses batch-by-batch filtering to bypass the 1000-result cap that applies
    to unfiltered queries. Each batch returns <500 companies, well under the limit.
    Covers the entire YC history from Summer 2005 through current batches (~5600 total).
    """
    if batches is None:
        batches = YC_ALGOLIA_BATCHES
    url = f"https://{_ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"
    headers = {
        "x-algolia-application-id": _ALGOLIA_APP_ID,
        "x-algolia-api-key": _ALGOLIA_API_KEY,
        "Content-Type": "application/json",
    }
    seen = {}
    for batch in batches:
        batch_enc = batch.replace(" ", "%20")
        try:
            r = requests.post(
                url,
                headers=headers,
                json={"requests": [{"indexName": "YCCompany_production", "params": (
                    "query=&hitsPerPage=1000&page=0"
                    '&tagFilters=["ycdc_public"]'
                    f'&filters=batch%3A"{batch_enc}"'
                )}]},
                timeout=15,
            )
            result = r.json().get("results", [{}])[0]
            hits = result.get("hits", [])
            nb = result.get("nbHits", 0)
            if nb > 1000:
                print(f"  [Algolia] {batch}: WARNING nbHits={nb} > 1000, truncated to {len(hits)}")
            else:
                print(f"  [Algolia] {batch}: {len(hits)} companies")
            for c in hits:
                n = c.get("name", "")
                if n and n not in seen:
                    seen[n] = c
            time.sleep(0.15)
        except Exception as e:
            print(f"  [Algolia] {batch}: ERROR {e}")
    return list(seen.values())

def fetch_yc_companies():
    """Fetch companies from YC API for recent batches (20/batch hard limit, legacy fallback)."""
    all_companies = []
    for batch in YC_BATCHES:
        try:
            r = requests.get(
                "https://api.ycombinator.com/v0.1/companies",
                params={"batch": batch, "limit": 200},
                timeout=10,
            )
            if r.status_code != 200:
                print(f"  [YC] {batch}: HTTP {r.status_code}")
                continue
            data = r.json()
            cos = data.get("companies", data if isinstance(data, list) else [])
            print(f"  [YC] {batch}: {len(cos)} companies")
            all_companies.extend(cos)
            time.sleep(0.5)
        except Exception as e:
            print(f"  [YC] {batch}: ERROR {e}")
    return all_companies


def probe_company(name, slugs, gh_slugs, ashby_slugs, sleep=0.3):
    """Probe a company. Returns (name, adapter, found_slug, status)."""
    for slug in slugs:
        if slug in gh_slugs:
            return name, "greenhouse", slug, "already"
        if slug in ashby_slugs:
            return name, "ashby", slug, "already"
    for slug in slugs:
        if probe_gh(slug):
            return name, "greenhouse", slug, "new"
        time.sleep(sleep)
        if probe_ashby(slug):
            return name, "ashby", slug, "new"
        time.sleep(sleep)
    return name, None, None, "miss"


def main():
    parser = argparse.ArgumentParser(description="Discover GH/Ashby job boards")
    parser.add_argument("--yc", action="store_true", help="Fetch YC batch companies")
    parser.add_argument("--curated", action="store_true", help="Probe curated list")
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not write")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent probe workers")
    parser.add_argument("--sleep", type=float, default=0.3, help="Sleep between probes")
    args = parser.parse_args()

    if not args.yc and not args.curated:
        print("Specify --yc and/or --curated", file=sys.stderr)
        sys.exit(1)

    data, cos, gh_slugs, ashby_slugs = load_existing()
    print(f"Loaded {len(cos)} companies ({len(gh_slugs)} GH, {len(ashby_slugs)} Ashby)")

    candidates = []

    if args.yc:
        print("\nFetching YC companies via Algolia (full directory, ~5600 total)...")
        yc_cos = fetch_yc_algolia()
        seen_names = set()
        for c in yc_cos:
            name = c.get("name", "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            slugs = name_to_slugs(name)
            if slugs:
                candidates.append((name, slugs))
        print(f"  {len(candidates)} unique YC companies to probe")

    if args.curated:
        print("\nAdding curated list...")
        curated_start = len(candidates)
        for display_name, slug_list in CURATED:
            candidates.append((display_name, slug_list))
        print(f"  {len(candidates) - curated_start} curated entries added")

    print(f"\nProbing {len(candidates)} candidates (workers={args.workers})...")
    new_entries = []
    already_count = 0
    miss_count = 0
    added_gh = 0
    added_ashby = 0

    gh_slugs_copy = set(gh_slugs)
    ashby_slugs_copy = set(ashby_slugs)

    def do_probe(item):
        name, slugs = item
        return probe_company(name, slugs, gh_slugs_copy, ashby_slugs_copy, sleep=args.sleep)

    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futures = {exe.submit(do_probe, item): item for item in candidates}
        for fut in as_completed(futures):
            name, adapter, slug, status = fut.result()
            if status == "already":
                print(f"[{adapter.upper()[:2]}] {slug}: already exists ({name})")
                already_count += 1
            elif status == "new":
                label = adapter.upper()[:2]
                print(f"[{label}] {slug}: ADDED ({name})")
                new_entries.append({"name": name, "adapter": adapter, "slug": slug})
                if adapter == "greenhouse":
                    gh_slugs_copy.add(slug)
                    added_gh += 1
                else:
                    ashby_slugs_copy.add(slug)
                    added_ashby += 1
            else:
                print(f"[MISS] {name}: not found")
                miss_count += 1

    print(f"\n=== SUMMARY ===")
    print(f"  Already present: {already_count}")
    print(f"  ADDED GH:        {added_gh}")
    print(f"  ADDED Ashby:     {added_ashby}")
    print(f"  Not found:       {miss_count}")
    print(f"  Total added:     {added_gh + added_ashby}")

    if new_entries and not args.dry_run:
        cos.extend(new_entries)
        data["companies"] = cos
        with open(COMPANIES_YAML, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\nWrote {len(cos)} companies to {COMPANIES_YAML}")
    elif new_entries and args.dry_run:
        print("\n[dry-run] Would add:")
        for e in new_entries:
            print(f"  {e}")
    else:
        print("\nNo new entries to add.")


if __name__ == "__main__":
    main()
