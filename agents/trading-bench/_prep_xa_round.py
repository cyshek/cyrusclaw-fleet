"""One-off targeted round prep (main-directed 2026-06-26 mutation sprint).

prepare_round() samples parents UNIFORMLY at random, so with a small n it may
never breed from the brand-new cross-asset parent. Main explicitly asked to
"let it breed from trend_follow_uup so you get dollar-trend + cross-asset
children for the first time." So we construct the (parent, directive) pairs
DIRECTLY: guarantee UUP coverage, then sample the rest of the 9-parent pool for
diversity. We reuse _build_llm_prompt + the same /tmp round layout the
orchestrator's prepare_round uses, so finalize_round() consumes it unchanged.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.strategy_gen import MUTATION_DIRECTIVES, _build_llm_prompt  # noqa: E402
from runner.tournament_loop import GATE_PASSING_PARENTS  # noqa: E402

SEED = 4262026  # reproducible
rng = random.Random(SEED)

# --- forced pairs: breed the NEW cross-asset parent first (main's ask) ---
# Directive indices (0-based): 0=lookback sweep, 1=vol filter, 3=combine 2nd signal,
# 12=trailing stop. These are the most sensible mutations for a dollar-trend leg.
forced = [
    ("trend_follow_uup", MUTATION_DIRECTIVES[0]),   # lookback sweep on SMA period
    ("trend_follow_uup", MUTATION_DIRECTIVES[1]),   # volatility filter
    ("trend_follow_uup", MUTATION_DIRECTIVES[3]),   # combine with a second signal
]

# --- diversity sample: the rest of the pool (exclude UUP to spread breadth) ---
other_parents = [p for p in GATE_PASSING_PARENTS if p != "trend_follow_uup"]
N_DIVERSITY = 5
diversity = []
for _ in range(N_DIVERSITY):
    p = rng.choice(other_parents)
    d = rng.choice(MUTATION_DIRECTIVES)
    diversity.append((p, d))

pairs = forced + diversity

round_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
round_dir = Path("/tmp") / f"tournament_round_{round_id}"
round_dir.mkdir(parents=True, exist_ok=True)

items = []
for i, (parent, directive) in enumerate(pairs, 1):
    h = hashlib.sha1(directive.encode()).hexdigest()[:6]
    name = f"{parent}__mut_{h}"
    prompt = _build_llm_prompt(parent, directive, name)
    prompt_path = round_dir / f"prompt_{i:02d}.txt"
    prompt_path.write_text(prompt)
    items.append({
        "i": i,
        "parent": parent,
        "directive": directive,
        "candidate_name": name,
        "prompt_path": str(prompt_path),
        "output_path": str(round_dir / f"output_{i:02d}.txt"),
    })

meta = {"round_id": round_id, "round_dir": str(round_dir), "items": items}
(round_dir / "meta.json").write_text(json.dumps(meta, indent=2))

print(json.dumps({
    "round_id": round_id,
    "round_dir": str(round_dir),
    "n": len(items),
    "items": [
        {"i": it["i"], "parent": it["parent"], "name": it["candidate_name"],
         "directive_head": it["directive"].split("\n")[0][:70],
         "prompt_path": it["prompt_path"], "output_path": it["output_path"]}
        for it in items
    ],
}, indent=2))
