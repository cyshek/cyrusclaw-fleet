# MACRO REGIME OVERLAY on the LIVE allocator_blend — VERDICT

**Date:** 2026-06-22 · **Lane:** cross-asset macro regime filter (NFCI financial conditions) on the live inv-vol allocator blend
**Script:** `strategies_candidates/macro_regime_allocator/macro_overlay.py` (+ `nfci_pit.py` for point-in-time NFCI)
**Result JSON:** `reports/_macro_regime_overlay_result.json`

## VERDICT: ⚠️ TAIL-HEDGE-ONLY — improves drawdown + Sharpe, NOT raw return. Do **not** apply as a return play.

A NFCI z-score de-risk overlay **converts the allocator's worst out-of-sample drawdown (2022, −22%) into a minor one (−14%)** and lifts OOS Sharpe 1.14 → 1.19–1.23, but the "no return cost" property is **knife-edge on the publication-lag assumption**: it only beats the live blend on OOS return at the single most-optimistic lag (lag0: +277.0% vs +276.2%), and gives up ~18pp of OOS return the moment one extra conservative day is applied (lag+1: +258.6% < +276.2%). The drawdown/Sharpe benefit is robust across lags; the return-neutrality is not. → **Risk tool, not a return improver. Flagged for Cyrus as an optional tail-hedge, not promoted.**

This is the **same landing zone as the VIX-term lane (closed 2026-06-22)** — a DD hedge that costs return with 1-day-lag-fragile "wins" — with one real distinction: NFCI's overlay materially helps **2022** (where VIX-term was identical to baseline), because NFCI tracks the slow rate-driven tightening that the vol complex missed.

---

## Hypothesis tested

A cross-asset macro REGIME signal (Chicago Fed **NFCI**, the purpose-built financial-conditions index) can improve the live inv-vol allocator by modulating exposure: de-risk (scale gross toward cash) when conditions are **TIGHT** (NFCI elevated), stay fully invested when **LOOSE**. Mechanism claim: both sleeves are long-equity-biased (full corr **0.58**); a macro gate firing *before* the slow SMA-200 price gate could cut drawdown in rate/credit shocks (2018-Q4, 2022) without giving up much bull return.

**Null to disprove:** the SMA-200 gate + inverse-vol sizing already capture all the regime information, so a macro overlay adds nothing net of cost (exactly what happened to the VIX-term lane).

---

## 1. Baseline anchor — REPRODUCED ✅ (sanity gate passed)

Reproduced the live inv-vol blend directly from the validated engine (`_allocator_blend_tests.build_sleeves` + `blend_portfolio` + `invvol_wfn(63)`):

| Metric | This run | Promoted/live anchor | Match |
|---|---|---|---|
| Full Sharpe | **1.009** | ~1.012–1.014 | ✅ |
| OOS Sharpe (2019+) | **1.142** | ~1.142–1.147 | ✅ |
| Full maxDD | **−23.9%** | −23.9% | ✅ |
| Full CAGR | **15.8%** | 15.9% | ✅ |
| Window | 2010-02-12 → 2026-06-22 (4113 d) | 2010-02 → 2026-06 | ✅ |
| OOS raw return | **+276.2%** | — | (anchor for the bar) |
| OOS maxDD | **−21.9%** | — | (anchor for the bar) |

Sleeves reproduce exactly: TQQQ vol-target Sharpe 0.863 / CAGR 20.8% / maxDD −34.5%; sector-rotation top-2 Sharpe 0.926 (common-window) / CAGR 12.9%. Anchor confirmed — proceeding.

---

## 2. Macro signal definition + EXACT lag applied (the make-or-break)

**Signal:** Chicago Fed **NFCI** (weekly, FRED series `NFCI`), fetched via the keyed FRED/ALFRED API (`runner/fred_cache.py` — never `fredgraph.csv`, which serves stale data from this VM).

**⚠️ Critical lookahead trap found & defused — NFCI is heavily REVISED during stress weeks.** Verified via the full ALFRED vintage table (`nfci_pit.py`):

| Obs week | First-known date | First-release value | Current revised value | Revision |
|---|---|---|---|---|
| 2018-12-14 | 2018-12-19 | **−0.750** | −0.428 | +0.322 |
| 2020-03-13 | 2020-03-18 | **−0.480** | +0.033 | +0.513 |
| 2020-03-20 | 2020-03-25 | **−0.170** | +0.177 | **+0.347 (sign flip!)** |
| 2022-10-21 | 2022-10-26 | −0.112 | −0.110 | +0.002 |

In **real time**, NFCI showed COVID and 2018-Q4 as *loose/negative* — the stress only appeared in *later revisions*. A backtest on the current-revised (`latest`) series would "de-risk COVID" purely on hindsight. **Therefore the study uses FIRST-RELEASE (as-known) NFCI only** (`nfci_pit.as_known_on`): on each date `d`, the overlay acts only on the value actually **published on or before `d`**.

**Exact lag:** the publication lag is **baked into the first-release date** — NFCI for a Friday week-end is published ~the following **Wednesday (5–6 calendar days later)**. So the value dated `2020-03-20` becomes actionable `2020-03-25`. The overlay then applies the as-known signal to the **next bar** (`s_{t-1} * r_t`). A `+1` and `+2`/`+3` trading-day extra-lag stress is run on top.

**Two rule families, pre-registered:**
- **LEVEL gate (binary + hysteresis):** de-risk when NFCI level ≥ `thr_off`, re-risk when ≤ `thr_off − 0.25`.
- **Z-SCORE (continuous):** causal trailing-252d z-score; `s = 1` for `z ≤ z_lo`, `s = 0` for `z ≥ z_hi`, linear between. (z normalization itself uses only past data — no lookahead.)

De-risked fraction earns **0** (conservative — no cash/T-bill yield credited). Switching cost **2 bps** charged on `|Δ gross exposure|`. Net @2bps, same path/window as baseline.

---

## 3. Overlay results (IS + OOS, net @2bps, vs unmodified live blend)

### LEVEL-gate sweep — fires almost never (a finding in itself)
The **as-known** NFCI level distribution over 2010–2026 maxes at **+0.070** (p95 = −0.21, p50 = −0.64). The post-2010 era was a structurally **loose**-conditions regime by NFCI's construction, so any level threshold ≥ +0.10 produces **zero de-risk days** → overlay ≡ baseline. Aggressive thresholds (≤ 0.0) only *cost* OOS return (thr=−0.10: 256.7% vs 276.2%). **Level gate: no help.**

### Z-SCORE sweep — the headline (full sweep shown, plateau visible)

| z=[lo,hi] | de-risk days | switches | Full Sh | OOS Sh | OOS ret | OOS maxDD |
|---|---|---|---|---|---|---|
| **[0.5, 1.5]** ★ | 1145 | 627 | **1.062** | **1.231** | **+277.0%** | **−13.7%** |
| [0.5, 2.0] | 1145 | 861 | 1.058 | 1.220 | +277.9% | −13.7% |
| [1.0, 2.0] | 819 | 534 | 1.045 | 1.173 | +269.6% | −17.0% |
| [1.0, 2.5] | 819 | 696 | 1.030 | 1.163 | +267.5% | −18.0% |
| [1.5, 2.5] | 565 | 444 | 1.011 | 1.158 | +270.6% | −18.8% |
| [0.0, 1.5] | 1724 | 1196 | 1.035 | 1.185 | +233.0% | −13.7% |
| **baseline** | 0 | 0 | 1.009 | 1.142 | +276.2% | −21.9% |

The z-overlay **plateau is broad** (every variant lifts Sharpe + cuts DD; the [0.5,1.5]–[0.5,2.0] corner is a plateau, not a spike), so this is *not* a knife-edge threshold-argmax. The headline **z=[0.5,1.5]**: OOS Sharpe **1.231** vs 1.142, OOS maxDD **−13.7%** vs −21.9%, OOS return **+277.0%** vs +276.2% (≈ tied at lag0).

---

## 4. Robustness — the +1-day lag test (this is what decides it)

| Config | de-risk days | Full Sh | **OOS Sh** | **OOS ret** | OOS maxDD |
|---|---|---|---|---|---|
| baseline live blend | 0 | 1.009 | 1.142 | **+276.2%** | −21.9% |
| overlay **lag0** (first-release) | 1145 | 1.062 | **1.231** | **+277.0%** ✅ | −13.7% |
| overlay **lag+1d** | 1145 | 1.038 | 1.191 | **+258.6%** ❌ | −13.7% |
| overlay lag+2d | 1141 | 1.020 | 1.159 | +248.9% ❌ | −14.0% |
| overlay lag+3d | 1136 | 1.025 | 1.166 | +252.1% ❌ | −14.0% |

**The Sharpe + DD benefit SURVIVES the lag (OOS Sharpe ≥ 1.16 at every lag, always > baseline 1.142; DD ~−14% at every lag).** This is materially *better* than the VIX-term lane, whose edge fully died on +1 day. **But the OOS raw-return advantage does NOT survive:** at lag0 the overlay ties/beats baseline return (+277.0%), and at lag+1 it drops to +258.6%, ~18pp **below** baseline +276.2%. Since the de-risk-day count barely moves with lag (1145 → ~1140, NFCI being weekly), the return erosion comes from acting one day later on the same de-risk windows — i.e. the return-neutrality was riding on the most optimistic publication-timing assumption.

**Decision rule (task-specified):** must beat live on **both** OOS Sharpe AND OOS return AND survive the 1-day lag. → Sharpe: ✅✅ (lag0 + lag1). Return: ✅ lag0, **❌ lag1**. → **Fails the return leg under realistic lag ⇒ not CLEARS-BAR.**

---

## 5. Episode decomposition — WHERE the benefit comes from

| Episode | Baseline ret / DD | Overlay lag0 ret / DD | Overlay lag+1 ret / DD |
|---|---|---|---|
| **2022 bear** | −14.4% / −19.6% | **−5.9% / −7.1%** | **−5.0% / −6.1%** |
| 2020-Q1 COVID | −3.6% / −18.6% | −7.1% / −13.7% | −7.5% / −13.7% |
| 2015–16 selloff | −8.5% / −18.4% | −7.3% / −13.7% | −9.0% / −14.6% |
| 2018-Q4 | −10.3% / −13.9% | −11.2% / −13.9% | −11.4% / −13.9% |
| 2011 summer | +2.3% / −7.1% | +1.8% / −6.6% | +2.6% / −6.5% |

**2022 is the entire engine of the benefit.** Baseline −14.4% return / −19.6% DD → overlay −5.0% / −6.1% (lag+1): a **+9.4pp return rescue** and DD cut by ~two-thirds. NFCI's z-score caught 2022's slow, persistent rate-tightening (234 de-risk days that year) — precisely the regime NFCI is built to track and which the price-SMA gate is too slow for.

- **COVID 2020:** DD improved (−18.6% → −13.7%) but at a **return cost** (−3.6% → −7.5%) — the overlay de-risked into the V-recovery and gave back upside. Net wash-to-negative. (And honestly so: NFCI *as-known* barely registered COVID in real time — the de-risk here is z-score-momentum, not a clean COVID call.)
- **2018-Q4 / 2015–16:** small DD help, small-to-negative return effect under lag.
- **Bull-market drag** (per-year OOS, lag+1 vs baseline): 2020 −7.9pp, 2025 −4.2pp, 2019 −2.4pp, 2023 −1.7pp — a steady small toll from de-risking healthy pullbacks that recover. Offset almost entirely by the single 2022 +9.4pp rescue, which is why OOS return nets out only ~18pp behind.

**De-risk is well-distributed across stress years** (2011: 104d, 2015: 174d, 2018: 134d, 2022: 234d) — not concentrated in 1–2 lucky days, so the signal is a genuine conditions read, not a fluke. But its *net return* benefit hangs almost entirely on 2022.

---

## 6. Regime-switch / activity counts
- Headline z=[0.5,1.5]: **1145 de-risk days** (27.8% of 4113), **627 regime switches** (continuous scaling → frequent small exposure changes; cost already charged at 2bps/switch and the result still nets positive on Sharpe).
- Level gate at any sane threshold: **0–24 de-risk days** (≈ never fires on as-known data).

---

## Bottom line

| Question | Answer |
|---|---|
| Reproduced baseline anchor? | ✅ Sharpe 1.009 / OOS 1.142 / maxDD −23.9% / CAGR 15.8% — exact |
| Macro signal + lag | NFCI **first-release (as-known)**, real publication lag (~Wed after Fri week-end, ~5–6 cal days), applied next-bar; +1/+2/+3d stress on top |
| Headline overlay (z=[0.5,1.5]) vs live, OOS | Sharpe **1.231** vs 1.142 · ret **+277.0%** vs +276.2% · maxDD **−13.7%** vs −21.9% (lag0) |
| 1-day-lag result | **Sharpe + DD survive** (1.191 / −13.7%); **return does NOT** (+258.6% < +276.2%) |
| **VERDICT** | **TAIL-HEDGE-ONLY** — robust DD/Sharpe improver, but return-neutrality is lag-fragile; net return benefit rides almost entirely on 2022. **Not a return play.** |

**Recommendation:** Do **not** promote as a return improver (fails the strict bar). **Flag for Cyrus** as an *optional drawdown hedge*: if the goal is to harden the allocator's tail (turn a −22% OOS drawdown into −14% and raise Sharpe) at the cost of ~0–18pp OOS return depending on execution timing, the NFCI z-overlay does that robustly and is cheap to run (weekly signal, free keyed data). If the goal is max return, it's redundant-to-costly like the VIX-term lane. **No live config changed** — research/measurement only.

### Files
- `strategies_candidates/macro_regime_allocator/macro_overlay.py` — full study (reproducible from cold cache; reuses the blend engine + fred_cache)
- `strategies_candidates/macro_regime_allocator/nfci_pit.py` — point-in-time (first-release) NFCI builder via ALFRED full-vintage table
- `reports/_macro_regime_overlay_result.json` — machine-readable results
