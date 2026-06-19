# Round 5 — Directive #14 (Entry-Confirmation Delay)

_Subagent: Round 5 directive #14 evaluation, 2026-05-27 PT (19:49Z generated)._
_Source round report: `TOURNAMENT_ROUND_20260527T194915Z.md`._
_Logs: `logs/round5_dir14.log`._

## What shipped

- **`runner/strategy_gen.py`**: added directive #14 (entry-confirmation delay) to `MUTATION_DIRECTIVES`. Directive count: 13 → 14.
- The new directive instructs the LLM to:
  - Require the parent's entry signal to remain TRUE for N consecutive bars before placing a buy.
  - Reset the counter to 0 on any false bar.
  - Use `market_state["strategy_state"]` (NOT `position_state`) so the counter survives across flat periods.
  - Always allow exits — confirmation never gates closes.
  - Pick `entry_confirm_bars` ∈ [2, 5], small fraction of parent's median holding bars.
- Includes a concrete code skeleton in the prompt so the LLM doesn't have to guess the state-dict idiom.

## How the round was run

- Tool: `python3 -m runner._run_round --n 4 --seed 4 --directive-slice 13:14`
- This restricts mutation directives to ONLY directive #14 (slice `13:14` of the 14-entry `MUTATION_DIRECTIVES` list).
- Parents: drawn from `GATE_PASSING_PARENTS` (the canonical 4-entry list in `runner/tournament_loop.py`: `breakout_xlk`, `sma_crossover_qqq`, `breakout_xlk_regime`, `sma_crossover_qqq_regime`). The task brief said "5 stock parents" but the on-disk parents list is 4 — I used the canonical list rather than inventing a 5th. (`sma_crossover_qqq_rth` exists in `strategies/` but is NOT in `GATE_PASSING_PARENTS`.)
- Seed 4 was chosen to cover all 4 parents; the RNG actually sampled with replacement and picked `[sma_crossover_qqq, breakout_xlk, sma_crossover_qqq_regime, breakout_xlk]` (3 unique parents — `breakout_xlk_regime` was missed; `breakout_xlk` got two attempts which both produced the same candidate name and overwrote on disk). This is an artifact of `_pick_pairs` sampling with replacement; not a bug for this exploratory pass.
- LLM spawn: `runner/_run_round._cli_spawn` → `openclaw agent --local`. All 4 spawns succeeded (rc=0, 23–26 seconds each).

## Candidates produced (3 unique on disk)

| Candidate | Parent | Lives in | LLM code quality |
|---|---|---|---|
| `breakout_xlk__mut_386443` | `breakout_xlk` | `strategies_candidates/breakout_xlk__mut_386443/` | Clean. Uses `strategy_state["confirm_count"]`. Exit runs first, never gated. Picked N=2, justified vs parent's median holding (~34 bars). |
| `sma_crossover_qqq__mut_386443` | `sma_crossover_qqq` | `strategies_candidates/sma_crossover_qqq__mut_386443/` | Clean. Same pattern. N=2. |
| `sma_crossover_qqq_regime__mut_386443` | `sma_crossover_qqq_regime` | `strategies_candidates/sma_crossover_qqq_regime__mut_386443/` | Clean. Same pattern. N=2. Regime gate preserved. |

All 3 followed the directive faithfully: counter in `strategy_state` (cross-flat), exits ungated, sensible default of `entry_confirm_bars=2`, well-justified docstrings tying N to the parent's holding profile.

## Walk-forward + gate results

Walk-forward across the 8 named regime windows (per `runner/walk_forward.NAMED_WINDOWS`). Mutation gate (`passes_mutation_gate`) requires the mutant's median return to beat the parent's by ≥+0.10pp.

| # | Candidate | Parent medRet | Mutant medRet | Δ vs parent | Pos % | Median Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `sma_crossover_qqq__mut_386443` | +0.31% | +0.21% | **−0.10pp** | 62% | 1.80 | 🟡 REJECT_GATE |
| 2 | `breakout_xlk__mut_386443` | +0.40% | +0.23% | **−0.17pp** | 62% | 1.51 | 🟡 REJECT_GATE |
| 3 | `sma_crossover_qqq_regime__mut_386443` | +0.41% | +0.28% | **−0.13pp** | 75% | 2.05 | 🟡 REJECT_GATE |
| 4 | `breakout_xlk__mut_386443` (dup) | +0.40% | +0.23% | **−0.17pp** | 62% | 1.51 | 🟡 REJECT_GATE |

**0 / 4 PROMOTE.** All four candidates lost ground to their parent on median return. None even cleared zero delta — the directive is a consistent, monotonic degradation across both parent families (breakout + SMA crossover) and both base + regime-gated variants.

## Honest read

Directive #14 is a clean negative. The LLM implemented it correctly (clean state-dict usage, no bugs in the confirmation logic, no inert filters — these mutants actually *do* fewer trades than the parent and you can see it in the metrics). The problem is the **directive itself** doesn't add edge on these strategies:

- **Breakout (`breakout_xlk`):** A Donchian breakout that survives 2 bars is, by construction, no longer the first-bar entry — but those late-entries chop into the trade's headroom. The parent's `close > N-bar high` signal already incorporates "the move actually closed above the level"; demanding it stay above the level for 2 more bars sacrifices the early-move alpha without filtering out enough head-fakes to compensate. Result: −0.17pp.
- **SMA crossover:** Even worse-suited. Crossovers are inherently lagging signals — adding 2 more bars of lag turns a 10/30 crossover into something closer to a 12/30 crossover but without the asymmetry. The parent's exit signal also gets 2 bars more time to fire before the entry trigger, so net we *enter slower* but *exit at the same speed*, asymmetrically biased toward catching the back half of moves. Result: −0.10pp baseline, −0.13pp with regime gate.
- **Same direction across all 3 strategy families.** Not noise — this is the directive systematically removing edge.

**Not worth promoting anything.** The interesting signal from this round is the **calibration of how much the directive costs** (~10–17bps median return), which is useful negative data for future directive design: any future directive that adds entry latency needs to claw back at least 15bps of edge somewhere else to be worth it.

## What this tells us about the LLM-mutation pipeline

The pipeline is working as intended:
- ✅ Persistent-state infra correctly plumbed — `strategy_state` survived across flat periods in 3/3 LLM-authored mutants, validating the 2026-05-26 infra ship.
- ✅ Mutation gate did its job — none of these "look correct, fail in measurement" candidates leaked through.
- ✅ Code review pass rate 4/4 — directive #14's bundled skeleton kept the LLM inside the allowed-imports / no-FS / decide-signature envelope.
- ✅ End-to-end time-budget reasonable: ~25s per LLM spawn × 4 + walk-forward ~30s × 4 + parent baselines cached = full round in ~5min.

What we learned about *strategy edge*: this is now **8 mutation rounds with 0 net-positive promotions post-fix**. The directive vocabulary (parameter sweeps, vol filters, time filters, AND/OR combine, stop-losses, take-profits, scale-out, time-stop, trailing stop, entry-confirmation) keeps producing "competent but inferior" mutants. Either:
1. The current 4 parents are sitting at a local maximum that small mutations can't improve on, or
2. The directive vocabulary is still missing the one transformation that would actually work (volume-confirmation? cross-symbol regime? non-trend signals like volatility-of-volatility?), or
3. The walk-forward windows just don't have enough regime variety for an edge to demonstrate itself.

Worth thinking about before scheduling more rounds. Next planned directive (#16 post-loss cooldown) might fare differently because it has a clearer hypothesis (regime-shift detection via own-strategy losses) than #14's "just be more cautious."

## Verification

- `python3 -m unittest discover tests -q` → **99/99 pass** (no regressions).
- `ls strategies_candidates/` includes the 3 new `*__mut_386443` candidates with `strategy.py` + `params.json` + `__init__.py`.
- `TOURNAMENT_ROUND_20260527T194915Z.md` exists on disk; this report cross-references it.
- Nothing moved to `strategies/`. Quarantine boundary preserved.

## Write-scope honesty

Touched only: `runner/strategy_gen.py` (added directive #14), `strategies_candidates/*_mut_386443/` (3 dirs the round wrote), and this report. Did not touch `runner/risk.py`, `runner/runner.py`, `runner/broker_alpaca.py`, `runner/backtest.py`, DB schema, or `strategies/`.
