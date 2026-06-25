# DISPERSION SPREAD PROBE — Implied−Realized Pairwise Correlation (Correlation Risk Premium)

**Date:** 2026-06-24 · **Analyst:** trading-bench (subagent) · **Type:** prototype-gate probe (research only, no trade/cron/config)
**Idea:** dispersion #3 from `reports/AQR_READING_SPRINT_20260624.md` — the orthogonal content of correlation lives in the implied−realized **spread** (correlation risk premium; Driessen-Maenhout-Vilkov 2009), NOT the level.
**Prior:** naive COR **level** already FALSIFIED — corr(ΔCOR3M, SPY ret) = −0.609 (lagging beta), level quintile sort backwards/non-monotone.

**Scripts:** `_disp_spread_probe.py` (gate), `_disp_spread_diag.py` (per-year level diagnostic), `_disp_spread_detrend.py` (detrended robustness). All `py_compile`-clean.

---

## Verdict: 🔴 **RED — shelf the dispersion class**

**One-line reason:** The spread passes orthogonality (max |corr| = 0.13) but FAILS the monotone forward sort on **both** 5d & 21d AND survives no detrending — and the "spread" is structurally a near-constant ~−0.19 offset (a sector-vs-stock correlation-object mismatch), not a tradeable risk premium. No monotonic forward predictive content exists in any form (raw / demeaned / z-scored).

---

## Method & scale alignment

- **Implied:** CBOE `COR1M_History.csv` CLOSE. Range 2.93–96.59 (mean 37.39) ⇒ index level = implied correlation ×100. **Divided by 100 → 0–1 scale.**
- **Realized:** average of the **36 unique pairwise** Pearson correlations of daily log-`adjclose` returns across the 9 long-history SPDR sectors (XLK,XLF,XLE,XLV,XLI,XLY,XLP,XLU,XLB), rolling **21d** (primary, matches COR1M ~1-mo horizon) and **63d** (robustness). Already 0–1 native.
- **Spread = implied(0–1) − realized(0–1).** SPY `adjclose` for returns / trend / forward returns.
- **Common axis:** SPY ∩ COR1M ∩ all 9 sectors = **5,148 days, 2006-01-03 → 2026-06-22** (spans 2008 GFC, 2020 COVID, 2022 bear). n_spread(21d)=5,127; n_spread(63d)=5,085.
- Spread(21d): mean **−0.191**, sd 0.134, [−0.564, +0.327]. implied mean 0.375, realized mean 0.565.

## Gate 1 — Orthogonality ✅ PASS (but hollow, see diagnostic)

| corr(spread, …) | 21d realized | 63d realized |
|---|---|---|
| ΔSPY daily return | **−0.126** | −0.165 |
| SPY 50d trend return | **−0.024** | −0.304 |
| SPY price/200d-SMA − 1 | **−0.133** | −0.279 |

Primary (21d) max |corr| = **0.133 < 0.30 → PASS.** The spread *does* strip the level's −0.609 beta contamination. (63d's −0.304 vs 50d-trend is borderline — longer realized windows re-import trend.)

## Gate 2 — Monotone forward sort ❌ FAIL (both horizons, both windows)

**21d realized window — fwd SPY log-ret by spread quintile (annualized):**

| | Q1 (low spread) | Q2 | Q3 | Q4 | Q5 (high spread) | verdict |
|---|---|---|---|---|---|---|
| fwd **5d** | +12.7% | +4.7% | +14.2% | +8.1% | +13.2% | **NON-MONOTONE** |
| fwd **21d** | +18.8% | +7.2% | +8.7% | +6.1% | +12.0% | **NON-MONOTONE** |

**63d realized window:** fwd5d `+13.0 | +10.4 | +1.8 | +12.7 | +14.6` → NON-MONOTONE; fwd21d `+13.7 | +10.0 | +7.7 | +9.5 | +11.7` → NON-MONOTONE. Both U-shaped/noisy, no sign structure.

## Diagnostic — the spread is a structural offset, not a risk premium

Per-year implied vs realized(21d): **the spread is negative in ALL 21 years** (−0.087 to −0.291), ~constant ~−0.19. Full-sample: implied 0.375 vs real21 **0.566** / real63 **0.588**. Textbook correlation RP requires implied ≥ realized; here realized is *persistently higher*. Cause: **CBOE COR1M = option-implied correlation across the ~50 largest SPX single stocks** (cap-weighted), whereas the realized basket = **9 SPDR sectors** — each already a diversified index, so cross-*sector* realized correlation runs structurally above cross-*stock* implied correlation. **Differencing them is apples-to-oranges**; the "spread" mostly inherits a shifted COR level, which is why ortho looks better but predictivity doesn't appear.

## Robustness — detrending does NOT rescue it

Stripping the structural offset (trailing-252d) leaves the sort non-monotone everywhere:

| signal | fwd5d quintiles (ann) | fwd21d quintiles (ann) |
|---|---|---|
| RAW spread | +12.7 / +4.7 / +14.2 / +8.1 / +13.2 → NON-MONO | +18.8 / +7.2 / +8.7 / +6.1 / +12.0 → NON-MONO |
| DEMEANED (−252d mean) | +11.5 / +9.4 / +4.3 / +9.9 / +16.6 → NON-MONO | +15.6 / +9.1 / +12.0 / +3.4 / +12.0 → NON-MONO |
| Z-SCORE (252d) | +13.7 / +6.3 / +5.4 / +11.7 / +14.6 → NON-MONO | +17.9 / +6.5 / +11.6 / +5.2 / +10.9 → NON-MONO |

## Conclusion

The hypothesis that survived the level falsification — "the orthogonal, tradeable content is in the implied−realized correlation spread" — **does not survive its own gate.** Orthogonality passes only because the spread is a near-constant offset off the (beta-laden) implied level; once you ask it to *sort forward equity returns*, it is as non-monotone and edge-free as the level was — in raw, demeaned, and z-scored form, on 5d and 21d, with 21d and 63d realized windows. Combined with the structural sector-vs-stock mismatch that makes the spread definitionally suspect, there is no salvageable equity-timing edge here.

**→ RED. Shelf the dispersion/correlation-premium class** for the SPY-timing use case. (A genuine correlation-RP harvest would require a *like-for-like* dispersion trade — short index vol / long single-name vol on the SAME constituent set — which is an options-execution strategy outside this backtester's cash-equity scope, not a COR-derived SPY throttle.)

## Files
`_disp_spread_probe.py` · `_disp_spread_diag.py` · `_disp_spread_detrend.py` · `_disp_spread_datacheck.py` (scratch, workspace root)
