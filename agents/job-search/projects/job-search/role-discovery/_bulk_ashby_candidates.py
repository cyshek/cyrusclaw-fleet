"""One-shot candidate list for Ashby slug discovery.

Compiled 2026-05-16. Sources: YC W26/S26 batches, Forbes AI 50 (2026),
Madrona/Greylock/Founders Fund/a16z public AI portfolios, the Latent Space
"100 startups to watch", Bessemer 100, ICONIQ AI infra list. Filtered to
companies likely on Ashby (modern AI/dev-tools startups, typically <500
employees, US-based hiring).

Run via: .venv/bin/python _bulk_ashby_candidates.py
"""
from __future__ import annotations
import sys
sys.path.insert(0, '.')
from bulk_discover_slugs import discover  # reuses existing probing logic

CANDIDATES = [
    # AI labs / model providers
    "Magic", "World Labs", "Poolside", "Sakana AI", "Reka AI", "Liquid AI",
    "Decart AI", "Black Forest Labs", "Mistral AI", "AI21 Labs",
    "Cohere", "Character AI",
    # AI dev tools / orchestration
    "Decagon", "Sierra AI", "Cresta", "Glean", "Crew AI", "LangSmith",
    "LlamaIndex", "Pinecone", "Weaviate", "Qdrant", "Chroma", "Marqo",
    "Galileo AI", "Patronus AI", "Arize", "Fiddler AI", "WhyLabs",
    "Comet", "Weights and Biases", "Distyl AI",
    # AI agents / vertical
    "Adept AI", "Imbue", "MultiOn", "Bland AI", "Tavus", "Vapi",
    "Synthesia", "Tavus", "Pika Labs", "Runway ML",
    # AI infra / compute
    "Lambda", "Crusoe Energy", "Together AI", "Fireworks AI", "Modal Labs",
    "Replicate", "Baseten", "Anyscale", "OctoML", "Mosaic ML",
    # Dev tools / platforms
    "Linear", "Vercel", "Cursor", "Codeium", "Continue", "Sourcegraph",
    "Tabnine", "Sweep AI", "Devin (Cognition Labs)", "Cognition",
    "Replit", "Supabase", "PlanetScale", "Neon", "Turso",
    # Productivity / SaaS
    "Notion", "Coda", "Linear", "Loops", "Resend", "Postman",
    "Pylon", "Default", "Common Room", "Lattice",
    # Security / observability
    "Snyk", "Sentry", "Persona", "Vanta", "Drata", "Henk",
    "Wiz", "Orca Security", "Apiiro", "Nuclei",
    # Vertical AI
    "Harvey AI", "Hippocratic AI", "Suno AI", "Writer", "Jasper",
    "Eleven Labs", "PolyAI", "Synthflow",
    # Notable AI startups from H2 2025 / 2026 batches
    "Anysphere", "Perplexity", "You.com", "Glean",
    "Mercor", "Mercor AI", "Distributional", "Distyl",
    "Iconiq", "Sigil", "Skydio", "Shield AI",
]

# Dedupe
CANDIDATES = list(dict.fromkeys(CANDIDATES))

# Filter against existing companies.yaml
import yaml
from pathlib import Path
with open(Path(__file__).parent / "companies.yaml") as f:
    docs = list(yaml.safe_load_all(f))
existing = set()
for d in docs:
    if isinstance(d, dict) and "companies" in d:
        for c in d["companies"]:
            existing.add(c.get("name", "").lower().strip())

NEW = [c for c in CANDIDATES if c.lower().strip() not in existing]
print(f"{len(CANDIDATES)} total candidates, {len(NEW)} not in companies.yaml")

import json
results = []
for i, name in enumerate(NEW):
    print(f"[{i+1}/{len(NEW)}] {name} ...", flush=True)
    r = discover(name)
    if r:
        adapter, slug, n = r
        results.append({"name": name, "adapter": adapter, "slug": slug, "jobs": n})
        print(f"   HIT -> {adapter}/{slug} ({n} jobs)")
    else:
        print(f"   miss")

out = Path(__file__).parent / "output" / "bulk_ashby_probe_20260516.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(results, indent=2))

# Group by adapter
ash = [r for r in results if r["adapter"] == "ashby"]
gh = [r for r in results if r["adapter"] == "greenhouse"]
lev = [r for r in results if r["adapter"] == "lever"]

print(f"\n=== RESULTS ===")
print(f"Ashby: {len(ash)} new")
print(f"Greenhouse: {len(gh)} new")
print(f"Lever: {len(lev)} new")
print(f"\nYAML to paste (sorted by adapter then name):")
print("# --- bulk-added 2026-05-16 ---")
for r in sorted(results, key=lambda x: (x["adapter"], x["name"])):
    print(f"  - {{ name: \"{r['name']}\", adapter: {r['adapter']}, slug: {r['slug']} }}  # auto, {r['jobs']} jobs")
print(f"\nFull JSON: {out}")
