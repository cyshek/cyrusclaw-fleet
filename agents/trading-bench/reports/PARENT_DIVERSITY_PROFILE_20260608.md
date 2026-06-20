# Parent-Pool Diversity Profile — 2026-06-08

**Purpose:** The mutation engine samples parents only from `GATE_PASSING_PARENTS`
(`runner/tournament_loop.py` ~L43) = `["breakout_xlk","sma_crossover_qqq",
"breakout_xlk_regime","sma_crossover_qqq_regime"]` — only **2 underlying signals**
(Donchian breakout on XLK; SMA-crossover on QQQ), each with a plain + regime-gated
variant. To diversify, we want to add *already-validated, genuinely different*
strategies. This report measures which other `strategies/` candidates actually clear
the **fitness gate** on their own, and whether they add a distinct signal family.

**Method (READ-ONLY):** For each strategy, ran the real
`runner.walk_forward.walk_forward(name)` (8-window regime-balanced walk-forward) then
`passes_fitness_gate(agg)`. No runner/strategy/test code was modified. Per-strategy
failures were trapped (none occurred). Raw JSON: `reports/_profile_parents_results.json`.

**Fitness gate (all must hold):** `median_return_pct > 0` · `pct_positive ≥ 0.50` ·
`pct_beat_bh_spy ≥ 0.50` · `median_sharpe > 0.50` · `≥3` windows with data.

`sharpe_sign_consistency` = fraction of the 8 windows whose per-window Sharpe shares
the sign of the median Sharpe (higher = more regime-robust direction).

## Results

All 8 strategies returned data in all 8/8 windows.

| strategy | signal family | symbol | median_ret% | median_sharpe | total_trades | pct_positive | sharpe_sign_consistency | fitness_gate | reason |
|---|---|---|---|---|---|---|---|---|---|
| momentum_arkk            | momentum        | ARKK | −0.36 | −0.83 | 118 | 38% | 0.62 | **FAIL** | median ret −0.36% ≤ 0; only 38% windows positive; median Sharpe −0.83 ≤ 0.50 |
| rsi_mean_revert_iwm      | mean-reversion  | IWM  | −0.04 | −0.28 |  75 | 38% | 0.62 | **FAIL** | median ret −0.04% ≤ 0; only 38% windows positive; median Sharpe −0.28 ≤ 0.50 |
| trend_follow_gld         | trend           | GLD  | −0.08 | −1.21 |  43 | 25% | 0.75 | **FAIL** | median ret −0.08% ≤ 0; only 25% windows positive; median Sharpe −1.21 ≤ 0.50 |
| sma_crossover_qqq_rth    | trend (SMA-x)   | QQQ  | +0.33 | +2.78 | 142 | 62% | 0.62 | **PASS** | passed |
| _breakout_xlk_ (parent)            | breakout        | XLK  | +0.40 | +2.75 |  96 | 62% | 0.62 | PASS | passed |
| _sma_crossover_qqq_ (parent)       | trend (SMA-x)   | QQQ  | +0.31 | +2.60 | 142 | 62% | 0.62 | PASS | passed |
| _breakout_xlk_regime_ (parent)     | breakout+regime | XLK  | +0.33 | +3.18 |  62 | 75% | 0.75 | PASS | passed |
| _sma_crossover_qqq_regime_ (parent)| trend+regime    | QQQ  | +0.41 | +2.95 |  88 | 75% | 0.75 | PASS | passed |

(The four parents are re-profiled as a baseline; their PASS results reconfirm the
current pool. Regime-gated variants carry the highest sign-consistency, 0.75.)

## Non-parent candidate verdicts (one-liner each)

- **momentum_arkk — FAIL.** Negative across the board (median Sharpe −0.83, 38% positive). Long-only momentum on a high-beta ARKK got chopped up in the bear/chop windows; not gate-worthy.
- **rsi_mean_revert_iwm — FAIL.** Essentially flat-to-negative (median ret −0.04%, Sharpe −0.28, 38% positive). Mean-reversion on IWM doesn't clear any of the four thresholds.
- **trend_follow_gld — FAIL.** Worst of the four (median Sharpe −1.21, only 25% of windows positive, just 43 trades). GLD trend-following is the weakest fit to this equity-regime panel.
- **sma_crossover_qqq_rth — PASS.** Clears the gate cleanly (median ret +0.33%, Sharpe +2.78, 62% positive, 142 trades) — but it is QQQ + SMA-crossover, i.e. an **entry-timing variant of an existing parent family**, not a new signal.

## RECOMMENDATION

**Add to the parent pool: none of the four candidates as a *diversifier*.** The goal
was to broaden the pool to genuinely different, validated signals. The data says that
goal is not satisfied by any candidate here:

- The three candidates that would have introduced a **distinct signal family**
  — `momentum_arkk` (momentum), `rsi_mean_revert_iwm` (mean-reversion),
  `trend_follow_gld` (trend on a non-equity, gold) — **all FAIL the fitness gate**,
  most of them badly (negative median Sharpe, <50% positive windows). Adding any of
  them would inject parents that lose money across the regime panel; they are
  **excluded**.
- The only candidate that **passes**, `sma_crossover_qqq_rth`, adds **no
  diversification**: same symbol (QQQ) and same signal family (SMA-crossover) as the
  existing `sma_crossover_qqq` / `sma_crossover_qqq_regime` parents. It is an
  entry-filter (RTH-only) refinement, so it would deepen concentration on the QQQ /
  SMA-crossover signal rather than broaden the pool. **Not recommended as a
  diversity add.**

### Bottom line
The current 2-signal parent pool (XLK-breakout, QQQ-SMA-crossover, ± regime) is, on
this evidence, the **only set of strategies in `strategies/` that both passes the gate
and is worth keeping as a parent**. There is **no existing, already-validated strategy
that simultaneously (a) clears the gate and (b) adds a new signal family.** True
diversification will require *building/tuning new* orthogonal strategies (e.g. a
short/flat-capable variant, or a mean-reversion / cross-sectional / vol strategy)
until they clear the gate — not promoting any of these four as-is.

If a marginal, same-family expansion is nonetheless desired (e.g. purely to add
genetic variety in the QQQ-SMA lineage), `sma_crossover_qqq_rth` is the only
gate-passing option — but flag it explicitly as a **non-diversifying** add, since it
narrows rather than broadens the signal base.
