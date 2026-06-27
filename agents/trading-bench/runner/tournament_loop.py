"""Tournament orchestrator — picks (parent, directive) pairs, generates
candidate strategies via LLM, evaluates each, writes a round report.

This is the function the NEXT subagent invokes to actually generate
candidates. This module itself does no LLM calls without explicit opt-in;
the spawn_fn is either injected (tests) or wired to OpenClaw's
sessions_spawn by the orchestrator subagent at call time.

CLI:
    python3 -m runner.tournament_loop --n 3 --dry-run

    --dry-run skips the LLM spawn entirely. Instead, it hand-rolls a dummy
    candidate that is a verbatim copy of `breakout_xlk_regime` renamed.
    This proves the plumbing end-to-end (code review → quarantine write →
    walk-forward → gate → report) without spending tokens.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from .strategy_gen import (  # noqa: E402
    MUTATION_DIRECTIVES,
    code_review,
    evaluate,
    generate_candidate,
)

# Strategies that have passed the fitness gate AND are eligible as parents.
# Update by hand when new strategies graduate (intentional; we don't want
# the orchestrator to auto-pick freshly-mutated candidates as parents until
# a human has reviewed them).
GATE_PASSING_PARENTS: List[str] = [
    "breakout_xlk",
    "sma_crossover_qqq",
    "breakout_xlk_regime",
    "sma_crossover_qqq_regime",
    # New archetypes added 2026-06-13: diversify signal families for mutation
    "rsi_oversold_spy",      # RSI mean-reversion on SPY (Sharpe 1.80, 62% pos)
    "volume_breakout_qqq",   # Volume-confirmed breakout on QQQ (Sharpe 2.80, 62% pos)
    "macd_momentum_iwm",     # MACD momentum on IWM (Sharpe 1.33, 75% pos)
    # Added 2026-06-25: low-corr GLD trend archetype (corr +0.019 vs pool,
    # orthogonal to equity book; profiles clean 8/8 windows). Diversifies the
    # mutation gene pool away from the equity-momentum cluster.
    "trend_follow_gld",      # Trend-follow on GLD (gold; distinct asset class)
    # Added 2026-06-26 (main-directed cross-asset DNA sprint): the SINGLE-NAME
    # carrier of the validated cross-asset TSMOM archetype. The slow 5-asset
    # 12-1 absolute-momentum book (reports/XA_TSMOM_12_1_GATE_20260626T164538Z.md,
    # OOS Sharpe 1.14 vs SPY 0.90 at half the drawdown) CANNOT be a parent (a
    # 12-mo lookback needs ~294 bars; the 60-90d NAMED_WINDOWS give ~62 -> zero
    # trades; and it is decide_xsec = single-name profiler can't run it). So the
    # cross-asset DNA is injected via this fast US-DOLLAR trend leg, chosen
    # empirically as the MOST equity-orthogonal carrier (monthly trend-return
    # corr to SPY -0.415, to GLD -0.344 -> orthogonal to BOTH the equity pool and
    # the gold parent). De-correlator parent (gate-failing by design; children
    # independently gated). Validated 5-asset book stays at strategies/xa_tsmom_12_1
    # as evidence + a standalone-tracker candidate.
    "trend_follow_uup",      # Trend-follow on UUP (US dollar; cross-asset de-correlator)
]


# ---------------------------------------------------------------------------
# Dry-run dummy candidate generator (no LLM call)
# ---------------------------------------------------------------------------

def _dry_run_spawn(*, prompt: str, task_label: str) -> dict:
    """Hand-rolled dummy: copy `breakout_xlk_regime` verbatim and rename it.
    Used to test the plumbing without LLM cost. Returns the same shape a
    real LLM subagent would return."""
    # Read the actual gold-standard strategy and pretend the LLM produced it.
    sp = WORKSPACE / "strategies/breakout_xlk_regime/strategy.py"
    pp = WORKSPACE / "strategies/breakout_xlk_regime/params.json"
    code = sp.read_text()
    params = pp.read_text()
    fake_output = (
        "```python\n"
        "# === strategy.py ===\n"
        f"{code}\n"
        "```\n\n"
        "```json\n"
        "# === params.json ===\n"
        f"{params}\n"
        "```\n"
    )
    return {"output": fake_output, "session_key": "dry-run-no-session"}


# ---------------------------------------------------------------------------
# One round
# ---------------------------------------------------------------------------

def _pick_pairs(n: int,
                parents: List[str],
                directives: List[str],
                seed: Optional[int] = None) -> List[Tuple[str, str]]:
    """Pick n random (parent, directive) pairs. Sampling with replacement so
    n > len(parents) * len(directives) is fine — and so the same parent can
    appear twice in a round (intentional: different directives = different
    candidates from the same seed)."""
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        pairs.append((rng.choice(parents), rng.choice(directives)))
    return pairs


def _get_postmortem_hint(parent: str, postmortem_dir: Path, directives: List[str]) -> Optional[str]:
    """Look up the directive suggested in the most recent postmortem for `parent`."""
    try:
        from .postmortem import get_postmortem_directive_hint
        return get_postmortem_directive_hint(parent, postmortem_dir, directives)
    except Exception:  # noqa: BLE001
        return None


def _pick_pairs_with_postmortem_hints(
    n: int,
    parents: List[str],
    directives: List[str],
    workspace: Path,
    seed: Optional[int] = None,
) -> List[Tuple[str, str]]:
    """Like _pick_pairs but checks postmortem notes for directive hints.

    For each pair sampled, checks if the chosen parent has a recent postmortem
    (within 14 days). If yes, uses the postmortem-suggested directive with 70%
    probability instead of a uniformly random directive.
    """
    rng = random.Random(seed)
    postmortem_dir = workspace / "reports" / "postmortem"
    pairs = []
    for _ in range(n):
        parent = rng.choice(parents)
        hint_directive = _get_postmortem_hint(parent, postmortem_dir, directives)
        if hint_directive and rng.random() < 0.70:
            directive = hint_directive
        else:
            directive = rng.choice(directives)
        pairs.append((parent, directive))
    return pairs


def run_one_round(n_candidates: int = 3,
                  *,
                  parents: Optional[List[str]] = None,
                  directives: Optional[List[str]] = None,
                  spawn_fn: Optional[Callable] = None,
                  dry_run: bool = False,
                  report_dir: Optional[Path] = None,
                  seed: Optional[int] = None,
                  ) -> dict:
    """Run one round of candidate generation + evaluation.

    Args:
        n_candidates: how many candidates to generate this round.
        parents: parent strategies to sample from. Defaults to GATE_PASSING_PARENTS.
        directives: mutation directives. Defaults to MUTATION_DIRECTIVES.
        spawn_fn: LLM subagent spawn function. If None and dry_run=False,
            generate_candidate's default raises NotImplementedError (this is
            intentional — orchestrator subagent must explicitly wire it).
        dry_run: if True, use _dry_run_spawn (no LLM call). Default False.
        report_dir: where to write the round report. Defaults to workspace root.
        seed: RNG seed for reproducible pair-picking. Default: random.

    Writes `TOURNAMENT_ROUND_<ISO-date>.md` to report_dir.

    Returns: {round_id, n_candidates, results: [...], report_path}.
    """
    parents = parents or GATE_PASSING_PARENTS
    directives = directives or MUTATION_DIRECTIVES
    report_dir = report_dir or WORKSPACE
    if dry_run and spawn_fn is None:
        spawn_fn = _dry_run_spawn

    # Loss-triggered postmortem: generate diagnostic notes for losing strategies.
    # These notes inform mutation directives in future rounds.
    try:
        from .postmortem import run_postmortems_for_all as _postmortems
        _postmortems()   # idempotent; writes only if lost + no postmortem this week yet
    except Exception as _pm_exc:  # noqa: BLE001
        print(f"[tournament_loop] postmortem step skipped: {_pm_exc}", file=sys.stderr)

    round_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    pairs = _pick_pairs_with_postmortem_hints(n_candidates, parents, directives, WORKSPACE, seed=seed)

    results = []
    for i, (parent, directive) in enumerate(pairs, 1):
        print(f"[{i}/{n_candidates}] parent={parent} directive={directive[:60]}...",
              file=sys.stderr)
        candidate = generate_candidate(parent, directive, spawn_fn=spawn_fn)
        eval_result = evaluate(candidate)
        results.append({
            "parent": parent,
            "directive": directive,
            "candidate_name": candidate["name"],
            "verdict": eval_result["verdict"],
            "code_review": eval_result["code_review"],
            "fitness_gate": eval_result["fitness_gate"],
            "walk_forward_summary": _wf_summary(eval_result.get("walk_forward_results")),
            "quarantine_path": eval_result.get("quarantine_path"),
            "error": eval_result.get("error"),
        })
        v = eval_result["verdict"]
        print(f"    -> {v}", file=sys.stderr)

    report_path = report_dir / f"TOURNAMENT_ROUND_{round_id}.md"
    report_path.write_text(_format_round_report(round_id, results, dry_run=dry_run))

    return {
        "round_id": round_id,
        "n_candidates": n_candidates,
        "results": results,
        "report_path": str(report_path),
        "dry_run": dry_run,
    }


def _wf_summary(wf: Optional[dict]) -> Optional[dict]:
    """Trim walk-forward result to the headline numbers for the report."""
    if not wf:
        return None
    return {
        "median_return_pct": wf.get("median_return_pct"),
        "pct_positive": wf.get("pct_positive"),
        "pct_beat_bh_spy": wf.get("pct_beat_bh_spy"),
        "median_sharpe": wf.get("median_sharpe"),
        "worst_return_pct": wf.get("worst_return_pct"),
        "best_return_pct": wf.get("best_return_pct"),
        "n_windows_with_data": wf.get("n_windows_with_data"),
        "total_trades": wf.get("total_trades"),
    }


def _format_round_report(round_id: str, results: List[dict], *, dry_run: bool) -> str:
    lines = [
        f"# Tournament Round {round_id}",
        "",
        f"_Mode: {'DRY-RUN (no LLM)' if dry_run else 'LIVE LLM generation'}_",
        f"_Generated: {datetime.utcnow().isoformat()}Z_",
        f"_Candidates: {len(results)}_",
        "",
        "## Summary",
        "",
        "| # | Parent | Directive | Candidate | Verdict | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        notes = []
        cr = r.get("code_review") or {}
        if cr.get("violations"):
            notes.append("code_review: " + "; ".join(cr["violations"][:2]))
        fg = r.get("fitness_gate") or {}
        if fg.get("reason") and not fg.get("passed"):
            notes.append("gate: " + fg["reason"])
        wf = r.get("walk_forward_summary") or {}
        if wf:
            notes.append(f"medRet={wf.get('median_return_pct', 0):+.2f}% "
                        f"pos={wf.get('pct_positive', 0) * 100:.0f}% "
                        f"medSharpe={wf.get('median_sharpe', 0):.2f}")
        if r.get("error"):
            notes.append("ERROR: " + r["error"][:120])
        directive_short = (r["directive"][:50] + "...") if len(r["directive"]) > 50 else r["directive"]
        verdict_icon = {
            "PROMOTE": "🟢 PROMOTE",
            "REJECT_GATE": "🟡 REJECT_GATE",
            "REJECT_CODE_REVIEW": "🔴 REJECT_CODE_REVIEW",
            "REJECT_CRASH": "💥 REJECT_CRASH",
        }.get(r["verdict"], r["verdict"])
        lines.append(
            f"| {i} | `{r['parent']}` | {directive_short} | `{r['candidate_name']}` | "
            f"{verdict_icon} | {' · '.join(notes) or '—'} |"
        )

    lines += ["", "## Verdict counts", ""]
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    for v, c in sorted(counts.items()):
        lines.append(f"- **{v}**: {c}")

    promoted = [r for r in results if r["verdict"] == "PROMOTE"]
    if promoted:
        lines += [
            "",
            "## Candidates flagged for manual promotion review",
            "",
            "These passed code review AND the walk-forward fitness gate. "
            "**They are quarantined in `strategies_candidates/` and NOT yet "
            "scheduled.** Tessera must read the code + the walk-forward detail "
            "below and move the directory by hand to `strategies/` before any "
            "live paper trading.",
            "",
        ]
        for r in promoted:
            lines.append(f"### `{r['candidate_name']}` (parent: `{r['parent']}`)")
            lines.append(f"- Directive: {r['directive']}")
            lines.append(f"- Quarantine path: `{r['quarantine_path']}`")
            wf = r.get("walk_forward_summary") or {}
            if wf:
                lines.append(
                    f"- WF: median return {wf['median_return_pct']:+.2f}%, "
                    f"{wf['pct_positive'] * 100:.0f}% positive, "
                    f"{wf['pct_beat_bh_spy'] * 100:.0f}% beat BH-SPY, "
                    f"median Sharpe {wf['median_sharpe']:.2f}, "
                    f"worst {wf['worst_return_pct']:+.2f}%, "
                    f"best {wf['best_return_pct']:+.2f}%, "
                    f"{wf['total_trades']} total trades."
                )
            lines.append("")

    rejected_code = [r for r in results if r["verdict"] == "REJECT_CODE_REVIEW"]
    if rejected_code:
        lines += ["", "## Rejected at code review", ""]
        for r in rejected_code:
            lines.append(f"- `{r['candidate_name']}` (parent `{r['parent']}`)")
            for v in (r.get("code_review") or {}).get("violations", []):
                lines.append(f"  - {v}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Run one tournament round (generate + evaluate candidates).")
    ap.add_argument("--n", type=int, default=3,
                    help="Number of candidates to generate this round (default 3).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip LLM spawn; use a hand-rolled dummy candidate for plumbing test.")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed for reproducible (parent, directive) sampling.")
    ap.add_argument("--report-dir", default=str(WORKSPACE),
                    help="Where to write the TOURNAMENT_ROUND_*.md report.")
    args = ap.parse_args()

    result = run_one_round(
        n_candidates=args.n,
        dry_run=args.dry_run,
        report_dir=Path(args.report_dir),
        seed=args.seed,
    )

    print(f"\nRound {result['round_id']} done — {result['n_candidates']} candidates.")
    print(f"Report: {result['report_path']}")
    counts = {}
    for r in result["results"]:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    for v, c in sorted(counts.items()):
        print(f"  {v}: {c}")


if __name__ == "__main__":
    main()
