"""Step 1: pick pair + emit prompt to /tmp/round_prompt.txt."""
import json, sys
from runner.tournament_loop import _pick_pairs, GATE_PASSING_PARENTS, MUTATION_DIRECTIVES
from runner.strategy_gen import _build_llm_prompt
import hashlib

pairs = _pick_pairs(1, GATE_PASSING_PARENTS, MUTATION_DIRECTIVES, seed=None)
parent, directive = pairs[0]
h = hashlib.sha1(directive.encode()).hexdigest()[:6]
name = f"{parent.replace('/', '_')}__mut_{h}"
prompt = _build_llm_prompt(parent, directive, name)
with open("/tmp/round_prompt.txt", "w") as f:
    f.write(prompt)
meta = {"parent": parent, "directive": directive, "candidate_name": name}
with open("/tmp/round_meta.json", "w") as f:
    json.dump(meta, f)
print(json.dumps(meta, indent=2))
