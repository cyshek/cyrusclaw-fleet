# L165 — Regime Detection as a First-Class Feature

**How the 8 live-book strategies behave across BULL / CHOP / BEAR, and whether a regime gate improves the book.**

Author: Tessera (sub-agent, research/prototype). Generated 20260624T233555Z.
Scope: **READ-ONLY** against protected code. No protected file touched (no `runner/`, `strategies/`, `risk.py`, `GATE.md`, or any `params.json` edit). Scratch + report only.

Source data:
- `reports/_volaware_series.json` — 8 live strategies × 4111 daily returns, 2010-02-16 → 2026-06-18.
- `reports/_erc_weights.json` → `capital_usd_v2_tradeable` (sum = $800), normalized to portfolio weights.
- SPY adjclose (Yahoo v8 chart API, cached `_spy_daily_l165.json`, 8407 days 1993→2026) for the regime classifier.

> ⚠️ **Scaling caveat carried throughout.** The 6 event/equity sleeves are **zero-cost signal-shape** daily series (~1% vol, per-unit-signal, NOT capital-scaled); only `tqqq_cot_combo` (~20% vol, 3×) and `allocator_blend` (~16% vol) embed real leverage. Cross-strategy comparison therefore leans on **Sharpe/Sortino (scale-invariant)**, not absolute CAGR/mean-bps. The book column is the ERC-capital-weighted blend, which is the economically meaningful object.

---

## 1. Regime definition (pure function of past SPY — no lookahead)

For each SPY trading day *t* (using only sessions with date ≤ *t*):

- `sma200(t)` = mean adjclose over the trailing **200** SPY sessions (inclusive of *t*).
- `rv20(t)` = sample stdev of the trailing **20** daily SPY simple returns (inclusive of *t*), annualized × √252.
- `med_rv(t)` = rolling **median of rv20** over the trailing **252** valid sessions (expanding until 252 available) — trailing-only.

Label:

| Regime | Rule |
|---|---|
| **BEAR** | `close(t) < sma200(t)` |
| **BULL** | `close(t) ≥ sma200(t)` **AND** `rv20(t) ≤ med_rv(t)` (uptrend + calm) |
| **CHOP** | `close(t) ≥ sma200(t)` **AND** `rv20(t) > med_rv(t)` (uptrend but elevated vol / whipsaw) |

The label for a strategy-date *d* is the label of the **most recent SPY session ≤ d** (so it uses only information available at *d*'s close). Every input is trailing — verified by a flip audit (the 2022-01-21 BEAR flip whipsaws back to CHOP on 01-24, exactly the boundary churn an honest trailing rule produces; no future data leaks in).

**Sanity checks (pass):**

| Window | BULL | CHOP | BEAR |
|---|---|---|---|
| 2020 Q1 COVID (02-19…04-07) | 0% | 26% | **74%** |
| 2022 bear (01-01…10-15) | 0.5% | 21% | **78%** |
| 2013 (calm bull) | — | 21% | 0% (79% BULL) |
| 2017 (calm bull) | **75%** | 25% | 0% |

Bear years also include 2011 (37%), 2010 (27%), 2015 (21%), 2018 (16%), 2025 (17%); zero-bear in 2013/2017/2021/2024. **Bear days are spread across the span, not one-regime clustered** — this matters for the OOS test below.

---

## 2. Regime occupancy (full span, 4111 days)

| Regime | Days | % |
|---|---:|---:|
| BULL | 2162 | **52.6%** |
| CHOP | 1286 | **31.3%** |
| BEAR | 663 | **16.1%** |
| (unlabeled warmup) | 0 | 0.0% |

---

## 3. Per-strategy × per-regime performance

Annualized **Sharpe** / **Sortino** (canonical fns), mean daily return (bps), % days in-market (|ret|>0). `w` = ERC portfolio weight.

| Strategy (w) | Metric | FULL | BULL | CHOP | BEAR |
|---|---|---:|---:|---:|---:|
| **breakout_xlk__mut_c382b1** (.093) | Sharpe / Sortino | 0.86 / 1.21 | **1.63 / 2.42** | 0.41 / 0.56 | −0.61 / −0.82 |
| | mean bps · in-mkt% | 0.34 · 62% | 0.61 · 79% | 0.19 · 51% | −0.22 · 26% |
| **sma_crossover_qqq_regime** (.087) | Sharpe / Sortino | 0.93 / 1.30 | **1.90 / 2.86** | 0.65 / 0.87 | −1.29 / −1.61 |
| | mean bps · in-mkt% | 0.34 · 68% | 0.63 · 87% | 0.26 · 56% | −0.47 · 30% |
| **sma_crossover_qqq_rth** (.087) | Sharpe / Sortino | 0.89 / 1.24 | **1.90 / 2.86** | 0.65 / 0.87 | −1.46 / −1.80 |
| | mean bps · in-mkt% | 0.33 · 69% | 0.64 · 88% | 0.26 · 56% | −0.56 · 31% |
| **rsi_oversold_spy** (.200) | Sharpe / Sortino | 0.18 / 0.25 | −0.08 / −0.10 | **1.34 / 2.70** | −0.19 / −0.26 |
| | mean bps · in-mkt% | 0.09 · 6% | −0.01 · 1% | 0.40 · 6% | −0.22 · 21% |
| **volume_breakout_qqq** (.109) | Sharpe / Sortino | 0.16 / 0.22 | **0.68 / 0.96** | −0.43 / −0.53 | −0.57 / −0.78 |
| | mean bps · in-mkt% | 0.04 · 31% | 0.19 · 44% | −0.12 · 21% | −0.13 · 7% |
| **macd_momentum_iwm** (.151) | Sharpe / Sortino | 0.17 / 0.23 | 0.14 / 0.20 | **0.44 / 0.61** | −0.90 / −1.03 |
| | mean bps · in-mkt% | 0.06 · 19% | 0.05 · 23% | 0.19 · 21% | −0.17 · **1.4%** |
| **tqqq_cot_combo** (.200) | Sharpe / Sortino | 0.85 / 1.18 | **1.43 / 2.06** | 0.92 / 1.24 | **−2.91 / −3.03** |
| | mean bps · in-mkt% | 6.94 · 84% | 12.81 · 97% | 7.42 · 94% | −13.12 · 22% |
| **allocator_blend** (.073) | Sharpe / Sortino | 1.01 / 1.40 | **1.55 / 2.25** | 1.08 / 1.46 | −1.07 / −1.33 |
| | mean bps · in-mkt% | 6.36 · 100% | 9.31 · 100% | 7.63 · 100% | −5.72 · 100% |

**ERC book aggregate per regime:**

| | FULL | BULL | CHOP | BEAR |
|---|---:|---:|---:|---:|
| Book Sharpe | 0.923 | **1.487** | 1.003 | **−2.625** |
| Book Sortino | 1.273 | 2.144 | 1.344 | −2.813 |
| Book mean bps | 1.98 | 3.44 | 2.20 | −3.24 |

Book full-span: CAGR 4.95%, maxDD −7.39%, Calmar 0.67 (baseline Sharpe 0.9226 — matches the standing ERC-book number).

---

## 4. Regime-sensitive vs regime-agnostic classification

Rule: **sensitive** if `|bullSharpe − bearSharpe| > 0.5` **OR** `bearSharpe < −0.5`. ("Long-biased ⇒ worse in bear" is *mechanical/expected* — I flag the genuinely interesting cases, not just the beta.)

| Strategy | Bull Sh | Chop Sh | Bear Sh | Bull−Bear | Verdict |
|---|---:|---:|---:|---:|---|
| tqqq_cot_combo | 1.43 | 0.92 | **−2.91** | 4.34 | **SENSITIVE — extreme** (3× leverage amplifies bear losses; the dominant book risk) |
| sma_crossover_qqq_rth | 1.90 | 0.65 | −1.46 | 3.36 | SENSITIVE (mechanical trend) |
| sma_crossover_qqq_regime | 1.90 | 0.65 | −1.29 | 3.19 | SENSITIVE (mechanical trend) |
| allocator_blend | 1.55 | 1.08 | −1.07 | 2.62 | SENSITIVE (levered long-biased) |
| breakout_xlk__mut | 1.63 | 0.41 | −0.61 | 2.24 | SENSITIVE (mechanical trend) |
| volume_breakout_qqq | 0.68 | −0.43 | −0.57 | 1.24 | SENSITIVE (but tiny weight/vol; near-flat everywhere) |
| macd_momentum_iwm | 0.14 | 0.44 | −0.90 | 1.04 | borderline; **best in CHOP**, near-absent in bear (1.4% in-mkt) |
| **rsi_oversold_spy** | −0.08 | **1.34** | −0.19 | 0.11 | **AGNOSTIC / genuine DIVERSIFIER** — bull/bear Sharpe gap ≈ 0; its edge lives in CHOP, the regime everything else is weakest |

**Headline qualitative findings:**
- **`rsi_oversold_spy` is the real diversifier.** Mean-reversion: flat in bull (1% in-market), its entire edge is in CHOP (Sharpe **1.34**, the regime where the trend book sags to ~0.4–0.65). It is *not* a bear hedge (mildly negative −0.19) but it is the one sleeve whose value is genuinely regime-orthogonal to the trend complex. Keep it ungated.
- **`macd_momentum_iwm`** is the second-most-complementary: peaks in CHOP (0.44), self-flattens in bear (1.4% in-market) so it barely participates in the bear drawdown anyway.
- **Everything else is long-trend beta** — strong in bull, fades in chop, bleeds in bear. That's mechanical, not a discovered signal.

---

## 5. The verdict question — does regime CONDITIONING improve the book?

Honest counterfactual: **flatten a strategy to cash (return→0) on BEAR-labelled days**, leave it untouched otherwise; compare ERC-book Sharpe/Sortino/CAGR/maxDD with vs without the gate, full span + IS/OOS. Cash gets 0 — capital is **not** re-leveraged to other sleeves (no free re-leverage). IS = first 70% (2010-02→2021-07, 2877 d), OOS = last 30% (2021-07→2026-06, 1234 d, of which **274 are BEAR** — a genuinely bear-heavy OOS thanks to 2022).

### Where the bear loss actually lives (decomposition of book bear-day mean return)

| Strategy | bear contrib (bps/day) | share of book bear loss |
|---|---:|---:|
| **tqqq_cot_combo** | −2.625 | **81.1%** |
| allocator_blend | −0.419 | 12.9% |
| sma_crossover_qqq_rth | −0.049 | 1.5% |
| rsi_oversold_spy | −0.044 | 1.4% |
| sma_crossover_qqq_regime | −0.041 | 1.3% |
| macd_momentum_iwm | −0.025 | 0.8% |
| breakout_xlk__mut | −0.021 | 0.6% |
| volume_breakout_qqq | −0.014 | 0.4% |
| **TOTAL** | **−3.238** | 100% |

**94% of the book's bear-regime bleed is just two sleeves (tqqq 81% + allocator 13%).** The 6 signal-shape sleeves contribute ~6% combined — gating them is noise.

### Gate counterfactuals (full span + OOS), vol-matched check

| Gate (flat in BEAR) | FULL Sh (base 0.923) | FULL maxDD (base −7.39%) | **FULL Sh vol-matched** | **OOS Sh (base 0.856)** | OOS dSh |
|---|---:|---:|---:|---:|---:|
| tqqq_cot_combo only | **1.148** | −5.13% | 1.148 | 0.932 | **+0.076** |
| allocator_blend only | 0.963 | −6.84% | 0.963 | 0.887 | +0.031 |
| **tqqq + allocator** | **1.185** | −5.06% | 1.185 | 0.961 | **+0.105** |
| tqqq+alloc+trend-trio | 1.194 | −5.06% | 1.194 | 0.973 | +0.117 |
| ALL 8 | 1.201 | −5.35% | 1.201 | 0.962 | +0.106 |

IS/OOS breakdown for **tqqq+allocator** (the recommended gate): IS dSharpe +0.33, **OOS dSharpe +0.105** (Sortino +0.154). The gate is **stronger in-sample than out-of-sample** (expected — 2022 is one big OOS bear) but it **does not reverse sign OOS** — it remains a real, if attenuated, improvement.

**Is it alpha or just lower vol?** Vol-matching the gated book back to the baseline's full-period vol (scale ≈1.03) leaves the Sharpe gain fully intact (1.148 vol-matched for tqqq-only, identical to raw because Sharpe is scale-invariant — and the **CAGR** at matched vol *rises* to 6.24% from 4.95%). So the gain is **not** merely de-risking: at the same risk budget the regime-gated book earns more. The maxDD improvement (−7.39%→−5.06%) is partly lower vol, but the Sharpe/Sortino lift is genuine risk-adjusted improvement.

**Turnover/cost honesty:** the BEAR boundary toggles **90 times** over 16.3 years ≈ **5.5 on/off events per year** — low. Each toggle for `tqqq_cot_combo` is a full exit/re-entry of a ~$160 3× position (~$480 notional). At a few bps round-trip that's a handful of dollars/yr — immaterial vs the Sharpe gain, but it is **not** modeled here (no fill model); flagged. The trailing-rule whipsaw (e.g. the 2022-01 BEAR→CHOP flip in 3 days) is the real cost source and argues for a small hysteresis band (e.g. require 2 consecutive BEAR closes, or a −1% buffer below the 200d) before flattening, in any production version.

---

## 6. VERDICT

**(a) Does regime conditioning improve the book? — YES, but the win is concentrated, not broad.** A BEAR-flatten gate lifts full-span book Sharpe 0.923→1.185 and OOS Sharpe 0.856→0.961 (+0.105), Sortino +0.154, maxDD −7.4%→−5.1%, and the gain survives vol-matching (so it's risk-adjusted improvement, not just de-risking). It holds OOS through the 2022 bear (274 OOS bear days) without flipping sign.

**(b) Which strategies are gate candidates, and what gate?** **`tqqq_cot_combo` (primary) and `allocator_blend` (secondary).** These two are 94% of the book's bear-regime loss; gating them captures ~95% of the available improvement (tqqq+alloc full Sh 1.185 vs all-8 1.201). The gate: **flatten `tqqq_cot_combo` and `allocator_blend` to cash when SPY < trailing-200d-SMA**, with a small hysteresis buffer (require 2 consecutive BEAR closes, or a ~1% band below the 200d) to suppress the whipsaw. `tqqq_cot_combo` alone already gives +0.076 OOS Sharpe and the cleanest maxDD cut (−7.39%→−5.13%) — if only one sleeve is gated, gate the 3× one.

**(c) What's NOT worth gating.** The 6 signal-shape sleeves (`breakout_xlk`, both `sma_crossover_qqq`, `rsi_oversold_spy`, `volume_breakout_qqq`, `macd_momentum_iwm`) contribute ≤1.5% each of the bear loss; gating them moves book Sharpe by +0.001…+0.005 (noise), and several are slightly *negative* OOS when gated. **Do not gate them.** In particular **`rsi_oversold_spy` should stay ungated** — it's the genuine diversifier (Sharpe 1.34 in CHOP, the regime the rest of the book is weakest in) and its bull/bear gap is ~0; gating it throws away the one regime-orthogonal sleeve. `macd_momentum_iwm` self-flattens in bear (1.4% in-market) so it needs no gate.

**Bottom line:** Regime detection is worth promoting to a first-class feature **as a targeted bear-flatten gate on the two levered long-biased sleeves (tqqq_cot_combo, allocator_blend)** — not as a blanket book-wide overlay. The marginal book Sharpe is real and OOS-robust but modest (+0.10 OOS); the cleaner story is the **maxDD reduction (−2.3pp)** plus a same-risk CAGR lift, with the bulk of value from de-risking the 3× sleeve in confirmed downtrends. Next step (out of scope here, needs protected-code change + Cyrus/main sign-off): prototype the gate with hysteresis on `tqqq_cot_combo` only and re-run the live walk-forward.

---

### Artifacts
- `_spy_daily_l165.json` — cached SPY adjclose (Yahoo v8), 8407 days.
- `_regime_l165.py` — regime classifier + per-strategy×regime + book counterfactual engine.
- `_regime_l165_followup.py` — focused tqqq/allocator gates + vol-match alpha-vs-derisking check + bear-loss decomposition.
- `_regime_l165_<stamp>.json` — full machine-readable results.
- `_regime_l165_followup.json` — focused counterfactual + decomposition results.
- `reports/REGIME_DETECTION_L165_20260624T233555Z.md` — this report.

**Protected files touched: NONE.** (No `runner/`, `strategies/`, `risk.py`, `GATE.md`, or `params.json` edit; classifier reads SPY from a scratch cache, all strategy data from `reports/_volaware_series.json` / `reports/_erc_weights.json` read-only.)
