# Bar C Evaluation Methodology — Tier 2 LLM-Decision Strategies

**Author:** Tessera (trading-bench)
**Date:** 2026-05-30
**Status:** DRAFT design doc, no code yet. Awaiting main review before implementation subagent spawns.

---

## Why this doc exists

Tier 2 infra shipped this morning (`runner/regime_classifier.py`, prompts, `llm_decisions` + `regime_decisions` DB tables, opt-in `regime_gate` shim in `runner.py`). The capability exists; nothing uses it yet. Bar C (in `GATE.md`) specifies the *rules* an LLM-decision strategy must satisfy. This doc specifies the *evaluator* — the runnable harness that scores a Tier 2 strategy against Bar C, the same way `runner/walk_forward.py` scores Tier 1 code strategies against Bar A.

Without this evaluator we cannot promote a Tier 2 strategy. With it, the path is:
1. Build a candidate Tier 2 strategy (a code strategy that consumes `get_today_regime()`).
2. Run it through the Bar C evaluator on backtest history.
3. If it passes Bar C, deploy to live paper (subject to Cyrus per-request approval per Bar E).

---

## Bar C re-statement (from GATE.md, for reference)

A Tier 2 strategy promotes only if ALL of:

1. **All of Bar A.** (Walk-forward 8 regimes, holdout, FP Sharpe ≥0.5, ≥30 trades, MaxDD ≤30%, code review, smoke pass.)
2. **Per-decision cost modeled.** `decisions_per_year` × `cost_per_decision_usd` in `params.json`. Backtest subtracts. Reject if LLM cost ≥30% of gross edge.
3. **Determinism log.** Every LLM call writes `{prompt_hash, model_version, seed, response, decision}` to `llm_decisions`. No log → no deploy. (Already enforced in `regime_classifier.py`.)
4. **Prompt frozen at deployment.** Prompt change = new strategy name = re-evaluate.
5. **Preferred archetypes are low decision-frequency.** (Once-daily regime classifier, weekly position sizer, EoD risk-on/off filter.)

---

## Core problem: backtesting an LLM-consuming strategy

Tier 1 strategies are pure functions over OHLCV bars — given the same bars, they produce the same decisions. Easy to backtest: replay bars, accumulate trades, score.

Tier 2 strategies are pure functions over `(OHLCV bars, regime_decision)` where `regime_decision` is an LLM output. The classifier's output is NOT deterministic given just OHLCV — it depends on the model, prompt version, temperature, and (potentially) ephemeral context the model picked up at inference time. To honestly backtest a Tier 2 strategy on 5 years of history, we have to either:

- **(A)** Re-run the LLM classifier for every historical date in the backtest, generating an as-of-that-date regime decision. Honest but expensive (gpt-4o-mini × 5y × 1/day ≈ 1825 calls × $0.005 = ~$9). Slow (rate-limited; minutes to hours). Lookahead-leak risk if the model's training data overlaps the backtest period.
- **(B)** Replay the actual production `regime_decisions` log we accumulate going forward. Cheap, deterministic, no lookahead risk (LLM was called real-time on those dates). But we need months of accumulated data before this is usable for backtesting — bootstrap problem.
- **(C)** Substitute a deterministic "stand-in classifier" (e.g., the code fallback `regime_uptrend(SPY, 50)`) during backtest. Trivial, deterministic, no LLM cost, but doesn't actually test the LLM's contribution. Useful as a *floor* check ("does the strategy work even with a dumb regime signal?") but not as the promotion gate.

**Proposed approach: B + C as a two-phase eval, with A as a one-time validation.**

### Phase 1 (immediate, deployment-blocking): Bar C eval against (C) deterministic stand-in

The candidate strategy must demonstrate that its consume-the-regime-signal logic is correct AND the strategy has standalone edge even when the regime signal is the boring `regime_uptrend(SPY, 50)`. This is the floor:

- Substitute `code_fallback_decision()` for `get_today_regime()` in the backtest.
- Run the full Bar A walk-forward against the strategy under this stand-in.
- If the strategy doesn't even pass Bar A under the deterministic fallback, the LLM upgrade can't save it — the strategy logic itself is broken or the regime signal doesn't help that archetype.

This catches "strategies that only work because the LLM is doing something the strategy itself doesn't know how to do." Those exist (genuine LLM edge) but they're a high bar — we want to know whether the strategy is FUNDAMENTALLY edge-bearing first.

### Phase 2 (deployment-blocking): Bar C eval against (A) one-time historical LLM replay

Once the strategy passes Phase 1, run a one-time historical replay against the real LLM classifier:

- Build feature bundles for every NY trading date in the backtest window using only data available AS OF that date (no lookahead).
- Call the LLM classifier with the frozen production prompt for each date.
- Write all decisions to `llm_decisions` with a `source='backtest_replay'` tag (distinguishes from `source='live'` rows).
- Re-run the Bar A walk-forward consuming these LLM decisions instead of the stand-in.
- **Two sub-gates:**
  - **(a)** Strategy with LLM regime ≥ Strategy with code-fallback regime in median walk-forward return AND in full-period Sharpe. (LLM must contribute non-negative edge.)
  - **(b)** Total replay LLM cost (`n_dates × $0.005`) divided by total backtest gross edge ≤ 30% (per GATE.md Bar C.2).

Phase 2 is run ONCE per candidate (not on every walk-forward re-iteration during development) because of cost. Tag in the candidate's params.json: `"phase2_eval_complete": true, "phase2_eval_ts": "..."`. Re-running Phase 2 is only required if the prompt changes (which per Bar C.4 = new candidate name anyway).

### Phase 3 (post-deploy, continuous): Production drift monitoring via (B)

Once deployed live, the production `regime_decisions` rows accumulate. A weekly cron job replays the strategy against the prior-month's production regimes and compares to the Phase-2 backtest expectations:

- `actual_returns_last_30d` vs `backtest_returns_last_30d_band`.
- `actual_regime_distribution` (% RISK_ON / RISK_OFF / CHOP) vs `backtest_regime_distribution`.
- If either drifts >2σ from backtest expectations → flag for review (Tessera + main).

Phase 3 catches prompt-version drift (Bar C.4 violation: if the model behind gpt-4o-mini silently updates, our frozen prompt produces different decisions than the backtest). Also catches genuine regime-shift in the underlying market the LLM wasn't trained on.

---

## Concrete files to build (Phase 1 + Phase 2)

### `runner/regime_backtest.py` — Phase 1 + Phase 2 evaluator

Single module, two modes:

```
python3 -m runner.regime_backtest --strategy <name> --phase 1
    Score the candidate against Bar A using the code-fallback regime stand-in.
    Fast (no LLM calls). Deterministic. Re-runnable.

python3 -m runner.regime_backtest --strategy <name> --phase 2 [--budget-usd N]
    Score the candidate against Bar A using actual LLM classifier replays.
    Slow (~1-3 hours for 5y of dates). Costs ~$9 per full replay.
    --budget-usd halts and reports partial results if budget exceeded.
    Writes all replay decisions to llm_decisions with source='backtest_replay'.
    Idempotent: re-using a previously-replayed (strategy, prompt_version, date)
    tuple reads from llm_decisions instead of re-calling the LLM.
```

**Internal architecture (~400 LOC, mirror `runner/walk_forward.py`):**

1. `build_feature_bundle_asof(symbol, date) -> dict` — reconstruct what the live classifier would have seen on `date`. Pulls bars up to `date - 1`, computes the same feature set the live prompt uses (SPY 50d SMA position, recent volatility, etc.). **MUST NOT** pull bars from `date` or after — that's lookahead. Add an assertion at the top of every replay call.
2. `replay_decision(date) -> regime_decision` — Phase 1 calls `code_fallback_decision()`; Phase 2 calls the LLM with the as-of feature bundle. Both return the same dict shape as `get_today_regime()`.
3. `inject_regime_into_market_state(market_state, regime_decision) -> market_state'` — monkey-patch the market_state dict before calling `decide()` so the strategy gets the regime decision via the same path it would in production.
4. `score_against_bar_c(candidate, decisions_log) -> ScoreReport` — runs Bar A walk-forward + applies the Bar C-specific gates (Phase 2 cost-vs-edge ratio; Phase 2 (a) LLM-vs-fallback comparison).

### `tests/test_regime_backtest.py` — ~10-15 tests

- Phase 1 produces identical results across two runs (determinism).
- Phase 2 replay reads from `llm_decisions` cache, not LLM, on second call.
- Lookahead assertion fires if `build_feature_bundle_asof` is called with `date` later than bundle data.
- Cost budget halts replay correctly.
- Score report correctly fails strategies whose Phase 2 cost ≥30% of gross edge.
- Score report correctly fails strategies whose Phase 1 fails Bar A.
- Score report correctly fails strategies whose Phase 2 LLM-regime underperforms Phase 1 code-fallback regime.

---

## First candidate strategy to test against the evaluator

Don't ship the evaluator without a candidate to run it on. Proposed first Tier 2 strategy:

### `regime_gated_xsec_momentum_xa` — Apply LLM regime gate to the wave-4 momentum winner

The wave-4 `xsec_momentum_xa_38d2b2` has FP Sharpe 1.13 standalone. Hypothesis: gating it with the LLM regime classifier (CHOP → all cash; RISK_OFF → only top-K from defensive subset of {TLT, GLD}; RISK_ON → standard top-K) could improve worst-window behavior without sacrificing FP Sharpe. Concrete test of Tier 2's value.

**Why this one first:**
- We have a real candidate to apply it to (clean baseline; cross-asset universe means LLM has TLT/GLD to fall back on in RISK_OFF).
- Pattern #1 says SPY-regime gate hurts momentum-xa (because momentum already encodes regime). The LLM classifier is a *richer* regime signal than SPY-only-trend, so this is a clean test of whether richer-regime helps where simpler-regime hurts. If it doesn't, Pattern #1 generalizes further (no-go for any ranking-already-encodes-regime strategy regardless of regime signal quality). Either result is informative.
- Doesn't require any new Tier 1 archetype work; recombines existing pieces.

**Bar C scorecard expectations for this candidate:**
- Phase 1 (code fallback): expect ≈ FP Sharpe 1.05-1.15. Pattern #1 predicts the SPY-based code fallback will be neutral-to-slightly-worse than baseline. If Phase 1 result is materially worse than baseline 1.13, the strategy logic is degraded — investigate before Phase 2.
- Phase 2 (LLM): goal is FP Sharpe ≥ Phase 1 by some margin (say ≥0.05 Sharpe units) AND lifting at least one Bar A windows from FAIL to PASS. If Phase 2 ties or loses to Phase 1, Tier 2 added no value for this archetype.

This is also a clean test of whether Bar C's 30%-cost-ratio gate is calibrated correctly: gpt-4o-mini at ~$0.005/decision × 252 decisions/year = $1.26/year. Strategy gross edge at FP Sharpe 1.13 on $100 notional × ~7% annualized = ~$7/year gross. Cost ratio ≈ 18%. Inside the 30% gate but not by a huge margin. If we drop to a more expensive model (e.g., gpt-4o at ~$0.05/decision), cost ratio jumps to 180% — auto-reject. The gate works.

---

## Cron wiring (after Phase 2 passes and Cyrus approves promotion)

Two cron lines need adding when a Tier 2 strategy goes live:

```
# Daily LLM classifier run at 09:25 ET (5 min before market open NYC)
25 13 * * 1-5  /path/to/tick.sh --classify-regime

# Standard hourly stocks tick continues — strategies consuming regime read from regime_decisions DB
```

The existing `regime_classifier.py --run` does the right thing (idempotent UPSERT into `regime_decisions`). Just need to wire the `--classify-regime` mode into `tick.sh`. Trivial (~10 LOC).

---

## Decision points for main

1. **Approve Phase 1 + Phase 2 + Phase 3 split**, or argue for collapsing some? Main might say Phase 3 (drift monitoring) is premature without a live Tier 2 strategy first — fair point, can defer.
2. **Approve `regime_gated_xsec_momentum_xa` as the first candidate** to test the evaluator on, OR propose a different one? My read: this one is the cleanest test because the baseline is already a strong candidate (so we can isolate LLM contribution). But it also depends on whether `xsec_momentum_xa_38d2b2` gets promoted via the pending Bar A amendment — if it doesn't promote, this Tier 2 candidate would consume from `strategies_candidates/` which is messy.
3. **Approve the eval-cost budget** for one full Phase 2 replay (~$9 per full backtest). Bar C compliance requires running it ≥1x per candidate. Cyrus has unlimited tokens; this is real-money OpenAI API spend, not OpenClaw quota. Worth flagging.
4. **Spawn an implementation subagent for `runner/regime_backtest.py`** with this design as the brief? Estimated ~6-8 hours subagent runtime for the evaluator + 10-15 tests, mirror of the `walk_forward_xsec` shipping pattern.

---

## Order of operations once main approves

1. Spawn `regime_backtest_impl` subagent with this design as brief. Output: `runner/regime_backtest.py` + tests, all 182 existing tests stable.
2. Build `regime_gated_xsec_momentum_xa` candidate in `strategies_candidates/`. (Cheap — wraps existing `xsec_momentum_xa` decide_xsec with regime-gate logic.)
3. Run Phase 1 evaluator. If FAIL, abandon candidate, choose next archetype.
4. If Phase 1 PASS, run Phase 2 evaluator with $20 budget cap. Report.
5. If Phase 2 PASS, write promotion memo + bring to Cyrus per Bar C + Bar E.

If Cyrus separately approves the Bar A amendment (currently in `reports/GATE_AMENDMENT_DRAFT_20260530T190000Z.md`), step 2 can promote the standalone `xsec_momentum_xa` first, then layer Tier 2 on top — cleaner experiment design (we observe pure-Tier-1 baseline live before adding Tier 2 complexity).

---

## What's NOT in this doc (deliberately)

- No automatic alerting on Phase 3 drift. First version is humans (Tessera + main) reading weekly drift reports. Auto-alert when we have empirical drift-distribution data and a meaningful threshold.
- No multi-model A/B (gpt-4o-mini vs gpt-4o vs claude). Premature optimization. Lock to gpt-4o-mini, document cost, only revisit if cost-ratio gate forces a model swap.
- No prompt-engineering loop. Bar C.4 freezes prompt at deployment. Iterative prompt tuning happens on `strategies_candidates/` only, not on deployed strategies.
- No safety overrides. Killswitch + risk caps in `runner/risk.py` still apply. LLM cannot trigger anything risk.py wouldn't allow a code strategy to.
