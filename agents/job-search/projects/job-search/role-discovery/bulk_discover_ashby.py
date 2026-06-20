#!/usr/bin/env python3
"""bulk_discover_ashby.py — Probe candidate org slugs against Ashby's public
posting-api. Print which ones return a valid jobs board (and how many roles).

Usage:
    .venv/bin/python bulk_discover_ashby.py
    .venv/bin/python bulk_discover_ashby.py --extra slug1,slug2,slug3
"""
from __future__ import annotations
import argparse, json, sys, time
import requests

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"

CANDIDATES = [
    # AI / infra / dev tools / data / app-layer
    "linear", "vercel", "modal", "cursor", "perplexity", "mistral", "runway",
    "elevenlabs", "replicate", "togetherai", "fireworksai", "baseten", "anyscale",
    "browserbase", "langchain", "llamaindex", "harvey", "characterai", "suno",
    "glean", "decagon", "sierra", "crusoe", "lambdalabs", "deepgram", "assemblyai",
    "weightsandbiases", "neon", "supabase", "prisma", "planetscale", "retool",
    "airbyte", "hex", "attio", "mercury", "ramp", "brex",
    "openai", "cohere", "notion", "quora", "anthropic",
    "exa", "bland", "drata", "imbue", "warp", "raycast", "tessl",
    "tavus", "poolside", "magic-ai", "magic", "crystaldba", "writer",
    "kalshi", "rerun", "datadome",
    # Variants worth probing
    "lambda", "weights-biases", "wandb", "characterai", "character-ai",
    "togetherai", "together-ai", "fireworks-ai", "elevenlabs", "eleven-labs",
    "magic-dev", "magicdev",
]


def probe(slug: str, timeout: int = 8) -> tuple[bool, int, str]:
    try:
        r = requests.get(API.format(slug=slug), timeout=timeout,
                         headers={"User-Agent": "openclaw-job-search-discover/1.0"})
        if r.status_code != 200:
            return False, r.status_code, ""
        data = r.json()
        jobs = data.get("jobs") or []
        return True, len(jobs), data.get("apiVersion", "")
    except Exception as e:
        return False, -1, str(e)[:60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", help="Comma-separated extra slugs to probe.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    candidates = list(CANDIDATES)
    if args.extra:
        candidates.extend([s.strip() for s in args.extra.split(",") if s.strip()])
    # de-dupe
    seen = set(); candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    found = []
    for slug in candidates:
        ok, count_or_status, info = probe(slug)
        if ok:
            found.append({"slug": slug, "open_jobs": count_or_status})
            if not args.quiet:
                print(f"  ✓  {slug:<30} {count_or_status:>4} open jobs")
        else:
            if not args.quiet:
                print(f"     {slug:<30}  -  ({count_or_status})")
        time.sleep(0.15)

    print(f"\nTOTAL: {len(found)} valid Ashby boards / {len(candidates)} probed")
    print(json.dumps(found, indent=2))


if __name__ == "__main__":
    main()
