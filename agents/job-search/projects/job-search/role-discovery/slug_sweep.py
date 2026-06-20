"""Slug sweep: for each failed company in the latest crawl, probe variant
slugs, alternate ATSes, and scrape careers pages to find a working endpoint.

Output: a YAML-ready diff to apply to companies.yaml.

Usage:  python slug_sweep.py [path-to-meta.json]
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml

ROOT = Path(__file__).parent
OUT = ROOT / "output"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

GH = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{}"
LEVER = "https://api.lever.co/v0/postings/{}?mode=json"

# Candidate ATSes to try when current ATS fails.
ATS_PROBES = {
    "greenhouse": [("greenhouse", GH), ("ashby", ASHBY), ("lever", LEVER)],
    "ashby":      [("ashby", ASHBY), ("greenhouse", GH), ("lever", LEVER)],
    "lever":      [("lever", LEVER), ("ashby", ASHBY), ("greenhouse", GH)],
}


def latest_meta() -> Path:
    metas = sorted(OUT.glob("*-meta.json"))
    if not metas:
        raise SystemExit("No meta.json files found")
    return metas[-1]


def slug_variants(name: str, slug: str) -> List[str]:
    """Generate plausible slug variants from company name + current slug."""
    n = name.lower()
    # collapse and strip
    base = re.sub(r"[^a-z0-9]", "", n)
    hyphen = re.sub(r"\s+", "-", n.strip())
    underscore = re.sub(r"\s+", "_", n.strip())
    variants = {
        slug,
        base,
        hyphen,
        underscore,
        base + "inc",
        base + "labs",
        base + "ai",
        base + "io",
        base + "hq",
        base + "1",
        base + "careers",
        slug + "inc",
        slug + "labs",
        slug + "ai",
        slug + "1",
        slug + "careers",
        slug.replace("-", ""),
        slug.replace("_", ""),
    }
    # remove empty + de-dupe preserving order roughly
    return [v for v in dict.fromkeys(variants) if v]


def probe(url: str, timeout: int = 8) -> Tuple[int, Optional[dict]]:
    """Return (status_code, parsed_json or None)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return r.status_code, None
        try:
            return 200, r.json()
        except Exception:
            return 200, None
    except requests.RequestException as e:
        return -1, None


def jobs_count(adapter: str, body: dict) -> int:
    if not body:
        return 0
    if adapter == "lever":
        return len(body) if isinstance(body, list) else 0
    if adapter == "greenhouse":
        return len((body.get("jobs") or [])) if isinstance(body, dict) else 0
    if adapter == "ashby":
        return len((body.get("jobs") or [])) if isinstance(body, dict) else 0
    return 0


def try_apis(name: str, current_adapter: str, current_slug: str) -> Optional[Tuple[str, str, int]]:
    """Try every (adapter, slug) variant. Return (adapter, slug, jobs) or None."""
    probes = ATS_PROBES.get(current_adapter, [])
    variants = slug_variants(name, current_slug)
    for adapter, url_tmpl in probes:
        for v in variants:
            url = url_tmpl.format(v)
            code, body = probe(url)
            if code == 200 and body is not None:
                n = jobs_count(adapter, body)
                if n > 0:
                    return (adapter, v, n)
    return None


# Patterns to discover ATS embeds inside a careers HTML page.
EMBED_PATTERNS = [
    (re.compile(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I), "greenhouse"),
    (re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", re.I), "greenhouse"),
    (re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I), "ashby"),
    (re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9_-]+)", re.I), "ashby"),
    (re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I), "lever"),
    (re.compile(r"api\.lever\.co/v0/postings/([a-z0-9_-]+)", re.I), "lever"),
]

# Common careers page locations to probe per company name.
def careers_urls(name: str) -> List[str]:
    base = re.sub(r"[^a-z0-9]", "", name.lower())
    hyphen = re.sub(r"\s+", "-", name.lower().strip())
    candidates = [
        f"https://{base}.com/careers",
        f"https://{base}.com/careers/",
        f"https://{base}.com/jobs",
        f"https://{base}.com/about/careers",
        f"https://www.{base}.com/careers",
        f"https://www.{base}.com/careers/",
        f"https://{base}.io/careers",
        f"https://{base}.io/careers/",
        f"https://{base}.ai/careers",
        f"https://{base}.dev/careers",
        f"https://www.{hyphen}.com/careers",
    ]
    return list(dict.fromkeys(candidates))


def scrape_for_embed(name: str) -> Optional[Tuple[str, str]]:
    for url in careers_urls(name):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        except requests.RequestException:
            continue
        if r.status_code != 200 or not r.text:
            continue
        for pat, adapter in EMBED_PATTERNS:
            m = pat.search(r.text)
            if m:
                slug = m.group(1).lower()
                if slug in {"embed", "for", "job_board", "v1", "boards", "postings"}:
                    continue
                return (adapter, slug)
    return None


def verify(adapter: str, slug: str) -> int:
    if adapter == "greenhouse":
        url = GH.format(slug)
    elif adapter == "ashby":
        url = ASHBY.format(slug)
    elif adapter == "lever":
        url = LEVER.format(slug)
    else:
        return 0
    code, body = probe(url)
    if code != 200 or body is None:
        return 0
    return jobs_count(adapter, body)


def sweep_one(failure: dict) -> dict:
    name = failure["company"]
    err = failure.get("error", "")
    # parse current adapter+slug from the error string if possible:
    #   "RuntimeError: greenhouse[wandb] HTTP 404"
    m = re.search(r"(greenhouse|ashby|lever)\[([^\]]+)\]", err)
    if not m:
        return {"name": name, "error": err, "status": "unparseable"}
    current_adapter, current_slug = m.group(1), m.group(2)

    # 1) try API variants
    found = try_apis(name, current_adapter, current_slug)
    if found:
        return {
            "name": name,
            "old": f"{current_adapter}/{current_slug}",
            "new": f"{found[0]}/{found[1]}",
            "jobs": found[2],
            "method": "api-variant",
        }

    # 2) scrape careers page
    embed = scrape_for_embed(name)
    if embed:
        adapter, slug = embed
        n = verify(adapter, slug)
        if n > 0:
            return {
                "name": name,
                "old": f"{current_adapter}/{current_slug}",
                "new": f"{adapter}/{slug}",
                "jobs": n,
                "method": "scraped-careers",
            }
        return {
            "name": name,
            "old": f"{current_adapter}/{current_slug}",
            "found_embed": f"{adapter}/{slug}",
            "jobs": 0,
            "method": "embed-but-empty",
        }

    return {"name": name, "old": f"{current_adapter}/{current_slug}", "status": "no-match-found"}


def main() -> None:
    if len(sys.argv) > 1:
        meta_path = Path(sys.argv[1])
    else:
        meta_path = latest_meta()
    print(f"Reading {meta_path.name}", flush=True)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    failures = meta.get("failures", [])
    print(f"{len(failures)} failures to investigate\n", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(sweep_one, f): f for f in failures}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            line = f"  {res['name']:24s}"
            if "new" in res:
                line += f" FIX: {res['old']} -> {res['new']}  ({res['jobs']} jobs, {res['method']})"
            elif "found_embed" in res:
                line += f" embed found ({res['found_embed']}) but API empty"
            else:
                line += f" no match (was {res.get('old', '?')})"
            print(line, flush=True)

    # bucket
    fixes = [r for r in results if "new" in r]
    misses = [r for r in results if "new" not in r]

    print(f"\n=== SUMMARY ===")
    print(f"Fixable: {len(fixes)} / {len(failures)}")
    print(f"Total recoverable jobs: {sum(r['jobs'] for r in fixes)}")
    print(f"Still unresolved: {len(misses)}")

    if fixes:
        print(f"\n=== YAML PATCHES (paste into companies.yaml) ===")
        for r in sorted(fixes, key=lambda x: x["name"]):
            new_adapter, new_slug = r["new"].split("/")
            print(f"  - {{ name: {r['name']}, adapter: {new_adapter}, slug: {new_slug} }}  # was {r['old']}, {r['jobs']} jobs")

    # save full report
    report = OUT / f"{meta_path.stem.replace('-meta','')}-slug-sweep.json"
    report.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull report: {report}")


if __name__ == "__main__":
    main()
