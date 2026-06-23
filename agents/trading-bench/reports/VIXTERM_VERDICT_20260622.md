# VIX TERM-STRUCTURE OVERLAY on the TQQQ vol-target sleeve — VERDICT

**Date:** 2026-06-22
**Research lane:** Does a VIX term-structure (VIX3M vs VIX) slope signal IMPROVE the existing TQQQ vol-target sleeve on RAW RETURN and/or DRAWDOWN, out-of-sample, net of costs?
**Status:** PAPER / RESEARCH ONLY. No live capital. New files only under `strategies_candidates/leveraged_long_trend/` + this report. No protected engine or live strategy touched.

## VERDICT: **NO** — does not clear the bar. Recommend **CLOSE**.

The overlay does **not** beat the existing sleeve on raw return out-of-sample net of costs, and the one configuration that "wins" OOS is a **knife-edge overfit** (catastrophic threshold neighbors + edge evaporates under a 1-day timing lag). The trend gate (SMA-200) already captures ~half the term-structure signal, and the residual is too rare/weak to overcome turnover cost. The only genuine, robust benefit is a **narrower 2020-COVID-style crash drawdown** — real but narrow, costly in return, and not generalizing to 2022. A clean negative.

---

## 1. Hypothesis

VIX term-structure slope `= VIX_close / VIX3M_close`.
- `slope > 1.0` → VIX above VIX3M → **backwardation** → acute stress/fear (classically precedes/coincides with equity weakness).
- `slope < 1.0` → VIX below VIX3M → **contango** → calm/risk-on.

Layered on the EXISTING TQQQ vol-target sleeve (SMA-200 trend gate + trailing-20d realized-vol target at 25% ann vol, sleeve weight cap 1.0, 3M T-bill cash for the rest), does conditioning EXPOSURE on the slope beat the sleeve's current gating — on raw cumulative return AND maxDD — OUT OF SAMPLE, net of 2bps costs? The honest baseline is the **existing sleeve**, not SPX.

## 2. Data & window

| Series | Source | Span | Use |
|---|---|---|---|
| VIX | `runner/cboe_cache.load_series("VIX")` | 1990-01-02 → 2026-06-19 (9211 rows) | close |
| VIX3M | `runner/cboe_cache.load_series("VIX3M")` | 2009-09-18 → 2026-06-18 (4213 rows) | close |
| TQQQ / QQQ / ^GSPC | Yahoo v8 adjclose (existing repo bars cache, reused — not re-fetched) | TQQQ inception 2010-02 | adjclose |

**Backtest window: 2010-02-11 → 2026-06-22 (4114 days).** VIX3M (2009-09-18) starts before TQQQ inception (2010-02), so there is **no data gap** — `slope_missing = 0` over the entire traded window (audited, not assumed). All sources are lookahead-safe (CBOE cache asserts `date < asof` on every read).

## 3. Signal definition + timing convention (lookahead-safe)

The existing sleeve decides the weight held over day `d` (= D+1) from data with date ≤ D (the prior decision day): trend gate uses underlying closes through D; realized vol uses sleeve returns ending on D. **The slope uses the IDENTICAL information set:**

```
slope_for(d) = level_asof("VIX", d) / level_asof("VIX3M", d)
```

`cboe_cache.level_asof(idx, d)` returns the most recent close **strictly before** `d`, i.e. the close on **D** (the decision day) for a position held over `d = D+1`. An index close for date D is EOD-observable after D's close and is applied to the **next** bar's position. This exactly mirrors the trend gate → **no lookahead** (verified: `asof("VIX","2020-03-20")` returns the 2020-03-19 close). A `slope_lag` knob lags the slope an additional whole trading day for a robustness check.

**Overlay mechanic:** overlaid weight `w = w_base × m(slope)`, clamped to `[0, w_max]`, where `w_base` is the existing sleeve's trend-gated inverse-vol weight and `m(slope) ∈ [0,1]` is the modulator. The overlay pays for its **own** extra turnover (|Δw| recomputed on the overlaid path; every gate flip is a full round-trip).

## 4. Variants tested

| Variant | Modulator `m(slope)` | Rationale |
|---|---|---|
| **baseline** | `1.0` (existing sleeve, untouched) | the bar to beat |
| hard_gate_1.00 | `0.0 if slope>1.00 else 1.0` | cash in backwardation |
| hard_gate_1.05 | `0.0 if slope>1.05 else 1.0` | cash in DEEP backwardation |
| half_gate_1.00 | `0.5 if slope>1.00 else 1.0` | half weight in backwardation |
| cont_linear | `clamp((1.05−slope)/0.15, 0, 1)` (lo=0.90, hi=1.05) | smooth fade, no knife-edge |

Thresholds (1.00/1.05) and the linear band (0.90..1.05) are round, ex-ante — **not** argmax-swept on OOS. A separate in-sample threshold sweep (§7) exposes any knife-edge.

**Sanity check — baseline reproduces the existing sleeve EXACTLY:** tot 2078.6%, CAGR 20.78%, maxDD −34.52%, Sharpe 0.863, avgW 0.515, rebal 3247 — bit-identical to `backtest_daily_voltarget` at target 0.25 over the same window. The comparison is apples-to-apples.

## 5. Results — full period (continuous-span Sharpe, sqrt(252); single uninterrupted curve)

**GROSS** (flat headline), full window:

| Variant | Total ret | CAGR | maxDD | Sharpe | avgW | rebal |
|---|---|---|---|---|---|---|
| **baseline (existing sleeve)** | **+2078.6%** | **20.78%** | **−34.52%** | **0.863** | 0.515 | 3247 |
| hard_gate_1.00 | +1836.7% | 19.91% | −36.34% | 0.860 | 0.498 | 3148 |
| hard_gate_1.05 | +2031.0% | 20.61% | −33.74% | 0.867 | 0.511 | 3216 |
| half_gate_1.00 | +1977.8% | 20.43% | −35.39% | 0.871 | 0.507 | 3249 |
| cont_linear | +1471.2% | 18.38% | −31.90% | 0.861 | 0.469 | 3255 |
| SPX buy&hold | +592.8% | 12.59% | −33.92% | 0.774 | — | 0 |
| 3x sleeve buy&hold | +39571% | 44.28% | −81.66% | 0.909 | — | 0 |

**Read:** **no variant beats baseline on raw return.** Best gate (1.05) is −47.6pp behind on total return while shaving only 0.78pp of maxDD. cont_linear cuts maxDD 2.6pp but sheds **607pp** of return. Sharpe deltas (±0.008) are inside noise.

**NET of costs** (recost grid: optimistic = engine 2bps; realistic = 5bps/side + 0.95%/yr ER), full window + frozen OOS:

| Variant | NET-2bps full ret | NET-real full ret | NET-real OOS ret | NET-real OOS dd | vs baseline OOS (ret / dd) |
|---|---|---|---|---|---|
| **baseline** | +2078.6% | +1841.4% | **+356.2%** | **−35.06%** | — |
| hard_gate_1.00 | +1836.7% | +1601.4% | +304.5% | −36.94% | **−51.7pp** / −1.88pp |
| hard_gate_1.05 | +2031.0% | +1793.1% | +371.0% | −34.29% | +14.8pp / +0.77pp |
| half_gate_1.00 | +1977.8% | +1739.2% | +332.3% | −35.96% | −23.9pp / −0.90pp |
| cont_linear | +1471.2% | +1278.5% | +294.1% | −25.62% | −62.1pp / **+9.44pp** |

SPX reference (cost-free buy&hold): full +592.8%, IS +147.9%, **OOS +177.1%**, dd −33.9%. Every variant — including baseline — clears SPX on OOS return by a wide margin; **but SPX is not the bar.** Against the **existing sleeve**, only hard_gate_1.05 shows a positive OOS return margin (+14.8pp), and §7 shows that margin is an overfit artifact.

## 6. 2020 COVID & 2022 bear behavior (the stress question)

**2020 COVID (2020-02-01 → 2020-06-30), gross within-window ret / maxDD:**

| | ret | maxDD |
|---|---|---|
| SPX | −4.6% | −33.9% |
| baseline | +2.0% | −20.76% |
| hard_gate_1.00 | +13.0% | −10.02% |
| hard_gate_1.05 | +19.0% | −9.34% |
| cont_linear | +10.6% | −6.68% |

→ **This is the one place the slope genuinely helps.** In the COVID crash the slope flipped into backwardation while QQQ was still above its 200-SMA (the crash was too fast for the trend gate), so the slope flattened exposure ahead of the trend gate and roughly **halved-to-thirded the drawdown** (−20.8% → −9.3% for the 1.05 gate). Real, mechanistic, and the strongest point in the overlay's favor.

**2022 bear (2022-01-01 → 2022-12-31):**

| | ret | maxDD |
|---|---|---|
| baseline | −17.8% | −17.81% |
| hard_gate_1.00 | −17.8% | −17.81% |
| hard_gate_1.05 | −17.8% | −17.81% |
| cont_linear | −17.6% | −17.56% |

→ **Every variant is identical to baseline.** The 2022 grind-down kept QQQ below its 200-SMA for essentially the whole year, so the SMA-200 gate already held the sleeve flat — the slope gate had **no in-market days to act on**. The slope adds nothing to a slow bear the trend gate already handles; it only helps the *fast* crash (2020) the trend gate is too slow for.

## 7. Redundant-with-SMA-200 decomposition + threshold-neighbor overfit check

**Decomposition (slope thr=1.00, in-market days only):**
- Backwardation days over the window: **317 total**, of which **157 (49.5%) were already gated out by SMA-200** — the trend gate alone removes half of all backwardation exposure.
- Among the **160** in-market backwardation days, forward 1-day sleeve return averages **+29.5%/yr** vs **+46.6%/yr** on the 3299 in-market contango days — a real **17.0%/yr** spread. So the slope is **not fully redundant**: surviving in-market backwardation days do carry materially worse forward returns.
- **But** 160 days over 16 years is thin, and the edge is swamped by (a) the gate's existing 49.5% coverage and (b) turnover cost. The orthogonal residual is too small/rare to lift the net result.

**Threshold neighbors — fit on IN-SAMPLE (≤2017) only, frozen OOS (NET realistic):** this is the overfit autopsy.

| thr | IS ret | OOS ret | OOS dd | OOS ret vs base | rebal |
|---|---|---|---|---|---|
| 0.95 | 161.9% | 321.6% | −23.11% | −34.6pp | 2908 |
| 0.98 | 240.4% | 237.6% | −33.06% | **−118.6pp** | 3101 |
| 1.00 | 300.2% | 304.5% | −36.94% | −51.7pp | 3148 |
| **1.02 (IS-best)** | **304.6%** | 311.7% | −37.20% | **−44.5pp** | 3186 |
| 1.05 | 282.4% | 371.0% | −34.29% | +14.8pp | 3216 |
| 1.08 | 287.6% | 384.3% | −36.42% | +28.1pp | 3226 |
| 1.10 | 292.2% | 407.6% | −35.24% | +51.4pp | 3226 |

Baseline (net realistic): IS +304.9%, **OOS +356.2%**, dd −35.06%.

**The honest frozen-OOS answer: the IS-best threshold (1.02) underperforms the baseline sleeve by −44.5pp OOS, net.** The thresholds that "beat" the baseline OOS (1.05/1.08/1.10) are **not** the ones in-sample selected, and they win only by **gating less and less** — i.e. by converging toward do-nothing (the baseline). The neighbor profile is violently non-monotonic (0.98 → −118.6pp, then 1.05 → +14.8pp): a **knife-edge with catastrophic neighbors**, the canonical overfit signature. Picking 1.05 in advance and calling its +14.8pp a win is hindsight.

## 8. Robustness — slope lag (NET realistic, hard_gate_1.05)

| slope_lag | full ret | OOS ret | OOS dd | OOS ret vs base |
|---|---|---|---|---|
| 0 | +1793.1% | +371.0% | −34.29% | +14.8pp |
| **1** | +1698.0% | +355.7% | −36.68% | **−0.5pp** |
| 2 | +1755.4% | +369.3% | −37.61% | +13.1pp |

**The +14.8pp OOS "edge" of the 1.05 gate evaporates to −0.5pp under a single-day timing lag.** A structural signal survives a one-day shift; this one does not. Combined with §7, the apparent OOS win is **timing-fragile noise**, not a robust edge.

## 9. Regime-switch / turnover sanity

Gate flips are frequent enough to not be a 5-switch mirage (hard_gate_1.05 ≈ 3216 weight-change days vs baseline 3247 — the overlay slightly *reduces* turnover by parking in cash during backwardation), so the result is statistically meaty, not a fluke of a handful of switches. The problem is not sample size; it's that the signal, honestly fit, does not beat the baseline.

## 10. Conclusion & recommendation

| Criterion (bar = beat the EXISTING sleeve, OOS, net) | Result |
|---|---|
| Raw return, OOS, net, honestly fit (IS-best thr frozen OOS) | **FAIL** (−44.5pp) |
| Raw return, OOS, net, cherry-picked thr (1.05) | +14.8pp — but overfit (§7) + timing-fragile (§8) |
| maxDD, full period, net | marginal (best −0.8pp; cont_linear −2.6pp but −607pp return) |
| maxDD, 2020 COVID crash specifically | **PASS** (−20.8% → −9.3%) — real, robust, narrow |
| maxDD, 2022 bear | no change (SMA-200 already flat) |
| Adds info orthogonal to SMA-200? | partially (17%/yr spread on 160 days) — too rare/weak to net out |

**VERDICT: NO.** The VIX term-structure slope does **not** improve the existing TQQQ vol-target sleeve on raw return out-of-sample net of costs. The trend gate already removes half of all backwardation exposure and fully handles slow bears (2022); the residual signal is real but too rare to overcome turnover cost; and the single config that beats the baseline OOS is an overfit knife-edge whose edge vanishes under a 1-day lag.

**The one honest, robust positive:** the slope flattens exposure faster than the SMA-200 gate in a **fast** crash (2020 COVID), cutting that specific drawdown by ~half. If a future objective is specifically *fast-crash tail protection* (not raw return or general DD), a **deep** backwardation gate (thr ≥ 1.05, or the smooth cont_linear for its −9.4pp OOS DD) is the only part worth revisiting — explicitly as a tail hedge that *costs* return, never as a return/Sharpe improver.

**Recommendation: CLOSE this lane.** Do not add the overlay to the sleeve. A clean negative.

---

### Reproduce
```
python3 -m strategies_candidates.leveraged_long_trend.backtest_voltarget_vixterm   # headline + stress + decomposition
python3 -m strategies_candidates.leveraged_long_trend.validate_vixterm             # frozen-OOS, net costs, threshold neighbors, lag robustness
```
Artifacts: `strategies_candidates/leveraged_long_trend/{backtest_voltarget_vixterm.py, validate_vixterm.py, vixterm_result.json, validation_vixterm_result.json}`.

### Measurement hygiene honored
- No lookahead: slope uses closes ≤ decision day D, applied to D+1 (CBOE cache asserts `date < asof`); `slope_missing = 0` audited over the traded window.
- Benchmark = the EXISTING sleeve on the SAME traded path (baseline reproduces it bit-for-bit), SPX secondary.
- Gross AND net (2bps + realistic 5bps/0.95%ER grid) reported.
- OOS mandatory: thresholds fit on IS (≤2017), frozen OOS (>2018) reported; neighbors shown (knife-edge exposed).
- Sample size: ~3200 weight-change days / 317 backwardation days / 160 in-market — not a small-N mirage.
- Redundancy with SMA-200 decomposed explicitly (in-market-days-only conditioning).
- Full-period continuous-span Sharpe (sqrt(252)), single uninterrupted curve — not median-of-windows.
