# Round 5 — Directive #16 (Post-Loss Cooldown)

_Subagent: Round 5 directive #16 evaluation, 2026-05-27 PT (19:55Z generated)._
_Source round report: `TOURNAMENT_ROUND_20260527T195402Z.md`._
_Logs: `logs/round5_dir16.log`._

## What shipped

- **`runner/strategy_gen.py`**: added directive #16 (post-loss cooldown) to `MUTATION_DIRECTIVES`. Directive count: 14 → 15 entries (slot #15 reserved for the still-blocked volume-confirmation directive).
- The new directive instructs the LLM to:
  - After a CLOSE whose exit price < `position_state[symbol]["avg_entry_price"]` (realized loss, fees ignored), set `strategy_state["cooldown_remaining"] = N`.
  - Decrement by 1 each bar; block ANY new entry while `> 0`.
  - Use `market_state["strategy_state"]` (cross-flat) so the counter survives the position going flat.
  - Exits NEVER gated by cooldown; safety backstops also unaffected (they short-circuit `decide()` before the strategy runs).
  - Pick `loss_cooldown_bars` ∈ [3, 20], roughly 0.25–1.0× parent's median holding bars.
- Includes a full working code skeleton in the prompt that pulls `avg_entry_price` from `position_state[symbol]` BEFORE the close clears it. Important design call: this avoids needing the strategy to mirror `entry_price` into `strategy_state` itself, because the runner already exposes it on every bar a position is open.

## How "detect realized loss" was solved

Investigated three options:

1. **`market_state` exposes `last_realized_pnl` after a close** — checked `runner/backtest.py` and `runner/runner.py`. Neither does. Closed trades land in `closed_trades` (backtest, post-loop) or in the `trades` DB table (live), but neither is wired into the next bar's `market_state`. Adding it would require touching backtest + runner + DB schema, which is out of write-scope.

2. **Strategy mirrors `entry_price` into `strategy_state` on entry, compares on close** — works, but redundant: `position_state[symbol]["avg_entry_price"]` is already authoritative and is refreshed every bar by both the backtester (line 396-401) and the live runner (line 90). Asking the strategy to mirror a value that the runner already provides invites drift bugs.

3. **Strategy reads `position_state[symbol]["avg_entry_price"]` at the moment of close, compares to `market_state["last_price"]`** — clean. The strategy reads BOTH values BEFORE returning the close action. After the action runs, `position_state[symbol]` is gone, but we've already captured what we needed and written `cooldown_remaining=N` into `strategy_state`. No new infra, no new fields, idempotent.

Picked option 3 and documented it explicitly in the skeleton so the LLM doesn't try to re-invent option 2.

Caveat noted in the directive: "exit price < avg_entry_price" ignores fees (~2bps round-trip on stocks) so it's a slight under-counter — a near-breakeven trade that lost only to fees won't arm cooldown. Honest trade-off vs requiring the strategy to know the cost model.

## How the round was run

- Tool: `python3 -m runner._run_round --n 4 --seed 16 --directive-slice 14:15`
- This restricts mutation directives to ONLY directive #16 (slice `14:15` of the 15-entry `MUTATION_DIRECTIVES` list).
- Parents: drawn from `GATE_PASSING_PARENTS` (canonical 4-entry list in `runner/tournament_loop.py`).
- Seed 16's RNG sampled `[breakout_xlk_regime, sma_crossover_qqq_regime, sma_crossover_qqq_regime, sma_crossover_qqq_regime]` (2 unique parents — `breakout_xlk` and `sma_crossover_qqq` were missed; `sma_crossover_qqq_regime` got 3 attempts which all produced the same candidate name and overwrote on disk, same artifact as directive #14's seed 4). Both regime-gated parents made it in, but the un-gated parents didn't — limitation of `_pick_pairs` sampling with replacement.
- LLM spawn: `runner/_run_round._cli_spawn` → `openclaw agent --local`. All 4 spawns succeeded (rc=0, 24–31 seconds each).

## Candidates produced (2 unique on disk)

| Candidate | Parent | Lives in | LLM code quality |
|---|---|---|---|
| `breakout_xlk_regime__mut_2728d3` | `breakout_xlk_regime` | `strategies_candidates/breakout_xlk_regime__mut_2728d3/` | Clean. N=8 (parent median holding=34, p25=16; ~0.24× median / 0.5× p25). Detect-loss check correctly placed before close action. Regime filter preserved. |
| `sma_crossover_qqq_regime__mut_2728d3` | `sma_crossover_qqq_regime` | `strategies_candidates/sma_crossover_qqq_regime__mut_2728d3/` | Clean. N=8. Same pattern. Regime filter preserved. Exits decoupled from cooldown bookkeeping. |

Both LLM mutants followed the directive faithfully: cooldown counter in `strategy_state` (cross-flat), exits ungated, `avg_entry_price` read pre-close as documented in the skeleton, no inert filter shenanigans, honest "expected firing rate" discussion in docstrings.

## Walk-forward + gate results

Walk-forward across the 8 named regime windows (per `runner/walk_forward.NAMED_WINDOWS`). Mutation gate (`passes_mutation_gate`) requires the mutant's median return to beat the parent's by ≥+0.10pp.

| # | Candidate | Parent medRet | Mutant medRet | Δ vs parent | Pos % | Median Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `breakout_xlk_regime__mut_2728d3` | +0.33% | +0.33% | **+0.00pp** | 75% | 3.18 | 🟡 REJECT_GATE |
| 2 | `sma_crossover_qqq_regime__mut_2728d3` | +0.41% | +0.41% | **+0.00pp** | 75% | 2.95 | 🟡 REJECT_GATE |
| 3 | `sma_crossover_qqq_regime__mut_2728d3` (dup) | +0.41% | +0.41% | **+0.00pp** | 75% | 2.95 | 🟡 REJECT_GATE |
| 4 | `sma_crossover_qqq_regime__mut_2728d3` (dup) | +0.41% | +0.41% | **+0.00pp** | 75% | 2.95 | 🟡 REJECT_GATE |

**0 / 4 PROMOTE.** Identical-to-parent across the board, with the cooldown firing in only ONE window out of 16 windows-evaluated.

### Per-window cross-check (mutant vs parent trade counts)

Re-ran walk-forward outside the tournament harness to verify the cooldown actually engages somewhere:

**`breakout_xlk_regime__mut_2728d3` vs parent `breakout_xlk_regime`:**

| window              | mut b/c   | mut_ret | par b/c   | par_ret | diff   |
|---------------------|-----------|---------|-----------|---------|--------|
| 2022-H1 bear        | 1b/1c     | -0.18%  | 1b/1c     | -0.18%  | same   |
| 2022-Q3 chop        | 5b/5c     | +0.41%  | 5b/5c     | +0.41%  | same   |
| 2023-H1 recovery    | 7b/6c     | +0.09%  | 7b/6c     | +0.09%  | same   |
| 2023-Q3 chop        | 5b/5c     | -0.02%  | 5b/5c     | -0.02%  | same   |
| 2024-Q2 bull        | 5b/4c     | +0.72%  | 5b/4c     | +0.72%  | same   |
| 2025-Q1 tariff bear | 1b/1c     | +0.26%  | 1b/1c     | +0.26%  | same   |
| 2025-Q3 bull        | 7b/6c     | +0.44%  | 7b/6c     | +0.44%  | same   |
| 2026-recent bull    | 2b/1c     | +2.40%  | 2b/1c     | +2.40%  | same   |

**Cooldown never engaged.** Same trade counts, same returns, all 8 windows.

**`sma_crossover_qqq_regime__mut_2728d3` vs parent `sma_crossover_qqq_regime`:**

| window              | mut b/c   | mut_ret | par b/c   | par_ret | diff   |
|---------------------|-----------|---------|-----------|---------|--------|
| 2022-H1 bear        | 1b/1c     | -0.21%  | 1b/1c     | -0.21%  | same   |
| 2022-Q3 chop        | 5b/5c     | +0.40%  | 5b/5c     | +0.40%  | same   |
| 2023-H1 recovery    | 9b/8c     | +0.74%  | 9b/8c     | +0.74%  | same   |
| 2023-Q3 chop        | 7b/7c     | +0.15%  | 7b/7c     | +0.15%  | same   |
| 2024-Q2 bull        | 6b/5c     | +0.83%  | 6b/5c     | +0.83%  | same   |
| 2025-Q1 tariff bear | **3b/3c** | -0.05%  | **4b/4c** | -0.04%  | **DIFF** |
| 2025-Q3 bull        | 9b/8c     | +0.42%  | 9b/8c     | +0.42%  | same   |
| 2026-recent bull    | 5b/4c     | +1.37%  | 5b/4c     | +1.37%  | same   |

**Cooldown engaged exactly ONCE across 16 windows** — 2025-Q1 tariff bear, where a losing trade armed the 8-bar cooldown and skipped one subsequent entry signal (4→3 trades). Net effect: ~-1bp (mutant -0.05% vs parent -0.04%), but rounds to the same median.

## Honest read

Directive #16 is a clean negative for **structural** reasons, not LLM-quality reasons. The LLM code is correct. The problem is the directive's hypothesis ("a recent loss = avoid the next N bars") barely fires on these parents because:

1. **Both candidates' parents have regime filters that ALREADY do this job, better.** The regime filter blocks entries whenever SPY < SMA(50), which is exactly the periods where losses cluster. By the time you've taken a loss inside an SPY-bull regime, you're often back in a tradeable regime by the cooldown window's end — and conversely, when the regime is bad, the regime filter has already blocked entries so the cooldown has nothing to add.

2. **Even on the `2025-Q1 tariff bear` window where it did fire**, the deferred trade was itself near-zero (the loss avoided was small and the trade skipped was small). Net effect was -1bp.

3. **The breakout parent literally never lost-AND-then-tried-to-re-enter-within-8-bars** across 8 historical windows. The natural reset cadence of Donchian channels in the post-loss state (you need a fresh N-bar high to even attempt entry) is already a de-facto cooldown of 8+ bars in most market conditions.

4. **The directive would shine on a non-regime-gated, mean-reverting parent** (think `rsi_mean_revert_eth`-style), where losses can cluster from chop and re-entries fire fast. None of the regime-gated breakout/crossover parents currently in `GATE_PASSING_PARENTS` exhibit that profile. The seed-16 RNG happening to draw 0 of the 2 non-regime parents in `GATE_PASSING_PARENTS` (`breakout_xlk`, `sma_crossover_qqq`) means this round didn't even test the directive against its best-fit candidates.

**Not worth promoting anything.** But unlike directive #14's *active degradation* (-0.10 to -0.17pp), this is *exact equivalence* — the directive isn't bad, it's just inert on these parents. That distinction matters: if `breakout_xlk` or `sma_crossover_qqq` (non-regime) had been in the seed-16 sample, or if the parent pool ever grows to include a mean-reverting strategy, this directive is still a reasonable thing to try.

## What this tells us about the LLM-mutation pipeline

- ✅ Persistent-state infra still working correctly — `strategy_state` survived across flat periods, the cooldown counter persisted post-close, and the runner correctly captured the `state['cooldown_remaining'] = N` write via the post-decide reassignment path.
- ✅ Mutation gate did its job — perfect-zero-delta candidates correctly rejected as "no improvement."
- ✅ Code review pass rate 4/4 — directive #16's bundled skeleton (with its explicit pre-close `avg_entry_price` read) kept the LLM inside the allowed-imports / no-FS / decide-signature envelope.
- ✅ End-to-end time-budget reasonable: ~27s avg per LLM spawn × 4 + walk-forward ~30s × 4 + parent baselines cached.

What we learned about *strategy edge*: this is now **9 mutation rounds with 0 net-positive promotions post-fix**. Directives #14 (entry-confirmation) and #16 (post-loss cooldown) are both *entry-gating* directives, and both came back inert-or-worse against the existing 4-parent pool. The pattern is the same as the inert-filter mutants from rounds 2–3: when the parent already has good entry timing (the regime filter does most of the heavy lifting), adding more entry gates doesn't help.

**The directive vocabulary is starting to look exhausted relative to the current parent pool.** Possible paths forward (none I'm authorized to ship on my own):

1. **Add non-regime-gated, non-trend-following parents** to `GATE_PASSING_PARENTS` so directives like #16 have a chance to fire meaningfully. Currently 3 of 4 parents are SMA / breakout / regime-gated, all trend-following.
2. **Try EXIT-side directives.** Every directive shipped so far has been a parameter sweep or an entry-gate. Exit-side mutations (e.g., scale-out at +R multiples, trailing-stop after a volatility threshold) actually showed real per-trade behavioral change post-position-state fix even when they didn't beat the gate — that's at least signal you can iterate on.
3. **Test #16 on the rejected candidate pool from earlier rounds**, not on already-passing parents. The hypothesis is more interesting against a strategy that loses sometimes than against one that wins consistently.

Worth surfacing to Cyrus before scheduling more rounds. Don't auto-pilot directive #17 until we've talked about parent-pool composition.

## Verification

- `python3 -m unittest discover tests -q` → **99/99 pass** (no regressions).
- `ls strategies_candidates/` includes the 2 new `*__mut_2728d3` candidates with `strategy.py` + `params.json` + `__init__.py`.
- `TOURNAMENT_ROUND_20260527T195402Z.md` exists on disk; this report cross-references it.
- Per-window cross-check via independent `walk_forward()` invocation confirms cooldown engaged in 1/16 (window, parent) pairs.
- Nothing moved to `strategies/`. Quarantine boundary preserved.

## Write-scope honesty

Touched only: `runner/strategy_gen.py` (added directive #16 + a reserved placeholder for #15), `strategies_candidates/*_mut_2728d3/` (2 dirs the round wrote), `logs/round5_dir16.log` (round log), and this report. Did not touch `runner/risk.py`, `runner/runner.py`, `runner/broker_alpaca.py`, `runner/backtest.py`, DB schema, or `strategies/`.
