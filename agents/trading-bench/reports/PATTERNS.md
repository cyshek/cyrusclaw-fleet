# PATTERNS.md — Institutional Knowledge

_Lessons that aren't gate violations but should inform future archetype design. Append-only. Cite evidence._

Format per entry:
- **Observation:** the pattern itself, one sentence
- **Evidence:** N confirmations with links to reports
- **Implication:** what this changes about how we design future archetypes

PATTERNS.md is the *positive* institutional memory; GATE.md is the *contractual* floor. They serve different jobs — don't mix them.

---

## Pattern #1 (2026-05-30) — SPY regime overlay strictly degrades sector-equity baskets

**Observation.** Adding `regime_uptrend(SPY, N=50)` as an outer gate on a strategy whose universe is US equity sector ETFs (XLK/XLF/XLU/etc.) is strictly worse than the same strategy without the gate. The "defensive in bears, enabled in bulls" intuition fails because sector ETFs already have 0.7-0.9 beta to SPY — the gate is double-defensive, cutting bull-side participation without buying meaningful bear-side protection that the per-symbol signal didn't already provide.

**Evidence (3 confirmations):**
- TSMOM SPY backtest (2026-05-30) — `reports/BACKTEST_TSMOM_SPY_20260530T171711Z.md`. Regime-gated variant Sharpe < raw variant across all 8 walk-forward windows.
- xsec momentum on 11 SPDR sectors (2026-05-30) — `reports/BACKTEST_XSEC_MOMENTUM_20260530T174735Z.md`. Regime filter strictly worse: cut exposure in winning regimes, sectors all share SPY beta → double-gating.
- xsec sector rotation / Faber GTAA (2026-05-30) — `reports/BACKTEST_XSEC_SECTOR_ROT_20260530T175458Z.md`. Regime filter strictly worse than raw across all sensitivity variants. Strategy already has its own per-symbol trend filter; SPY gate is redundant.

**Implication for future archetypes.**
1. **Do NOT pair `regime_uptrend(SPY)` with any strategy whose universe is US equity sector ETFs.** Use the strategy's own signal (per-symbol trend / vol / rank) as the only filter. If you want a defensive overlay, it has to add information SPY-trend doesn't already encode — e.g., per-symbol drawdown limits via `safety_backstop`, VIX-level regime, breadth thinning.
2. **Counter-cases worth testing before generalizing:** does this also apply to single-stock S&P universes? to cross-asset baskets? **Likely no** — when the universe has 0.3-0.5 SPY beta (bonds, gold, REITs), the SPY gate adds real information. Don't blanket-ban it; ban it specifically for sector-equity.
3. **For new sector-equity archetypes:** explicitly document in the report whether you tried the SPY regime gate and confirm the pattern, OR justify why your strategy is the exception. Don't silently skip the variant.

---

## Pattern #2 (2026-05-30) — Single-data-point class generalization trap (process pattern)

**Observation.** When the first within-class data point exposes what looks like a systemic issue (e.g., "this whole strategy class hits gate X"), the framing is tempting but unreliable. The second within-class data point frequently refutes it. Bringing a class-level policy framing to main (or to the channel as durable narrative) on n=1 produces a premature and partially wrong story that has to be retracted.

**Evidence (1 incident, canonical):**
- **2026-05-30 17:49 PT** — xsec momentum (#1) backtest (`reports/BACKTEST_XSEC_MOMENTUM_20260530T174735Z.md`) landed with 19% in-position, failing the amended Bar A 25% bars-in-position floor. Subagent flagged: "the floor is broken for cross-sec basket strategies." I posted that framing to channel (msg 1510339953404542986) and BACKLOG.
- **2026-05-30 17:54 PT** — xsec low-vol (#3) backtest (`reports/BACKTEST_XSEC_LOWVOL_20260530T175400Z.md`) landed with **67% in-position** on identical infrastructure, still REJECT but for genuine Sharpe-miss reasons (0.36 vs 0.50 bar). Floor-sensitivity sweep confirmed lowering 25→10% changed nothing for low-vol. Floor is a **momentum-class property** (high-churn rotation of top names), NOT a structural xsec property.
- **2026-05-30 17:58 PT** — xsec sector-rotation (#8) landed: dynamic basket size (avg 5.25) clears the floor naturally at N=150. Third data point: adaptive-basket strategies aren't floor-blocked either. Final picture: floor is a *fixed-K rotator* problem, not anything broader.
- **Channel correction:** msg 1510341305807540316 reframed; lesson recorded.

**Implication for future class-level claims.**
1. **Single subagent finding → log to daily memory + flag to BACKLOG as OPEN. Do NOT post to channel as durable narrative. Do NOT bring to main as policy proposal.**
2. **≥2 within-class data points → framing earns the right to be posted as a proposal.**
3. **Exception:** hard safety or correctness issues (test failures, data corruption, risk-cap bypass) need immediate flag regardless of sample size.
4. **Applied corollary for the trading bench specifically:** "systematically blocked by gate X" claims about a strategy class need at least one within-class strategy that DOESN'T hit the same blocker before the framing is durable.
5. **When you DO bring the proposal, structure the evidence as a refute-test:** show the data point that *could* have refuted it and didn't, not just the data point that confirmed it.

---

## Pattern #3 (2026-05-30, n=1 — CANDIDATE pattern, do not act on alone)

**Observation.** Monthly-rebalance basket strategies whose full-period Sharpe demonstrates real edge (≥0.50) can systematically fail the per-window walk-forward median-Sharpe gate (also ≥0.50) due to **horizon mismatch**: 60-90 day walk-forward windows contain only 1-7 fills, which is too sparse for stable Sharpe estimation. The walk-forward median Sharpe is then a noise-dominated estimate, NOT a measurement of edge. Full-period Sharpe is the better estimator when fill density is low.

**Evidence (1 data point, flagged candidate-only per Pattern #2):**
- xsec sector-rotation Faber GTAA cross-asset (2026-05-30) — `BACKTEST_XSEC_SECTOR_ROT_XA_20260530T180748Z.md`. Full-period Sharpe 0.85 (N=200) / 0.98 (N=150) clearly clears the 0.50 gate. Walk-forward median Sharpe 0.16-0.35 misses. Strategy made 1-7 fills per 60-90d window. The wave-4 subagent flagged this as the binding gate-miss and a possible Pattern #3 candidate.

**Adjacent supporting datum (not within-class, but illustrative):** `xsec_momentum_xa_38d2b2` (`BACKTEST_XSEC_MOMENTUM_XA_20260530T180628Z.md`) shows the same shape — full-period Sharpe **1.04** (corrected 2026-05-31; the originally-cited 1.13 was the best single window, 2025-Q3 bull — see Pattern #4) passes, median per-window Sharpe 0.49 misses, 28 trades across 8 windows (3.5/window, low density). Same structural pattern, but I'm not counting this as a Pattern #3 within-class confirmation because the BINDING gate miss for that candidate was the K-invariant in-position floor, not the Sharpe horizon issue.

**Implication (TENTATIVE, awaiting ≥1 more within-class confirmation per Pattern #2):**
1. For monthly-rebalance strategies that PASS full-period Sharpe ≥0.50 but FAIL walk-forward median Sharpe, instrument fill-density per window. If median fills/window is ≤5, the walk-forward Sharpe is structurally noisy and should not be the binding gate.
2. Potential bench amendment (do NOT propose yet): for low-fill-density strategies, replace the per-window median Sharpe gate with a per-window pooled Sharpe (concatenate trade returns across windows, compute Sharpe once on the pooled vector).
3. **The interesting cross-pattern check:** if Pattern #3 turns out to be real AND the floor-clause is amended, `xsec_momentum_xa_38d2b2` (Sharpe 1.04 full-period, corrected) and `xsec_sector_rot_xa_257225` (Sharpe 0.98 full-period N=150) both become promotable. That's enough to take both findings to main jointly once the within-class evidence is sufficient.

**Next within-class data points to look for.** Any future monthly-rebalance basket strategy that passes full-period Sharpe but fails the walk-forward median Sharpe with median fills/window ≤5. Likely candidates: cross-asset risk-parity, biweekly variants of existing strategies, single-symbol monthly trend-follow.

---

## Pattern #4 (2026-05-31) — FP-Sharpe-span integrity: a claimed full-period number over a phantom data span is invalid

**Status: HARD RULE (not a tentative pattern). Ratified by main, wave-5 integrity ruling Finding 3b.**

**Statement.** Any "full-period Sharpe" (or full-period return, drawdown, trade count) claim **must state the actual data span it was computed over, and that span must never extend beyond the bars-cache coverage floor.** For this bench the floor is **2020-07-27** (Alpaca free IEX feed depth; every basket leg's earliest real bar). A number cited over a span the data does not cover is **invalid and must be struck**, even if the strategy is otherwise sound.

**Two distinct failure modes this rule catches — both occurred together in the canonical incident:**
1. **Phantom span.** The `xsec_momentum_xa_38d2b2` promotion memo cited "FP Sharpe 1.13, span 2010-01-04 → 2026-05-09" — a 6.4-year span. The cache holds nothing before 2020-07-27. Cache *filenames* reflect the *requested* date range; Alpaca silently returns only the bars it has. So a backtest "over 2010–2026" actually ran over 2020–2026 with the pre-2020 portion contributing zero bars — the cited span was fiction.
2. **Best-window sold as full-period.** The "1.13" was the Sharpe of the single best regime window (2025-Q3 bull), not the full-period Sharpe. True FP Sharpe on real data is **1.04**. Conflating a best-window number with a full-period number inflates the headline.

**The silent enabler (now fixed):** `walk_forward_xsec` with default `warmup_days=0` returned **0 trades / +0.00% in every window** for a 252-bar-lookback strategy (the lookback couldn't compute from short window slices). That do-nothing result was reported silently rather than erroring — so a naive re-run "confirmed" nonsense and a careful re-run (warmup≥400) produced different numbers, with no signal that the two differed because of warmup. Fixed 2026-05-31: the harness now RAISES `ZeroTradesError` when 0 trades occur across all data windows (opt-out via `--allow-zero-trades`). See `runner/walk_forward_xsec.py`.

**Operating rules going forward:**
1. Every Sharpe/return/DD/trade-count claim in a backtest or promotion memo states its exact data span (`YYYY-MM-DD → YYYY-MM-DD`) and confirms span start ≥ 2020-07-27.
2. "Full-period" means the **aggregate across the whole walk-forward panel**, never a single window. Best-window numbers are labeled "best window (<regime>)".
3. Walk-forward runs on slow-lookback strategies pin `--warmup-days ≥ 400`. A run that needs the override `--allow-zero-trades` to complete is, by definition, producing no signal — do not cite its numbers.
4. When a parallel IC recomputes a headline number and it differs, **the burden is on the original claim** — re-derive on real data before defending it.

**Canonical incident:** `reports/PROMOTION_RECORD_CORRECTION_20260531T024500Z.md`. The bench caught its own promotion memo's number via a parallel wave-5 IC cross-check; the strategy survived (real FP Sharpe 1.04 ≥ 1.0 fast-track bar) but the *record* was corrected and this rule was written so the class of error can't recur silently.

---

## Pattern #5 (2026-05-31) — Cross-asset vol-ranking owns the most cash-like leg: high Sharpe, no return. Archetype CLOSED.

**Status: HARD NEGATIVE RESULT. Archetype closed by main (wave-5 low-vol IC ruling). Do NOT re-run. No wave-6.**

**Statement.** Ranking assets by realized volatility *across asset classes* and holding the lowest-vol K is **not the low-vol anomaly** — it is a duration/cash-likeness sort. The bottom of a cross-asset vol ranking is always the most cash-like instrument (short Treasuries, T-bills), which have low return *by construction*. So a cross-asset low-vol basket mechanically parks in near-cash, mechanically halves its volatility, and produces a **high Sharpe with almost no return**. That is metric-gaming, not edge.

**Evidence (within-class, ≥2 data points — this is a confirmed pattern, not a candidate):**
1. **Wave-4 `xsec_lowvol_xa_38a206`** — REJECTED. K=3 FP Sharpe 0.97 (<1.0) with a 2022-Q3 catastrophe; the TLT leg bled -$15.18 (long-duration "low vol" was a duration-risk illusion that got crushed in the 2022-23 hiking cycle while still scoring low realized vol).
2. **Wave-5 `xsec_lowvol_xa2_440761`** (SHY-for-TLT barbell) — NOT PROMOTED (`reports/DISPOSITION_xsec_lowvol_barbell_20260531T030000Z.md`). Fixing the TLT bleed by swapping to SHY pushed FP Sharpe to **1.23** (highest of all cross-asset candidates) — but only because SHY is held 100% of months as a near-cash anchor. Real return **~0.75%/yr (bench equity) / ~7.5%/yr (deployed)**. High Sharpe, no return — the pattern in its purest form.
3. **Wave-5 expanded 10-asset universe** (adding IEF/SHY/LQD/USMV) — every variant collapsed to **NEGATIVE Sharpe** (-0.37 to -0.74), parking permanently in SHY+IEF+LQD and never rotating. Adding more low-vol assets makes it *worse*: the ranking just finds more quiet near-cash to sit in.

**The deep lesson.** The low-vol anomaly is an **intra-asset-class** effect: low-vol *stocks* beat high-vol *stocks* (within equities), low-vol *within a credit tier*, etc. Applied *across* asset classes, "lowest realized volatility" collapses to "most cash-like," and you've built a cash-heavy barbell, not an anomaly harvester. Inverse-vol *sizing* makes it strictly worse (over-weights the calmest = most-cash leg). Equal-weight + a near-cash anchor are also mutually destructive with inverse-vol.

**Consequences:**
1. **Do not propose any further cross-asset low-vol variant.** The archetype is closed. Universe expansion, lookback tuning, and weighting schemes have all been tried; the ceiling is "high-Sharpe barbell with no return."
2. **The barbell is retained as a DEFENSIVE/capital-preservation sleeve candidate only**, never as alpha (see disposition memo).
3. **This pattern is WHY Bar A #5 clause (f) (absolute-return floor ≥8%/yr-on-deployed) exists.** The barbell is the canonical strategy that clause (f) rejects: clears Sharpe, fails return. A pure Sharpe gate would have admitted it.
4. **General rule for future archetypes:** if a strategy's Sharpe is high but its absolute return is low, suspect a low-vol/cash-anchor denominator effect before believing the Sharpe. Check what fraction of the book sits in the most cash-like leg.

**Canonical artifacts:** `reports/BACKTEST_XSEC_LOWVOL_XA2_20260531T023858Z.md` (the barbell backtest + §5 honest caveat), `reports/DISPOSITION_xsec_lowvol_barbell_20260531T030000Z.md` (disposition), `reports/BACKTEST_XSEC_LOWVOL_XA_20260530T180728Z.md` (wave-4 parent).

---

## Pattern #6 — Price-based single-stock cross-sectional has no risk-adjusted edge at retail cost (2026-06-02, n=4)

**Claim:** Single-stock cross-sectional signals derived purely from PRICE/RETURN (momentum, short-horizon reversal, low-vol ranking) do not clear the corrected front door (FP-continuous-span Sharpe ≥1.0 net of 4bps round-trip) over 2020-07→2026, on EITHER a narrow correlated universe OR a wide dispersed one.

**Evidence (4 rejects, distinct failure modes, one verdict):**
- xsec momentum, 20-name blue-chip: FP-cont Sharpe +0.21 (flat basin, no edge). `reports/SS_MOMENTUM_MONTHLY_20260602T002021Z.md`
- xsec short-reversal, 20-name: real GROSS alpha (Sharpe to 1.62 calm tapes) but turnover-cost-strangled (946 RT → net −8.7%/yr); low-turnover fix → true FP-cont Sharpe 0.73 + overfit knife-edge. `reports/LOWTURN_MEANREV_20260601T210128Z.md`
- xsec low-vol, 20-name: cash-anchor barbell, Sharpe-via-denominator not selection. (wave-5 disposition)
- xsec momentum, 95-name DISPERSED: FP-cont Sharpe +0.16 (dispersion didn't move it). Drop the high-idio-vol tail → Sharpe EXACTLY 0.00 (positives were tail noise). Tail that pays also craters −90% → fails #5(b). `reports/XSEC_DISPERSED_UNIVERSE_20260602T003839Z.md`

**The load-bearing lesson:** universe dispersion was the diagnosed root cause after the 20-name rejects — it was mechanically correct (the names DID lack dispersion) but NOT the binding constraint. The binding constraint is the SIGNAL CLASS: price-derived cross-sectional factors are the most-arbitraged signals in public markets; whatever edge existed is gone net of retail cost. Widening the universe only surfaced uncompensated idio-vol tail risk.

**Operational consequence:** do NOT spend more cycles on price-based single-stock xsec (any universe, any param). A revisit requires a DIFFERENT SIGNAL INPUT — fundamentals, earnings-revision, cross-asset/macro, vol-term-structure, event-driven — not universe or parameter engineering. Codified: the next edge search must leave price-cross-sectional space.

## Pattern #7 — HYG/LQD credit spread carries no daily-bar SPY-timing edge net of cost (2026-06-02, n=2 decision shapes)

**Claim:** Using the HYG/LQD (high-yield vs investment-grade) credit-spread ratio as a daily risk-on/off timer for SPY exposure produces no tradeable edge net of 4bps, in EITHER decision shape tested.
- Symmetric SMA-cross (round 1): FP-cont Sharpe [−1.51,−0.32], whipsaw in chop. `reports/NONPRICE_SIGNAL_20260602T005844Z.md`
- Asymmetric default-long + confirmed-veto + slow-reentry (round 2): FP-cont Sharpe [−1.56,−0.44], whipsaw replaced by lag-cost (veto fires after the drawdown, re-entry misses the bounce). `reports/NONPRICE_SIGNAL_R2_20260602T010535Z.md`

**Lesson:** "credit leads equities" is real MACRO truth but not expressible as a daily-bar SPY timer net of retail cost — the lead-time is too noisy/short to trade the round-trips profitably. Don't revisit HYG/LQD-as-SPY-timer. (Distinct from whether credit has edge as a slower portfolio-construction input — untested, lower priority.)

## Pattern #8 (POSITIVE lead, not a reject) — vol-regime timing is the first non-price signal with real sub-threshold edge (2026-06-02)

**Observation:** A VIXY-level binary risk-on/off timer on SPY (de-risk when VIXY > its own short SMA) produced FP-cont Sharpe **+0.87** on a robust plateau, +7.45%/yr, 78 round-trips, beating BH-SPY by ~0.9 Sharpe — NOT a cash-mirage (makes real money trading actively). Honest REJECT at the 1.0 front door, but categorically different from every other non-price basin (all negative/mirage). `reports/NONPRICE_SIGNAL_R2_20260602T010535Z.md`

**Why it matters:** consistent with the published Moreira-Muir (2017) vol-managed result. The binary gate is a crude approximation of the literal proportional inverse-vol construction (which our single-symbol backtester couldn't fairly express — no fractional-sizing primitive). The implied-vol channel (VIXY) beat the realized-vol variant (+0.24), confirming implied vol is the right input. **This is the one lead worth pushing 0.87→1.0:** cleaner implied-vol proxy (VIX term-structure) + true 2-sleeve proportional sizing. First evidence that uncrowded non-price edge may exist for us.

### Pattern #8 UPDATE (2026-06-02 R3) — the vol-regime lead DEFLATED under an honest ruler

Round 3 tested the two flagged levers (true proportional sizing + cleaner implied-vol). **The +0.87 did NOT hold: it fell to +0.544** once re-expressed as a real fractional-deployment vol-managed sleeve and benchmarked against a SAME-PATH BH-SPY (+0.25) instead of round-2's single-symbol-path near-zero bench. Both levers spent — proportional ≈ binary, and the "cleaner implied-vol" hypothesis was REFUTED (realized vol beat the VIXY/VIXM term-structure ratio). Vol-regime timing is **tapped out sub-threshold** on this construction; no lever worth another round. Memo `reports/VOL_REGIME_R3_20260602T011741Z.md`.

**MEASUREMENT-HYGIENE LESSON (new sub-pattern):** A Sharpe measured on one evaluator path (single-symbol `walk_forward`) against a near-zero benchmark can FLATTER a signal vs the same signal expressed on the deployment path it would actually trade on, benchmarked against the same-path BH. R2's 0.87 vs R3's 0.544 is the same strategy, two rulers. **Never compare FP-cont Sharpe across evaluator paths; always benchmark on the SAME path the strategy trades.** This is a cousin of the median-of-windows mirage — both are ruler-choice flattering a result.
