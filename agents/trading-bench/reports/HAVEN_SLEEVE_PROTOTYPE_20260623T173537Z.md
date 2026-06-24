# Haven Sleeve Prototype (GLD/TLT) — Standalone Eval + eff-N Study

**Date:** 2026-06-23 (UTC stamp 20260623T173537Z)
**Assignment:** main (10:30 mgmt-check) — build the GLD/TLT haven sleeve flagged in the weekly tournament report as the next structural improvement (book is eff-N≈2.2, ~65% NASDAQ-tech beta concentration, all-red on a correlated risk-off day).
**Mission bar:** BEAT SPX ON RAW RETURN. Gates suspended. Honest measurement non-negotiable.
**Scratch/engine:** `_haven_sleeve_tests.py` (reuses `_allocator_blend_tests.build_sleeves/blend_portfolio/report_blend` verbatim). Result JSON: `reports/_haven_sleeve_result.json`. No protected/live files touched.

---

## TL;DR — VERDICT: PARTIAL PASS → SHELF-READY structural diversifier, NOT a paper-clock promotion under the current pure-raw-return bar.

A standalone GLD/TLT haven sleeve is a **genuine, independent diversifier** (corr to the levered-Nasdaq leg **−0.07**, to SPX **−0.15**) that **lifts the book's eff-N from 1.50 → 2.27** and, unlike the trend/CTA sleeves we closed this morning, **beats SPX raw at every tested weight** while cutting drawdown and lifting Sharpe. It earns its keep in 6 of 8 named risk-off windows (covid +5.4% vs SPY −19.4%; 2008 GFC +15.2% vs −36.9%; 2011 +18.6%; 2025 tariff +10.3%).

**But the honest catch is the same shape as the trend study:** every haven-augmented blend still **trails the validated 2-sleeve blend on raw return** (best 864% vs 990% full-period). Under a **pure raw-return mandate, the 2-sleeve wins the headline metric outright** — so I am **not** promoting the haven to the live paper clock. The haven buys a *frontier trade*: ~13pp of raw return (still +276pp over SPX) for +0.77 eff-N, +2.2pp shallower maxDD, and +0.03 Sharpe.

**This resolves the "next structural improvement" question with a concrete, parameter-pinned recommendation:** if/when Cyrus values de-concentration or risk-adjusted return over pure raw return, deploy the haven as a **fixed/capped 10% 3rd sleeve** (the eff-N→2.27 leg). Until then it is **shelf-ready crash-insurance**, dominated on the one metric that currently counts.

---

## What was built

A self-contained GLD/TLT "haven" sleeve = the two classic flight-to-safety assets combined into one monthly-rebalanced, intramonth-drifting, 2bps-cost return series. Three weighting schemes tested:
- **50/50** fixed,
- **60/40** TLT/GLD (bond-heavy classic),
- **inverse-vol parity** (63d trailing, past-only) — the canonical sleeve.

Then four questions, each on validated machinery:
1. **Standalone economics** on the haven's own deep window (2004-11 → 2026-06; GLD/TLT both exist), vs SPY buy-&-hold.
2. **Killer battery** — haven behavior in 8 named risk-off / regime windows (the test a hedge must pass).
3. **Correlation gate + eff-N** — does adding the haven actually de-concentrate the 2-sleeve book? (participation-ratio of the sleeve-return correlation matrix).
4. **3-sleeve blend** — does raw return still beat SPX with the haven added (naive inv-vol, capped 10/15/20/25%, fixed 10/15/20%)?

**Honest-measurement controls:** adjusted-close daily returns (GLD/TLT pay distributions → adjclose is correct); 2bps one-way cost on inter-asset turnover (same as the validated blend); OOS split 2018-12-31 (same constant); SPX (^GSPC) on the same traded path; weights set at month-open from PAST-only trailing vol (no lookahead).

---

## 1. Standalone haven — clean NEGATIVE on raw return (expected; it's insurance, not an engine)

Deep window **2004-11-19 → 2026-06-23** (5,430 days), vs SPY buy-&-hold raw **+824%**:

| Scheme | Full Sharpe | CAGR | maxDD | Raw return | OOS Sharpe | Beats SPX raw? |
|---|---:|---:|---:|---:|---:|:---:|
| 50/50 | 0.623 | 7.3% | −32.8% | **352%** | 0.610 | ❌ |
| 60/40 (TLT-heavy) | 0.578 | 6.5% | −35.1% | 289% | 0.481 | ❌ |
| **inverse-vol** | **0.658** | 7.3% | −30.4% | **357%** | **0.682** | ❌ |

**Read:** A GLD/TLT sleeve returns ~7%/yr at ~0.66 Sharpe — less than half SPX's raw return. **This is the correct, expected result:** a haven is a drawdown/decorrelation instrument, not a return engine. The standalone fails the raw-return bar by design. Inverse-vol is the best of the three (highest Sharpe, shallowest DD, best OOS) → use it as the sleeve.

---

## 2. Killer battery — the haven EARNS ITS KEEP in 6 of 8 risk-off windows

Inverse-vol haven vs SPY buy-&-hold, in named stress windows:

| Window | Haven return | SPY return | Haven maxDD | Hedge worked? |
|---|---:|---:|---:|:---:|
| 2020-Q1 covid crash | **+5.4%** | −19.4% | −13.2% | ✅ |
| 2008 GFC (Sep08–Mar09) | **+15.2%** | −36.9% | −9.8% | ✅ |
| 2011 debt-ceiling | **+18.6%** | −13.8% | −6.2% | ✅ |
| 2018-Q4 selloff | **+5.9%** | −13.5% | −2.5% | ✅ |
| 2025-Q1 tariff bear | **+10.3%** | −7.6% | −3.9% | ✅ |
| 2022-H1 bear | −10.7% | −20.0% | −16.0% | ⚠️ (lost less) |
| **2022 full year** | **−14.9%** | −18.2% | −25.1% | ❌ rate-shock |
| **2013 taper-tantrum** | **−10.2%** | +3.0% | −14.8% | ❌ rate-shock |

**Read — and the critical honest limitation:** the haven is a true hedge in *equity-led* / flight-to-quality stress (covid, GFC, 2011, 2018-Q4, 2025) where money flees INTO bonds and gold. It **FAILS in rate-shock regimes** (2022, 2013 taper-tantrum) where rising real rates hit **both** bonds AND gold simultaneously — exactly the years equities also fall, so the hedge is absent when correlated risk hits via the rate channel. **This is the haven's Achilles heel and must not be papered over:** it does not protect against an inflation/rate-driven drawdown, which is a live macro risk. It protects against growth-scare / liquidity-crisis drawdowns, which are a *different* and also-live risk.

---

## 3. Correlation gate + eff-N — the haven is the genuinely independent leg (PASSES)

Daily-return correlation of the inverse-vol haven sleeve (full common window 2010-02 → 2026-06):

| Haven vs… | corr |
|---|---:|
| **TQQQ vol-target leg** | **−0.074** |
| sector-rotation leg | +0.379 |
| **2-sleeve blend** | +0.171 |
| **SPX** | **−0.145** |

**Effective number of independent bets (participation ratio of the correlation matrix):**

| Book | eff-N |
|---|---:|
| 2-leg (TQQQ vol-target + sector rotation) | **1.495** |
| 3-leg (+ haven) | **2.265** |

3-leg correlation matrix:
```
              TQQQ-leg   ROT-leg   HAVEN
TQQQ-leg        1.000     0.581    -0.074
ROT-leg         0.581     1.000     0.379
HAVEN          -0.074     0.379     1.000
```

**Read:** The current 2-sleeve book is effectively **~1.5 independent bets** — the two equity sleeves are 0.58-correlated (both long-equity-biased, the concentration the tournament report flagged). Adding the haven lifts eff-N to **2.27**, a **+51%** increase in independent bets. The haven's near-zero corr to the levered-Nasdaq leg (−0.07) and negative corr to SPX (−0.15) is exactly the de-concentration the report asked for. **The correlation gate PASSES decisively.**

**The honest caveat on the corr gate (don't oversell it):** the haven's correlation to the blend **rises in stress** — covid +0.525, 2025 tariff +0.614, 2022 bear +0.368. So in the *fastest* equity crashes the haven is less independent than its full-sample −0.07 suggests (gold sometimes gets sold for liquidity early in a panic before the flight-to-quality bid). The full-sample eff-N gain is real and structural; the *stress-conditional* hedge is good but not perfect.

---

## 4. 3-sleeve blend — BEATS SPX raw at every weight, but TRAILS the 2-sleeve (the frontier trade)

All on the full common window **2010-02-12 → 2026-06-23**, inverse-vol 63d, 2bps. **SPX raw = +588%. 2-sleeve baseline = +990%.**

| Variant | Raw ret | Sharpe | OOS Sharpe | maxDD | OOS raw | Beats SPX raw? | Beats 2-sleeve raw? |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| **2-sleeve baseline** | **990%** | 1.005 | 1.127 | −23.9% | 270% | ✅ | — |
| haven fixed/cap 10% | 864% | 1.032 | 1.149 | −21.7% | 246% | ✅ | ❌ |
| haven fixed/cap 15% | 806% | 1.045 | 1.158 | −21.6% | 235% | ✅ | ❌ |
| haven fixed/cap 20% | 750% | 1.056 | 1.166 | −21.6% | 224% | ✅ | ❌ |
| haven cap 25% | 698% | 1.066 | 1.173 | −21.5% | 213% | ✅ | ❌ |
| naive inv-vol (≈45% haven) | 595% | 1.122 | 1.189 | −20.4% | 182% | ✅ (barely) | ❌ |

**Read — the decisive contrast with this morning's trend study:**
- **Trend/CTA sleeves LOST to SPX raw** (3-sleeve+SYN_TREND = 280% < SPX 595%) because they have ~zero long-run drift and inv-vol piled 40-60% into them, starving the return engine.
- **The haven sleeve BEATS SPX raw at every weight** (698-864%) because GLD/TLT have *positive* long-run drift (~7%/yr) — so even a meaningful allocation stays well above SPX. This is a materially better diversifier than trend for a raw-return mandate.
- **The naive inv-vol over-allocates** (~45% to the haven), dropping raw return to 595% (barely > SPX) — same over-allocation pathology as the trend study. **The fix is the same: cap the haven.** A 10% cap holds raw return at 864% (+276pp over SPX) while still delivering the eff-N de-concentration.
- **BUT every haven variant trails the 2-sleeve on raw return** (best 864% < 990%). Under a **pure raw-return mandate the 2-sleeve wins outright.** The haven costs ~13pp of raw return for +0.77 eff-N, +2.2pp shallower maxDD, +0.03 Sharpe, +0.02 OOS Sharpe.

---

## 5. Redundancy check — the rotation leg ALREADY holds havens 55% of the time (but conditionally)

The sector-rotation leg ranks SPY/QQQ/GLD/TLT by 3-month momentum and holds the top-2. Re-deriving its monthly picks (195 months, 2010+):

| ROT leg holds… | months | % |
|---|---:|---:|
| SPY | 115 | 59% |
| QQQ | 127 | 65% |
| GLD | 83 | 43% |
| TLT | 65 | 33% |
| **≥1 haven (GLD or TLT)** | 108 | **55%** |
| **both havens** | 40 | **21%** |

**Read — the most important honest nuance in this whole study:** the book is **not** haven-free today. The rot leg already holds a haven 55% of months. So a standalone haven sleeve is **partially redundant**. The structural value of a *dedicated* sleeve is that it holds the insurance **unconditionally and continuously**, whereas the rot leg holds havens **momentum-conditionally** — which means it is (a) **late to the haven in a fast crash** (3-month momentum hasn't flipped to GLD/TLT yet when the equity leg is already falling), and (b) **fully out of havens during equity ramps** when a permanent insurance allocation would still be carried. The eff-N gain (1.50→2.27) is precisely the value of converting that conditional, lagged exposure into an always-on independent leg. **This is real but incremental** — the marginal de-concentration is smaller than it would be if the book held zero havens today.

---

## Disposition & recommendation

**PARTIAL PASS.** The haven sleeve clears the structural-diversifier gate (eff-N 1.50→2.27, corr −0.07 to the levered leg, beats SPX raw at every weight, lifts Sharpe + cuts maxDD, hedges 6/8 risk-off windows). It does **not** clear the *pure raw-return* bar as a replacement: every variant trails the 2-sleeve on raw return.

**I am NOT wiring it into the live paper tournament right now**, because under the current mission (BEAT SPX ON RAW RETURN, maximize profit) the 2-sleeve blend strictly dominates the headline metric, and the redundancy check shows the book already carries conditional haven exposure. Wiring in a strictly-dominated sleeve would dilute the live book's raw return for a benefit (de-concentration) the current mandate doesn't price.

**Concrete shelf-ready spec (pre-registered, deploy on a mandate shift):** if Cyrus ever (a) reinstates a risk-adjusted bar, (b) wants the book's eff-N raised / tail-risk cut, or (c) the levered sleeves hit a capital-efficiency / drawdown wall — deploy the haven as a **fixed 10% 3rd sleeve, inverse-vol-weighted internally (GLD/TLT), monthly rebalance, 2bps**. That operating point: raw **864%** (still +276pp over SPX), Sharpe **1.032**, OOS **1.149**, maxDD **−21.7%**, **eff-N 2.27**. Engine is already written and validated; promotion would be a ~1-day wiring job mirroring the existing `allocator_blend` (the 3-sleeve `blend_portfolio` path already runs).

**What would make this a full PASS (promote-to-paper):** any ONE of — the mandate becomes risk-adjusted (then the +0.03-0.05 Sharpe / −2pp maxDD / +0.77 eff-N is the win); OR the haven is shown to protect a *rate-shock* drawdown too (it currently does not — 2022/2013 are the failure mode; a TIPS or commodity-trend addition could patch that hole but expands scope); OR the levered-Nasdaq engine's drawdown becomes the binding constraint on go-live sizing (then trading raw return for −2pp maxDD is rational).

**Limitations flagged honestly:** (1) fails in rate-shock regimes (2022/2013 — bonds AND gold both fall); (2) stress-conditional correlation to the blend rises to +0.5–0.6 (less independent in fast crashes than the −0.07 full-sample corr implies); (3) partially redundant with the rot leg's existing 55%-of-months conditional haven exposure; (4) full history starts 2004 (GLD inception) — no pre-2004 / 1970s-stagflation read on how GLD/TLT co-behave in sustained high inflation.

---

*Numbers cross-checked console↔JSON. Scratch: `_haven_sleeve_tests.py`, `_rot_picks.py`, `reports/_haven_sleeve_result.json`. No protected files / crontab / paper clock touched.*
