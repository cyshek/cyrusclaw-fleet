# H1 CROSS-ASSET CARRY — COMMODITY-ROLL-YIELD LEG + COMBINED SLEEVE (feasibility / kill-test)

**Stamp:** 20260623T193840Z · **Engine:** `_h1_carry_commodity_combined_tests.py` · **Result JSON:** `reports/_h1_carry_commodity_combined_result.json`
**Hypothesis source:** `reports/LITERATURE_HYPOTHESES_20260623T185057Z.md` §2 H1 + §5 sketch; bond-leg report `reports/H1_CARRY_BONDLEG_20260623T191733Z.md` §9 ("what the commodity leg must add").
**Verdict: ❌ CLOSE the commodity leg — it is the DIRTY-PROXY outcome main warned about.** The commodity-roll-yield "carry" signal **loses to its own no-signal EW control by −77.5pp OOS** (the make-or-break dirty-proxy test, **k2 FAIL**), and its entire apparent edge is a **post-2018 regime artifact**: it has a **negative in-sample Sharpe on every split convention** (IS Sharpe −0.44, full-period Sharpe **−0.01 ≈ 0**) and only turns positive out-of-sample. The combined bond+commodity sleeve's gaudy OOS Sharpe (0.967) is real diversification *math* riding on a non-robust leg — but adding the commodity leg **LOWERS the combined full-period Sharpe to 0.268, well below the bond leg standing alone (0.578)**. The honest conclusion: **the bond leg is the only real carry signal here; the commodity leg is fund-mechanics/regime noise and must NOT be promoted.** A combined sleeve does not clear 0.5 on any trustworthy (full-period) basis.

---

## TL;DR — k1–k5 (OOS = 2019-01-01+, net 2 bps, OOS_SPLIT 2018-12-31, matches bond leg)

| # | Criterion | Result | Number |
|---|---|---|---|
| **k1** | Commodity leg OOS Sharpe ≳ 0.4 | ⚠️ **PASS (but hollow)** | **0.708** — *inflated by vol-suppression (cash-parking); see k2 + IS guard* |
| **k2** | Commodity leg BEATS its EW control OOS net (**dirty-proxy make-or-break**) | ❌ **FAIL** | signal **+39.0%** vs EW **+116.5%** → **Δtot −77.5pp** (loses badly) |
| **k3** | Commodity leg BEATS static-long-optimized OOS (timing adds over beta) | ✅ marginal PASS | Δtot **+4.3pp**, ΔSharpe +0.285 (timing avoids *some* contango bleed) |
| **k4** | corr(commodity leg, bond leg) ≤ 0.3 | ✅ **PASS** | **−0.28** (genuinely uncorrelated to the bond leg) |
| **k5** | **Combined sleeve OOS Sharpe ≥ 0.5 + low book corr** | ⚠️ **OOS-only mirage** | combined **OOS 0.967** but **FULL 0.268** (< bond-leg-alone 0.578); corr→SPY 0.25, →TQQQ 0.16 |

**Overall: CLOSE.** k2 — the one test specifically designed to catch the dirty commodity-ETF proxy — **fails decisively**. The commodity carry signal cannot beat a dumb equal-weight hold of the very same ETFs out-of-sample. Combined with a **negative in-sample Sharpe on every split**, this is a clean (if nuanced) negative: the commodity leg is **not a trustworthy orthogonal return source**. The bond leg remains the only real signal in the H1 carry family, and it does not clear 0.5 alone.

---

## 1. What was built (methodology — PIT / lag / cost)

A self-contained engine (`_h1_carry_commodity_combined_tests.py`, workspace root). The **commodity + combined core imports ONLY `_h1_carry_bondleg_tests`** (which imports only `runner/fred_cache`), reusing its data-loading, `Panel`, `sharpe`/`metrics`/`backtest_weights`/`monthly_returns`/`corr`, `OOS_SPLIT`, and **`run_one` for the bond-leg daily path** — so the two legs are consistent to the decimal. The **allocator-frontier section additionally imports `_allocator_blend_tests`** (root-level, **not** protected) *lazily* to reproduce the live 2-sleeve daily paths exactly (read-only; it only computes return streams). `runner/*.py` (beyond `fred_cache`), `strategies*/`, cron, `*.db`, broker/clock/allocator were **not** written.

**The signal — commodity roll-yield carry (framing A, spread-as-signal/timing):**
On a single complex, the carry/roll premium shows up as the **OPTIMIZED/DEFERRED-roll ETF out-performing the NAIVE front-month ETF when the curve is backwardated, under-performing when contangoed**. So the **trailing return spread (optimized − naive)** over a lookback window IS the curve-shape signal:
- At each **month-end T**, per complex compute `spread = ret_opt(T−lb→T) − ret_naive(T−lb→T)` on data **with index ≤ T** (PIT-safe).
- `spread > 0` (backwardated / deferred-roll winning) ⇒ **hold the OPTIMIZED-roll product**, vol-targeted to a modest budget; `spread ≤ 0` (contangoed) ⇒ **flat / sit in SHY** (cash anchor). i.e. curve shape **times** exposure.
- Complexes combined **equal-risk-weight** (each vol-targeted to the same per-leg budget = inverse-vol across legs).
- **Vol-target each active complex** to 9% annual (20-day realized vol of the optimized ETF), **cap at 1.0×** (never levered — a diversifier sleeve). Gross capped at 1.0.

**Optimized-vs-naive pairs tested (same complex):**
- **crude:** `USL` (12-mo laddered) or `DBO` (optimized-roll) **vs** `USO` (front WTI)
- **broad:** `DBC` (optimized broad) or `USCI` (deferred rules-based) **vs** `GSG` (front GSCI) or `DJP`
- **nat-gas:** `UNL` (12-mo laddered) **vs** `UNG` (front nat-gas)

**Primary config (economically-motivated default, NOT tuned):** `deep_crude_broad` set = {crude `USL` vs `USO`, broad `DBC` vs `GSG`}, **126-day** roll-yield lookback, **9%** per-leg vol target, threshold 0, **2 bps** round-trip.

**Two panels to preserve history (the `Panel` calendar-intersection gotcha):** including 2010-start ETFs (`USCI`/`UNL`) would truncate *every* series to 2010. So a **DEEP panel** (USO/USL/DBO/DBC/GSG/DJP + SHY, **4,663 days 2007-12-06 → 2026-06-22, 223 rebalances**) carries crude+broad complexes back to 2008; a **FULL panel** (all + SHY, 2010-08-10 →, 191 rebalances) is used only for sets that include the 2010+ instruments. Any config leaning on USCI/UNL is flagged shallower-OOS.

**Anti-lookahead mechanics (inherited from the bond-leg engine, identical):** signal on data ≤ dates[T]; weights effective at **T+1** (1-day lag); held constant daily, marked on **adjclose** returns; freshly-traded weights do **not** capture the trade-day's already-realized return. Cost = `(bps/1e4)·Σ|w_new−w_old|`. **Sharpe = (mean/std)·√252, ddof=1, continuous concatenated series — never median-of-windows.** OOS split **2018-12-31** (matches bond leg).

---

## 2. The signal vs its two controls — FULL / IS / OOS (net 2 bps)

| Series | FULL Sharpe | FULL tot | FULL maxDD | **IS≤2018 Sharpe** | **IS tot** | **OOS Sharpe** | **OOS tot** |
|---|---|---|---|---|---|---|---|
| **Commodity carry signal** (primary) | **−0.014** | −6.5% | −41.4% | **−0.440** | **−32.7%** | **0.708** | **+39.0%** |
| **EW control** (USL/USO/DBC/GSG, no signal) | 0.031 | — | — | — | — | **0.509** | **+116.5%** |
| Static-long-optimized control (always-hold USL+DBC vt) | −0.025 | — | — | — | — | 0.423 | +34.8% |

**Reading it (the decisive contrast with the bond leg):**
- **The signal LOST money in-sample** (IS Sharpe −0.44, −32.7% over 2008-2018) and has a **full-period Sharpe of essentially zero/negative (−0.014)**. The OOS Sharpe of +0.71 is **not** a stable property — it is a post-2018 regime in which oil curves backwardated again (see §5/§6). The bond leg, by contrast, had IS 0.633 / OOS 0.434 — *consistent and positive throughout.* This commodity leg is the opposite profile.
- **The OOS Sharpe is hollow / vol-suppression-driven.** The signal's OOS *total return* (+39.0%) is **far below** the EW control's (+116.5%); the only reason its OOS *Sharpe* (0.708) edges the EW's (0.509) is that it sits in cash ~27% of the time and runs at ~6.5% vol (low denominator). **A higher Sharpe with one-third the return, achieved by being out of the market, is not an edge** — it is risk reduction you could get more cheaply by just holding less of the EW basket.
- **k2 is the ballgame and it fails.** The whole point of the EW-of-same-instruments control (per the BAB/fundamentals lesson) is to catch exactly this: a long-commodity sleeve dressed up as "carry timing." On net total return the carry signal **underperforms a dumb monthly-rebalanced EW hold of the identical four ETFs by −77.5pp OOS**. The "signal" is not harvesting a curve-shape premium over the dumb baseline — it is **leaving return on the table** by going to cash, and what return it does make is long-commodity beta.

---

## 3. Lookahead canary — honest ≠ cheat (no leakage)

A deliberately-cheating variant peeks at the roll-yield spread **~1 month FORWARD** instead of as-of month-end.

| Path | FULL Sharpe |
|---|---|
| **Honest** (spread as-of ≤ month-end, +1-day trade lag) | **−0.014** |
| Cheat (+1mo-forward spread) | −0.294 |

**Paths differ (Δ 0.28) → no leakage.** (As with the bond leg, the cheat path is *worse* — a forward-peeked spread is a noisier instruction because commodity curves whipsaw month-to-month. Reassuring on leakage; but this canary only proves the pipeline isn't *secretly* cheating — it does **not** rescue a signal whose honest full Sharpe is ≈ 0.)

---

## 4. Cost grid — monotonic, NOT the killer (the signal is the problem, not frictions)

Primary signal, turnover **33.6%/rebal** (notably higher than the bond leg's 13.4% — the spread-timing churns the cash↔commodity switch):

| Round-trip bps | FULL Sharpe | OOS Sharpe | FULL total |
|---|---|---|---|
| 0 | −0.003 | 0.719 | −5.1% |
| 1 | −0.008 | 0.714 | −5.8% |
| 2 | −0.014 | 0.708 | −6.5% |
| 5 | −0.030 | 0.691 | −8.5% |

Cost is monotonic and modest (5 bps shaves OOS Sharpe 0.017) — these ETFs are liquid. **Cost is NOT the killer here** (I flagged it as plausible up front given the churn, but the data says no). Even at **0 bps** the full Sharpe is still ≈ 0 (−0.003) and the OOS edge still loses to the EW control on total return. The lane dies on **raw signal + the dirty-proxy control**, not on frictions. Breakeven vs the EW control is **never reached** — the signal loses to EW on net total return at *every* cost level (a return-deficit, not a cost-deficit).

---

## 5. Robustness sweep — a "broad plateau" that is actually a SHARED REGIME ARTIFACT (the honest knock)

36 configs: complex-set ∈ {`deep_crude_broad`, `deep_crude_broad_dbo`, `all3_USL_DBC_UNL`, `all3_DBO_DBC_UNL`, `broad_only_DBC`, `all3_USL_USCI_UNL`} × lookback ∈ {63, 126, 252}d × vol-target ∈ {8%, 10%}. All net 2 bps.

**Aggregate OOS Sharpe min/median/max = 0.133 / 0.703 / 0.912; 24/36 clear 0.5, 36/36 OOS-positive.**

At first glance this looks like the *good* kind of robustness (a broad positive plateau, no knife-edge — the opposite of BAB's negative-littered surface). **But this reading is a trap, and the honest interpretation is the reverse:**

- **The sweep only reports OOS Sharpe.** *Every one of these 36 configs shares the same IS→OOS regime split* — they all lost money in-sample and only "work" post-2018 (the split-robustness table in §6 shows this is a property of the *signal family*, not one config). So "24/36 clear OOS 0.5" is **not** evidence the signal is robust across knobs — it is evidence the **entire family is dependent on the single post-2018 commodity regime.** A broad plateau of configs that all fail in-sample is a broad plateau of the *same* fragility, not 36 independent confirmations.
- The plateau is **not** a knife-edge cherry-pick (good), but it is also **not** a genuine cross-knob robustness pass (the OOS window is the same favorable regime for all). The right summary: *regime-robust within 2019–2026, regime-fragile before it* — which for a forward-looking promotion decision is a **fail**, because it implicitly bets the post-2018 backwardation regime persists.

---

## 6. The decisive honesty check — IS/OOS split-robustness + year-by-year (this is why it's CLOSE)

**Commodity leg, four OOS split conventions** (the bond-leg report ran the analogous continuity check):

| OOS split | **IS Sharpe** | IS total | OOS Sharpe | OOS total |
|---|---|---|---|---|
| 2014-12-31 | **−0.635** | −29.4% | +0.386 | +32.5% |
| 2016-12-31 | **−0.504** | −31.4% | +0.534 | +36.4% |
| 2018-12-31 (primary) | **−0.440** | −32.7% | +0.708 | +39.0% |
| 2020-12-31 | **−0.298** | −29.1% | +1.003 | +31.9% |

**The IS Sharpe is NEGATIVE on every split**, and the OOS Sharpe *mechanically rises* as the split moves later (the bad years 2008/2014/2015 get absorbed into IS). This is the signature of a **regime artifact**, not a robust edge — a walk-forward trader standing at *any* of these split dates would have just lived through a multi-year drawdown and (correctly) doubted the strategy.

**Year-by-year commodity-leg total return** (where the edge lives):

| | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ret % | **−13.1** | +4.9 | −3.9 | +2.5 | −3.4 | −2.7 | **−16.5** | **−11.2** | +9.4 | +0.7 | −2.5 | **+12.7** | −6.5 | +5.6 | −0.6 | +4.9 | +5.4 | +5.7 | +7.7 |

**Lost money in 8 of 11 IS years (2008–2018); made money in 7 of 8 OOS years (2019–2026).** The "edge" is concentrated entirely in the post-2018 period when WTI backwardation returned (shale capital discipline, demand recovery, 2021–22 supply tightness). That is a **real economic regime** — but it is *one* regime, and the signal was a money-loser through the entire prior decade of structural contango. **You cannot promote a signal on the strength of the one regime it happened to work in**, especially when it fails the dumb-EW control even within that regime.

---

## 7. Stress windows — the signal's risk-reduction is real but it's just "hold less"

Total return over each window (signal vs EW vs static-optimized):

| Window | n | **Signal tot** | Signal Sharpe | EW tot | Static-opt tot | Read |
|---|---|---|---|---|---|---|
| 2008-09 GFC | 252 | −9.1% | −1.10 | **−39.2%** | −9.1% | signal/static cut exposure → lost ~30pp less than dumb EW (the contango/curve signal *did* dodge the worst) |
| 2020 covid | 104 | −8.9% | −1.34 | **−36.7%** | −10.5% | same — going-to-cash on negative roll-yield avoided the oil crash (negative WTI futures) |
| 2022 rate-shock | 251 | −0.6% | −0.10 | **+25.3%** | +10.2% | **the tell:** 2022 was a *commodity bull* (war, inflation); the signal sat in cash much of it and **missed +26pp** the EW basket captured |

**Reading:** the signal's crisis behavior (−9% in 2008/2020 vs EW −37/−39%) confirms it *is* doing curve-shape risk-reduction — it dodges contango blowups. **But 2022 exposes the cost:** in a genuine commodity *bull*, the cash-parking left **+26pp on the table** vs the dumb EW hold. Net across the full sample, the avoided-contango wins do **not** outweigh the missed-bull and the in-sample bleed — which is exactly why the full Sharpe is ≈ 0 and the OOS total return loses to EW. It's a **defensive overlay, not an alpha** — the same disposition BAB earned today.

---

## 8. Orthogonality — uncorrelated to the bond leg (k4 PASS), but long-commodity-beta to equities

| corr (monthly) | Commodity leg |
|---|---|
| **vs bond leg** | **−0.28** ✅ (k4 PASS — genuinely uncorrelated, the one thing that worked) |
| vs SPY | **+0.45** ⚠️ (materially long-commodity-beta; the bond leg was −0.20) |
| vs TQQQ | +0.32 |

**k4 passes** — the commodity leg is genuinely uncorrelated to the bond leg (−0.28), which is *why* the inverse-vol combine produces a high OOS number (the diversification math is real). **But** corr→SPY +0.45 is a long-commodity-beta fingerprint — far higher than the bond leg's −0.20. The commodity leg is much more "risk-on commodity exposure" than "orthogonal carry premium," consistent with it being mostly-long the optimized basket (ON ~73% of months).

---

## 9. THE COMBINED SLEEVE — real diversification *math* on a non-robust leg (k5 is an OOS-only mirage)

Combined carry sleeve = **equal-risk-weight (inverse-vol, 63d, lookahead-safe monthly)** of the **bond-leg primary path** (imported `run_one`: FULL 0.578 / OOS 0.434) + the **commodity-leg primary path**, on the overlapping span **2008-07-02 → 2026-06-22**.

| Combined sleeve | FULL | **IS≤2018** | **OOS 2019+** | maxDD | corr→SPY | corr→TQQQ |
|---|---|---|---|---|---|---|
| inverse-vol(bond, commodity) | **0.268** | **−0.05** | **0.967** | −17.6% | 0.25 | 0.16 |

**Combined IS/OOS split-robustness** (same regime artifact, inherited from the commodity leg):

| split | IS Sharpe | OOS Sharpe |
|---|---|---|
| 2014-12-31 | −0.14 | +0.58 |
| 2016-12-31 | −0.16 | +0.86 |
| 2018-12-31 | −0.05 | +0.97 |
| 2020-12-31 | +0.10 | +0.88 |

**Why the combined OOS Sharpe (0.967) is legitimate math but a misleading headline:**
- The two legs have OOS Sharpe 0.43 (bond) + 0.71 (commodity) with **near-zero daily correlation (−0.018)**. The diversification math is genuine: naive 50/50 daily-average gives OOS 0.83, theoretical equal-risk `(s1+s2)/√(2(1+ρ))` = 0.81, inverse-vol (tilting toward the calmer/higher-Sharpe leg, lookahead-safe) = 0.97. **k5's combined OOS 0.967 ≥ 0.5 and the book corrs (0.25/0.16) are low — so k5 "passes" as written.**
- **BUT it inherits the commodity leg's regime artifact wholesale.** Combined **IS Sharpe is −0.05 to −0.16** (negative in-sample on every split before 2020); combined **FULL Sharpe is 0.268** — and critically, **adding the commodity leg LOWERS the combined full Sharpe below the bond leg standing alone (0.578 → 0.268).** The commodity leg's decade of in-sample losses drags the diversified sleeve *down* on any full-period basis. The "combined clears 0.5" claim is true **only** in the cherry-picked 2019+ window; on the honest full-period (forward-proxy) basis the combined sleeve is *worse* than just trading the bond leg.
- **The honest forward read:** a combined sleeve does **not** clear 0.5 on a trustworthy basis. The bond leg alone (full 0.578) is strictly better than the combined sleeve (full 0.268). The commodity leg subtracts value everywhere except the one favorable OOS regime.

---

## 10. ALLOCATOR-FRONTIER LIFT — the add-on *looks* additive, but it's the same OOS-window illusion

Reproduced the **live 2-sleeve allocator** (TQQQ vol-target + sector rotation top-2) exactly via `_allocator_blend_tests.build_sleeves()` (read-only import), then compared an inverse-vol **2-sleeve** vs **3-sleeve (+ combined carry)** blend on the identical common window **2010-02-12 → 2026-06-22** (4,113 days; TQQQ inception bounds the start). Apples-to-apples per `reports/ALLOCATOR_BLEND_20260621.md`.

**Carry sleeve's correlation to the live book (daily, common window):**

| corr | value |
|---|---|
| combined carry → TQQQ sleeve | **+0.006** (essentially zero — genuinely orthogonal) |
| combined carry → rotation sleeve | **+0.253** |
| combined carry → SPX | **+0.009** |
| (TQQQ → rotation, for reference) | +0.581 |

**Inverse-vol allocator: live 2-sleeve vs +carry 3-sleeve:**

| Allocator (inverse-vol, monthly, lookahead-safe) | FULL Sharpe | FULL maxDD | OOS Sharpe |
|---|---|---|---|
| LIVE 2-sleeve (TQQQ + rotation) | 1.004 | −28.0% | 1.123 |
| **+ carry (3-sleeve)** | **1.041** | **−12.8%** | **1.232** |
| **Δ (add carry)** | **+0.037** | **+15.1pp shallower DD** | **+0.109** |

**Reading it honestly — this is the most seductive table in the report, and it must be read with §6/§9 in mind:**
- On its face, adding the combined carry sleeve **raises the allocator's full Sharpe (1.004 → 1.041), raises OOS Sharpe (1.123 → 1.232), and nearly HALVES the max drawdown (−28.0% → −12.8%)** — and the carry sleeve's corr to the wild TQQQ leg is ~0 and to SPX is ~0. That is *exactly* the orthogonal-diversifier profile the allocator wants, and if you stopped here you would (wrongly) call this a PASS.
- **The catch is the same one that sinks k5:** the allocator common window is **2010+**, and the carry sleeve's contribution to that window is **dominated by its post-2018 good regime** (recall the combined sleeve's 2010-2018 IS Sharpe is ≈ 0 to −0.16). The drawdown-halving and Sharpe-lift are *real over 2010-2026*, but they are **purchased largely by the commodity leg's 2019-2026 regime luck plus the bond leg's genuine 2022 hedge**. Decompose it: the **bond leg alone** is the honest, all-weather orthogonal contributor (full 0.578, corr −0.20 to SPY, hedged 2022); the **commodity leg** adds the cosmetic OOS sparkle that does not survive an in-sample look.
- **The correct allocator takeaway:** if the book wants an orthogonal eff-N raiser, the **bond carry leg is the part worth wiring** (it lifts the frontier on an all-weather basis and is the subject of the bond-leg report's "shelf-with-trigger" disposition). Bolting on the commodity leg makes the *backtest* prettier but adds a leg that lost money for a decade and fails its own dumb-EW control — i.e. it improves the historical frontier by adding **regime-fitted** return, not robust orthogonal return. **Do not promote the 3-sleeve-with-commodity allocator on the strength of this table.**

---

## 11. VERDICT — CLOSE the commodity leg; the H1 carry sleeve does NOT graduate

**k1 PASS(hollow) / k2 FAIL / k3 PASS(marginal) / k4 PASS / k5 OOS-only-mirage → overall CLOSE.**

The single criterion main built specifically to catch the dirty commodity-ETF proxy — **k2, beats-its-own-EW-control** — **fails by −77.5pp OOS total return.** This is reinforced, not rescued, by everything else:

- ❌ **The commodity carry signal is fund-mechanics/long-beta noise, not a harvested premium.** It loses to a dumb monthly EW hold of the same four ETFs (k2), and its higher *Sharpe* is pure vol-suppression (cash-parking at ~6.5% vol, +39% vs EW's +116% return). corr→SPY +0.45 confirms it's mostly long-commodity beta.
- ❌ **The apparent OOS edge is a single-regime artifact.** Negative IS Sharpe on *every* split (−0.30 to −0.64), money-losing in 8 of 11 in-sample years, with the entire positive contribution concentrated in the post-2018 backwardation regime. The full-period Sharpe is ≈ 0 (−0.014).
- ⚠️ **The combined sleeve's 0.967 OOS Sharpe is legitimate diversification math on a non-robust leg** — but combined **FULL Sharpe is 0.268**, *below the bond leg standing alone (0.578)*. Adding the commodity leg makes the OOS window sparkle while **lowering** the honest full-period risk-adjusted return. The combined sleeve does **not** clear 0.5 on any trustworthy (forward) basis.
- ✅ **The two genuine positives** — k4 (corr −0.28 to the bond leg) and the allocator drawdown-halving — are real but **inseparable from the regime luck**; they are not enough to overcome a leg that fails its make-or-break control and has a ≈0 full-period Sharpe.

### Disposition (the go/no-go main needs)
**NO-GO on the commodity leg and NO-GO on the combined H1 carry sleeve as a paper candidate.** This is the **PARTIAL → leaning CLOSE** outcome the task anticipated: *the bond leg is real but the commodity leg is too dirty/regime-dependent to clear 0.5 combined on an honest basis.* Stated exactly per the task's PARTIAL definition — **what is missing:** a commodity-carry signal that (a) beats its own EW control net (it doesn't), and (b) has a positive in-sample Sharpe / is not a single-regime artifact (it isn't). Without both, the combined sleeve's >0.5 is a 2019-2026 mirage.

**What this means for the bond leg:** unchanged from its own report — **shelf-with-trigger.** The bond carry leg remains the only real, all-weather, orthogonal carry signal on the bench (full 0.578, OOS 0.434, corr −0.20/−0.14 to the book, beats both its controls, hedged 2022). It misses 0.5 standalone and **the commodity leg cannot be the second leg that lifts it over** — so the H1 "combined carry sleeve" thesis, as instantiated with these commodity-ETF proxies, **fails.** The bond leg's disposition is independent of this close: it is shelf-worthy as a small orthogonal **eff-N** contributor *if/when* the allocator mandate shifts to raising blend Sharpe/eff-N (see bond-leg report §9), but it does not need — and does not get — the commodity leg.

### Revisit-triggers (what would have to change to reopen the commodity leg)
- **A non-ETF curve-shape instrument.** The core problem is the proxy: front-vs-deferred *ETF* spreads conflate genuine roll-yield with expense drag / tracking error / fund mechanics, and the signal is mostly long-beta. A **true futures-calendar-spread** (front vs deferred WTI futures, or the GSCI roll-adjusted excess-return vs spot-return indices) would isolate the curve-shape premium cleanly. If that data became free/available, the carry signal could be re-tested without the dirty-proxy confound — the analog of the bond leg's "a cleaner curve-carry instrument" trigger.
- **An in-sample-positive configuration.** Any reopening must show a **positive IS Sharpe** (not just OOS), i.e. the premium must exist before 2019, or it is a regime bet not an edge. None of the 36 swept configs clears this bar.
- **Beating the EW control net.** Non-negotiable. Until a commodity-carry variant beats a dumb EW hold of its own instruments on net total return OOS, it is noise.
- **A different carry expression** (e.g. cross-sectional commodity carry — long backwardated complexes, short contangoed ones, beta-neutral) rather than the long-only timing tested here. The long-only timing is structurally a defensive overlay; a market-neutral cross-complex spread is the genuinely-untested version (analogous to how single-name beta-neutral was the untested BAB case). That is a separate hypothesis, not a tweak of this one.

---

## 12. Honesty rails self-check
- ✅ **adjclose only** (USO/UNG and the leveraged-roll products drift hard on raw close; all loads use `adjclose`).
- ✅ **1-day signal lag:** spread computed on data ≤ month-end, positions effective T+1; freshly-traded weights do not capture the trade-day's already-realized return (inherited from the bond-leg backtest engine, verified identical).
- ✅ **Full continuous-span Sharpe** `(mean/std)·√252`, ddof=1, on the concatenated daily series — reuses the bond-leg `sharpe`/`metrics` (mirrors `runner/fp_sharpe.py`). **Never median-of-windows.**
- ✅ **Monotonic cost grid** 0/1/2/5 bps + breakeven framing; shown NOT to be the killer (dies on raw signal even at 0 bps; loses to EW at every cost). Turnover (33.6%/rebal) reported up front.
- ✅ **Real OOS walk-forward** (OOS_SPLIT 2018-12-31, **matched to the bond leg**) + **four-split IS/OOS robustness** (the decisive check) + 2008/2020/2022 stress windows reported separately.
- ✅ **No-signal EW control** (EW hold of the same commodity ETFs) — the make-or-break dirty-proxy test — AND **static-long-optimized control** (always-hold the optimized basket vol-targeted), both on the identical traded path + cost. The signal **fails** the EW control (k2) and only marginally beats static-optimized (k3).
- ✅ **Lookahead canary** (cheat peeks +1mo-forward spread) proves honest ≠ cheat path → no leakage.
- ✅ **Combined sleeve** built by importing the bond-leg `run_one` primary path (not re-derived) + equal-risk inverse-vol combine; reported on its **full AND OOS AND four-split** basis (not just the flattering OOS number), with the diversification math independently cross-checked (naive 50/50 0.83, theoretical 0.81, inverse-vol 0.97).
- ✅ **Allocator frontier** reproduced via the live allocator engine (read-only import), apples-to-apples on the common 2010+ window; the drawdown-halving reported **honestly as regime-fitted**, not sold as robust orthogonal lift.
- ✅ **Did not manufacture a pass.** The initial auto-verdict logic was corrected when the k2 failure + negative-IS regime artifact surfaced: the honest call is CLOSE on the commodity leg / NO-GO on the combined sleeve, with the genuine positives (k4, the diversification math, the cosmetic allocator lift) stated but explicitly subordinated to the make-or-break failures. A clean honest negative — the dirty-proxy outcome main flagged as the central risk.
- ✅ **PROTECTED dirs untouched:** the commodity+combined core imports only `_h1_carry_bondleg_tests` (→ `runner/fred_cache`); the allocator section imports `_allocator_blend_tests` (root-level, not protected) read-only. No `runner/*.py` (beyond `fred_cache`), `strategies*/`, crontab, `*.db`, broker, paper-clock, or allocator files were written.

---

*Files: engine `_h1_carry_commodity_combined_tests.py` (root, runs clean: `python3 _h1_carry_commodity_combined_tests.py`, exit 0); machine-readable `reports/_h1_carry_commodity_combined_result.json`; this report `reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md`. Data: cached `data_cache/yahoo/{USO,USL,DBO,DBC,GSG,DJP,USCI,UNG,UNL,GLD,SHY,TLT,IEF,SPY,TQQQ,QQQ}_parsed.json` (adjclose) + keyed-FRED `T10Y2Y` via the bond-leg engine. Single consistent UTC stamp 20260623T193840Z across all three deliverables.*
