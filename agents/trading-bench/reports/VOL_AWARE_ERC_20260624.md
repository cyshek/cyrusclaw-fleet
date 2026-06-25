# Vol-Aware (Full-Covariance) ERC — Confirm/Refute "Moves Weights Only at the Margin"

**Date:** 2026-06-24 · **Author:** opus quant subagent (trading-bench) · **Window:** 2010-02-16 → 2026-06-18 (4,111 common trading days) · **Budget:** $800 · **Paper-only**

---

## TL;DR — VERDICT: borderline. Mechanical rule trips MATERIAL; substance says NO live change.

The vol-aware refinement reshuffles only **$48.78 of $800 in aggregate (6.1% of budget)** — *under* the 10% "noise" threshold. But it trips the stricter sub-tests: **`volume_breakout_qqq` moves +40.1%** of its own base and the **rsi/macd diversifier pair swaps order** (both stay top-2). By the letter of the pre-stated decision rule that is **MATERIAL-change**. By substance it is **immaterial**: the move is small in dollars, concentrated in the one *proxy* sleeve (least trustworthy series), and driven by a **time-in-market vol artifact** that the original correlation-ERC actually handles *better* for these mostly-flat event sleeves.

> **Recommendation to parent/Cyrus: keep the existing correlation-ERC `capital_usd_v2_tradeable` weights. Do NOT adopt the vol-aware notionals.** The phrase "moves weights only at the margin" in `ERC_CAPITAL_WEIGHTING_20260624.md §5` is **literally too optimistic** under the strict rule (one sleeve moves 40%), but **correct in spirit** (no book restructuring is warranted; the largest dollar move is $36 into a documented proxy). The full vol-aware notionals are reported below as the method's honest output, but they are *not* an improvement worth a live change.

---

## 1. Method

Goal: take each live strategy's **actual trailing realized vol** (full-sample, 4,111d) and run a **full-covariance** ERC (Σ = D·R·D), versus the shipped baseline that ran ERC on the **unit-vol correlation** matrix and used a leverage-divide as a crude vol proxy.

**Step 1 — rebuilt the 8 daily return series** (the exact recipe behind `reports/_interstrategy_corr_matrix.json`, restricted to the 8 live names, in `_erc_weights.json["live"]` order):

- **6 event strategies (1–6)** → each strategy's unchanged `decide()` run through `runner.backtest.backtest()`, fed **daily adjclose bars** (Yahoo v8 via `runner/daily_bars_cache.py`, split/div-adjusted) shaped into the engine's `{t,o,h,l,c,v}` contract, `timeframe='1Day'`, **zero-cost** (`CostModel(spread_bps=0, fee_bps=0)`).
  - `volume_breakout_qqq` → **PROXY**: native `volume_mult=3.0` fires 0 daily entries, so relaxed to **1.0** (matches the documented baseline relaxation). Flagged throughout.
  - `sma_crossover_qqq_rth` → daily bars stamped at **15:00 UTC** so its 14:30–20:00 UTC RTH gate is a transparent no-op (≈1.00 corr with the regime variant on daily — expected/documented).
- **tqqq_cot_combo (7)** → VT equity via `run_backtest_voltarget(target_ann_vol=0.25, vol_window=20, sma_window=200)`, with the **COT overlay** layered by multiplying each day's VT target weight by the **live strategy's own** `strategies/tqqq_cot_combo/strategy.py::_get_cot_scale(0.5, date)` (0.5× on bearish ES AM-net WoW weeks, 3-day publication lag), daily return = `effective_weight × raw TQQQ adjclose return`. This is byte-for-byte `_xstrat_corr._tqqq_cot_combo_series` — the construction that produced the **documented** baseline matrix.
  - *Note on `target_ann_vol`:* the baseline corr-matrix and this rebuild use **0.25** for fidelity to the documented matrix; the live `params.json` says **0.40**. The gap is discussed in §6 — using 0.40 only *raises* the combo's vol (29% vs 20.5%), which pushes its already-near-zero ERC weight *even lower*, so it cannot change the verdict.
- **allocator_blend (8)** → `import _allocator_blend_tests as ab; ab.build_sleeves()` + `ab.blend_portfolio(..., invvol_63d)` → daily equity → returns (exactly what `runner/allocator_paper_tracker.py` does; zero sleeve-logic duplication).

**Step 2** — annualized vol = `std(rets, ddof=0) · √252` (population, matching `_allocator_blend_tests.annualized_vol`).

**Step 3** — Σ = D·R·D with D = diag(Step-2 vols), R = the reproduced 8×8 correlation; ran the same Maillard-Roncalli-Teiletche ERC fixed-point on the **covariance**. Converged to **exactly equal risk contributions** (RC = 12.50% ± 0.000000).

**Step 4** — translated to capital **without** dividing by leverage (see §5), applied the **same share-floor** as baseline v2 (tqqq ≈ 2 TQQQ shares ≈ $160; $50 dust floor), renormalized to $800, compared to `_erc_weights.json["capital_usd_v2_tradeable"]`.

### 1a. Load-bearing validation gate — series reproduce the documented correlation matrix ✅

| Check | Result |
|---|---|
| Standalone Sharpes vs `INTERSTRATEGY_CORRELATION_20260622.md §diagnostics` | breakout 0.497 (doc 0.510), sma_regime 0.512 (0.532), sma_rth 0.496 (0.514), volume 0.169 (0.164, proxy), rsi 0.280 (0.271), macd 0.032 (0.027), combo 0.841, allocator 1.001 (1.006) — **all within tolerance** ✅ |
| Common window | **2010-02-16 → 2026-06-18, 4,111 days** — exact match to the documented window ✅ |
| Correlation submatrix vs `_erc_weights.json["corr_submatrix"]` | **mean \|Δ\| = 0.0043**; **bulk max \|Δ\| = 0.0152** (excluding one cell) ✅ |
| Only outlier cell | `tqqq_cot_combo × allocator_blend` = 0.840 repro vs 0.794 base (Δ=0.046) — VT-amplitude-sensitive; **proven immaterial** (see §3a) |

The reproduction is essentially exact for all 6 event strategies, the allocator, rsi, and macd. **The series are real, not garbage — the gate passes.**

---

## 2. The 8 annualized vols (the information correlation-only ERC threw away)

| # | Strategy | Lev | **Ann vol** | In-market % of days | Vol *when active* | Read |
|---|---|---|---|---|---|---|
| 1 | breakout_xlk__mut_c382b1 | 1.0 | **1.01%** | 61.6% | 1.3% | low-vol equity-trend |
| 2 | sma_crossover_qqq_regime | 1.0 | **0.92%** | 68.2% | 1.1% | low-vol equity-trend |
| 3 | sma_crossover_qqq_rth | 1.0 | **0.93%** | 68.7% | 1.1% | ≈ dup of #2 |
| 4 | rsi_oversold_spy | 1.0 | **1.22%** | **5.6%** | **5.1%** | **flat 94% of the time; punchy when in** |
| 5 | volume_breakout_qqq | 1.0 | **0.68%** | 31.1% | 1.2% | **PROXY**, lowest vol |
| 6 | macd_momentum_iwm | 1.0 | **0.87%** | 19.1% | 2.0% | low-vol small-cap mom |
| 7 | tqqq_cot_combo | 3.0 | **20.52%** | 85.3% | 24%+ | **genuinely high-vol 3× sleeve** |
| 8 | allocator_blend | 1.3 | **15.81%** | 100% | 15.8% | **genuinely high-vol blend** |

**Key fact:** the levered sleeves (7,8) carry **15–22× the realized vol** of the event sleeves. That asymmetry — *real*, embedded in returns — is exactly what the correlation-only ERC could not see (it assumed unit vol for all 8 and divided out a 3×/1.3× *constant* as a stand-in).

---

## 3. Vol-aware (covariance) ERC — risk weights

ERC converged in 39 iters; **risk contributions exactly equal (12.50% each)**.

| Strategy | Ann vol | **Risk weight** | RC |
|---|---|---|---|
| breakout_xlk__mut_c382b1 | 1.0% | 11.68% | 12.50% |
| sma_crossover_qqq_regime | 0.9% | 12.07% | 12.50% |
| sma_crossover_qqq_rth | 0.9% | 11.91% | 12.50% |
| rsi_oversold_spy | 1.2% | 20.74% | 12.50% |
| volume_breakout_qqq | 0.7% | 20.37% | 12.50% |
| macd_momentum_iwm | 0.9% | 21.91% | 12.50% |
| tqqq_cot_combo | 20.5% | **0.57%** | 12.50% |
| allocator_blend | 15.8% | **0.76%** | 12.50% |

The covariance-ERC drives `w_i ≈ (1/vol_i)`-flavored weights (correlation-adjusted): the two high-vol levered sleeves collapse to **<1% risk weight** (they each contribute a full 1/8 of risk on tiny capital), and the low-vol event sleeves absorb the rest, tilted toward the *least-correlated* ones (rsi, macd, volume).

### 3a. Robustness — the one imperfect cell does NOT matter

Re-running the covariance-ERC with the **baseline** `corr_submatrix` (the documented 0.794 cell) instead of my reproduced R changes every risk weight by **≤ 0.057%**:

| Strategy | ERC w (my repro R) | ERC w (baseline R) | Δ |
|---|---|---|---|
| rsi_oversold_spy | 20.74% | 20.70% | 0.04% |
| tqqq_cot_combo | 0.57% | 0.58% | 0.01% |
| allocator_blend | 0.76% | 0.77% | 0.01% |

**The entire divergence from baseline is vol-driven, not correlation-driven** — precisely as intended. The combo↔allocator cell discrepancy is cosmetic.

---

## 4. Capital comparison & divergence metric

Two translations are shown: **pure** (raw vol-aware weight → $, no floor) exposes the mechanism; **tradeable** (with the same share-floor as baseline v2) is the comparable object.

| Strategy | Baseline $ | **Vol-aware $** (tradeable) | Δ$ | Δ% | *(pure, no-floor $)* |
|---|---|---|---|---|---|
| breakout_xlk__mut_c382b1 | 74.36 | 69.81 | −4.55 | −6.1% | 93.41 |
| sma_crossover_qqq_regime | 69.59 | 72.14 | +2.55 | +3.7% | 96.52 |
| sma_crossover_qqq_rth | 69.88 | 71.20 | +1.32 | +1.9% | 95.26 |
| rsi_oversold_spy | 159.65 | 124.04 | **−35.61** | **−22.3%** | 165.96 |
| volume_breakout_qqq (proxy) | 86.94 | 121.77 | **+34.83** | **+40.1%** | 162.92 |
| macd_momentum_iwm | 120.96 | 131.03 | +10.07 | +8.3% | 175.30 |
| tqqq_cot_combo | 160.00 | 160.00 | 0.00 | 0.0% | **4.53** |
| allocator_blend | 58.62 | 50.00 | −8.62 | −14.7% | **6.09** |
| **TOTAL** | **800.00** | **800.00** | | | 800.00 |

**Divergence metrics:**
- **Total capital reshuffled** (Σ\|Δ\|/2) = **$48.78 = 6.1% of budget**
- **Max single-strategy \|Δ%\|** = **40.1%** (`volume_breakout_qqq`, the proxy)
- Diversifier ranking: baseline non-tqqq top-3 = `[rsi, macd, volume]`; vol-aware = `[macd, rsi, volume]` → **rsi/macd swap; both remain top-2**.

---

## 5. The leverage-vs-vol double-count reasoning (the subtle part)

This is the single place a mistake hides, so it is made explicit.

- The **baseline** ran ERC on the *unit-vol correlation* matrix (it had no vols), producing pure risk weights, then translated to capital by **dividing by leverage** (3× sleeve → ⅓ the capital). Leverage was a **stand-in for the vol it didn't measure**. That's why baseline put tqqq's *pure* ERC at ~$30 before the share-floor rescued it to $160.
- The **vol-aware** ERC uses each sleeve's **actual realized return vol**. A 3×-levered TQQQ sleeve *realizes* ~20% vol **because** it is 3×-levered — **the leverage is already inside the vol.** Therefore the honest translation is **capital_i ∝ w_i directly, with NO further leverage divide.** Dividing again would double-penalize the levered sleeves.
- Consequence (visible in the *pure* column): the covariance-ERC alone already drives tqqq → **$4.53** and allocator → **$6.09** — *lower* than the baseline's pre-floor $30, precisely because realized vol is a stronger, truer penalty than the constant 3× proxy. The **share-floor** (identical to baseline v2: 2 TQQQ shares ≈ $160) then rescues tqqq to keep the 3× sleeve tradeable, and that floor is what makes tqqq's final Δ$ = 0.
- **Net:** the levered sleeves are handled essentially the same as baseline after flooring (tqqq pinned at $160; allocator $58→$50). All the actual movement is **among the 1× event sleeves**, where the vol-aware method reallocates by *true relative vol* instead of treating them as equal-vol.

---

## 6. Decision rule — explicit application

> **Pre-stated rule:** CONFIRM "no change" iff *(total reshuffled < ~10% of budget ≈ $80)* **AND** *(no single strategy moves > ~15–20% of its own base)* **AND** *(diversifier rsi/macd ranking preserved)*. Else report the vol-aware notionals as a recommended change.

| Condition | Threshold | Result | Pass? |
|---|---|---|---|
| Total reshuffled | < $80 (10%) | **$48.78 (6.1%)** | ✅ |
| Max single \|Δ%\| | < 20% | **40.1%** (volume_breakout, proxy) | ❌ |
| Diversifier ranking | rsi #1, macd top-3 | rsi #2 / macd #1 (both top-2) | ❌ (swap) |

**Mechanical verdict: MATERIAL-change** (2 of 3 sub-tests fail).

**Substantive verdict: immaterial; keep baseline.** Why the mechanical flag overstates it:
1. **It's small in dollars.** $49 of $800 is reshuffled — the book is *not* restructured. 7 of 8 sleeves move < $11 except rsi (−$36) and volume (+$35), and those two are equal-and-opposite within the diversifier bucket.
2. **The 40% move is the PROXY.** `volume_breakout_qqq`'s +40% rests on its 0.68% vol — the **lowest and least trustworthy** number in the set (its native gate fires 0 daily entries; the 1.0× relaxation is an upper-bound signal shape, not its real behavior). A 40% capital swing built on a proxy vol is not a credible mandate to move live money.
3. **The rsi cut is a time-in-market artifact, not a risk signal.** `rsi_oversold_spy` is in cash **94% of days**; its low *full-sample* vol (1.22%) is mostly "mostly flat," yet its **active** vol (5.1%) is the *highest* of the event sleeves. Full-sample-vol ERC penalizes it for sitting in cash — which is exactly backwards from why it's the crown-jewel diversifier. The baseline correlation-ERC, which overweighted rsi on its near-zero correlation, captures its diversification value **more** sensibly here. So the vol-aware "correction" to rsi is, if anything, the *less* defensible weighting.

**Conclusion:** the open refinement flagged in `ERC_CAPITAL_WEIGHTING_20260624.md §5` is resolved. "Moves weights only at the margin" is **literally too strong** (one proxy sleeve moves 40%), but the intended claim — *no meaningful book restructuring; correlation-ERC is sufficient* — **holds**. **No live config change recommended.** (Any change would be the parent's/Cyrus's call regardless; this report writes no `params.json` and no live config.)

---

## 7. Honest caveats

- **Leverage-vs-vol double-count:** addressed in §5 — vol-aware ERC embeds leverage in realized vol, so capital ∝ weight with **no** leverage divide; the levered sleeves end up floor-pinned exactly as in baseline v2.
- **`volume_breakout_qqq` is a PROXY** (volume gate 3.0→1.0). Its vol (0.68%) and thus its +40% capital swing are the **least reliable** outputs here. Its real daily-native behavior is "rarely trades."
- **Backtested vol ≠ live vol.** These are daily-resolution backtests over 2010–2026; the live book trades a 1Hour clock at small notional with few fills. The *structure* (levered sleeves are ~15–20× higher vol than event sleeves) is robust; exact coefficients will differ live.
- **Vol is trailing & full-sample, not forward.** A single 4,111-day vol per sleeve ignores regime/time-varying vol. The rsi time-in-market artifact (§6.3) is a direct symptom: full-sample vol is a poor risk proxy for sleeves that are flat most of the time. A live implementation should prefer **trailing-window, in-market-conditional** vol — which is closer to what the *correlation*-ERC + leverage-proxy already approximates for these flat sleeves.
- **`target_ann_vol` for the combo:** rebuilt at **0.25** (baseline-matrix fidelity); live `params.json` is **0.40**. At 0.40 the combo's vol rises to ~29%, dropping its ERC risk weight from 0.57% toward ~0.40% — i.e. *more* extreme, still floor-pinned at $160. Verdict unchanged either way.
- **`sma_crossover_qqq_rth`** is ≈1.00 corr with the regime variant on daily bars (RTH gate is a daily no-op) — its near-equal weight to #2 is expected, not independent diversification.

---

## 8. Provenance / no-protected-file-modified

- **Scratch (workspace root):** `_volaware_erc_series.py` (builds the 8 series → `reports/_volaware_series.json`), `_volaware_erc_compute.py` (validation gate + vols + covariance-ERC + comparison → `reports/_volaware_erc_result.json`).
- **Imported READ-ONLY:** `runner/backtest.py`, `runner/daily_bars_cache.py`, `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`, `strategies/tqqq_cot_combo/strategy.py::_get_cot_scale`, `_allocator_blend_tests.py`. Independently corroborated against the still-present `_xstrat_corr.py` (the original baseline generator) and `_book_vol_probe.py`.
- **mtime-verified UNCHANGED** (all predate this session): `runner/backtest.py`, `runner/risk.py`, `runner/daily_bars_cache.py`, `runner/allocator_paper_tracker.py`, `GATE.md`, `strategies/tqqq_cot_combo/{strategy.py,params.json}`, `strategies/volume_breakout_qqq/{strategy.py,params.json}`, `strategies/rsi_oversold_spy/strategy.py`, `backtest_daily_voltarget.py`, `_xstrat_corr.py`, `_allocator_blend_tests.py`. **No `params.json`, no `runner/*.py`, no `strategies/*`, no `risk.py`, no `GATE.md` was modified.** Writes confined to `reports/` and root `_volaware_erc*.py`.

*Artifacts: `reports/_volaware_series.json` (8 series + diagnostics), `reports/_volaware_erc_result.json` (vols, weights, capital, deltas, decision).*
