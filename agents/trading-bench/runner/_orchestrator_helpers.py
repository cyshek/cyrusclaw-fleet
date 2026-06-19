"""Helpers used by the orchestrator subagent to drive ONE round when it must
manually wire sessions_spawn from the OpenClaw runtime.

Two-step flow:
  1. prepare_round(n) -> picks (parent, directive) pairs, builds prompts,
     dumps them to /tmp so the orchestrator can read & spawn each one.
  2. finalize_round(round_dir) -> reads back the LLM outputs from disk,
     runs evaluate() per candidate, writes TOURNAMENT_ROUND_*.md, returns
     the same dict run_one_round would have.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.strategy_gen import (  # noqa: E402
    MUTATION_DIRECTIVES,
    _build_llm_prompt,
    evaluate,
)
from runner.tournament_loop import (  # noqa: E402
    GATE_PASSING_PARENTS,
    _format_round_report,
    _pick_pairs,
    _wf_summary,
)


def prepare_round(n: int, seed: int | None = None) -> dict:
    round_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    pairs = _pick_pairs(n, GATE_PASSING_PARENTS, MUTATION_DIRECTIVES, seed=seed)
    round_dir = Path("/tmp") / f"tournament_round_{round_id}"
    round_dir.mkdir(parents=True, exist_ok=True)
    items = []
    import hashlib
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
    return meta


def finalize_round(round_dir: str) -> dict:
    rd = Path(round_dir)
    meta = json.loads((rd / "meta.json").read_text())
    results = []
    for item in meta["items"]:
        out_path = Path(item["output_path"])
        if not out_path.exists():
            results.append({
                "parent": item["parent"],
                "directive": item["directive"],
                "candidate_name": item["candidate_name"],
                "verdict": "REJECT_CRASH",
                "code_review": None,
                "fitness_gate": None,
                "walk_forward_summary": None,
                "quarantine_path": None,
                "error": f"missing output file {out_path}",
            })
            continue
        llm_output = out_path.read_text()
        from runner.strategy_gen import _split_artifacts
        code, params = _split_artifacts(llm_output)
        candidate = {
            "name": item["candidate_name"],
            "code": code,
            "params": params,
            "parent": item["parent"],
            "directive": item["directive"],
            "agent_session_key": item.get("session_key", "manual-orchestrator"),
            "raw_llm_output": llm_output,
        }
        eval_result = evaluate(candidate)
        results.append({
            "parent": item["parent"],
            "directive": item["directive"],
            "candidate_name": candidate["name"],
            "verdict": eval_result["verdict"],
            "code_review": eval_result["code_review"],
            "fitness_gate": eval_result["fitness_gate"],
            "walk_forward_summary": _wf_summary(eval_result.get("walk_forward_results")),
            "quarantine_path": eval_result.get("quarantine_path"),
            "error": eval_result.get("error"),
        })

    report_path = WORKSPACE / f"TOURNAMENT_ROUND_{meta['round_id']}.md"
    report_path.write_text(_format_round_report(meta["round_id"], results, dry_run=False))
    return {
        "round_id": meta["round_id"],
        "n_candidates": len(results),
        "results": results,
        "report_path": str(report_path),
        "dry_run": False,
    }
