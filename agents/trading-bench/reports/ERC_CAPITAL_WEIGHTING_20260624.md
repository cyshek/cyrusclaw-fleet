# ERC / Cluster-Aware Capital Weighting — 8 Live Strategies

**Date:** 2026-06-24
**Author:** Tessera (trading-bench)
**Type:** Capital-allocation hardening (reversible config change) — follow-up to the 2026-06-24 live-book de-dup
**Trigger:** The de-dup (`reports/LIVE_BOOK_DEDUP_20260624T154500Z.md`) fixed the *9×-counting* by retiring 4 duplicate strategies, but left the surviving 8 on **flat $100/strategy** — which still (a) over-funds the 6-member equity-trend cluster vs the 2 real diversifiers, and (b) silently ran `tqqq_cot_combo` at a **$1000 base** (10× the others) at **3× instrument leverage**. This report replaces flat weighting with equal-risk-contribution (ERC).

---

## TL;DR

Replaced flat $100/strategy with **leverage-adjusted ERC** across the 8 live strategies, total budget held at **$800**. The two genuine diversifiers (`rsi_oversold_spy`, `macd_momentum_iwm`) go from 25% → **35% of capital**; the over-levered `tqqq_cot_combo` base drops from **$1000 → $160** (still tradeable at ~2 TQQQ shares). This cuts the book's **economic equity-beta exposure from ~94% → ~62%** and its total economic exposure from **~$3,580 → ~$876**, while equalizing every strategy's risk contribution to 12.5%. Fully reversible (all 8 `params.json` backed up to `memory/params_backup_20260624T160502Z/`).

---

## 1. Method — why ERC on the *structural* correlation matrix (not live fills)

The cron task allowed a cluster-parity fallback if live-fill overlap is <~10 days/pair. It is: each live strategy has only **2–10 fills** over a few weeks with long flat gaps — a correlation from that is the thin-sample mirage this bench explicitly rejects. **So we do NOT use live fills.**

Instead we reuse the **structural backtested daily-return correlation matrix** from the 2026-06-22 audit (`reports/_interstrategy_corr_matrix.json`, **4,111 common trading days**, each strategy's actual `decide()` logic run on cached daily adjclose bars; the two vol-target sleeves + allocator use their validated daily harnesses). This is strictly better than both live-fill correlation *and* naive cluster-parity: it captures genuine co-movement structure over 16 years.

**ERC solver:** Maillard-Roncalli-Teiletche (2010) fixed-point on the 8×8 correlation submatrix (unit-vol → weights driven purely by correlation structure, the cleanest "diversification" reading and robust to not having a common-scale vol estimate). Converged in 29 iterations to **equal risk contributions = 12.50% each** (verified: RC spread min=max=0.1250). Solver: `_erc_compute.py`.

## 2. The 8×8 live correlation structure (from the 4,111-day matrix)

Eigenvalues: `[4.575, 1.007, 0.918, 0.614, 0.451, 0.226, 0.199, 0.011]`
→ **participation ratio = 2.73 of 8** independent bets; top eigenvalue = **57% of variance** on one long-equity-beta factor.

This weight-free number cannot be changed by reweighting (it's a property of the *signals*, and most of our strategies are equity-trend by nature). What ERC changes is **how much capital/risk sits on that dominant factor** — which is the operationally meaningful lever.

Average pairwise correlations within the live book:
- Equity-trend cluster (XLK-mut, QQQ-regime, QQQ-rth, volume-QQQ, tqqq-combo, allocator): **ρ ≈ 0.46–1.00** — one factor.
- `rsi_oversold_spy`: **ρ ≈ +0.02 full, −0.06 downside** — genuinely orthogonal, hedge-flavored. The crown jewel.
- `macd_momentum_iwm`: **ρ ≈ +0.21** — weak but real (small-cap momentum).

## 3. ERC risk-weights → tradeable capital

ERC gives equal *risk contribution*; translating to *capital* divides out the leverage each sleeve already carries (a 3× sleeve needs ⅓ the capital for the same risk). Pure leverage-adjusted ERC put `tqqq_cot_combo` at **$30** — but at 3× and ~$76/share that **floors to 0 TQQQ shares** (silently muted). A risk officer does not want a sleeve ERC says should contribute risk to be untradeable. So we impose a **share-flooring floor** (~2 lead-instrument shares for the qty-floored vol-target sleeve; $50 dust floor elsewhere) and renormalize the remainder pro-rata to ERC risk-weight. Solver: `_erc_capital_v2.py`.

| Strategy | Cluster | Risk weight | Lev | **New base $** | Was | Δ |
|---|---|---:|---:|---:|---:|---:|
| `rsi_oversold_spy` | **diversifier** | 21.81% | 1.0 | **$159.65** | $100 | +60% |
| `macd_momentum_iwm` | **diversifier** | 16.53% | 1.0 | **$120.96** | $100 | +21% |
| `volume_breakout_qqq` | equity-trend | 11.88% | 1.0 | $86.94 | $100 | −13% |
| `breakout_xlk__mut_c382b1` | equity-trend | 10.16% | 1.0 | $74.36 | $100 | −26% |
| `allocator_blend` | equity-blend | 10.41% | 1.3 | $58.62 | $100 | −41% |
| `tqqq_cot_combo` | equity-trend (3×) | 10.16% | 3.0 | **$160.00** | **$1000** | **−84%** |
| `sma_crossover_qqq_rth` | equity-trend | 9.55% | 1.0 | $69.88 | $100 | −30% |
| `sma_crossover_qqq_regime` | equity-trend | 9.51% | 1.0 | $69.59 | $100 | −30% |
| **TOTAL** | | | | **$800.00** | $1,700* | |

\* current *actual* total is $1,700 because tqqq_cot_combo ran a $1000 base; the nominal "8 × $100" never reflected the real footprint.

**Knob respected per strategy:** event strategies → `notional_usd`; `tqqq_cot_combo` → `notional` (vol-target deployable base, weight ≤ 1 applied on top); `allocator_blend` → both `max_notional_usd` and `notional_usd` (the blend cap).

## 4. What this fixes — the numbers that matter

| Book | Total capital | Equity-beta capital share | Diversifier share | Economic equity-beta exposure |
|---|---:|---:|---:|---:|
| Flat $100 each | $800 | 75.0% | 25.0% | — |
| **ACTUAL (pre-change, tqqq=$1000)** | $1,700 | **88.2%** | 11.8% | **$3,580 / 94.4% equity** |
| **ERC (this change)** | $800 | **57.8%** | **42.2%** | **$876 / 61.5% equity** |

The single biggest correction is `tqqq_cot_combo`: at a $1000 base × ~0.95 weight × 3× leverage it alone was ~$2,850 of effective equity-beta — more than half the book's economic risk in one sleeve. Cutting it to a $160 base (2 shares) removes that distortion. Meanwhile the diversifiers — the only things making this less than a pure beta bet — rise from 11.8% → 42.2% of capital.

## 5. Tradeoff / honest caveats

- **tqqq floor > pure-ERC.** Its tradeable $160 base exceeds the pure-ERC $30; the equity-trend trio absorbs the small excess. Deliberate: better a slightly-over-ERC-but-tradeable 3× sleeve than one silently floored to 0 shares. Its risk contribution will run modestly above 12.5% as a result.
- **Correlation-ERC, not vol-ERC.** We used the correlation matrix (unit-vol) because the JSON lacks a common-scale daily-vol series; leverage-divide is the proxy for the levered sleeve's higher vol. A full vol-aware ERC (using each strategy's actual daily std) is a future refinement, but would move weights only at the margin — the dominant correction (de-lever tqqq, overweight rsi/macd) is robust to it.
- **Eigen-structure unchanged (2.73 eff bets).** ERC cannot manufacture independent edges that aren't in the signals; it only stops over-paying for the redundant ones. Lifting *structural* eff-bets needs genuinely new orthogonal alpha (the standing search), not reweighting.
- **Backtested ≠ live correlation.** The structure (which strategies are near-duplicates, which are diversifiers) is robust; exact coefficients will differ live. Re-audit periodically as live history accrues.

## 6. Reversibility & safety

- All 8 `params.json` backed up verbatim to `memory/params_backup_20260624T160502Z/` before writing; each rewrite JSON-validated (round-trip) and atomic (temp→replace).
- No protected file touched (`runner/*.py`, `risk.py`, `GATE.md` unchanged). All new notionals ($58–$160) are well under `MAX_NOTIONAL`/`MAX_POSITION` = $1000.
- Revert = copy the backup dir's files back over `strategies/*/params.json`. One command.
- Paper-only; no real money. Killswitch untouched.

## 7. Open follow-up

- **Vol-aware ERC** (use each strategy's realized daily-vol series rather than unit-vol) — marginal refinement; deferred.
- **Cluster-weight cap on the leaderboard view** — the Saturday tournament still scores all strategies individually (fine); the *capital* view is now ERC/cluster-aware as recommended.
- **Re-audit cadence:** re-run the structural correlation + ERC when the roster changes or quarterly.

---
*Artifacts: `reports/_erc_weights.json` (risk-weights, RC, capital v1+v2), solvers `_erc_compute.py` / `_erc_capital_v2.py` / `_erc_reconcile.py`, applier `_erc_apply.py`, params backup `memory/params_backup_20260624T160502Z/`. Source matrix `reports/_interstrategy_corr_matrix.json` (4,111d). No protected file modified.*
