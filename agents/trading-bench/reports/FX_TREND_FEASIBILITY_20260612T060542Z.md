# FX Trend-Following Feasibility — HONEST First Pass (per-pair single-SMA)

**Generated:** 2026-06-12 06:05 UTC · **Status:** RESEARCH / PAPER-ONLY. No leverage. No live orders, no live keys. Protected `runner/` and `strategies/` untouched; all code lives in `/tmp/fx_trend/`. Result JSON: `/tmp/fx_trend_result.json`.

**One-line verdict:** **DEAD LANE as a standalone return engine.** Best out-of-sample, unlevered, cost-adjusted result is **~1.6–1.7% CAGR / Sharpe ~0.26–0.31** for a single pair; **0 of 5 majors beat SPX raw** (SPX ≈ +592% / 9.0% CAGR same window). And critically: **costs are NOT the killer** — FX spreads are negligible exactly as hoped, but the trend *signal itself* is weak and param-unstable. No-leverage FX trend cannot clear this bench's mission bar. Its only defensible role is a low-vol, SPX-uncorrelated **diversifier sleeve**, not a money engine.

---

## 1. Method

- **Data:** Yahoo v8 daily FX (`runner/fx_bars_cache.py`, browser-UA, IP-unwalled from this VM, on-disk cache). 5 majors: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF. Spans 2003-12 → 2026-06 (AUDUSD 2006-05). **All 5 loaded; none 404/429'd.** FX has no splits/divs ⇒ raw close is the price (adjclose == close).
- **Benchmark:** `^GSPC` adjclose via `runner/daily_bars_cache.py` (same Yahoo source), buy-and-hold over each pair's own span.
- **Rule (simplest defensible trend):** `long when close_t > SMA_N(close)_t`; **long-only-or-flat** (flat below) AND **long/short** (−1 below) variants both tested.
- **Param grid (robustness, NOT cherry-pick):** N ∈ {50, 100, 150, 200}.
- **Lookahead guard:** signal computed from closes **through bar t**, position applied to **bar t+1**'s close-to-close return (1-day lag). Verified (see §6).
- **Annualization:** √252 (weekday/equity convention, per `runner.backtest.bars_per_year` — FX trades ~252 days/yr, NOT 365).

### Cost model
- `runner.backtest.CostModel` convention: `spread_bps` is **one-way**. Cost charged on `|Δweight|` of notional at each flip, subtracted from that day's return.
- **Baseline: 0.5 bp one-way = 1.0 bp round-trip** (realistic blended FX major).
- **Sensitivity grid: 0.25 / 0.5 / 1.0 bp one-way (= 0.5 / 1.0 / 2.0 bp round-trip).**

---

## 2. Per-pair results (baseline 1bp round-trip, net of cost, UNLEVERED)

Long/flat = the no-leverage default mode. "OOS" = N chosen on 2003–2017 train by Sharpe, evaluated on 2018–2026 test (best of long/flat vs long/short by OOS Sharpe).

- **EURUSD**  — LF N=200: CAGR **+0.95%**, Sharpe **0.17**, maxDD −20.5%, 134 trades · LS N=200: +1.39% / 0.18 · B&H **−3.4%** · **OOS** (long/short N=200): CAGR **+1.61% / Sharpe 0.26**
- **GBPUSD**  — LF N=150: CAGR **+0.44%**, Sharpe **0.10**, maxDD −18.0%, 198 trades · LS N=150: +1.77% / 0.24 · B&H **−22.1%** · **OOS** (long/flat N=150): CAGR **+0.25% / Sharpe 0.07**
- **USDJPY**  — LF N=100: CAGR **−0.34%**, Sharpe ≈0.00, maxDD −56.9%, 393 trades · LS N=100: −2.24% / −0.14 · B&H **+40.4%** · **OOS** (long/flat N=50): CAGR **+1.74% / Sharpe 0.31** ⚠️ (see §4 — regime luck, not stable)
- **AUDUSD**  — LF N=200: CAGR **+0.57%**, Sharpe **0.11**, maxDD −34.5%, 173 trades · LS N=200: +0.67% / 0.12 · B&H **−8.3%** · **OOS** (long/flat N=50): CAGR **−3.16% / Sharpe −0.43** (overfit collapse)
- **USDCHF**  — LF N=200: CAGR **−2.44%**, Sharpe **−0.31**, maxDD −44.4%, 241 trades · LS N=150: −3.35% / −0.28 · B&H **−42.2%** · **OOS** (long/short N=150): CAGR **−3.26% / Sharpe −0.41**

**vs SPX raw:** SPX over the common window ≈ **+592% total / +9.0% CAGR / Sharpe ~0.5+**. **0 / 5 pairs beat SPX raw** on total return. The best FX CAGR (~1.7%) is ~5× *below* SPX.

**vs Buy-and-Hold the pair:** trend does "beat B&H" for 4/5 pairs — but only because B&H the USD pairs was *negative* over this dollar-strong window (you avoided losses, you didn't make real money). Beating a losing benchmark by being mostly-flat is not edge.

---

## 3. Cost sensitivity — the headline non-finding

Best-N long/flat, full period, by round-trip spread:

- **EURUSD N=200:** 0.5bp → CAGR 0.96% · 1.0bp → 0.95% · 2.0bp → 0.92%
- All pairs: Sharpe moves **< 0.01** across the entire 0.5→2.0 bp range.

**Conclusion:** FX spreads are negligible — this confirms the *entire premise* of testing FX (the opposite of crypto, where a ~4% round-trip ate everything). **But it doesn't help**, because the signal makes so little that there's nothing for cheap costs to save. **Cost realism was the right thing to check and it came back clean; the lane still fails on signal quality.**

---

## 4. Out-of-sample (train 2003–2017 → test 2018–2026)

Param N selected on TRAIN by Sharpe, carried unchanged into TEST. Train/test split is leak-free: SMA stays warmed across the boundary; only the realized-return *date* determines train vs test membership.

- **EURUSD** (long/short, N=200): train Sh 0.16 → **test Sh 0.26** — *generalized* (selection picked the best train N and it held). The most intellectually honest "best."
- **GBPUSD** (long/flat, N=150): train Sh 0.12 → test Sh 0.07 — mild decay, still ~flat.
- **USDJPY** (long/flat, N=50): train Sh **−0.14** → test Sh **+0.31**. ⚠️ **Red flag, not a win:** the N chosen on train was a *loser* in-sample and only turned positive OOS — that's regime luck (post-2022 JPY trend), not a stable edge. Headline OOS Sharpe but zero process validity.
- **AUDUSD** (long/flat, N=50): train Sh **0.36** → test Sh **−0.43** (degradation 0.79). **Textbook overfit collapse** — looked best in-sample, died out-of-sample.
- **USDCHF** (long/short, N=150): train Sh −0.24 → test Sh −0.41. Consistently bad.

**Read:** Of 5 pairs, exactly ONE (EURUSD) shows a selection that both made sense in-sample and survived OOS, and even it is a sub-0.3 Sharpe at ~1.6% CAGR. The others are noise, luck, or collapse.

---

## 5. Robustness — plateau vs knife-edge (long/flat Sharpe across N)

- **EURUSD:** N50 −0.15 · N100 −0.17 · N150 +0.08 · N200 +0.17 → **KNIFE-EDGE** (sign flips)
- **GBPUSD:** N50 −0.20 · N100 −0.06 · N150 +0.10 · N200 +0.04 → **KNIFE-EDGE** (sign flips)
- **USDJPY:** N50 −0.04 · N100 0.00 · N150 −0.04 · N200 −0.06 → flat plateau, **all ≤ 0**
- **AUDUSD:** N50 +0.06 · N100 +0.05 · N150 +0.02 · N200 +0.11 → plateau, weakly positive
- **USDCHF:** N50 −0.40 · N100 −0.35 · N150 −0.32 · N200 −0.31 → stable plateau, **all strongly negative**

**No pair shows a broad, clearly-positive plateau.** The two pairs that look "best" at long lookbacks (EURUSD, GBPUSD) are knife-edges that are *negative* at short N — meaning the positive result hinges on a specific lookback, the hallmark of an unstable (likely spurious) signal. AUDUSD is the only weakly-positive plateau and it collapsed OOS (§4).

---

## 6. Skeptical self-check — lookahead

Ran two explicit tests (`/tmp/fx_trend/lookahead_test.py`):

1. **Same-bar leak test (EURUSD N=200):** correct next-bar engine → Sharpe **0.173 / +24.4%**. Deliberately-leaky same-bar variant → Sharpe **0.936 / +352%**. The leak inflates the result **~5×** and is in the *higher* direction. → confirms (a) our 1-day lag is correctly the conservative side, and (b) **our reported numbers are NOT contaminated** by the classic "use today's close to both signal and trade" leak. A too-good 0.9 Sharpe would have screamed leak; our honest 0.17 does not.
2. **SMA truncation-invariance:** recomputed the signal with the series cut at t (no future bars) at multiple sample dates — **identical** to the full-series signal. **PASS** — the moving average reads no future data.

I checked for lookahead specifically because the EURUSD/GBPUSD knife-edge could have hidden one; it did not. The weakness is real, not a bug masking real edge.

---

## 7. Blunt verdict

**Is there a tradeable, unlevered edge in FX trend net of realistic spreads? NO — marginal at absolute best, and not for the mission bar.**

- Best honest OOS number: **EURUSD long/short, N=200 → ~1.6% CAGR / Sharpe 0.26** (the only selection that generalized). The higher USDJPY OOS (0.31) is regime luck and should be discounted.
- **0/5 beat SPX raw**, by a factor of ~5× on CAGR. A no-leverage FX book runs at ~5–7% vol and structurally cannot out-*return* a 16%-vol equity index that compounded for two decades.
- **Costs are not the problem** (FX spreads ≈ negligible, confirmed across 0.5–2.0bp). The problem is a weak, knife-edge trend signal that half the pairs can't even get the *sign* right out-of-sample.

**What would have to be true to pursue it anyway:**
1. **Leverage** (rail-forbidden here). At ~5–6% unlevered vol, you'd need ~2.5–3× just to reach SPX *volatility*, and even then Sharpe ~0.2–0.3 means the levered return is mediocre with fat drawdowns. For context only (clearly NOT the verdict): the best pair's ~1.6% unlevered CAGR scales to roughly ~3% at 2× / ~8% at 5× *gross of borrow/financing and ignoring the magnified −20%+ drawdowns* — still sub-SPX and far riskier. **Leverage does not rescue this.**
2. **A basket, not single pairs** — diversifying 6 majors lifts Sharpe via decorrelation (the prior `FX_LANE_20260609` basket got the full-period maxDD down to −18% at ~6.4% vol). But that prior work *also* found the basket at only +0.30% CAGR — same conclusion: diversifier, not engine.
3. **A genuinely uncorrelated role.** The one real, defensible property (from `FX_LANE_20260609`): FX trend is **negatively correlated to SPX (−0.14)** and was **positive in 2008 + 2020 crises**. As a 5–10% crisis-hedge sleeve it has portfolio value; as a standalone return engine it's dead.

**Recommendation: DEAD LANE for standalone return. Do NOT build an FX-trend strategy chasing the mission bar.** If FX stays on the board at all, it's only as a small, uncorrelated, low-vol diversifier/crisis-hedge sleeve — and that decision belongs to portfolio construction, not to this return-bench. This first-pass single-SMA test corroborates the earlier `FX_LANE_20260609` basket finding from an independent angle (per-pair, proper N-grid, clean train/test split): the absence of tradeable unlevered FX-trend edge is robust.

---

*Artifacts: driver `/tmp/fx_trend/fx_trend_bt.py`, lookahead test `/tmp/fx_trend/lookahead_test.py`, full results `/tmp/fx_trend_result.json`. Prior related: `reports/FX_LANE_20260609.md`.*
