# Tier 2 Phase-1 Eval — `regime_gated_xsec_momentum_xa` (deterministic stand-in)

**Author:** Tessera subagent (tier2-first-strategy)
**Date:** 2026-05-31 02:37 UTC
**Candidate:** `strategies_candidates/regime_gated_xsec_momentum_xa_c87bbf/`
**Parent:** `strategies/xsec_momentum_xa_38d2b2` (wave-4 promoted, FP Sharpe 1.13, MaxDD -2.00%, promotes via Bar A bullet #5)
**Evaluator:** `runner/regime_backtest.py` (NEW, Phase-1 only) — deterministic stand-in `code_fallback_decision()` = `regime_uptrend(SPY, 50)`. **Zero LLM cost.**
**Phase:** 1 of 2. **Phase 2 (real LLM replay) NOT run** — separate cost-incurring step needing sign-off.

---

## TL;DR verdict

**Phase-1 FAIL on Bar A — same failure modes as the parent (structural in-position floor + median-Sharpe miss), NOT a new logic defect.** Under the dumb SPY-50 stand-in the regime gate **strictly degrades the aggregate** vs the ungated parent (medSharpe 0.49 → 0.22, medRet +0.34% → +0.11%) — a clean **Pattern #1 generalization datum**. BUT the gate **does improve bear-regime median** (+0.04% → +0.33%), confirming the de-risk mechanism functions as designed; it just doesn't pay for the bull-side participation it sacrifices when the regime signal is this crude.

**Recommendation: do NOT promote. Phase 2 (LLM replay, ~$9) is a MARGINAL bet — run it only if main wants the empirical Tier-2-value answer for the record. My honest read: the structural gates (in-position floor, trade-count, median-Sharpe horizon) that sink the parent are gate-architecture problems no regime signal can fix, so Phase 2 cannot lift this candidate to promotion. Phase 2's value is purely informational (does a richer regime read beat the SPY-50 floor?), not a path to deployment.**

---

## 1. What was built

### Candidate: `regime_gated_xsec_momentum_xa_c87bbf`
The parent `decide_xsec` reproduced **exactly** (same 12-1 ranking, K=2, monthly cadence, 6-ETF cross-asset basket `SPY,EFA,TLT,VNQ,DBC,GLD`), plus **one** addition: a risk-on/risk-off gate consuming a regime-decision dict shaped like `runner.regime_classifier.get_today_regime()`:

- **RISK_ON** → full parent exposure (K=2, full per-leg notional). Bit-for-bit the parent.
- **RISK_OFF** → `risk_off_top_k=1` winners, per-leg notional scaled by `risk_off_notional_scale=0.5` (basket caps at $50), and rotate toward defensive `{TLT, GLD}` if any defensive leg is in the broader top-K (or pull the strongest defensive leg from the full ranking).
- **CHOP** → treated as RISK_OFF by default (`chop_as_risk_off=true`).
- **Kill-switch** `use_regime_gate=false` → ignores any injected decision = pure parent (A/B baseline).

Bar C cost-model fields declared in `params.json`: `decisions_per_year=252`, `cost_per_decision_usd=0.005` (gpt-4o-mini once-daily ≈ $1.26/yr).

### Evaluator: `runner/regime_backtest.py` (NEW)
- `score_phase1()` runs the candidate through the **full Bar A walk-forward** (`walk_forward_xsec`, 8 named regime windows, +400d warmup/window) **twice**: GATED (stand-in injected) and UNGATED (kill-switch = parent baseline).
- Per tick, `make_regime_injector(mode="standin")` reads the as-of-tick `market_state["regime"]["spy_closes"]` (already built no-lookahead by `backtest_xsec`), computes `code_fallback_decision()`, and injects it into `market_state["regime"]["decision"]` — the exact production path.
- `mode="llm"` (Phase 2) deliberately **raises `NotImplementedError`** so Phase 1 can never accidentally spend money. Phase 2 is a separate approved step.

---

## 2. Phase-1 Bar A scorecard (deterministic SPY-50 stand-in)

### Gated candidate (regime gate ON, stand-in injected)

| Window | Regime | Trades | Return % | Sharpe | MaxDD % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 5 | -0.05 | -0.09 | -0.62 | -1.18 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 3 | -0.49 | -1.03 | -0.69 | -0.85 | ✅ | 19 | ❌ |
| 2023-H1 recovery | bull | 3 | +0.38 | 0.74 | -0.53 | +0.44 | ❌ | 19 | ✅ |
| 2023-Q3 chop | chop | 4 | -0.51 | -0.94 | -0.81 | -0.44 | ❌ | 18 | ❌ |
| 2024-Q2 bull | bull | 4 | +0.15 | 0.29 | -0.34 | +0.09 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 3 | +0.72 | 1.26 | -0.34 | +0.15 | ✅ | 18 | ✅ |
| 2025-Q3 bull | bull | 6 | +1.13 | 2.84 | -0.20 | +0.53 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 2 | +0.08 | 0.16 | -0.44 | +0.74 | ❌ | 14 | ✅ |

**Aggregate:** medRet **+0.11%** · 62% positive · 62% beat BH · medSharpe **0.22** · worst -0.51% (2023-Q3 chop) · **trades 30**
**Per-regime median:** bull +0.26% · chop -0.50% · **bear +0.33%**
**Bar A bullet #1:** 🔴 FAIL — 3/8 windows fail (2022-H1 bear 19%<25% in-pos; 2022-Q3 chop 19%<25%; 2023-Q3 chop ret<BH & 18%<25%)
**Fitness gate (median Sharpe ≥0.5):** 🔴 FAIL — 0.22 ≤ 0.50

### Ungated baseline (use_regime_gate=false = parent behavior)

| Window | Regime | Trades | Return % | Sharpe | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 4 | -0.40 | -0.41 | 19 | ❌ |
| 2022-Q3 chop | chop | 4 | -0.38 | -0.44 | 19 | ❌ |
| 2023-H1 recovery | bull | 2 | +0.28 | 0.44 | 19 | ✅ |
| 2023-Q3 chop | chop | 4 | -0.51 | -0.94 | 18 | ❌ |
| 2024-Q2 bull | bull | 2 | +0.42 | 0.76 | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 2 | +0.47 | 0.53 | 18 | ✅ |
| 2025-Q3 bull | bull | 6 | +1.13 | 2.84 | 18 | ✅ |
| 2026-recent bull | bull | 4 | +0.40 | 0.54 | 14 | ✅ |

**Aggregate:** medRet **+0.34%** · 62% positive · 62% beat BH · medSharpe **0.49** · trades 28
**Per-regime median:** bull +0.41% · chop -0.45% · **bear +0.04%**

> **Parity check ✅** — the ungated path reproduces the published parent numbers exactly (medRet +0.34%, medSharpe 0.49, ~28 trades; ref `BACKTEST_XSEC_MOMENTUM_XA_20260530T180628Z.md` §3). This confirms the gate-consumption logic is correct and the RISK_ON branch is bit-for-bit the parent (also unit-tested: `TestRiskOnMatchesBaseline`).

---

## 3. Does the regime gate help or hurt under the dumb signal?

| Metric | Ungated (parent) | Gated (SPY-50 stand-in) | Δ |
|---|---|---|---|
| Median return | +0.34% | +0.11% | **−0.23pp** |
| Median Sharpe | 0.49 | 0.22 | **−0.26** |
| Median return — **bull** | +0.41% | +0.26% | −0.15pp |
| Median return — **chop** | −0.45% | −0.50% | −0.05pp |
| Median return — **bear** | +0.04% | **+0.33%** | **+0.29pp** ✅ |
| Trades | 28 | 30 | +2 |

**The gate HURTS in aggregate — a Pattern #1 generalization datum.** This is *expected and honest*: the deterministic stand-in IS `regime_uptrend(SPY, 50)`, the exact filter PATTERNS.md #1 says strictly degrades these baskets, and the parent's own report already showed it hurts the cross-asset version (medSharpe 0.49 → −0.25 with the old always-on filter). My gate is gentler than that always-on filter (it only de-risks, never goes fully flat, and rotates toward defensives), so the damage is smaller (0.49 → 0.22, not → −0.25) — but it's still net-negative.

**The one genuinely interesting signal:** the gate **improves bear-regime median by +0.29pp** (+0.04% → +0.33%). The de-risk-toward-defensives mechanism *does* protect in the two bear windows — 2025-Q1 tariff bear goes +0.47% → +0.72%. The problem is the SPY-50 signal is too laggy/noisy to avoid clipping bull participation and whipsawing in chop, so the bear-side win doesn't pay for the bull/chop-side losses. **This is precisely the gap a richer LLM regime read would need to close: keep the bear protection, stop clipping bulls.**

---

## 4. Why Bar A fails (and why no regime signal fixes it)

The candidate inherits the **parent's structural failure modes**, which are gate-architecture properties, not signal-quality problems:

1. **In-position floor (Bar A #1).** Fixed-K monthly rebalance ⇒ ~18-19% bars-in-position, K-invariant, structurally below the 25% floor (documented exhaustively in the parent report §5 and PATTERNS.md #2). **No regime signal changes occupancy** — the gate de-risks *within* the rebalance cadence; it doesn't make the strategy hold more often.
2. **Median-Sharpe horizon (fitness gate).** The parent clears this by exactly 1bp (0.49 vs 0.50) and only promotes via Bar A bullet #5 (full-period Sharpe ≥1.0). The gate, by clipping bull Sharpe, drops median Sharpe to 0.22 — **further** from the bar.
3. **Trade count.** 30 across windows (≥30 just clears bullet #4 here, but the parent's full-period count was the binding 22<30 miss; the gate doesn't materially help).

**The parent only promotes via bullet #5** (full-period Sharpe ≥1.0, MaxDD ≤$200, V3 per-window). I did **not** re-score the gated candidate against bullet #5 (out of task scope — Phase 1 is the Bar A floor check), but since the gate *lowers* full-period risk-adjusted return under the stand-in, it would need the LLM to *raise* full-period Sharpe above the parent's 1.13 to have any bullet-#5 path. That's a tall order for a once-daily regime overlay.

---

## 5. Is Phase 2 (real LLM replay) worth running?

**Honest answer: marginal — informational value only, not a promotion path.**

**Arguments FOR running Phase 2 (~$9, ~1-3h):**
- It's the **first real test of Tier 2's core thesis**: can an LLM regime read do something `regime_uptrend(SPY, 50)` can't? The bear-regime +0.29pp result shows there's a *real lever* here (de-risk helps bears); the question is whether a richer signal stops clipping bulls/chop. A clean yes/no is genuinely valuable for the whole Tier 2 program direction.
- The cost-ratio gate (Bar C.2) gets a real-data calibration check: $1.26/yr cost vs ~$7/yr gross edge ≈ 18%, inside the 30% gate. Worth confirming empirically.

**Arguments AGAINST:**
- **Even a Phase-2 win cannot promote this candidate.** The binding Bar A failures (in-position floor, median-Sharpe horizon) are *structural to fixed-K monthly rotation* — no regime overlay touches them. Phase 2 could show "LLM > SPY-50" and the candidate *still* fails Bar A bullets #1/#3, and would need to clear bullet #5 (full-period Sharpe ≥1.0) which it's moving *away* from under the stand-in.
- **Lookahead risk in LLM replay:** gpt-4o-mini's training cutoff overlaps the 2022-2024 backtest window. The model "knows" 2022 was a bear. Phase-2 results on those windows are optimistically biased and not trustworthy as forward edge — exactly the concern the methodology doc flagged for approach (A). The only clean LLM-replay windows are post-training-cutoff, which we don't have enough of yet.

**My recommendation:** **Defer Phase 2.** Instead, the higher-leverage Tier 2 move is to apply the (now-validated) `regime_backtest.py` evaluator to a candidate whose *base archetype already passes Bar A on its own merits* — so that a positive LLM contribution can actually graduate something. Gating a candidate that only squeaks through via bullet #5 means the LLM has no headroom to matter. If main still wants the empirical "LLM vs SPY-50" datum for the Tier 2 program record, $9 + lookahead-caveat is a defensible spend — but flag it as a research data point, **not** a deployment evaluation, and weight only the post-2024 windows.

---

## 6. Files created

```
strategies_candidates/regime_gated_xsec_momentum_xa_c87bbf/
    __init__.py
    strategy.py        # decide_xsec consuming regime decision dict
    params.json        # parent params + gate knobs + Bar C cost fields
runner/regime_backtest.py            # NEW Phase-1 evaluator (Phase-2 seam blocked)
tests/test_regime_backtest.py        # 12 tests (stand-in, risk-off↓exposure, risk-on=baseline, determinism, lookahead guard, Phase-2 block, CHOP)
reports/TIER2_REGIME_GATED_XSEC_PHASE1_20260531T023748Z.md  # this file
```

## 7. Test & gate status

- **`runner/regime_backtest.py` Phase-1 eval:** ran clean end-to-end (real bars, 8 windows × 2 variants).
- **New tests:** `tests/test_regime_backtest.py` — **12 passed**.
- **Full suite:** `python3 -m pytest -q` → **225 passed** (was 213 pre-task; +12 new; **zero regressions**).
- **Candidate smoke (Bar A #7):** `./tick.sh --candidate regime_gated_xsec_momentum_xa_c87bbf` → **rc=0, SMOKE OK xsec, no DB writes** (`actions={DBC=buy, GLD=buy}`).
- **Hard constraints honored:** only the candidate dir + the ONE new `runner/regime_backtest.py` + its test file were created. No existing runner/GATE/promoted-strategy files modified. No LLM calls (Phase-2 path raises). No pip install.

---

## 8. Honest caveats

- **Phase 1 is a floor check, not a verdict on Tier 2.** It says "the gate logic is correct and a dumb regime signal hurts." It says nothing about whether a *good* regime signal helps — that's Phase 2, deferred.
- **Bullet #5 not re-scored for the gated variant.** Out of scope; flagged because the parent's only promotion path is #5 and the gate moves full-period risk-adjusted return the wrong way under the stand-in.
- **The bear +0.29pp improvement is real but small** (n=2 bear windows, sub-1% magnitudes on $100 notional). Don't over-read it; it's a directional signal that the de-risk mechanism functions, not evidence of edge.
- **I did not promote and did not run Phase 2.** Both require explicit sign-off per task spec + Bar C/Bar E.
