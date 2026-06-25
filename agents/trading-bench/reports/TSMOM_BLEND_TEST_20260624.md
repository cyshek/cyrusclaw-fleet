# TSMOM Blend Test — Equity Book × Core4 Multi-Asset TSMOM

**Date:** 2026-06-24
**Author:** trading-bench subagent (`tsmom_blend_test`)
**Question:** Does blending the live 8-strategy equity book with the core4 multi-asset TSMOM sleeve (DBC/GLD/TLT/UUP, 12-1 EW, corr→SPY ≈ −0.01) produce a meaningfully better **risk-adjusted** outcome than the pure equity book? At what blend ratio?

**Verdict:** **GREEN — a small TSMOM sleeve (≈20%, i.e. 80/20 equity/TSMOM) is worth paper-tracking.** On the honest, vol-normalized (unit-risk) construction, an 80/20 blend **raises Sharpe (0.964 → 1.037) AND lowers maxDD (−12.5% → −10.2%)** while giving up only ~9% of total return. The improvement holds across 70/30 too. The naive raw-series reading says the opposite — but that reading is **methodologically contaminated** (see §2) and should not drive the decision.

---

## 0. Construction & honesty notes (READ FIRST)

- **Equity book = 8 LIVE strategies**, ERC-**risk**-weighted (the `risk_weights` field of `reports/_erc_weights.json`, each contributing 12.5% of portfolio risk). The 4 retired strategies (`breakout_xlk`, `breakout_xlk_regime`, `sma_crossover_qqq`, `leveraged_long_trend_paper`) are excluded.
- Per-strategy daily series come from `_xstrat_corr.build_all_series()`. **The two levered sleeves (`tqqq_cot_combo` 3×, `allocator_blend` 1.3×) already embed their leverage** in the returns, so combining by risk-weight (not capital/$) is correct — capital-weighting would double-count that leverage.
- **Common window across all 8 = 2010-02-16 … 2026-06-18 (4111 trading days).** This starts at TQQQ/levered-ETF inception, so **the 2008 crisis (2008-09 … 2009-03) is OUT OF the book's range — no 2008 book number is fabricated** (core4 alone spans to 2008-05, but the blend can only be evaluated where the book exists).
- Core4 TSMOM standalone (its own full span 2008-06 … 2026-06): **Sharpe 0.298, CAGR 2.59%, maxDD −24.7%, corr→SPY −0.013** — confirms the brief's "Sharpe ≈0.305 standalone, crisis-positive, ≈zero SPY correlation."
- **Blend = fixed-weight, daily-rebalanced** (`X·book + (1−X)·core4`). This is the **idealized upper bound**; a real implementation would rebalance periodically (monthly/quarterly) and give up a little to drift + turnover cost.
- SPY benchmark = buy-hold on the same path (the **raw-return mission bar**).

---

## 1. PRIMARY RESULT — vol-normalized (unit-risk) book ⟵ decision basis

**Why this is the honest comparison:** the raw `_xstrat_corr` series mix two incompatible scales (see §2). To combine 8 strategies *as ERC intends* — each an equal-risk bet — every sleeve is first scaled to a common **10% annualized vol**, then ERC-risk-weighted. Core4 is then blended in **as-is** (its real, unscaled standalone series). This is what an ERC book actually targets, and it makes the equity book directly comparable to core4 on a risk basis.

Full-period (2010-02-16 → 2026-06-18, n=4111), fixed-weight daily-rebalanced:

| Ratio (eq/TSMOM) | Sharpe | CAGR % | maxDD % | annVol % | corr→SPY | TotRet % | 2020 crisis | 2022 |
|---|---|---|---|---|---|---|---|---|
| **baseline book (100/0)** | 0.964 | 6.13 | −12.53 | 6.38 | 0.729 | 163.8 | −8.42% | −5.03% |
| **80/20** | **1.037** | 5.74 | **−10.19** | 5.53 | 0.677 | 148.5 | −5.86% | −3.39% |
| **70/30** | **1.017** | 5.52 | **−9.42** | 5.43 | 0.605 | 140.4 | −4.56% | −2.59% |
| 60/40 | 0.952 | 5.29 | −8.66 | 5.58 | 0.507 | 132.0 | −3.26% | −1.79% |
| 50/50 | 0.857 | 5.05 | −8.72 | 5.96 | 0.399 | 123.4 | −1.95% | −1.00% |
| core4 standalone | 0.411 | 3.64 | −24.74 | 9.88 | 0.010 | 79.1 | +4.70% | +2.81% |
| **SPY buy-hold** | 0.877 | 14.51 | −33.72 | 16.9 | 1.000 | 811.8 | −13.23% | −18.18% |

**Reading:**
- **80/20 is the sweet spot.** It is the only ratio that beats the baseline on **both** Sharpe (1.037 > 0.964, +7.6%) **and** maxDD (−10.19% vs −12.53%, a 19% shallower trough), at a modest cost of ~9% total return (148.5% vs 163.8% over 16 yrs).
- **70/30** also beats baseline on both metrics (Sharpe 1.017, maxDD −9.42%) — even shallower DD, slightly less Sharpe lift. Reasonable if you weight DD-reduction over peak Sharpe.
- **Past 70/30, Sharpe rolls over** (60/40 → 0.952, 50/50 → 0.857): you're now paying too much of core4's weak 3.64% CAGR for diminishing risk benefit. The diversification benefit is real but the sleeve's low return caps how much you want.
- **Crisis behavior improves monotonically** with TSMOM weight — exactly the crisis-alpha the sleeve was hypothesized to add. The book alone is only mildly negative in 2020/2022 (it de-risks via regime filters), but the blend cuts those further and core4 is outright positive in both.
- **vs SPX raw:** the blend (and the pure book) **trail SPY's raw return massively** (148–164% vs 812%) — but that is the *entire point of a low-vol absolute-return book*: it runs at ~6% vol vs SPY's ~17%, and it **beats SPY on Sharpe** (1.04 vs 0.877 at 80/20) with **1/3 the drawdown** (−10% vs −34%). On a vol-matched or leverage-to-target basis the book is the superior risk-adjusted vehicle; on raw unlevered return it is not, by design.

---

## 2. SECONDARY / DIAGNOSTIC — raw-series blend (as literally specified) and why it misleads

Applying the ERC `risk_weights` directly to the **raw** `_xstrat_corr` series (no vol-normalization) gives:

| Ratio | Sharpe | CAGR % | maxDD % | corr→SPY | TotRet % |
|---|---|---|---|---|---|
| baseline book (100/0) | 1.422 | 4.91 | −3.82 | 0.619 | 118.7 |
| 80/20 | 1.339 | 4.74 | −3.95 | 0.488 | 113.0 |
| 70/30 | 1.164 | 4.64 | −5.15 | 0.381 | 109.7 |
| 60/40 | 0.985 | 4.53 | −6.32 | 0.284 | 106.0 |
| 50/50 | 0.831 | 4.41 | −7.69 | 0.206 | 102.1 |
| core4 standalone | 0.411 | 3.64 | −24.74 | 0.010 | 79.1 |
| SPY buy-hold | 0.877 | 14.51 | −33.72 | 1.000 | 811.8 |

Read naively this says "**baseline Sharpe 1.42 is unbeatable — every blend hurts → RED.**" **Do not trust this number.** It is a scale artifact:

- The 6 non-levered event sleeves' raw series are **equity-curve returns on a $100k account with tiny per-trade position sizing** — their *as-traded* annualized vol is **~0.01%** (they sit in cash most days and size conservatively). Their daily returns are single-basis-points **of the whole account**.
- The 2 levered sleeves (`tqqq_cot_combo`, `allocator_blend`) are **full-notional vol-target harness** returns — realistic **18.9% / 16.1%** annualized vol.
- Risk-weighting series of **~0.01% vol** alongside series of **~18% vol** does **not** equalize risk. The near-zero-vol sleeves' faint, smooth drift dominates the blended **Sharpe** (a smooth tiny uptrend has a huge Sharpe), producing the illusory 1.42 and a fake −3.82% maxDD. This book is not investable at that vol; it's the *unscaled* curve of conservatively-sized event strategies.

The vol-normalized construction in §1 removes this contamination by putting every sleeve on equal risk footing first — which is precisely what an ERC book is *for*. Capital-weighting was **not** used as the primary combiner (it would double-count the levered sleeves' leverage, per the brief); the ERC file ships `capital_usd` (not capital *weights*), and a $-weighted variant would only re-introduce the scale problem from the other direction, so it is omitted as uninformative.

---

## 3. Verdict & recommendation

**GREEN — paper-track an 80/20 equity/TSMOM blend** (with 70/30 as the more DD-averse alternative).

- On the honest unit-risk construction, **80/20 strictly dominates the pure book on risk** (Sharpe +7.6%, maxDD 19% shallower) for ~9% less total return — a clearly favorable risk-adjusted trade, and it sharpens crisis behavior (2020 −8.4%→−5.9%, 2022 −5.0%→−3.4%).
- The benefit comes from core4's **≈0 correlation to the equity book** (corr→SPY drops 0.729→0.677 at 80/20, →0.605 at 70/30) and its **crisis-positive** payoff — not from its return (a weak 3.64% CAGR), which is exactly why you want only a *small* slice. Beyond 30% TSMOM the weak CAGR starts dragging Sharpe back down.
- **Honest caveat on raw return:** the sleeve's 2.68–3.64% CAGR *does* dilute total return, and the whole book already trails SPX raw by design. If the mandate is "**beat SPX raw, unlevered**," neither the book nor any blend does that — but that is not what a 6%-vol absolute-return book is for. If the mandate is **best risk-adjusted return / shallowest drawdowns** (the Sharpe+DD bar), the 80/20 blend is the best configuration tested.
- **Implementation reality check:** these are daily-rebalanced idealized numbers. A monthly/quarterly-rebalanced live version will capture most but not all of the benefit and add small turnover cost. Recommend paper-tracking 80/20 (and logging 70/30 in parallel) against the pure book before any capital decision. **No live-capital move is implied by this research.**

---

### Reproduce
```
python3 _blend_test_main.py        # raw-series (diagnostic, §2)  -> reports/_tsmom_blend_result.json
python3 _blend_volnorm.py          # vol-normalized (primary, §1) -> reports/_tsmom_blend_volnorm_result.json
python3 _book_vol_probe.py         # per-sleeve vol diagnostic (the scale finding)
```
Primitives reused (not reimplemented): `_tsmom_engine.run_tsmom / sharpe_from_returns / max_drawdown / total_return / corr / spy_buyhold_on_path / BPY`, `_xstrat_corr.build_all_series`, `reports/_erc_weights.json` risk weights.
