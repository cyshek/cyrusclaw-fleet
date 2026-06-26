# IMPLIED−REALIZED CORRELATION SPREAD — Correlation-Risk-Premium Probe

**Date:** 2026-06-25
**Author:** Tessera (trading-bench) — research subagent `corr-risk-premium-probe`
**Type:** Pre-committed PROTOTYPE-GATE probe (research-only; no trades, no cron, no config, no protected-file edits)
**Lane:** Idea #3 of `reports/AQR_READING_SPRINT_20260624.md` — implied index correlation (CBOE COR1M) MINUS realized pairwise sector correlation, as a complacency/crash gauge (Driessen–Maenhout–Vilkov 2009 correlation risk premium).
**Scratch:** `corr_risk_premium_probe.py`, `corr_risk_premium_robustness.py` (workspace root; both `py_compile`-clean).

---

## TL;DR — VERDICT: **RED. Close the free-data dispersion class.**

The SPREAD `S(d) = z(COR1M_implied) − z(realized_pairwise_corr)` **passes orthogonality decisively** (it genuinely strips the inverse-SPY-trend content that the LEVEL carries) **but has no forward-return predictive content.** The quintile sort is **non-monotone at the natural h=21 horizon (U-shaped)**, the Q5−Q1 spread is **−0.32% with Newey-West t = −0.58** (indistinguishable from zero), and the sign **flips across horizons** (+0.02% / −0.32% / −1.41% at h=5/21/63) **and across IS/OOS** (+0.08% pre-2016 → −0.60% in 2016+). The failure is **robust across three independent normalizations** (full-sample z, causal rolling-252d z, causal rolling-252d percentile-rank), so it is not a normalization artifact.

This is the second and final nail. The AQR sprint already falsified the COR3M **level** (idea #5 — it re-labels inverse-SPY beta). The **spread** was the last defensible, orthogonal expression of the dispersion class. It is orthogonal as advertised — and predicts nothing. **The whole dispersion/correlation class is now done from free data.**

| Gate | Result | Pass? |
|---|---|---|
| **(1) Orthogonality** corr(S, SPY 63d-ret) | **−0.083** (n=5085) | ✅ <0.30 |
| **(1) Orthogonality** corr(S, SPY/SMA200) | **−0.182** (n=4949) | ✅ <0.30 |
| **(2) Forward sort** h=21 monotonicity | **NON-MONOTONE** (up=2/4) | ❌ |
| **(2)** Q5−Q1 @ h=21 | **−0.315%** | ❌ noise |
| **(2)** sign consistent across h=5/21/63 | **NO** (+0.02 / −0.32 / −1.41) | ❌ flips |
| **(3)** Q5−Q1 @ h=21 Newey-West t | **−0.58** | ❌ \|t\|≪1.5 |
| **(3)** IS/OOS sign stability | **NO** (+0.08% → −0.60%) | ❌ flips |

**Plateau vs knife-edge:** neither — it's **noise** (no horizon shows a monotone, significant sort; the only "signal" is the well-known low-vol-begets-good-returns artifact sitting in BOTH tails). **Canary-clean: YES** (no protected/strategy file touched; verified by hash + mtime).

---

## 1. Protected-file integrity (verified at finish)

This session's entire write-set = two scratch `.py` files + this report. No protected or strategy file was opened for writing. Confirmed by content hash + mtime (every protected file's mtime predates my scratch files; gateway clock is UTC and the bench was independently active 16:17–18:37 UTC earlier today):

```
runner/runner.py                                  0f763975f2d8ba535352f6a8306afb8b
runner/risk.py                                    e303317e0d2ac796a1fa43e372f0a113
runner/walk_forward.py                            6fb34eeac25d3ff463dc11e6bbfbdadc
runner/strategy_gen.py                            a9d17ee44e6658c30c457a2e133c14ad
runner/backtest.py                                5b6492b93d6f74189d2cb29c617cb118
runner/backtest_xsec.py                           d8927364605e9253d54284bd4068c874
runner/allocator_paper_tracker.py                 0b5242474a9bad75562c94595bacbc23
strategies/tqqq_cot_combo/strategy.py             ab0890eddf501d5af049d378ab07145c
strategies/breakout_xlk__mut_c382b1/strategy.py   6cbf9eb1cbc9c907656beb73d4034505
```

(Note: this workspace is not a git repo, so the canary is hash/mtime-based, not `git status`-based.)

---

## 2. Data + spans (confirmed on disk, printed by the probe)

| Series | Source | Span used | n |
|---|---|---|---|
| **Implied leg** COR1M close | `data_cache/cboe/COR1M_History.csv` (CBOE 1M implied index correlation, MM/DD/YYYY) | 2006-01-03 → 2026-06-23 | 5149 |
| **Realized leg** avg pairwise corr of 9 sectors | `runner.daily_bars_cache.get_daily` (Yahoo adjclose), trailing N=21 log-returns | built 2006-02-01 → 2026-06-22 | 5128 |
| **SPY** (trend + forward returns) | `daily_bars_cache.get_daily('SPY')` adjclose | 1993-01-29 → 2026-06-25 | 8408 |
| Sectors XLK XLF XLE XLV XLI XLP XLY XLU XLB | same | 1998-12-22 → 2026-06-22 | 6915–6918 each |

**Sector set:** the 9 GICS-original SPDR sectors (XLK XLF XLE XLV XLI XLP XLY XLU XLB). XLRE (starts 2015-10) and XLC (starts 2018-06) were **excluded** — too short for the 2006+ window, as the task specified.

**Common span used for the spread:** 2006-02-01 → 2026-06-22 (latest start = realized-corr's first valid 21d window; earliest common end = sectors' 2026-06-22). **n = 5128 dates with BOTH legs present.**

**Scale sanity (why normalization is mandatory):** COR1M close mean=37.45, sd=17.77, range [2.93, 96.59] (correlation-index *points*, ~100×implied historically but drifted). Realized avg pairwise corr mean=0.565, sd=0.192, range [0.066, 0.946] (a true 0–1 Pearson average). The two legs live on **completely different scales** → differencing raw is meaningless; both legs MUST be standardized first. raw corr(implied, realized) = **+0.739** (they co-move strongly, as expected — implied tracks realized — which is exactly why the *spread* is the orthogonal content, not either level).

---

## 3. Normalization choice (justified)

**Primary:** `S(d) = z(COR1M_implied) − z(realized_pairwise_corr)`, where each leg is z-scored (mean-0/var-1) over the **full common span**. Chosen because (a) it puts both legs on a common, unit-variance scale so the difference is interpretable, (b) it is the simplest defensible choice and matches how the DMV correlation-risk-premium is conventionally expressed (standardized implied-minus-realized), and (c) the probe's question is about the *time-variation* of the spread, which full-sample z preserves while neutralizing the CBOE scale drift. Resulting S: mean +0.000, sd 0.722, range [−1.98, +2.84].

**Caveat acknowledged:** full-sample z uses the whole-sample mean/sd, which is mildly forward-looking for the *standardization constant* (not for the underlying data). I therefore re-ran the entire forward-sort under two **causal** alternatives (rolling-252d z, and rolling-252d percentile-rank) in §6 — the RED holds under all three, so the full-sample-z convenience does not change the verdict.

---

## 4. Gate (1) — ORTHOGONALITY: **PASS** (the spread does its one job)

Correlation of S(d) against two SPY-trend proxies, both strictly trailing:

| Proxy | corr with S | n | Gate \|corr\|<0.30 |
|---|---|---|---|
| SPY 63-day trailing return | **−0.083** | 5085 | ✅ PASS |
| SPY price / 200d SMA | **−0.182** | 4949 | ✅ PASS |

**This is the one thing that worked.** Contrast with the raw LEVELS (the AQR-sprint finding that killed idea #5 — the level is inverse-SPY beta in disguise):

| Raw level | corr(·, SPY 63d-ret) | corr(·, SPY/SMA200) |
|---|---|---|
| COR1M **implied** level | **−0.416** | **−0.517** |
| **realized** corr level | **−0.355** | **−0.388** |
| **SPREAD** S = z(impl)−z(real) | **−0.083** | **−0.182** |

The spread collapses the inverse-trend content from ~−0.42/−0.52 (level) down to −0.08/−0.18 — **it genuinely strips the beta**, exactly as Driessen–Maenhout–Vilkov's "the spread is the orthogonal content" predicts. So the orthogonality thesis is *confirmed*. The lane dies at the next gate, not this one.

---

## 5. Gate (2)+(3) — FORWARD-RETURN SORT: **FAIL** (no predictive content)

Days sorted into quintiles by S(d); mean forward SPY return per quintile at h ∈ {5, 21, 63} trading days. Signal at d, return strictly d+1…d+h (no overlap leak).

**Full sample (mean forward SPY return %, by S-quintile, n≈1021/quintile):**

| Quintile | S-range | h=5 % | h=21 % | h=63 % | n |
|---|---|---|---|---|---|
| Q1 (low S) | [−1.98, −0.60] | +0.296 | **+1.557** | +4.065 | 1021 |
| Q2 | [−0.60, −0.17] | +0.148 | +0.823 | +2.852 | 1021 |
| Q3 | [−0.17, +0.16] | +0.128 | **+0.505** | +2.138 | 1022 |
| Q4 | [+0.16, +0.59] | +0.311 | +0.856 | +2.926 | 1021 |
| Q5 (high S) | [+0.59, +2.84] | +0.317 | **+1.242** | +2.656 | 1022 |
| **Q5−Q1** | | **+0.021** | **−0.315** | **−1.409** | |

**The shape is a U, not a monotone ramp.** At h=21, returns fall Q1→Q3 then rise Q3→Q5 — both extreme quintiles (very low AND very high spread) show *above-average* forward returns, the middle is flat. That is the signature of a **vol-level confound bleeding through both tails** (low-realized-corr calm markets sit in low-S; high-implied-fear panic-rebound markets sit in high-S; both historically precede positive drift), **not** a clean complacency-vs-crash sort. Monotonicity at h=21: **NON-MONOTONE (2/4 steps up, 2/4 down).**

**Sign flips across horizons:** Q5−Q1 = **+0.021% / −0.315% / −1.409%** at h=5/21/63. A real risk-premium signal would hold sign across nearby horizons; this one is positive at a week, negative at a month, strongly negative at a quarter — a knife-edge sign-change, i.e. noise.

**Statistical honesty (Q5−Q1 @ h=21, Newey-West, Bartlett lag=21 to absorb the daily-overlap in the h=21 forward window):**

| Leg | mean fwd(h=21) | NW-SE | t | n (overlapping daily) |
|---|---|---|---|---|
| Q1 | +1.557% | 0.323 | +4.83 | 1021 |
| Q5 | +1.242% | 0.430 | +2.89 | 1022 |
| **Q5−Q1** | **−0.315%** | **0.538** | **−0.58** | eff. indep n ≈ 5128/21 ≈ **244** |

Both quintiles individually have positive forward returns (it's SPY — equity drift is positive on average); the *difference* that the strategy would trade is **−0.32% with t=−0.58**, i.e. statistically zero. The required bar was \|t\|≳1.5 minimum to justify a build. **Misses by a mile.**

**IS/OOS sign stability (split 2016-01-01, longer than usual since COR1M reaches 2006):**

| Window | n | Q1 (h=21) | Q5 (h=21) | Q5−Q1 | monotone? |
|---|---|---|---|---|---|
| Pre-2016 | 2497 | +1.018% | +1.098% | **+0.079%** | non-mono (3/4 up) |
| 2016+ | 2631 | +2.089% | +1.490% | **−0.599%** | non-mono (1/4 up) |

**Sign FLIPS across the split** (+0.08% IS → −0.60% OOS). Even if one cherry-picked a direction, it doesn't survive out-of-sample.

---

## 6. Robustness — the RED is not a normalization artifact

Re-ran the full forward-sort under three normalizations (`corr_risk_premium_robustness.py`):

| Normalization | h=21 monotonicity | Q5−Q1 @ h=21 | Q5−Q1 t (NW lag21) | sign-consistent across h? |
|---|---|---|---|---|
| Baseline full-sample z(impl)−z(real) | NON-MONO (2/4) | −0.315% | **−0.58** | NO |
| (A) **causal** rolling-252d z(impl)−z(real) | NON-MONO (1/4) | −0.069% | **−0.14** | NO |
| (B) **causal** rolling-252d pctrank(impl)−pctrank(real) | NON-MONO (1/4) | −0.439% | **−0.90** | NO |

All three: non-monotone at h=21, \|t\| < 1, sign flips across horizons. The causal variants (which a live system would actually use, no full-sample standardization) are if anything *weaker*. **Conclusion holds regardless of normalization choice.**

---

## 7. No-lookahead statement

- **COR1M close on date d** is an implied/quoted index value, knowable at EOD d and **not revised** — no restatement leak.
- **Realized corr on date d** uses sector log-returns through d's close only (each return is close-to-close, realized AT the close it's dated to), over a **strictly trailing** 21-day window (all dates ≤ d). Window dates require *all* sectors present so the correlation vectors stay aligned; no future bar enters.
- **SPY trend proxies** (63d-return, /SMA200) use closes ≤ d only.
- **Forward returns** use closes **strictly d+1…d+h** (P[d] → P[d+h]); the signal is dated d, the return window starts the next trading day → **no overlap between the signal observation and its forward-return window**.
- **Sector + SPY adjclose are PIT by construction** (a close at d was knowable at d); `daily_bars_cache` enforces this with its asof/asof_strict guards.

The only overlap present is the *expected* one *within* the pooled forward-return series (consecutive days share most of their h-day window) — handled by the Newey-West HAC SE (lag=h) and reflected in the "effective independent n ≈ n/21 ≈ 244" caveat. No signal↔return leak.

---

## 8. Honest caveats

- **The orthogonality result is real and worth banking as a finding:** the implied−realized correlation spread *is* a beta-stripped quantity (−0.08/−0.18 vs trend, down from the level's −0.42/−0.52). The lane doesn't fail because the construct is degenerate; it fails because, once you remove the beta, what's left **doesn't forecast SPY**. That's a cleaner, more informative RED than #5's "it was just beta."
- **N=21 realized window** was chosen to match COR1M's 1-month implied horizon. A different realized lookback (40d, 63d) could shift details, but the U-shape + sign-instability is structural (it's the vol-level confound in both tails), and the t-stat has no margin (−0.58); no lookback choice rescues a t≪1 with a flipping sign.
- **9 sectors, not 11** — XLRE/XLC excluded for span. Adding them post-2018 cannot fix a 2006-spanning sort and would shorten the sample.
- **Direction was measured, not assumed** — I did not pre-bake "high spread = bearish." The data says high-S and low-S *both* precede above-average drift (U-shape); there is no monotone direction to assume.
- **This is the index-timing expression only.** It does not test a *dispersion options* trade (selling index vol / buying single-name vol to harvest the correlation risk premium directly) — that requires single-name options data we don't have and is a paid-data, different-mechanism lane. The free-data, SPY-timing/sizing expression of the correlation risk premium is what's dead here.

---

## 9. Verdict & disposition

**RED — CLOSE THE DISPERSION/CORRELATION CLASS (from free data).**

- The **level** (COR3M/COR1M percentile as an equity throttle) was already falsified (AQR sprint idea #5): it's inverse-SPY beta re-labeled.
- The **spread** (this probe) is the orthogonal residual — and it has **no forward-return content**: non-monotone, t≈−0.6, sign-unstable across horizons and across IS/OOS, robust to normalization.

Both the level and the orthogonal spread fail. There is **no remaining free-data expression** of the correlation/dispersion idea that both (a) isn't just beta and (b) predicts returns. **Shelf the class.** Do not build a strategy on this. The next dispersion attempt would require **single-name options data** (a paid feed) to trade the correlation risk premium *directly* as a vol-dispersion options structure — a separate, money-gated decision, not a free-data lane.

**One-liner for the log:** Corr-risk-premium SPREAD probe = RED. Orthogonality PASSES (corr(S,SPY63d)=−0.08, corr(S,SPY/SMA200)=−0.18 — the spread genuinely strips the beta the LEVEL carries), but the forward sort is noise: h=21 NON-MONOTONE (U-shaped), Q5−Q1=−0.32% t=−0.58 (n_eff≈244), sign flips across h=5/21/63 (+0.02/−0.32/−1.41) AND across IS/OOS (+0.08%→−0.60%), robust across 3 normalizations. Both the level (idea #5, dead) and the spread now fail → close the free-data dispersion class. Canary-clean.
