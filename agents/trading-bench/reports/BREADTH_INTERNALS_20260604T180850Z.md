# BREADTH / MARKET-INTERNALS — SPY timing overlay

**UTC:** 20260604T180850Z
**Lane:** MARKET-BREADTH / INTERNALS as a SPY long-or-cash timing overlay (grow-to-10 seat; the last real swing of the overnight session).
**Signal substrate:** the 40-name large-cap universe from `reports/XSEC_UNIVERSE_20260604T082828Z.md` (exact set reused). Breadth = cross-sectional health of those 40 names; the only INSTRUMENT traded is **SPY** (spot, long-or-cash, exposure ≤ cash — no margin/short/derivatives).
**Verdict: RELABEL-REJECT.** Breadth is mechanically coupled to SPY trailing momentum (corr **+0.56 to +0.74**); the one headline number that "breaks 0.5" (+0.848) is a single-definition / single-lookback defensive-trend filter whose entire edge is dodging the 2022 bear, with a near-zero information ratio (+0.13) and zero forward predictive content (fwd-1d corr ≈ −0.01). It **confirms the ~0.5 ceiling**; it does not break it.

---

## 1. RELABEL-vs-vol-and-momentum (THIS DECIDES EVERYTHING — read first)

Per the brief, breadth only earns a real test if it is measurably ORTHOGONAL (low corr) to BOTH (a) SPY trailing realized vol and (b) SPY trailing return/momentum. I computed both at the SIGNAL level, on the aligned common dates, BEFORE trusting any backtest. SPY trailing-vol lookback = 20d; SPY trailing-return lookback = 20d. (`reports/_breadth_relabel_diag.py` → `_breadth_relabel_corrs.json`.)

| breadth signal / z-window | n aligned | corr(breadth_z, **SPY vol**) | corr(breadth_z, **SPY momentum**) | corr(breadth_z, **SPY fwd 1-day ret**) |
|---|---:|---:|---:|---:|
| pct_above_50sma  / z60  | 1363 | −0.073 | **+0.614** | −0.014 |
| pct_above_50sma  / z120 | 1303 | −0.176 | **+0.707** | −0.017 |
| pct_above_200sma / z60  | 1213 | −0.147 | **+0.617** | −0.014 |
| pct_above_200sma / z120 | 1153 | −0.260 | **+0.557** | −0.010 |
| ad_line          / z60  | 1404 | +0.113 | +0.403 | −0.020 |
| ad_line          / z120 | 1334 | −0.070 | **+0.735** | −0.010 |

**Read:**
- **Orthogonal to VOL? YES** — |corr to SPY realized vol| is low everywhere (−0.26…+0.11). Breadth is NOT a relabel of the vol-level lane. Good — that's the one corpse it avoids.
- **Orthogonal to MOMENTUM? NO — this is the kill.** corr(breadth_z, SPY trailing return) is **+0.40 to +0.74**, i.e. moderate-to-high for EVERY candidate. Breadth and SPY price trend are mechanically coupled exactly as the brief warned (more names above their MA ⇔ price has been rising). The *only* cell with corr < 0.5 (ad_line/z60, +0.40) is also the *weakest-signal* cell; every breadth definition strong enough to matter is ≥ +0.56 to momentum.
- **Forward predictive content? ~NONE.** corr(breadth_z, SPY forward 1-day return) ≈ **−0.01 to −0.02** across the board. Breadth correlates with the PAST trend (the relabel), not the FUTURE — it carries essentially no leading information about SPY's next move. A genuine market-internals "leads-the-index" effect would show a non-trivial positive forward corr; here it is statistical zero.

**Adjudication (same standard used to reject the dispersion lane r=0.65→vol and the macro-nowcast lane tonight):** high momentum coupling + zero forward content ⇒ **breadth is a relabel of the already-dead SPY-momentum/trend lane.** Per the brief this is REJECT *regardless of Sharpe*. Everything below is the confirmatory backtest — it does not rehabilitate the signal.

---

## 2. Signal definitions (causal, no-lookahead)

`strategies_candidates/breadth_internals/strategy.py` — single-name {SPY} fractional-deployment sleeve (same construction proven by `vol_regime_spy_prop`: $1000 rail, undeployed notional = idle cash in NAV, deploy a fraction to SPY; resize via close-then-rebuy with `resize_band` hysteresis). The breadth SIGNAL replaces the vol gauge:

- **pct_above_50sma / pct_above_200sma** — % of the 40 names whose close on date *d* is above that name's OWN SMA(50 / 200) computed over the trailing window ending at *d* (denominator = names with enough history that day). Z-scored over a trailing `z_lookback`.
- **ad_line** — advance-decline line: cumulative Σ(#up − #down) day-over-day across the 40 names; z-score its trailing SLOPE (Δ over `ad_slope_lb`) so the cumulative drift doesn't dominate.

**No-lookahead:** the breadth series is precomputed once over the 40-name panel, but each date *d*'s value uses only closes/SMAs with t ≤ *d*; at decision time we read breadth[as_of] where `as_of` is the current VISIBLE SPY bar date (harness hands bars t ≤ clock_t). Harness fills NEXT tick ⇒ **breadth(d) → trade SPY(d+1)**, strictly causal. Cost model ON (`CostModel.alpaca_stocks`).

**Survivorship caveat (flagged, not hidden):** the 40 names are a FIXED set known to survive to 2026 → breadth reads OPTIMISTICALLY healthy (a real point-in-time index would be unhealthier, with delistings/fallen-angels dragging breadth down). This biases the test toward breadth looking BETTER than reality; a REJECT under that bias is only reinforced.

---

## 3. Sweep (pre-committed BEFORE looking at results) — plateau vs knife

Grids (lookbacks × thresholds) pre-committed in `reports/_breadth_driver.py`; results in `_breadth_results.json`. FP = canonical `fp_continuous_sharpe` over the 8-window panel.

**BH-SPY bench on THIS panel (the bar to beat, risk-adjusted): FP-cont +0.316.** (Lower than the +0.46 the universe memo cited because the 320-day warmup shifts each window's visible start; the bench computed on the identical panel as the strategy is +0.316 — that is the honest apples-to-apples bar.)

| sweep family | n cells | max FP | median FP | min FP |
|---|---:|---:|---:|---:|
| pct50_binary  | 12 | +0.257 | +0.101 | −0.246 |
| pct50_prop    |  8 | +0.130 | +0.051 | −0.073 |
| **pct200_binary** | 12 | **+0.848** | +0.634 | +0.230 |
| ad_binary     | 16 | +0.550 | +0.285 | +0.124 |

**Only pct_above_200sma binary clears 0.5 — and it is a KNIFE, not a plateau:**
- The 12 pct200 cells split cleanly by ONE parameter, `z_lookback`: all six **z120** cells cluster +0.634…+0.848 (median ~0.77); all six **z60** cells cluster +0.230…+0.544 (median ~0.30). **Halving the z-window halves the Sharpe.** That is a lookback cliff, not a stable ridge.
- It is also DEFINITION-fragile: the two *other* breadth definitions (pct50, ad_line) never exceed +0.55, and pct50 — the textbook "breadth thrust" input — tops out at a feeble **+0.257** (below BH). A signal whose result swings from 0.26 to 0.85 purely on which breadth flavor + which lookback you pick is overfit by the brief's own definition ("a single-cell spike = overfit, REJECT").

---

## 4. Headline cell, honestly: pct200/z120/enter+0.25/exit−0.25 — FP +0.848

This is the single best cell. I report it in full because it superficially "beats 0.5 and beats BH," and then show why that is a mirage.

- **FP-cont Sharpe +0.848** vs BH-SPY **+0.316** on the same panel. Avg deployment 0.48 (deploys meaningfully — not a pure cash-mirage on the deployment axis).
- **SPY-relative (`runner.spy_relative`, concatenated panel, 252 bars/yr):** strat ann **+7.57%**, SPY ann **+4.16%**, **excess +3.40%/yr**, **information ratio +0.13**, n=2226.
  - **IR +0.13 is the tell.** An information ratio of ~0.13 means the +3.4% excess is NOT a reliable, repeatable edge — it is within tracking noise. A genuine timing skill shows IR well north of 0.3. The high FP is being manufactured by ONE regime, not by consistent out-performance.

### 4a. Per-window decomposition — the edge is "dodge 2022," nothing else
(`reports/_breadth_lowo.py` → `_breadth_lowo.json`.)

| window | regime | breadth ret | BH ret | edge |
|---|---|---:|---:|---:|
| 2022-H1 | **bear** | +10.24% | −9.21% | **+19.44%** |
| 2022-Q3 | **chop** | +1.36% | −19.56% | **+20.93%** |
| 2023-H1 | recovery | +5.32% | −8.23% | +13.55% |
| 2023-Q3 | chop | +7.97% | +0.13% | +7.84% |
| 2024-Q2 | **bull** | +15.76% | +29.77% | **−14.01%** |
| 2025-Q1 | bear | +0.99% | +8.00% | −7.00% |
| 2025-Q3 | bull | +13.36% | +19.02% | −5.67% |
| 2026 | **bull** | +12.99% | +27.89% | **−14.91%** |
| | | | **beats BH 4/8** | |

The profile is the unmistakable signature of a **defensive de-risk filter**: huge wins in the 2022 bear/chop (+19–21%), big give-ups in bull legs (−14–15%). Breadth isn't *predicting* — it's *de-risking when price/vol already turned down*, which is rewarded on a panel anchored by a violent 2022 bear. **Beats BH on only 4/8 windows**; net risk-adjusted "edge" is a regime artifact.

### 4b. Leave-one-window-out (LOWO) — the +0.848 is propped by 2022, killed by bulls
Full-panel FP +0.848. Dropping each window:
- drop 2024-Q2 **bull** → +0.740 (−0.108, the window that hurts it most), drop 2026 bull → +0.768, drop 2025-Q3 bull → +0.772 — bull windows DRAG it down.
- drop 2023-H1 → +0.956, drop 2023-Q3 → +0.948, drop 2025-Q1 → +0.915, drop 2022-Q3 → +0.914 — removing chop/recovery RAISES it.
The cell's whole identity is "be defensive"; it lives or dies on whether the panel is bear-heavy. That is regime-fitting, not a stationary signal.

### 4c. Decisive control — breadth vs SPY's OWN 200-SMA trend (no cross-section at all)
(`reports/_breadth_control_spytrend.py` → `_breadth_control_spytrend.json`.) Same sleeve + same z/threshold/hysteresis machinery, signal = z-score of (SPY close / SPY SMA200 − 1) — **zero breadth, zero cross-section**:
- SPY-own-trend control tops out at **FP +0.446** (best at sma=50/z120; the 200SMA/z120 variants never de-risk, dep≈1.03, so they just ≈ BH +0.316).
- So breadth's +0.848 DOES exceed the naive single-name trend control (+0.446) — i.e. breadth is not a *trivially identical* relabel of SPY's own 200-SMA. **BUT** the gap is entirely the 2022 windows (§4a), where the 40-name breadth happened to roll over slightly earlier/cleaner than SPY's own price — a one-bear timing fluke, consistent with the +0.56 momentum corr and the ≈0 forward corr. It is a *better-tuned defensive filter on one historical bear*, not orthogonal forward information.

---

## 5. Gate-discipline scorecard

| Check | Best breadth cell (pct200/z120) |
|---|---|
| Honest FP-cont Sharpe | +0.848 |
| ≥ 1.0 gate front door | ❌ (0.85) |
| Beat BH-SPY risk-adj (FP, same panel) | ✅ on paper (0.85 > 0.316) — but see relabel/IR |
| Beat BH-SPY per-window | 4/8 (coin-flip) |
| **RELABEL guard — corr to SPY momentum** | ❌ **+0.557 (signal-level); fwd-1d corr ≈ −0.01** |
| RELABEL guard — corr to SPY vol | ✅ low (−0.26) |
| Information ratio (excess reliability) | ❌ **+0.13 (noise-level)** |
| Plateau vs knife | ❌ **KNIFE** (z120 0.85 vs z60 0.30; pct50/ad never >0.55) |
| Edge source | ❌ one-regime (dodge-2022) defensive filter, LOWO-confirmed |
| Trade count | ✅ 56 |
| Instrument MaxDD | ✅ ~−0.0% (mostly cash/idle in stress) |

Front door (≥1.0) fails outright. Even granting the on-paper BH beat, it is disqualified by the relabel corr, the noise-level IR, the knife-edge, and the single-regime decomposition — every overfit/relabel tripwire in the brief fires.

---

## 6. Verdict & relation to the ceiling

**RELABEL-REJECT.**

1. **Relabel of SPY-momentum/trend (primary).** Breadth_z correlates +0.56…+0.74 with SPY trailing return and ≈ −0.01 with SPY forward return — it encodes the *past* price trend, not future information. That is precisely the already-dead momentum lane in cross-sectional clothing. Per the brief, high momentum corr ⇒ REJECT regardless of Sharpe.
2. **The one number that breaks 0.5 (+0.848) is overfit/regime-luck.** It is single-definition (pct200 only; pct50 = +0.26), single-lookback (z120 only; z60 = +0.30 → knife), has a noise-level information ratio (+0.13), and its entire excess is a defensive dodge of the 2022 bear (LOWO + per-window confirmed) — the SAME defensive payoff the vol-level lane (+0.54) already monetizes when vol spikes.
3. **Orthogonality scorecard:** orthogonal to VOL ✅ but NOT to MOMENTUM ❌. The brief required low corr to BOTH. One pass + one fail = relabel, not a clean orthogonal signal.

**Does breadth break the ~0.5 SIGNAL ceiling? NO — it confirms it.** The only cell above 0.5 is a defensive trend-filter relabel with zero forward content; the genuinely breadth-specific, lookback-robust signal sits at ~0.26–0.55, right on/under the ceiling. This is the **11th independent data point** reinforcing the ~0.5 FP-cont Sharpe SIGNAL ceiling on the 2020-07→2026 free-IEX daily surface. Market internals — structurally different *information* though they are — do not, on this surface and horizon, carry leading risk-on/risk-off content that SPY's own price/vol lacks; the apparent edge is the same de-risk-in-stress payoff already mapped, mechanically tied to the price trend.

**ZERO promotion authority exercised.** This is a clean REJECT (relabel-reject, not a near-miss) → within autonomous authority, no Cyrus/main escalation required. An honest REJECT is the expected and valuable outcome here.

---

## 7. Honest limitations
- **Survivorship bias (optimistic)** §2 — only reinforces the REJECT.
- **8-window / ~5.5yr single broad bull-with-dips macro era.** Breadth's classic evidence (e.g. Zweig breadth thrust off 2008/09 washouts) sits in pre-2020 history unobtainable on the free IEX tier. A genuinely different/longer EVAL SURFACE — not another signal transform — remains the standing recommendation.
- **Daily close breadth only.** Intraday breadth (tick/up-vol vs down-vol, TICK/TRIN) and a true point-in-time index membership (survivorship-free) are untested and would be the only honest next probes for breadth specifically — but they require data this tier doesn't have.
- The +0.848 cell is reported for completeness and explicitly NOT endorsed; it would be a textbook overfit promotion.

**Protected files md5-verified UNCHANGED at start and finish:** `runner.py` 4be185e4…, `backtest.py` 9444ee5e…, `backtest_xsec.py` 2278a4c8…, `risk.py` e4c227e0….

**Artifacts:** `strategies_candidates/breadth_internals/{strategy.py,params.json}`, `reports/_breadth_relabel_diag.py` + `_breadth_relabel_corrs.json`, `reports/_breadth_driver.py` + `_breadth_results.json`, `reports/_breadth_control_spytrend.py` + `_breadth_control_spytrend.json`, `reports/_breadth_lowo.py` + `_breadth_lowo.json`.
