"""Orchestrator wrapper: runs run_one_round() with a spawn_fn that shells out
to `openclaw agent --local --json` to spin up a one-shot LLM subagent and
returns its final assistant text.

Used by the orchestrator subagent for the first live tournament round.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.tournament_loop import run_one_round  # noqa: E402


def _cli_spawn(*, prompt: str, task_label: str) -> dict:
    """Run a fresh embedded agent turn via the `openclaw agent` CLI and
    return its final assistant text in the {output, session_key} shape that
    `generate_candidate` expects."""
    # Unique session-key per candidate so each invocation starts cold.
    sk = f"agent:trading-bench:strategy-gen-{task_label}-{uuid.uuid4().hex[:8]}"
    cmd = [
        "openclaw", "agent",
        "--local",
        "--json",
        "--agent", "trading-bench",
        "--session-key", sk,
        "--message", prompt,
        "--timeout", "600",
    ]
    t0 = time.time()
    print(f"[spawn] {task_label} session={sk}", file=sys.stderr, flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    elapsed = time.time() - t0
    print(f"[spawn] {task_label} done in {elapsed:.1f}s rc={proc.returncode}",
          file=sys.stderr, flush=True)
    if proc.returncode != 0:
        return {
            "output": "",
            "session_key": sk,
            "error": f"openclaw agent exited {proc.returncode}: {proc.stderr[-500:]}",
        }
    # The CLI emits a banner line about plugins to stdout then a JSON object.
    # Be defensive: find the first '{' and JSON-load from there.
    out = proc.stdout
    brace = out.find("{")
    if brace < 0:
        return {"output": "", "session_key": sk,
                "error": f"no JSON in stdout: {out[:500]}"}
    try:
        payload = json.loads(out[brace:])
    except Exception as e:
        return {"output": "", "session_key": sk,
                "error": f"JSON parse failed: {e}; head={out[brace:brace+300]}"}
    # The visible text field is the assistant's final reply. The CLI puts
    # it under `meta.*` (current schema) but older runs landed it under
    # `data.*` — accept either.
    meta = payload.get("meta") or payload.get("data") or {}
    text = (meta.get("finalAssistantVisibleText")
            or meta.get("finalAssistantRawText")
            or "")
    if not text:
        # Last resort: scan the whole payload for the field.
        def _find(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("finalAssistantVisibleText", "finalAssistantRawText") and isinstance(v, str) and v:
                        return v
                    r = _find(v)
                    if r:
                        return r
            elif isinstance(o, list):
                for v in o:
                    r = _find(v)
                    if r:
                        return r
            return None
        text = _find(payload) or ""
    return {"output": text, "session_key": sk}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--directive-slice", type=str, default=None,
                    help="Restrict mutation directives to a Python slice, e.g. '9:13' "
                         "to sample only directives 10-13 (0-indexed 9-12). "
                         "Useful for focused tests of newly-added directives.")
    args = ap.parse_args()

    directives = None
    if args.directive_slice:
        from runner.strategy_gen import MUTATION_DIRECTIVES
        try:
            start_s, end_s = args.directive_slice.split(":")
            start = int(start_s) if start_s else None
            end = int(end_s) if end_s else None
            directives = MUTATION_DIRECTIVES[start:end]
            if not directives:
                print(f"ERROR: --directive-slice {args.directive_slice} "
                      f"selected 0 directives from {len(MUTATION_DIRECTIVES)}",
                      file=sys.stderr)
                sys.exit(2)
            print(f"Restricting to {len(directives)} directives "
                  f"(slice {args.directive_slice} of {len(MUTATION_DIRECTIVES)})",
                  file=sys.stderr)
        except ValueError:
            print(f"ERROR: --directive-slice must be 'start:end' (got {args.directive_slice!r})",
                  file=sys.stderr)
            sys.exit(2)

    result = run_one_round(
        n_candidates=args.n,
        spawn_fn=_cli_spawn,
        seed=args.seed,
        directives=directives,
    )
    print(f"\nRound {result['round_id']} done.")
    print(f"Report: {result['report_path']}")
    counts = {}
    for r in result["results"]:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    for v, c in sorted(counts.items()):
        print(f"  {v}: {c}")


if __name__ == "__main__":
    main()
