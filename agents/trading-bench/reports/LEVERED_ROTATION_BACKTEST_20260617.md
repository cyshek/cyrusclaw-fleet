# Levered Rotation with Trend Gate — Backtest Report
**Date:** 2026-06-17  
**Author:** trading-bench subagent  
**Script:** `/tmp/levered_rotation_backtest.py`  
**Status:** PAPER/RESEARCH ONLY — never live

---

## 1. Design & Motivation

### Why Rotation?
The live `leveraged_long_trend_paper` strategy holds a single ETF (TQQQ, 3x QQQ) trend-gated and vol-targeted. The hypothesis tested here: **can rotating among similar broad-cap 3x ETFs (TQQQ/UPRO/SPXL) add alpha versus holding just TQQQ?**

Rational for the universe choice:
- **TQQQ** (3× QQQ) — Nasdaq-100 exposure, highest vol/return in bull markets
- **UPRO** (3× SPY) — S&P 500 exposure, slightly lower vol than TQQQ
- **SPXL** (3× SPX) — effectively same underlying as UPRO (another ProShares/Direxion S&P product); included as diversity
- **Rejected:** SOXL/TECL (sector 3× ETFs) — too concentrated, catastrophic 2022 drawdown; TECS/SDOW (inverse) — off-mission for a trend-following system

### Design Specification
- **Universe:** TQQQ (→ QQQ gate), UPRO (→ SPY gate), SPXL (→ SPY gate)
- **Trend gate:** underlying index must be above its 200-day SMA to qualify
- **Rotation signal:** trailing 252-bar momentum on the ETF itself (higher = better)
- **Rebalance cadence:** monthly (first trading day of each calendar month)
- **Cash:** full cash (0% return) when no ETF qualifies
- **Vol-targeting:** `weight = min(TARGET_VOL / realized_vol(20d), 1.0)` where `TARGET_VOL = 0.25`
- **Transaction cost:** 2 bps per side on absolute weight change (abs-weight model, more conservative than flat per-switch for continuous sizing)
- **Start date:** 2010-02-11 (TQQQ inception — binding constraint)
- **OOS split:** train end = 2017-12-31 / test start = 2018-01-01

### Two Scenarios
- **Scenario A (top-1):** Hold only the single highest-momentum qualifying ETF, vol-targeted to 25% ann vol, capped at 100% weight
- **Scenario B (equal-weight):** Hold all qualifying ETFs in equal weight (1/n), each independently vol-targeted to 25% ann vol × (1/n) base

### Lookahead Contract
Identical to `leveraged_long_trend_paper`:
- Signal computed from closes through day D (inclusive)
- Position held over day D+1
- Realized vol computed from ETF returns ending on or before day D
- No future data in any signal calculation

---

## 2. Data

| Symbol | Bars | First Bar | Last Bar | Role |
|--------|------|-----------|----------|------|
| TQQQ   | 4,105 | 2010-02-11 | 2026-06-08 | 3× QQQ sleeve |
| UPRO   | 4,264 | 2009-06-25 | 2026-06-08 | 3× SPY sleeve |
| SPXL   | 4,423 | 2008-11-05 | 2026-06-08 | 3× SPX sleeve |
| QQQ    | 6,854 | 1999-03-10 | 2026-06-08 | TQQQ underlying/gate |
| SPY    | 8,396 | 1993-01-29 | 2026-06-08 | UPRO+SPXL underlying/gate |
| ^GSPC  | 14,229 | 1970-01-02 | 2026-06-08 | Benchmark |

All data: Yahoo v8 chart API, `adjclose` (split+dividend adjusted). All from disk cache.

**Trading calendar:** 4,105 days (2010-02-11 → 2026-06-08), TQQQ-limited.  
**Monthly rebalance decisions:** 196

---

## 3. Full-Period Results (2010-02-11 → 2026-06-08, ~16.3 years)

| Strategy | Total Return | CAGR | Max DD | Ann Vol | Sharpe | % In Market |
|----------|-------------|------|--------|---------|--------|-------------|
| **Scenario A** (top-1 rotation) | **1,342%** | **17.8%** | **-41.9%** | **29.0%** | **0.712** | 83.8% |
| **Scenario B** (equal-weight) | **1,401%** | **18.1%** | **-38.3%** | **27.7%** | **0.740** | 83.8% |
| SPX benchmark | 587% | 12.6% | -33.9% | 17.2% | 0.773 | 100% |
| **TQQQ vol-target baseline** *(live strategy)* | **~1,881%** | **~21.4%** | **~-52%** | — | **0.842** | — |

### ETF Allocation Breakdown (Scenario A — top-1)
| ETF | Holding Days | % of Period |
|-----|-------------|-------------|
| TQQQ | 2,455 | 59.8% |
| UPRO | 527 | 12.8% |
| SPXL | 457 | 11.1% |
| Cash | 665 | 16.2% |

TQQQ dominates the top-1 selection — UPRO/SPXL offer little differentiation since they track the same underlying (SPY). The rotation mostly toggles between TQQQ and cash with occasional UPRO/SPXL stints.

### ETF Allocation Breakdown (Scenario B — equal-weight)
| ETF | Holding Days (w>0) | % of Period |
|-----|-------------------|-------------|
| TQQQ | 3,319 | 80.9% |
| UPRO | 3,295 | 80.3% |
| SPXL | 3,295 | 80.3% |
| Cash | 665 | 16.2% |

All three ETFs are in market simultaneously the vast majority of the time (same SPY/QQQ gate behavior). Avg gross exposure in-market: 0.705.

---

## 4. OOS Results (2018-01-01 → 2026-06-08, ~8.4 years)

| Strategy | Total Return | CAGR | Max DD | Ann Vol | Sharpe |
|----------|-------------|------|--------|---------|--------|
| **Scenario A** (top-1 rotation) | **165%** | **12.3%** | **-41.9%** | **30.4%** | **0.535** |
| **Scenario B** (equal-weight) | **170%** | **12.6%** | **-38.3%** | **29.0%** | **0.555** |
| SPX benchmark | 175% | 12.8% | -33.9% | 19.3% | 0.719 |
| **TQQQ vol-target baseline** *(live strategy)* | **~354%** | **~18.5%** | — | — | **~0.842** |

### Critical OOS finding
Both rotation scenarios **fail to beat SPX in OOS**:
- Scenario A: 165% vs SPX 175% → **underperforms by ~10 pp**
- Scenario B: 170% vs SPX 175% → **underperforms by ~5 pp**

Both scenarios **massively underperform the existing TQQQ vol-target baseline** in OOS:
- Rotation A: 165% vs baseline 354% → **189 pp behind**
- Rotation B: 170% vs baseline 354% → **184 pp behind**

OOS Sharpe:
- Rotation A: 0.535, Rotation B: 0.555 vs SPX 0.719 → worse risk-adjusted returns than a passive SPX index in OOS
- Baseline: ~0.842 (OOS estimate from existing reporting)

---

## 5. Analysis: Why Does Rotation Underperform?

### 5a. UPRO and SPXL are redundant
UPRO and SPXL both track the S&P 500 × 3. Their underlyings for the SMA-200 gate are both SPY. In Scenario B they act as a 2/3 dilution of TQQQ with 1/3 being essentially duplicated S&P exposure. In Scenario A, momentum typically picks TQQQ during Nasdaq bull runs (which dominate the data since 2010), making UPRO/SPXL effectively dead weight that only gets selected when Nasdaq underperforms — which is exactly when leveraged ETFs produce their worst risk-adjusted returns.

### 5b. Monthly rebalance is a return drag
Monthly rebalance means the strategy holds the old top-1 for up to ~22 days after it may have been dethroned. The TQQQ vol-target strategy implicitly rebalances its vol-scaling daily (the vol-target weight changes every day), which tunes exposure more precisely.

### 5c. Vol-target interaction with equal weighting
In Scenario B, the vol-target is applied to a 1/3 base weight per ETF. Since all three ETFs have similar (high) realized vol, each ETF's scaled weight ≈ `0.25 / rvol × 0.333`. This produces total gross exposure ≈ `0.25 / rvol` when all three qualify — effectively the same aggregate exposure as the TQQQ-only strategy but split across three instruments. The diversification benefit (lower portfolio vol) is real (-1.4 pp vol vs Scenario A) but not enough to compensate for the lower individual return profile of UPRO/SPXL vs TQQQ in bull markets.

### 5d. TQQQ provides the alpha; diluting it hurts
The TQQQ vol-target strategy extracts the Nasdaq-100 leverage premium. QQQ has historically outperformed SPY on a returns basis, and therefore TQQQ > UPRO/SPXL in most bull-market environments. Rotating into UPRO/SPXL means holding lower-return leverage when SPY > QQQ trends — which adds vol without commensurate return.

### 5e. OOS 2022 performance
The 2022 bear market is the key OOS stress test. Both rotation strategies suffered -41.9% / -38.3% max drawdown OOS. The trend gate (SMA-200) on the underlying did protect against the worst of the crash, but when both SPY and QQQ are below SMA-200 simultaneously (as in 2022), both strategies sit in cash — no differentiation possible. The TQQQ-only baseline avoids additional drawdown from SPXL/UPRO exposure during early-bear transitions when sometimes only one underlying crosses below SMA-200.

---

## 6. Comparison to Existing Strategy

| Metric | Rotation A | Rotation B | TQQQ Vol-Target (live) |
|--------|-----------|-----------|----------------------|
| **OOS beat SPX?** | ❌ No (165% vs 175%) | ❌ No (170% vs 175%) | ✅ Yes (354% vs 175%) |
| **OOS Sharpe > SPX?** | ❌ No (0.535 vs 0.719) | ❌ No (0.555 vs 0.719) | ✅ Yes (~0.842 vs 0.719) |
| **Full-period beat SPX raw?** | ✅ Yes (1342% vs 587%) | ✅ Yes (1401% vs 587%) | ✅ Yes (1881% vs 587%) |
| **Full-period Sharpe vs baseline** | ❌ 0.712 < 0.842 | ❌ 0.740 < 0.842 | — |
| **Max DD vs baseline** | ✅ Better (-41.9% vs -52%) | ✅ Better (-38.3% vs -52%) | — |
| **OOS total return vs baseline** | ❌ 165% vs 354% | ❌ 170% vs 354% | — |

The rotation strategies do reduce max drawdown vs the TQQQ-only baseline (a genuine benefit — -38 to -42% vs -52%). However, this comes at an enormous cost to returns and Sharpe ratio in OOS. The existing strategy **dominates on every metric that matters to the mission** (beat SPX raw OOS).

---

## 7. Is Rotation Worth Adding as a Second Strategy?

**Short answer: No, not as designed.**

**Diversification argument:**
- Lower correlation to the TQQQ-only baseline is likely (different ETF mix) — but the OOS result shows this doesn't help: both strategies underperform SPX in OOS
- Adding a second strategy that underperforms SPX OOS means any portfolio blending of the two would drag returns toward SPX-underperformance, not add alpha

**The max-DD improvement argument:**
- Scenario B has better max DD (-38% vs -52% for baseline) — this IS real
- But -38% max DD is still far worse than SPX itself (-33.9%) so it doesn't meet a meaningful risk bar
- The TQQQ vol-target baseline already *attempts* to solve the DD problem via its vol-sizing; this rotation offers a different (and in OOS, worse) path to the same goal

**Would a better rotation universe help?**
- Adding *inverse* ETFs (SQQQ) as a "short" leg would require trend-reversal prediction, not just a gate
- Adding *different* underlying sectors (SOXL, TECL) reintroduces the concentration/sector-cyclicality problem
- The core issue is that all three broad-cap 3× ETFs are highly correlated — true diversification isn't achievable in this universe

**Possible improvement directions (not backtested here):**
1. **Daily rebalance instead of monthly** — aligns with the vol-target frequency, may reduce lag
2. **Add a VIX gate** (as in leveraged_long_trend) — the baseline already does this; could compress the 2022 drawdown further
3. **Different universe:** add a 2× alternative (SSO/QLD) for lower-vol years alongside 3× — but this changes the leverage thesis

---

## 8. Methodology Notes

- **Cash return:** 0% (conservative; T-bill adds ~25-50 bps/yr, immaterial to the verdict)
- **Cost model:** abs-weight change × 2 bps per side (more conservative than flat per-switch for continuous vol-targeting)
- **Survivorship bias:** inherent — TQQQ/UPRO/SPXL survived because the indices they track went up. This bias is present in both the rotation and the baseline; it doesn't change the *relative* verdict between them
- **Lookahead:** confirmed clean — all decisions use data with date ≤ decision day; the vol estimate and SMA signal are computed from returns/closes ending on the decision day, not the held day
- **Tests:** `python3 -m pytest tests/ -x -q` → **626 passed, 1 skipped** (all clean, no regression introduced)

---

## 9. Verdict

> **Both rotation scenarios FAIL to beat SPX raw return OOS, and both are dramatically inferior to the existing `leveraged_long_trend_paper` strategy on every mission-relevant metric. The max-DD improvement is real but insufficient to justify adding this as a second strategy.**

The fundamental problem: TQQQ/UPRO/SPXL are too correlated to provide meaningful diversification, and UPRO/SPXL reduce returns during Nasdaq bull markets without commensurate risk reduction. The baseline TQQQ-only strategy with daily vol-targeting is the tighter, more return-efficient implementation of the same general idea.

**Recommendation:** 
- **Do NOT promote either rotation scenario as a second strategy**
- The TQQQ vol-target baseline (`leveraged_long_trend_paper`) remains the only strategy beating SPX OOS
- If rotation-diversity is desired, the better path is: (1) improve the existing strategy's OOS drawdown via VIX gate tuning, or (2) explore fundamentally different alpha sources (momentum on single stocks, earnings drift) rather than rotation within highly-correlated leverage products

---

## RESULT

**LEVERED ROTATION FAILS: both rotation scenarios (top-1 momentum and equal-weight) underperform SPX raw return OOS (165-170% vs SPX 175%), are dramatically inferior to the existing TQQQ vol-target baseline (165-170% vs 354% OOS), and offer no net value as a second strategy despite modestly improved max drawdown (-38-42% vs baseline -52%).**
