# AQR / Quant Research Reading Sprint — Synthesis Report

**Date:** 2026-06-30
**Author:** trading-bench (sprint synthesis subagent)
**Scope:** Mechanism + feasibility triage of TAA / risk-parity / return-stacking / crisis-alpha literature against the live bench roster. **No backtest numbers in this document** — confirm-or-kill runs for the two top picks are already in flight (see §6).

---

## 1. Sprint objective + methodology

**Objective.** Find a construction or overlay that closes the one genuine structural gap in the live roster: **the sector-rotation strategy has no crash-off switch.** It always holds the least-bad 2 of its 4 risk assets (SPY/QQQ/GLD/TLT), even when all four are falling together. Secondary objective: find capital-efficiency or robustness wrappers that raise risk-adjusted return *without* introducing a new directional signal (which would re-open already-closed lanes).

**Sources consulted.** Two parallel scouts read across the standard TAA / managed-futures / portable-alpha canon:
- **Scout A** — Return Stacking (Newfound/ReSolve portable-alpha writeups), risk-parity construction, rebalance-timing-luck (Newfound), CPPI/TIPP convex floors, and TS-momentum diversified-futures replication.
- **Scout B** — Keller/Keuning *Defensive Asset Allocation* (DAA) and *Vigilant Asset Allocation* (VAA), Antonacci *Dual Momentum* / GEM, Accelerating Dual Momentum (ADM), and trend-overlay-on-allocator-weights.

**Filter (the screen every candidate had to pass).** Three gates, in order:
1. **Free-data buildable.** Must be implementable on Yahoo v8 daily + FRED/CBOE/EDGAR only. Anything needing cross-asset futures breadth, shorting legs, or paid estimate-revision history is killed on data grounds.
2. **Orthogonal to closed lanes.** The bench has already burned and closed a long list (cross-sec value/quality/momentum/low-beta/BAB; macro-liquidity gate; VIX-term-structure; credit-spread timing; Moreira-Muir vol-managed; FX trend/carry; overnight drift; SKEW; dispersion/correlation; seasonality; turn-of-month; multi-horizon ensemble on a single leveraged instrument). A candidate that is a relabel of any of these is killed.
3. **Not the debunked overlay.** The primary negative prior — Allocate Smartly (May 2026): trend-following overlay ("surfing the equity curve") across 100+ TAA strategies **does not** improve risk-adjusted return; every variant either sacrifices raw return (short MAs) or fails to improve UPI. Any candidate that reduces to "put a trend filter on the equity curve / on the allocation weights" is killed by this prior at scale.

Nine candidates were scouted; **five survive** as genuinely new mechanism + free-data buildable; **four are killed** (three relabels + one debunked-at-scale overlay).

---

## 2. Candidate summary table

| # | Candidate | Mechanism class | Data status | Orthogonality to roster | Verdict |
|---|-----------|-----------------|-------------|-------------------------|---------|
| A1 | **Return Stacking** | Capital efficiency / portable-alpha overlay | Free (Yahoo + FRED) | **New axis** — gross exposure & financing, not a signal | **YES — top pick A** (backtest running) |
| A2 | **Rebalance-Timing-Luck immunization** | Meta-construction wrapper (staggered tranches) | Free (Yahoo) | New — robustness layer, modifies no signal | **YES — free robustness layer**, not standalone alpha |
| A3 | **CPPI / TIPP convex floor** | Risk-management overlay (path-dependent governor) | Free (Yahoo) | New — conditions on realized-path-vs-floor | **CONDITIONAL YES** — overlay, not alpha; lower priority |
| B1 | **DAA (canary crash switch)** | Regime-gated crash-off (decoupled canary) | Free (Yahoo) | **New** — exactly the crash-off switch the roster lacks | **YES — strongest candidate** (backtest running) |
| B2 | **VAA (graded breadth cash dial)** | Continuous breadth-momentum cash fraction | Free (Yahoo) | New, but adjacent to DAA | **POSSIBLE** — DAA is cleaner; lower priority |
| A4 | TS-momentum futures replica | Managed-futures replication | **Gated** (needs futures breadth/shorts) | Long-only ETF proxy = relabel of roster | **NO — relabel / data-gated** |
| B5 | GEM / Dual Momentum baseline | Absolute+relative dual momentum | Free | Roster rotation already does abs+rel selection | **NO — relabel** |
| B4 | TSMOM on allocator weights | Trend overlay on equity curve | Free | Hits the Allocate Smartly debunk directly | **NO — debunked at scale** |
| B3 | Accelerating Dual Momentum (ADM) | Momentum-of-momentum gate | Free | Adjacent to DAA, more params | **MARGINAL** — revisit only if DAA clears |

---

## 3. Surviving candidates — full write-ups

### A1 — Return Stacking (portable-alpha overlay) — **TOP PICK A**

**Mechanism.** Hold $1 of a core sleeve and layer a *financed* diversifier on top of the same dollar, so notional exposure exceeds 100%. The diversifier is funded at the financing rate, so the realized stacked return is core plus the diversifier's *excess-over-financing*:

```
R_stacked = R_core + StackSize × ( R_diversifier − Fee/12 − ( R_TBill + Financing/12 ) )
```

The Sharpe lift comes from **capital efficiency** — getting two return streams out of one dollar — not from any new directional signal. The only thing that can kill it is the financing drag swamping the diversifier's excess return; that drag is exactly what the backtest measures directly and is therefore the single falsifiable quantity.

**Instantiation for this bench.** Core = sector-rotation (or the inv-vol allocator blend). Diversifier = the TQQQ vol-target sleeve, or the XA TSMOM sleeve — both already validated, so no new signal is being introduced, only re-stacked. Financing leg = FRED `TB3MS` / `DGS3MO` (already wrapped in `runner/fred_cache.py`).

**Data.** Fully free. Every input series is already computed by the runner; this is an arithmetic overlay on existing return streams.

**Orthogonality.** Completely new axis. The inv-vol allocator blend is a *sum-to-1* convex combination; stacking is explicitly *not* sum-constrained — it adds gross exposure financed at the bill rate. Nothing in the closed-lane list touches gross exposure / financing.

**Build estimate.** **Low.** A function that takes two existing daily return series + a financing series and returns the stacked series; plus a sensitivity sweep over `StackSize` (e.g. 0.25 → 1.0) and the choice of core/diversifier pairing. No new data ingestion.

**Verdict: YES — top pick A.** Reuses validated sleeves; the financing drag is the one falsifiable thing the backtest measures. **Confirm-or-kill backtest already spawned (runner subagent in progress).**

---

### A2 — Rebalance-Timing-Luck (RTL) immunization — staggered tranches

**Mechanism.** A date-locked monthly strategy's return depends on *which day of the month* it rebalances — Newfound documents >100 bp/yr of dispersion across otherwise-identical factor strategies purely from rebalance-date luck. Immunize by running **N copies of the same strategy offset by 1/N of the rebalance period** and equal-weight-averaging their returns. For the sector-rotation (monthly, currently date-locked), run **21 daily-offset tranches** and average. This is a free Sharpe/robustness improver at **zero signal cost** — no parameter of any signal changes.

**Data.** Free (Yahoo). Same inputs as the existing sector-rotation; just evaluated on 21 offset schedules.

**Orthogonality.** Meta-construction wrapper. It does not modify any signal, threshold, or universe — it only removes an artifact of the arbitrary rebalance date. Orthogonal to everything because it is *construction*, not *signal*.

**Build estimate.** **Low–medium.** Loop the existing monthly engine over 21 phase offsets, average the equity curves. Main cost is making the rebalance date a parameter if it is currently hard-coded.

**Verdict: YES — but as a free robustness layer, not a standalone alpha lane.** It will not invent return where there is none; it removes noise/luck from the measurement of whatever the rotation already earns. Worth a quick experiment on the sector-rotation, and worth folding into *any* date-locked monthly strategy on the roster (including DAA/VAA if either graduates). Do not oversell it as alpha.

---

### A3 — CPPI / TIPP convex crash-floor overlay

**Mechanism.** Define a floor as a moving high-water level at ~80–85% of the running peak (TIPP ratchets the floor up with new peaks; classic CPPI floors at a fixed level). Cushion = portfolio − floor. Risk-asset exposure = multiplier × cushion (multiplier ~3–5), capped at 100% (or at the sleeve's max). As the portfolio rises, the cushion grows and exposure increases; as it falls toward the floor, exposure is mechanically cut to cash. The payoff is **convex and path-dependent** — a rules-based exposure governor, not a forecast.

**Data.** Free (Yahoo). Operates purely on the portfolio's own equity curve plus a cash proxy (`SHY`/bills).

**Orthogonality.** Conditions on **realized-path-vs-floor** — distinct from vol-regime (closed: Moreira-Muir) and from VIX-term-structure (closed). It is a different state variable: distance of the live equity curve from its ratcheted floor.

**Build estimate.** **Medium.** The mechanics are simple, but the honest evaluation is the work: the dangerous failure mode is **deleverage-into-a-V-bottom-and-never-re-risk** (sell at the floor, miss the recovery). The backtest must explicitly measure whipsaw cost and the "floored and never recovered" path, not just the smoothed-drawdown headline.

**Verdict: CONDITIONAL YES — risk-management overlay, not alpha.** Useful specifically if the bench decides it needs a *hard* tail floor (e.g. wrapped around the leveraged TQQQ sleeve). Lower priority than A1 and B1 because (a) it adds no return, only shapes the downside, and (b) the whipsaw failure mode is real and must be measured before any deployment. Note the conceptual overlap with the already-live crash-insurance paper tracker (−10%-trailing-DD-gated cash sleeve) — CPPI is the continuous, ratcheted generalization of that binary gate, so evaluate them head-to-head rather than stacking both.

---

### B1 — DAA: Keller/Keuning Defensive Asset Allocation (canary crash switch) — **★ STRONGEST CANDIDATE**

**Mechanism.** Two universes, checked monthly.

- **Canary universe `{VWO, BND}`** decides the regime via the **13612W** momentum filter — an annualized weighted average of 1/3/6/12-month total returns:

  ```
  13612W = ( 12·r1 + 4·r3 + 2·r6 + 1·r12 ) / 4
  ```

- **Gate (binary, canary-driven):**
  - **Both canaries positive** → 100% into the **top-T risk assets** (equal-weight top `T=6`, ranked by 13612W, from the G12 universe: `SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, HYG, LQD`).
  - **Exactly one canary negative** → 50% risk (top-T) + 50% into the **best bond** from `{SHY, IEF, LQD}`.
  - **Both canaries negative** → 100% into the single **best bond** from `{SHY, IEF, LQD}`.

The defining structural feature: **the signal asset ≠ the traded asset.** VWO/BND act as a leading "canary in the coal mine" for global risk appetite and decide *how much* risk to hold; the risk basket (SPY/QQQ/…) decides *what* to hold. Historically the average cash/bond fraction is **<30%** — i.e. surgical de-risking around real stress, not chronic under-investment.

**Data.** All Yahoo daily ETFs, monthly resample. VWO and BND both trade live from ~2007, so the canary is buildable over the full post-GFC sample. Trivial ingestion (all symbols already fetchable via the Yahoo v8 cache).

**Orthogonality.** **Genuinely new — and it hits the exact gap.** The bench's sector-rotation has *zero* crash-off switch; DAA's entire reason for existing is that switch. The decoupling of the canary (VWO/BND) from the holdings (SPY/QQQ/…) is structurally new versus everything on the roster, which selects holdings and exposure from the *same* assets. This is *not* GEM (see kills): GEM's absolute-momentum filter is computed on the asset it then holds; DAA's is computed on a *separate* canary pair.

**Build estimate.** **Low.** Monthly-resampled 13612W on 14 ETFs, a three-branch gate, equal-weight top-6 — all standard ops already in the runner. The one care-point is point-in-time correctness on the monthly resample (use month-end closes, no intramonth lookahead).

**Verdict: YES — strongest candidate.** It is the cleanest, best-documented, fully-free-data implementation of precisely the regime-gated crash-off switch the bench is missing. **Confirm-or-kill backtest already spawned (runner subagent in progress).**

---

### B2 — VAA: Vigilant Asset Allocation (graded breadth-momentum cash fraction)

**Mechanism.** Single universe, breadth-based **continuous** cash dial. Compute 13612W (same formula as DAA) on all `N` assets; count `b` = number of assets with **non-positive** 13612W momentum; set **cash fraction = b/N**; deploy the remaining `(1 − b/N)` equal-weight into the **top-1 (aggressive) or top-3 (moderate)** risk assets by 13612W. As breadth deteriorates, the cash fraction rises smoothly toward 100% — a continuous risk dial, versus DAA's binary canary gate.

**Data.** Free (Yahoo). Same 13612W machinery as DAA.

**Orthogonality.** New relative to the roster (a breadth-driven graded cash fraction), but **adjacent to DAA** — same momentum filter, different (continuous vs binary) gating. Building both is partially redundant.

**Build estimate.** **Low** — it is DAA's machinery with a `b/N` cash fraction instead of the canary branch.

**Verdict: POSSIBLE — but DAA is cleaner.** Documented behavior is **~60% average cash**, i.e. chronic under-investment in bull markets, which historically costs raw return. Lower priority than DAA. If DAA clears its confirm-or-kill, it is worth A/B-ing VAA's graded dial against DAA's binary canary on the *same* universe to see whether the continuous version trades less raw return for a smoother ride — but do not build VAA *before* DAA's result is in.

---

## 4. Killed candidates (one line each, with root cause)

- **TS-momentum diversified-futures replica (A4) — NO.** Root cause: the only free-data version is a *long-only ETF proxy*, which is a relabel of what the live roster already holds; true cross-asset breadth + shorting legs require futures data the VM cannot get for free.
- **GEM / Dual Momentum baseline (B5) — NO (relabel).** Root cause: the roster's sector-rotation already performs absolute + relative momentum selection; adding MSCI World as a 5th asset is cosmetic, not a new mechanism. (Contrast with DAA, which is *not* a relabel because its signal asset is a decoupled canary.)
- **TSMOM on allocator weights / "surfing the equity curve" (B4) — NO (debunked at scale).** Root cause: this is precisely the overlay Allocate Smartly (May 2026) tested across 100+ TAA strategies and found does not improve risk-adjusted return — overfit. The primary source already settled this.
- **Accelerating Dual Momentum (ADM, B3) — MARGINAL/parked.** Root cause: more free parameters than DAA (short- vs long-lookback acceleration gate) with thinner academic support; offers no orthogonal axis DAA doesn't already cover. Revisit *only* if DAA clears and we want a momentum-acceleration variant to A/B.

---

## 5. Top recommendations

**Build, in this order:**

1. **DAA (B1) — first.** It directly closes the one genuine structural gap (no crash-off switch in the sector-rotation), is the best-documented free-data crash gate, and the decoupled VWO/BND canary is structurally new versus the entire roster. Highest expected information-per-build.
2. **Return Stacking (A1) — second (parallel, not blocking).** Orthogonal axis (capital efficiency / financing), reuses *already-validated* sleeves, near-zero build cost. Its result is independent of DAA's, so the two confirm-or-kill runs proceed in parallel.

**Both A1 and B1 already have confirm-or-kill backtests spawned (runner subagents in progress)** — their numbers are incoming and will decide graduation. This sprint deliberately commits no numbers to either; it establishes only that both are mechanism-sound and free-data buildable.

**Hold in the on-deck queue (build only on a trigger):**
- **RTL immunization (A2)** — fold in as a *free robustness layer* on whichever monthly strategy graduates (sector-rotation, and DAA if it clears). Cheap, signal-neutral, removes rebalance-date luck. Not a standalone lane.
- **CPPI/TIPP floor (A3)** — build only if the bench decides it wants a *hard* tail floor; evaluate head-to-head against the existing crash-insurance paper tracker (the binary −10%-DD gate), since CPPI is its continuous generalization. Must measure whipsaw / never-recover paths honestly before deployment.
- **VAA (B2)** — build only *after* DAA's result is in, as an A/B of continuous-dial vs binary-canary on the same universe.

**Do not build:** the four killed candidates in §4. In particular do not re-attempt any trend-overlay-on-equity-curve / on-allocator-weights variant — the primary source has debunked that class at scale.

---

## 6. Honest caveats — what this sprint does NOT tell you

- **No performance claims.** This document is **mechanism + feasibility only.** Every "YES" means *worth a real backtest*, not *proven edge*. The actual Sharpe / UPI / max-DD / cash-fraction numbers for the two top picks come from the **confirm-or-kill runner subagents already in progress** — read those before graduating anything.
- **"Free-data buildable" ≠ "robust."** All five survivors clear the data gate, but only the backtest exposes the failure modes flagged above: for Return Stacking, whether financing drag swamps the diversifier's excess; for DAA, whether the canary is whipsaw-prone out-of-sample and whether the <30% cash claim holds on *our* sample/period; for CPPI, the deleverage-into-V-bottom path.
- **Sample / regime dependence.** DAA, VAA, and most TAA results in the literature are dominated by the 2008 and 2020 drawdowns. A clean in-sample result driven by two crash events is fragile; insist on out-of-sample and sub-period stability before trusting the headline.
- **Point-in-time discipline.** Monthly-resample candidates (DAA/VAA) must use month-end closes with no intramonth lookahead; the ETF universes (VWO/BND, the G12) only exist from ~2007, capping sample length — do not silently backfill with index proxies.
- **Overlap with live infrastructure.** CPPI conceptually overlaps the live crash-insurance tracker, and Return Stacking's diversifier reuses sleeves already in production. Treat these as *integrations to A/B against what exists*, not as net-new orthogonal lanes, when judging marginal value.
- **The negative prior is load-bearing.** The single most useful thing this sprint did was *not* re-open the trend-overlay lane. If a future reader is tempted by "just put a trend filter on it," the Allocate Smartly result (100+ strategies, no risk-adjusted improvement) is the documented reason not to.

---

*End of report.*
