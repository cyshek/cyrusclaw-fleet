# LOSS-TRIGGERED POSTMORTEM LOOP — enrichment + generation-prompt injection

**Run:** 20260630T160838Z · **Agent:** trading-bench · **Assignment:** BACKLOG [V]4 (main-assigned) · **Model:** opus
**Mode:** infra build (paper-research). No live order paths, no crontab changes, no .db writes beyond `reports/postmortem/` storage. All 6 protected md5s unchanged.

---

## TL;DR

The loss-triggered postmortem loop **already existed in skeleton** (`runner/postmortem.py` + wiring in `runner/tournament_loop.py`): a per-round hook that writes a "why did this lose" note for any strategy with a negative realized PnL over the trailing 7 days, a 5-cause classifier, and a directive-biasing hint for the mutation step. This assignment **made it actually diagnostic and actually fed it into generation** — closing the four gaps between the skeleton and main's spec:

1. **Regime at loss time** — the note now states the *actual* market regime during the loss window (SPY net return + % of days above its 50-day SMA → BULL / BEAR / CHOP), not just a heuristic inference. (Previously absent; `REGIME_MISMATCH` was guessed from win-rate/buy-fraction with no market context.)
2. **Cost-vs-edge breakdown** — explicit dollar split of the loss into *directional edge* (implied gross PnL) vs *transaction-cost drag* (turnover × 2bps), with a ⚠️ flag when cost drag alone exceeds the net-loss magnitude (= a turnover problem, not an edge problem).
3. **Signal-quality metrics** — profit factor, hit rate, win/loss size ratio, the breakeven hit-rate the payoff profile *needs*, and the gap between them, with a ⚠️ flag when the strategy wins too rarely for its asymmetry.
4. **Postmortem injected as a generation-prompt PREFIX** — the mutation LLM now receives a compact LOSS-ANATOMY block (cause + regime + the quality warnings + top directive) for the parent it's mutating, so mutations *learn from how the parent specifically lost* rather than only getting a directive nudge. (Previously the postmortem only biased which directive was sampled.)

**Pinning tests written first** (13 new, `tests/test_postmortem_enrich.py`), full suite green (**872 passed, 3 pre-existing skips**).

---

## What was already there (skeleton — kept, not rebuilt)

- `runner/postmortem.py::run_postmortems_for_all()` is called inside `run_one_round()` every tournament round — the **loss-triggered hook** fires automatically (idempotent: writes only if the strategy lost AND no note exists for the ISO-week yet).
- FIFO round-trip PnL matching, a 5-cause classifier (`THIN_SAMPLE` / `COST_BLOWOUT` / `SIGNAL_DECAY` / `REGIME_MISMATCH` / `UNKNOWN`), narrative generation, and directive suggestion.
- `get_postmortem_directive_hint()` → `_pick_pairs_with_postmortem_hints()` biases directive selection 70% toward the postmortem-suggested directive.
- 13 existing tests in `tests/test_postmortem.py`.
- Notes land in `reports/postmortem/<strategy>_<YYYY-WW>.md` (weekly-idempotent; this keeps re-run safety, vs the spec's date-stamped form which would re-write daily).

## What this assignment added

### `runner/postmortem.py` (non-protected)
- **`_cost_edge_breakdown(stats, cost_bps=2.0)`** → `{gross_pnl_usd, cost_drag_usd, cost_bps, cost_exceeds_net_loss, cost_frac_of_gross}`. Reconstructs implied gross (pre-cost) PnL from net + turnover×bps.
- **`_signal_quality(pnls)`** → `{n, profit_factor, hit_rate, win_loss_ratio, breakeven_hit_rate, hit_rate_minus_breakeven}`. Guarded against div-by-zero / inf (no-wins → profit_factor 0.0, breakeven 1.0).
- **`_regime_label_from_metrics(net_return_pct, frac_above_sma)`** → `BULL`/`BEAR`/`CHOP` (pure, network-free, fully unit-tested).
- **`_benchmark_regime_at_loss(cutoff_iso, ...)`** → fetches SPY daily adjclose via the read-only `daily_bars_cache.get_daily()`, slices the loss window, computes net return + frac-above-50d-SMA, labels the regime. Degrades to `regime: UNKNOWN, available: False` on any failure (never crashes the note).
- **`build_postmortem_prompt_context(strategy, postmortem_dir)`** → extracts the high-signal lines (cause, regime, ⚠️ warnings, Directive 1) from the most recent (≤14-day) postmortem into a compact markdown blob for prompt injection.
- `_compute_stats` now also returns `pnls` (the round-trip list) so signal-quality can be computed without a second FIFO pass.
- `_format_postmortem` extended with **Regime / Cost vs Edge / Signal Quality** sections (all optional — absent args → old format preserved).

### `runner/strategy_gen.py` (non-protected)
- `_build_llm_prompt(..., postmortem_context=None)` — prepends a `## PARENT LOSS ANATOMY` guidance block when context is supplied. **No-context path is byte-identical** to before (pinned by `test_build_llm_prompt_byte_identical_without_context`) — preserves the protected-md5 enforcement model that `code_review` relies on.
- `generate_candidate(..., postmortem_context=None)` — threads the context to the prompt builder.

### `runner/tournament_loop.py` (non-protected)
- `run_one_round()` now calls `build_postmortem_prompt_context(parent, ...)` per (parent, directive) pair and passes it into `generate_candidate()`. Prints `+ loss-anatomy context injected for <parent>` when a recent postmortem exists. Falls through to `None` (unchanged behavior) when none.

---

## Verification

**End-to-end dry-run** (`python3 -m runner.tournament_loop --n 2 --dry-run --seed 42 --report-dir /tmp`, no LLM, no orders):
```
[1/2] parent=sma_crossover_qqq directive=...combine its entry signal...
    + loss-anatomy context injected for sma_crossover_qqq   ← feature firing
    -> REJECT_GATE
[2/2] parent=rsi_oversold_spy directive=...
    -> REJECT_DUPLICATE
```
The injection fires for parents with a recent postmortem; evaluation/quarantine machinery unchanged.

**Live note regeneration** (`macd_momentum_iwm`, overwrite) now shows the populated sections:
```
**Regime at loss (SPY):** `CHOP` (+1.7% over window, 83% of days above 50d SMA)
## Cost vs Edge   → Gross PnL $-1.8842 | Cost drag $0.1689 | Net $-2.0531   (directional, not cost-driven)
## Signal Quality → Profit factor 0.00 | Hit 0% | breakeven 100% | ⚠️ below breakeven
```

**Regime helper smoke (network):** SPY last 7d → `{regime: CHOP, net_return_pct: +1.66%, frac_above_sma: 0.83, available: True}` — produces real labels (an earlier draft called a non-existent `get_adjclose`; fixed to the real `get_daily` API).

**Tests:** 13 new pins (`tests/test_postmortem_enrich.py`) + 13 existing (`tests/test_postmortem.py`) green; **full suite 872 passed / 3 skipped**.

**Integrity:**
```
0f763975…  runner/runner.py          ← baseline ✓
e303317e…  runner/risk.py            ← baseline ✓
717c36e6…  runner/backtest.py        ← baseline ✓
d8927364…  runner/backtest_xsec.py   ← baseline ✓
8c3df32c…  runner/walk_forward_xsec.py ← baseline ✓
bccefaba…  runner/safety_backstop.py ← baseline ✓
```
No crontab edit. No .db write outside `reports/postmortem/`. tournament.db read-only (SELECT-only queries; its mtime reflects the live cron, not this work).

---

## Threshold / hook summary (as requested)

- **Hook:** `run_postmortems_for_all()` inside `run_one_round()` — fires once per tournament round, for every strategy in the trades table.
- **Loss threshold:** realized FIFO PnL over the trailing `n_days=7` window `< loss_threshold_usd` (default `-1.0`). Configurable per call.
- **Idempotency:** one note per `strategy × ISO-week`; `overwrite=False` by default.
- **Output path:** `reports/postmortem/<strategy>_<YYYY-WW>.md`.
- **Feedback into mutation:** (a) directive-selection bias (70%, pre-existing) + (b) **NEW** generation-prompt loss-anatomy prefix.

## Follow-ups (optional, logged to BACKLOG)
- The note path is weekly (`_<YYYY-WW>`), not the spec's daily date-stamp — chosen for re-run idempotency. If main wants the date-stamped form too, it's a one-line label change.
- Regime benchmark is hard-coded SPY; could be made per-strategy (e.g. QQQ for QQQ strategies) for sharper regime attribution.
- `datetime.utcnow()` deprecation warnings in tournament_loop/cot_cache are pre-existing, unrelated to this change.
