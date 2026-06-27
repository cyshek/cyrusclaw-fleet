# Equity Cross-Parent Combo Round + 2-Parent Prompt Hardening — VERDICT

_2026-06-26 · trading-bench (Tessera) · main-greenlit hardening sprint_

## TL;DR

Two deliverables, both done:

1. **INFRA SHIPPED — genuine 2-parent combo prompts.** `_build_llm_prompt` now
   accepts an optional `second_parent` kwarg that injects the **second parent's
   real `strategy.py` source** as a labeled SECOND PARENT block, so the LLM fuses
   actual signal mechanisms instead of reconstructing one from a prose
   description. Purely additive; default call is **byte-identical** (golden MD5
   pinned). 6 new tests; full suite **843 passed / 3 skipped**.

2. **EMPIRICAL VERDICT — naive 2-parent fusion is value-destructive here.** Ran
   the first-ever genuine equity cross-parent round (5 combos where the LLM saw
   both parents' code). **All 5 REJECT_GATE** — and the reason is structurally
   important: every solo equity parent already has a strong standalone Sharpe
   (0.66–1.39), and fusing two of them **destroys** the risk-adjusted edge every
   time.

## The infra gap that was closed

Previously `_build_llm_prompt(seed, directive, name)` injected **only the single
seed parent's code**. A "combine parent A with parent B" directive was therefore
**guidance-text-only** — the model never saw B's actual signal logic, so
cross-parent combos were blind (B reconstructed from prose). That is almost
certainly why past combo mutations were weak.

**Fix (surgical, additive):** new optional `second_parent` kwarg. When set, B's
`strategy.py` is injected under a `## SECOND PARENT (\`<name>\`)` header with
explicit fusion guidance (prefer OR-combine entries; keep exits reachable; trade
the PRIMARY parent's symbol/timeframe). When `None` (every existing caller), the
assembled prompt is byte-identical — verified by pinning the pre-change MD5
`c122c51be2662bbecf477a71eaa0b3ce`.

- File: `runner/strategy_gen.py` (md5 `a9d17ee4…` → `1ff0239d…`). The
  load-bearing **enforcement** functions (`code_review`, `evaluate`,
  `_split_artifacts`, dedup) are logically unchanged — the full suite, which
  exercises them heavily, is green.
- Tests: `tests/test_strategy_gen_second_parent.py` (6 tests) — byte-identical
  backward-compat, second-parent injection, primary-block preservation,
  graceful handling of a missing second parent.
- Suite: **843 passed / 3 skipped** (was 837).

## The round — 5 genuine cross-parent combos (round `20260626T213436Z`)

Each combo's median Sharpe vs the candidate's **own** strongest solo parent:

| Combo | Combo medSharpe | medRet | pos | Strongest solo parent (Sharpe) |
|---|---|---|---|---|
| macd_momentum_iwm × breakout_xlk | 0.55 | +1.14% | 62% | breakout 1.36 / macd 0.66 |
| sma_crossover_qqq × macd_momentum_iwm | 0.24 | +0.49% | 62% | sma 1.29 / macd 0.66 |
| breakout_xlk × rsi_oversold_spy | 0.26 | +0.45% | 50% | breakout 1.36 / rsi 0.89 |
| volume_breakout_qqq × rsi_oversold_spy | **−0.51** | −0.29% | 50% | volbreak 1.39 / rsi 0.89 |
| rsi_oversold_spy × sma_crossover_qqq (filter) | 0.00 (**0 trades**) | +0.00% | rsi 0.89 |

Solo-parent walk-forward baselines: breakout_xlk **1.36**, volume_breakout_qqq
**1.39**, sma_crossover_qqq **1.29**, rsi_oversold_spy **0.89**,
macd_momentum_iwm **0.66**.

## Why every fusion lost (the generalizable lesson)

- **OR-fusion dilutes.** Adding the second parent's entries pulls in lower-quality
  signals → raw return / trade-count UP, Sharpe DOWN. `macd×breakout` is the clean
  demonstration: it *raised* raw return to +1.14% median but *cut* Sharpe from the
  parent's 0.66 to 0.55. The gate flagged it precisely: "raw-return beat is
  leverage/variance, not risk-adjusted edge."
- **AND-fusion over-restricts.** `rsi×sma-uptrend-filter` (buy-the-dip-only-in-an-
  uptrend) was so restrictive it fired **0 trades** across 8 windows.
- **Worst case goes negative.** `volbreak×rsi` fused a 1.39-Sharpe parent down to
  −0.51.

The `MUTATION_SHARPE_DELTA_TOL = -0.10` gate caught all five — working exactly as
designed. **You cannot improve an already-strong solo signal (e.g. a 1.36-Sharpe
Donchian breakout) by bolting a second signal onto it; the cross-term is noise.**

## What this means for future combo lanes

1. **Don't naively fuse two already-strong parents** — proven value-destructive.
2. A combo that could plausibly win must pair a strong parent with a **weak-but-
   orthogonal** signal that covers a regime the strong parent misses — not two
   high-Sharpe parents.
3. Or combine at the **book level** (allocator / sleeve weighting), where
   diversification helps, rather than at the **signal level** inside one `decide()`,
   where it dilutes.

The infra to do (1)–(2) now exists and is measurable. The empirical answer for the
naive case is logged so we don't re-run it.

## Artifacts

- `runner/strategy_gen.py` (hardened), `tests/test_strategy_gen_second_parent.py`
- `_prep_equity_crossparent_round.py` (prep; meta now carries `parent`+`directive`)
- `TOURNAMENT_ROUND_20260626T213436Z.md` (round report)
- No orders placed, no spend, hard rails untouched (paper-only + killswitch intact).
