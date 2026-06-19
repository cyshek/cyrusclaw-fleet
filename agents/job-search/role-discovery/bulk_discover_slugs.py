"""Bulk discover ATS slugs for a list of candidate companies.

For each company, probes Greenhouse / Ashby / Lever variants of the slug
derived from the name. Reports verified hits (>=1 job).

Use this to seed companies.yaml with new employers.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

import requests

ROOT = Path(__file__).parent

# Companies I know employ PM / TPM / SE / Solutions Architect titles in the US.
# Filtered to ones likely missing from companies.yaml or worth re-verifying.
# === 2026-05-19 sweep: AI-native / dev-tools / AI infra not yet in companies.yaml ===
# Curated from Forbes AI 50 2025, YC W25/S25/X25 AI cohort, and known
# high-growth AI/agent/voice/coding/devtool startups missing from our list.
CANDIDATES = [
    # --- Frontier / model labs not yet covered ---
    "Thinking Machines",       # Mira Murati's lab
    "Safe Superintelligence",  # Ilya Sutskever
    "Imbue",                   # Sophie Imbue (may be greenhouse)
    "Liquid AI",               # may have ashby
    "AI21 Labs",
    "Contextual AI",
    "Adept AI",
    "Essential AI",
    "Manifest AI",
    "H Company",               # ex-DeepMind
    "Mira Network",
    # --- AI agents / vertical agents ---
    "Sierra AI",               # try alt of Sierra
    "Decagon AI",
    "Crew AI",
    "CrewAI",
    "Multion",
    "Adept",
    "Lindy AI",
    "Relevance AI",
    "Cognosys",
    "Imbue AI",
    "Klarity",                 # AI legal/finance
    "Hippocratic",
    "Abridge",                 # AI medical scribe
    "Suki AI",
    "Curai Health",
    "Atomic AI",
    "Tennr",                   # healthcare AI agents
    "Datacurve",
    "Daloopa",
    # --- AI voice / video / multimodal ---
    "Hume AI",
    "Cartesia",                # voice models
    "Inworld",                 # character AI for games
    "Captions",
    "Pika Labs",
    "HeyGen",
    "Photoroom",
    "D-ID",
    "Tavus AI",
    "Sindarin",                # voice agents
    "Retell AI",
    "Vocode",
    # --- AI coding / dev tools ---
    "Magic Dev",               # magic.dev coding lab
    "Magic.dev",
    "Codeium",                 # exa-Windsurf — may have Ashby
    "Windsurf",
    "Cline",
    "Aider",
    "Phind",
    "Bolt",                    # bolt.new / StackBlitz
    "StackBlitz",
    "v0",                      # Vercel sub-brand (skip, covered)
    "All Hands AI",            # open-source devin
    "Sweep",
    "Pulley",
    "Lovable AI",
    "E2B",                     # AI code sandbox
    "Trigger.dev",
    "Restate",
    "Inngest",
    # --- AI infra / inference / orchestration ---
    "Modal",                   # already as Modal Labs but try slug variant
    "Anyscale",                # already in
    "Outerbounds",             # Metaflow
    "Predibase",
    "Featureform",
    "Substrate",
    "Octo AI",
    "OctoML",
    "Cerebras",
    "Sambanova",
    "Groq AI",                 # alt slug
    "Etched",                  # AI chip
    "Rebellions",
    "Tenstorrent",
    "Ayar Labs",
    "Lightmatter",
    # --- Vector / data infra ---
    "Turbopuffer",
    "LanceDB",
    "MotherDuck",
    "Tinybird",
    "Chalk",                   # feature store
    "Tecton",
    "Featureform",
    "Materialize",
    "Estuary",
    "Stream",                  # getstream.io
    "Convex",
    # --- Observability / eval / safety ---
    "LangSmith",               # LangChain sub-brand — same
    "Weights & Biases",        # already in
    "Braintrust",              # LLM eval
    "Confident AI",
    "Galileo",                 # LLM observability
    "Lakera",                  # AI security
    "Robust Intelligence",
    "Credo AI",
    "Calypso AI",
    # --- AI sales / GTM / RevOps ---
    "11x AI",                  # AI SDRs
    "Artisan",                 # AI BDR
    "Rox",                     # rox.com sales AI
    "Clay",                    # GTM data
    "Default",                 # default.com inbound
    "Unify",                   # unifygtm.com
    "Regie AI",
    "Lavender",
    # --- AI legal / finance / vertical SaaS ---
    "EvenUp",                  # already in as private
    "Eve Legal",
    "Spellbook",
    "Robin AI",
    "Ironclad",                # already noted private
    "Pilot AI",
    "Rogo",                    # finance AI
    "Hebbia",                  # already in
    # --- AI ops / RPA / agents enterprise ---
    "Moveworks",
    "Aisera",
    "Cresta AI",               # alt of Cresta
    "Ada",                     # ada.cx support AI
    "Forethought",
    "Kore.ai",
    "Glean AI",                # alt of Glean
    # --- AI security ---
    "Protect AI",
    "HiddenLayer",
    "Prompt Security",
    "Calypso AI",
    # --- Other recent unicorns / growth ---
    "Mercor",                  # already in
    "Scale",                   # alt of Scale AI
    "Distyl AI",               # already as Distyl
    "Reka",                    # alt of Reka AI
    "Sakana",                  # alt of Sakana AI
    "Poolside AI",
    "Tavus",                   # already in
    "Bland",                   # already in as Bland AI
    "Decagon",                 # already in
    "Cresta",                  # already in
    # Original legacy candidates kept for re-verification:
    "Snowflake",
    "MongoDB",
    "Twilio",
    "Cloudflare",
    "Zendesk",
    "HashiCorp",
    "Confluent",
    "Elastic",
    "GitHub",
    "GitLab",          # may already be in
    "Atlassian",
    "Okta",
    "Auth0",           # owned by Okta but may have separate listings
    "ServiceNow",
    "Workday",
    "DocuSign",
    "Box",
    "Dropbox",         # may already be in
    "Slack",           # owned by Salesforce; may have own listing
    "Asana",           # may already be in
    "Linear",
    "ClickUp",
    "Monday.com",
    "Airtable",        # may already be in
    "Calendly",        # may already be in
    "Loom",
    "Webflow",
    "Vercel",
    "Netlify",
    "Supabase",
    "Mux",
    "Clerk",
    "Linear",
    "Plaid",           # may already be in
    "Brex",
    "Ramp",
    "Mercury",
    "Carta",
    "Rippling",
    "Deel",
    "Gusto",
    "Pilot",
    "Modern Health",
    "Glean",           # may already be in
    "Perplexity",
    "Mistral",
    "Hugging Face",
    "LangChain",
    "Replicate",
    "Together AI",
    "Fireworks AI",
    "Modal",           # may already be in
    "Lambda Labs",
    "Crusoe",
    "Runway",
    "Stability AI",
    "Adept",
    "Inflection",
    "Character.AI",
    "Eleven Labs",
    "Suno",
    "Cresta",          # already fixed
    "Glean",
    "Harvey",
    "Hebbia",
    "Decagon",
    "Sourcegraph",
    "Tabnine",
    "Codeium",
    "Cognition",
    "Tessl",
    "Augment",
    "Browserbase",
    "Tavily",
    "Exa",
    "ElevenLabs",
    "Writer",
    "Jasper",
    "Copy.ai",
    "Otter.ai",
    "Fathom",
    "Fireflies",
    "Rev",
    "Loom",
    "Notion",          # may already be in
    "Coda",            # already in but broken
    "Quip",            # owned by Salesforce
    "Linear",
    "Height",
    "Shortcut",
    "Pivotal Tracker",
    "Airbase",
    "Pleo",
    "Spendesk",
    "Vouch",
    "Newfront",
    "At-Bay",
    "Coalition",
    "Cyera",
    "Lacework",
    "Orca Security",
    "Aqua Security",
    "Snyk",            # already fixed
    "Checkmarx",
    "Veracode",
    "HackerOne",       # already fixed
    "Bugcrowd",
    "Synack",
    "Tenable",
    "Rapid7",
    "CrowdStrike",
    "SentinelOne",
    "Cybereason",
    "Vectra",
    "ExtraHop",
    "Darktrace",
    "Recorded Future",
    "Mandiant",        # owned by Google
    "Palo Alto Networks",
    "Zscaler",
    "Cloudfront",
    "Fastly",
    "Imperva",
    "Akamai",
    "Edgio",
    "Bunny.net",
    "Algolia",
    "Meilisearch",
    "Typesense",
    "Pinecone",        # already fixed
    "Weaviate",
    "Qdrant",
    "Chroma",
    "Marqo",
    "LlamaIndex",
    "Vespa",
]

GH = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{}"
LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def slug_variants(name: str) -> List[str]:
    n = name.lower().strip()
    base = re.sub(r"[^a-z0-9]", "", n)
    hyphen = re.sub(r"\s+", "-", n)
    underscore = re.sub(r"\s+", "_", n)
    no_dots = n.replace(".", "")
    no_dots_base = re.sub(r"[^a-z0-9]", "", no_dots)
    out = {
        base, hyphen, underscore, no_dots_base,
        base + "ai", base + "io", base + "inc", base + "labs", base + "hq",
        base + "1", base + "careers", base + "jobs",
        no_dots_base + "ai", no_dots_base + "io", no_dots_base + "inc",
    }
    return [v for v in dict.fromkeys(out) if v]


def probe(adapter: str, slug: str) -> Optional[Tuple[str, str, int]]:
    if adapter == "greenhouse":
        url = GH.format(slug)
    elif adapter == "ashby":
        url = ASHBY.format(slug)
    elif adapter == "lever":
        url = LEVER.format(slug)
    else:
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return None
        j = r.json()
        if adapter == "lever":
            n = len(j) if isinstance(j, list) else 0
        else:
            n = len((j or {}).get("jobs", []))
        if n > 0:
            return (adapter, slug, n)
    except Exception:
        pass
    return None


def discover(name: str) -> Optional[Tuple[str, str, int]]:
    variants = slug_variants(name)
    # Try each adapter * variant combination.
    # Stop on first hit with the most jobs (priority: greenhouse > ashby > lever)
    best = None
    for adapter in ("greenhouse", "ashby", "lever"):
        for v in variants:
            r = probe(adapter, v)
            if r and (best is None or r[2] > best[2]):
                best = r
                # don't break - want highest count
        if best:
            return best
    return None


def main():
    print(f"Probing {len(CANDIDATES)} candidates...")
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(discover, c): c for c in CANDIDATES}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = None
            if r:
                a, s, n = r
                results.append({"name": name, "adapter": a, "slug": s, "jobs": n})
                print(f"  HIT: {name:24s} -> {a}/{s} ({n} jobs)", flush=True)
            else:
                print(f"  ---  {name}", flush=True)

    out = ROOT / "output" / "candidate_companies_probe.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\n=== {len(results)} verified candidates ===\n")
    print("YAML to paste:\n")
    for r in sorted(results, key=lambda x: (x["adapter"], x["name"])):
        print(f"  - {{ name: {r['name']}, adapter: {r['adapter']}, slug: {r['slug']} }}  # auto-discovered, {r['jobs']} jobs")
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()
