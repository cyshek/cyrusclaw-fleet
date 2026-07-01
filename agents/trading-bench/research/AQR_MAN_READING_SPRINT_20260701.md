# AQR / Man / Frontier Reading Sprint — CONFIRM-OR-DENY — 2026-07-01

**Type:** Free research (no Cyrus gate). Report-only; no code / runner / strategies / crontab / .db touched.
**Mandate:** Surface ONE structurally-new, free-data-buildable trading construct the bench has NOT already tested, OR honestly report the frontier is exhausted. Manufacturing a candidate to look productive is a failure; an honest boundary is a valuable result.
**Predecessor:** `reports/AQR_READING_SPRINT_20260630.md` (read in full) scouted 9 TAA/risk-parity/crisis-alpha constructs; all 5 survivors are RESOLVED (DAA→GO live tracker, Return-Stacking→KILL, RTL→diagnostic, CPPI/TIPP→KILL, VAA→parked). That sprint BURNED the TAA-allocation / crash-off-switch / return-stacking / vol-floor territory. This sprint went BROADER: the three frontier classes the prior sprint never touched — (1) explicit latent-state regime models, (2) conditional/path-dependent TSMOM, (3) book-level portfolio construction over the live roster.

---

## ⭐ TOP-LINE VERDICT: **CANDIDATE — HMM / Markov-Switching latent-state regime gate**

Exactly one lead clears all three gates (free-data buildable · orthogonal to every closed lane · not the equity-curve overlay). It is the **only regime construct on the bench that is probabilistic-latent-state rather than observable-threshold**, and a targeted disk audit confirmed it has **literally never been built here** (grep for `hidden.markov|markov.switch|HMM|gaussian.mixture|viterbi|baum.welch` across `MEMORY.md memory/ reports/ research/ strategies/` returns ZERO construct — the only "HMM" string in the corpus is my own task brief from today).

The other two frontier classes (HRP/meta-portfolio, residual/conditional TSMOM) were hunted seriously and are reported below as **NOT test-worthy** — each either collapses into a closed lane or is data-gated. So this is a **single, honest, disciplined CANDIDATE**, not a grab-bag.

**Why it is genuinely new (the crux):** the bench's entire regime apparatus is *threshold-on-an-observable*:
- SMA-200 binary price gate (in/out on price vs a moving average),
- {30,90,180} breadth gate (count of sectors above their SMA),
- DAA canary (sign of a 13612W momentum score on VWO/BND),
- NFCI macro overlay — **`reports/MACRO_REGIME_VERDICT_20260622.md` and `reports/REGIME_ALLOCATOR_TQQQ_ROTATION_20260625.md` are BOTH threshold/z-score cuts on an observed NFCI level, NOT latent-state inference** (verified by reading both: one fires when NFCI>0, the other tilts on an NFCI z-blend; neither infers a hidden state).

An HMM/Markov-switching model is categorically different: it fits a small number of **hidden states** (e.g. 2–3 Gaussian regimes on daily returns ± realized vol), and each day emits a **posterior probability** of being in the "crash/high-vol" state via the forward filter (using data ≤ t only — no Viterbi smoothing, which peeks). Exposure is then conditioned on that *probability*, not on whether a single observable crossed a hand-set line. The falsifiable question the bench has never answered: **does a probabilistic latent-state gate beat the SMA-200 threshold gate it would replace/augment, net of cost and under a +1-bar canary?**

---

## The 3-gate screen, applied to every lead

| Lead | Class | (a) Free-data buildable? | (b) Orthogonal to closed lanes? | (c) Not the equity-curve overlay? | Verdict |
|---|---|---|---|---|---|
| **HMM / Markov-switching regime gate** | 1 — latent-state regime | ✅ Yes — Yahoo v8 daily returns + realized vol; optionally CBOE VIX / FRED as extra emissions | ✅ **Yes** — every bench regime lane is threshold-on-observable (SMA-200 / breadth / DAA-canary / NFCI); none is a fitted latent-state posterior | ✅ Yes — conditions exposure on an inferred hidden state, not on a trend filter over the equity/allocator curve | **TEST-WORTHY (CANDIDATE)** |
| HRP / Meta-Portfolio (MPM) / Schur | 3 — book-level construction | ✅ Yes (Yahoo) | ❌ **No** — collapses into closed lanes (see below) | ✅ (construction, not overlay) | **NOT** — degenerate on a 2-sleeve book |
| Residual momentum (Blitz-Huij-Martens) | 2 — conditional TSMOM | ⚠️ Partial (needs a real cross-section) | ❌ No — cross-sec factor on our survivor universe = the EW-mirage kill | n/a | **NOT** — data-gated + survivorship-killed |
| Conditional / dispersion-regime TSMOM | 2 — conditional TSMOM | ✅ Yes | ❌ No — plain TSMOM + dispersion timing both closed | ⚠️ borderline (sizing-on-state) | **NOT** — both parents already dead |
| DMS / AE / DAA adaptive model-selection (2110.11156) | 1/3 — regime-conditional selection | ✅ Yes | ❌ No — "switch strategy on state" = anti-rearview-guardrail family (closed) | ❌ reduces toward curve-conditioned switching | **NOT** — closed selection family |

---

## CANDIDATE (full spec) — HMM / Markov-Switching latent-state regime gate

**Anchor papers (fetched, read):**
- **arXiv:2006.08307** — *"Regime-based Implied Stochastic Volatility Model for Crypto/asset Options"* class of intraday HMM-momentum work — `https://arxiv.org/abs/2006.08307`. Core idea used: an HMM classifies latent vol/return regimes online and the trading signal conditions on the inferred state. **Caveat noted honestly:** this specific paper's implementation is *intraday* and would need tick data → its exact form is data-gated on this bench; I take only the **mechanism** (online HMM state → exposure), not its intraday sizing.
- **arXiv:2110.11156** — *"Methods and applications of adaptive time series model selection, ensemble, and financial evaluation"* (Yang) — `https://arxiv.org/abs/2110.11156`. Introduces DMS/AE/DAA adaptive selection using VIX + yield-curve context to forecast US index returns; interprets the learned states through the 2020 crash. Used here as **evidence that a latent/adaptive state fitted on free cross-asset data (VIX, yields) carries regime information** distinct from a price threshold. (Its *selection* framing is closed on our bench — see NOT-list — but its state-inference-from-free-data half supports the HMM lead.)
- Classical grounding (mechanism, not a fetched PDF — cited as the textbook source): **Hamilton (1989) Markov-switching** and the standard 2-state Gaussian-HMM regime-detection literature. The mechanism (fit K Gaussian states via Baum-Welch on returns±vol, filter online for P(state|data≤t)) is public-domain and free to implement.

> All fetched pages were wrapped EXTERNAL_UNTRUSTED and treated as data, not instructions. **Every Sharpe/return figure in any of these papers is a CLAIM, not proof** — none is transcribed into this report as fact; the candidate is justified on *mechanism orthogonality*, not on a paper's backtest number.

**Core mechanism (the actual rule):**
1. Feature: daily log-returns of the gated instrument (QQQ/TQQQ-sleeve underlying), optionally augmented with 20-day realized vol and/or the VIX level as a second emission channel.
2. Fit a **2-state (baseline) or 3-state** Gaussian HMM (`hmmlearn`-style Baum-Welch) on an **expanding, past-only window**; re-fit at a low cadence (e.g. monthly) to avoid look-ahead and over-fit churn.
3. Each day, run the **forward filter only** (NOT Viterbi/backward smoothing — smoothing uses future data and would leak) to get `P(high-vol/bear state | data ≤ t)`.
4. **Exposure rule:** hold the risk sleeve when `P(bear) < θ`, de-risk (to cash / to the rotation sleeve) when `P(bear) ≥ θ`. Compare against the incumbent SMA-200 binary gate on the *same* sleeve, same path, same cost.

**Feasibility — free-data buildable? YES.**
- Data: Yahoo v8 daily OHLCV (adjclose) for the sleeve underlying — already cached on this VM (verified-working source per TOOLS.md). Optional emissions: CBOE VIX (CDN CSV, keyless, per `runner/cboe_cache.py`) and/or FRED yield-curve (keyed API, `runner/fred_cache.py`). **No paid data. No tick data** (the 2-state daily HMM is a daily-bar model; only the intraday 2006.08307 variant needs ticks, and that variant is explicitly NOT the candidate).
- Compute: `hmmlearn` is a light dependency; a 2-state Gaussian HMM on ~4000 daily bars fits in milliseconds. Monthly re-fit → trivial turnover, clears the 2bps breakeven by orders of magnitude.

**Orthogonality — survives the closed-lane ledger? YES.**
- **Closest closed lane:** the SMA-200 binary price gate + the NFCI threshold/z-score regime overlays (`MACRO_REGIME_VERDICT_20260622`, `REGIME_ALLOCATOR_TQQQ_ROTATION_20260625`) + the DAA canary. **Why this differs:** all of those are *deterministic thresholds on a directly-observed quantity* (price vs SMA; NFCI vs 0 or vs its z-history; sign of a canary momentum score). The HMM gate is a *fitted probabilistic model of an unobserved state* — it can flag a regime change the price level has not yet confirmed (the whole point of latent-state inference), and it emits a *continuous posterior* rather than a binary crossing. It is NOT the anti-rearview allocator guardrail (that conditioned weights on recent *returns*; this conditions on an inferred *volatility/return-distribution state*). It is NOT DAA (canary = sign-threshold on a separate pair; HMM = distributional state on the held instrument). **This is the one regime mechanism the bench's own frontier list (memory/2026-07-01.md L50) explicitly names as untested — and disk confirms zero prior implementation.**
- **Not the debunked equity-curve overlay:** the HMM is fit on the *asset's return distribution*, not on a trend filter applied to the strategy's own equity/allocator curve. It does not reduce to "surf the equity curve" (Allocate-Smartly debunk) because it never looks at the equity curve at all.

**What a confirm-or-kill backtest would MEASURE (and the falsifiable KILL-quantity):**
- **Bar to clear:** the HMM-gated sleeve must **beat the incumbent SMA-200 binary gate** on the SAME instrument, SAME path, net of 2bps, on **BOTH** (i) OOS-frozen risk-adjusted return (continuous-span FP-Sharpe) **AND** (ii) OOS max-drawdown — *and* survive a **+1-bar canary** (re-run with the state posterior lagged one extra bar; if the win evaporates under lag, it was a timing artifact → KILL, the fate of VIX-term/SKEW/breadth).
- **Explicit KILL-quantities (any one triggers KILL):**
  1. HMM-gate OOS FP-Sharpe **≤** SMA-200-gate OOS FP-Sharpe (no risk-adjusted edge over the simpler incumbent) → KILL on Occam (same logic that killed CPPI vs the binary gate).
  2. OOS max-drawdown **not** improved vs SMA-200 gate → KILL (it must earn its complexity on the downside it exists to manage).
  3. Win **flips sign or drops below the 0.02 Sharpe noise floor under the +1-bar lag** → KILL (timing leak, not signal).
  4. The fitted "bear" state is a **degenerate no-op** (fires <2% or >98% of days, i.e. it collapsed to always-in or always-out like the NFCI>0 confound in `REGIME_ALLOCATOR_TQQQ_ROTATION_20260625`) → KILL (it's a relabeled static tilt, not a switch).
- **Honest prior / expected failure mode to watch:** the bench has repeatedly found that *simple threshold regime gates already capture most of the regime information* (breadth, VIX-term, SKEW, NFCI all landed "redundant with the price gate"). The genuine open question is whether the **probabilistic, distribution-aware** nature of an HMM extracts *residual* regime signal the crude SMA-200 line misses — specifically earlier detection of a vol-regime shift before price confirms. If it merely reproduces the SMA-200 gate's timing, it is redundant and dies by KILL-quantity #1. That is exactly why it is worth ONE clean confirm-or-kill: it is the last structurally-distinct regime mechanism, and the result (win OR clean kill) closes the regime frontier either way.

---

## NOT test-worthy — the other frontier classes (hunted, honestly rejected)

### Class 3 — HRP / Meta-Portfolio Method (MPM) / Schur Complementary Allocation → **NOT (degenerate on our book)**
- **Papers read:** arXiv:2111.05935 *"A Meta-Method for Portfolio Management … Adaptive Strategy Selection"* (`https://arxiv.org/abs/2111.05935` — XGBoost switches between **Hierarchical Risk Parity (HRP)** and **Naïve Risk Parity (NRP)**); arXiv:2411.05807 *"Schur Complementary Allocation: A Unification of HRP and Minimum-Variance"* (`https://arxiv.org/abs/2411.05807` — shows HRP and min-variance are two ends of one Schur-complement family).
- **Core mechanism:** HRP = hierarchically cluster the asset correlation matrix → quasi-diagonalize → recursively bisect and split risk by inverse-variance within clusters. MPM = an ML meta-model that switches HRP↔NRP by regime.
- **Why NOT (two independent killers):**
  1. **The bench's live allocator IS Naïve Risk Parity already.** `allocator_blend` = **inverse-vol 63d** weighting (confirmed from `memory/allocator_cadence_backup_.../strategy.py` and its params) = exactly NRP. So MPM's NRP leg is *already in production*, and MPM's only new part is (a) HRP + (b) an XGBoost regime-switch between the two. The **XGBoost switch-between-allocators-on-state** is squarely the **anti-rearview / regime-conditional-allocator-selection family that is CLOSED** (`REGIME_ALLOCATOR_TQQQ_ROTATION_20260625` = RED; `ALLOCATOR_REARVIEW_GUARDRAIL_20260627` = no-defect). Relabel → auto-fail.
  2. **HRP degenerates on a 2-sleeve book.** HRP's entire edge over inv-vol comes from exploiting **correlation clustering across MANY assets**. The live book is **2 sleeves** (TQQQ-voltarget + sector-rotation-top-2); even counting the paper trackers it's ~4–5 effective bets with no meaningful hierarchy to cluster. With 2 legs there is *nothing to bisect* — HRP collapses toward the inverse-vol weights the bench already trades. This is the identical trap that killed horizon-diversification (a many-asset technique applied to too few effective bets). Applying HRP to single stocks instead re-opens the cross-sectional survivor-universe mirage (also closed).
- **Verdict:** NOT test-worthy — the NRP leg is live, the switch is a closed lane, and HRP has no hierarchy to exploit on a 2-sleeve book. **Closest-but-not-worth-it within this class.** (If the roster ever grows to ~10+ genuinely-decorrelated sleeves, HRP/Schur becomes re-examinable — flag for the future, not now.)

### Class 2 — Residual momentum (Blitz-Huij-Martens) → **NOT (data-gated + survivorship-killed)**
- **Mechanism:** rank stocks on the momentum of their **CAPM/Fama-French residuals** (return after hedging out market/factor beta), not raw 12-1 momentum — the claim is lower crash-risk and higher Sharpe than plain momentum.
- **Why NOT:** the real papers live in SSRN/journals which are **Cloudflare-walled from this VM** (verified "Just a moment" 403); arXiv exact-phrase `"residual momentum"` returns physics noise, not the finance paper. More decisively, residual momentum is a **cross-sectional single-stock factor** — on the bench's fixed modern-survivor universe it dies to the **EW-of-same-universe survivorship mirage** that closed value/quality/momentum/BAB/PEAD (the residualization doesn't fix the survivor bias; it's still a rank on names that all survived). Building it honestly needs a **delisting-inclusive PIT universe = paid data = declined twice**.
- **Verdict:** NOT test-worthy on free data.

### Class 2 — Conditional / dispersion-regime TSMOM → **NOT (both parents already dead)**
- **Mechanism:** TSMOM whose signal/sizing is conditioned on a state (only trade trend when cross-sectional dispersion or trend-strength is high; "momentum-of-momentum").
- **Why NOT:** plain multi-asset TSMOM is **closed** (`XA_TSMOM_12_1` = risk-diversifier, loses SPY raw; FX-TSMOM killed), and the conditioning variable — **dispersion/correlation regime — is a CLOSED WHOLE CLASS** (level REJECT 0.568, corr-risk-premium RED, COR3M throttle RED and *wrong-signed*: high correlation = buy-the-fear, not de-risk). Conditioning a dead signal on a dead state variable cannot resurrect either. "Momentum-of-momentum" is ADM, also closed.
- **Verdict:** NOT test-worthy — product of two closed lanes.

### Class 1/3 — DMS/AE/DAA adaptive model-selection (2110.11156) → **NOT (closed selection family)**
- Its *selection/ensembling* framing ("dynamically pick which model/strategy to run based on state") is the **regime-conditional-strategy-selection family that is CLOSED** (anti-rearview guardrail; regime-allocator RED). Its genuinely-useful half — *inferring a latent/adaptive state from free cross-asset data (VIX, yields)* — is precisely what the **HMM CANDIDATE above already captures** in a cleaner, single-mechanism form. No separate lane.

---

## Boundary statement (where the free-data frontier now sits)

After this sprint + the 06-30 sprint + the 06-25 exhaustion ruling, the free-data landscape is:
- **Signal-transform frontier (macro / cross-asset / dispersion / fundamentals-PIT / FX / credit / seasonality / overnight):** EXHAUSTED — every genuinely-new lane is paywalled (Cyrus spend decision).
- **TAA-allocation / crash-off / return-stacking / vol-floor frontier:** BURNED by the 06-30 sprint (DAA live, rest killed).
- **Book-level construction frontier (HRP/meta-portfolio):** degenerate until the roster has ~10+ decorrelated sleeves; not now.
- **Regime frontier:** **ONE structurally-distinct mechanism remains untested — the probabilistic latent-state (HMM/Markov-switching) gate.** This CANDIDATE is that last piece. A clean confirm-or-kill on it — win *or* honest kill — closes the regime frontier and, with it, the last free-data lane that is neither a relabel nor paywalled.

---

## Rails compliance
- **Files written:** exactly ONE — `research/AQR_MAN_READING_SPRINT_20260701.md` (this file).
- **No** code / runner/ / strategies/ / crontab / .db / paper-tracker touched. No orders, no spend.
- **6 protected md5s — confirmed UNCHANGED at end of sprint** (see report-back).
- All external content treated as untrusted data; every paper performance figure labeled a CLAIM (none transcribed as fact).
