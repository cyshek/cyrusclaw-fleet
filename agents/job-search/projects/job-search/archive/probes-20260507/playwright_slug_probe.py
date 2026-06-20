"""Playwright-based slug probe for JS-rendered careers pages.

For each unresolved company, launches a real Chromium, navigates to the
careers page, waits for network idle, and captures:
  - any URL that matches a known ATS pattern (Greenhouse/Ashby/Lever/Workday/SmartRecruiters/iCIMS)
  - both as a fully-rendered DOM scan AND as a network request observation

Outputs a JSON report with proposed slug fixes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PWTimeout

ROOT = Path(__file__).parent
OUT = ROOT / "output"

# Companies to probe with their candidate careers URLs.
TARGETS: List[Tuple[str, List[str]]] = [
    ("Coinbase",         ["https://www.coinbase.com/careers/positions"]),
    ("Retool",           ["https://retool.com/careers"]),
    ("Weights & Biases", ["https://wandb.ai/careers", "https://wandb.com/careers"]),
    ("Census",           ["https://www.getcensus.com/careers"]),
    ("Coda",             ["https://coda.io/careers"]),
    ("Miro",             ["https://miro.com/careers/", "https://miro.com/careers/all-jobs/"]),
    ("Chainalysis",      ["https://www.chainalysis.com/careers/"]),
]

ATS_PATTERNS = [
    (re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", re.I), "greenhouse"),
    (re.compile(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I), "greenhouse"),
    (re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9_-]+)", re.I), "ashby"),
    (re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I), "ashby"),
    (re.compile(r"api\.lever\.co/v0/postings/([a-z0-9_-]+)", re.I), "lever"),
    (re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I), "lever"),
    (re.compile(r"jobs\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I), "smartrecruiters"),
    (re.compile(r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)/postings", re.I), "smartrecruiters"),
    (re.compile(r"([a-z0-9_-]+)\.icims\.com/jobs", re.I), "icims"),
    (re.compile(r"([a-z0-9_-]+)\.wd[0-9]+\.myworkdayjobs\.com/([a-z0-9_-]+)", re.I), "workday"),
]

JUNK = {"embed", "for", "job_board", "v1", "boards", "postings", "api", "jobs", "v0", "embeds"}


def extract_slugs(text: str) -> List[Tuple[str, str]]:
    """Return list of (adapter, slug) tuples found in text."""
    found = []
    seen: Set[Tuple[str, str]] = set()
    for pat, adapter in ATS_PATTERNS:
        for m in pat.finditer(text):
            slug = m.group(1).lower()
            if slug in JUNK:
                continue
            key = (adapter, slug)
            if key not in seen:
                seen.add(key)
                found.append(key)
    return found


def verify(adapter: str, slug: str) -> int:
    """Verify the candidate slug returns real jobs."""
    if adapter == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    elif adapter == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    elif adapter == "lever":
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    elif adapter == "smartrecruiters":
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    else:
        # icims and workday need a more specific check; mark as suggested but unverified
        return -1
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return 0
        j = r.json()
        if adapter == "lever":
            return len(j) if isinstance(j, list) else 0
        if adapter == "smartrecruiters":
            return j.get("totalFound", 0)
        return len(j.get("jobs", []) or [])
    except Exception:
        return 0


def probe_company(browser: Browser, name: str, urls: List[str]) -> dict:
    print(f"\n=== {name} ===", flush=True)
    network_urls: List[str] = []
    page_html_total = ""

    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page: Page = ctx.new_page()
    page.on("request", lambda req: network_urls.append(req.url))
    page.on("response", lambda res: network_urls.append(res.url))

    last_error = None
    for url in urls:
        try:
            print(f"  navigating: {url}", flush=True)
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PWTimeout:
                pass
            # scroll to trigger lazy-loaded job lists
            for _ in range(3):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(800)
            page_html_total += "\n" + page.content()
            print(f"    rendered ({len(page_html_total)} chars cumulative)", flush=True)
        except Exception as e:
            last_error = str(e)[:100]
            print(f"    error: {last_error}", flush=True)
            continue

    ctx.close()

    # Extract candidates from both DOM and observed network URLs
    dom_finds = extract_slugs(page_html_total)
    net_text = "\n".join(network_urls)
    net_finds = extract_slugs(net_text)
    all_finds = list(dict.fromkeys(dom_finds + net_finds))
    print(f"  DOM candidates: {dom_finds}")
    print(f"  Net candidates: {net_finds}")

    verified = []
    for adapter, slug in all_finds:
        n = verify(adapter, slug)
        if n > 0:
            verified.append((adapter, slug, n))
            print(f"  + VERIFIED {adapter}/{slug} ({n} jobs)", flush=True)
        elif n == -1:
            verified.append((adapter, slug, -1))
            print(f"  ? unverified (workday/icims need manual check) {adapter}/{slug}", flush=True)

    # pick best (highest job count)
    best = None
    if verified:
        best = max(verified, key=lambda t: t[2] if t[2] > 0 else 0)

    return {
        "name": name,
        "tried_urls": urls,
        "all_candidates": all_finds,
        "verified": verified,
        "best": best,
        "error": last_error,
    }


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, urls in TARGETS:
            try:
                res = probe_company(browser, name, urls)
            except Exception as e:
                res = {"name": name, "error": f"probe-crash: {e}"}
                print(f"  CRASH: {e}", flush=True)
            results.append(res)
        browser.close()

    out_path = OUT / "playwright_slug_probe.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    print("\n\n=== SUMMARY ===")
    fixed = [r for r in results if r.get("best") and r["best"][2] > 0]
    print(f"Fixed: {len(fixed)} / {len(TARGETS)}")
    for r in fixed:
        a, s, n = r["best"]
        print(f"  - {r['name']}: {a}/{s} ({n} jobs)")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
