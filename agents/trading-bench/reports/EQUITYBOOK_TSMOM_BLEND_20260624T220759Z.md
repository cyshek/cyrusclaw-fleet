# EQUITY-BOOK × core4-TSMOM BLEND TEST

**UTC:** 20260624T220759Z · **Agent:** trading-bench (opus subagent) · **Scope:** paper/research only — no promotion, no cron, no trades
**Follow-up to:** `reports/MULTIASSET_TSMOM_SLEEVE_20260624T171551Z.md` (the standalone core4-TSMOM sleeve, which explicitly flagged *"run a blended test … measure whether the near-zero correlation lifts the COMBINED full-period Sharpe above the equity book alone"*).

---

## VERDICT: 🟡 AMBER — modest, robust risk-adjusted lift; helps Sharpe by de-risking, not by cutting drawdown. Shelf-with-trigger.

Adding a **20% core4-TSMOM sleeve** (X=0.80 equity book / 0.20 core4) raises the combined full-period Sharpe from **0.923 → 0.992** (**ΔSharpe +0.069**, ≈ +7.5% relative) at a raw-return cost of only **−0.17 CAGR points** (4.95% → 4.79%). The lift is **robust, not a knife-edge** — the Sharpe curve rises monotonically from X=1.00 to a broad plateau at X∈{0.85, 0.80, 0.75} and falls off smoothly. The correlation thesis holds: **corr(book, core4) = +0.046** over 4,111 common days.

**But it lands AMBER, not GREEN, on two honest grounds:**
1. **The win is vol-reduction, not drawdown-cut.** maxDD barely moves (−7.39% → −6.98%, only **+0.41 abs pts** at X=0.80). The book is *already* a shallow-drawdown low-vol ERC book (5.4% ann vol, −7.4% maxDD); core4 mostly trims ann vol (5.40% → 4.83%), which mechanically lifts Sharpe. It does **not** open a meaningfully better efficient frontier — the Sharpe gain comes with a proportional give-back of return, which is most of what "de-risking" looks like.
2. **core4 is not a universal crisis hedge.** It paid off big in the two marquee crises (2020 COVID **+4.7%**, 2022 **+2.8%**, both while the book was negative) but it **hurt in 2018-Q4** (core4 −8.71% vs book −4.56%, so the blend's Q4-2018 loss *deepens* with more core4). The diversification benefit is regime-contingent on trend persistence.

**Recommendation:** paper-track the **X=0.80 blend (20% core4)** as a candidate diversifier overlay and watch whether the 2020/2022-style crisis offset recurs out-of-sample, but do **not** wire it live on the strength of an in-sample +0.07 Sharpe that is mostly de-risking. If the goal is simply lower combined vol, "scale the existing book down" achieves most of the same maxDD relief without adding a second sleeve to operate. Promotion to live is a parent/Cyrus call.

---

## 1. Method & the book-return construction assumption

### 1.1 Ingredient A — the ERC-weighted LIVE EQUITY BOOK daily return
Built directly from the validated daily series behind the ERC / vol-aware-ERC work:
- `reports/_volaware_series.json` → `["live"]` (8 strategy names, fixed order), `["common_dates"]` (4,111 daily ISO dates **2010-02-16 → 2026-06-18**), `["returns_matrix"]` (4,111 × 8 daily returns, col order = `["live"]`).
- **Capital weights** = `reports/_erc_weights.json["capital_usd_v2_tradeable"]` (the SHIPPED LIVE allocation of the $800 budget):

| strategy | $ | w = $/800 |
|---|---:|---:|
| breakout_xlk__mut_c382b1 | 74.36 | 0.0930 |
| sma_crossover_qqq_regime | 69.59 | 0.0870 |
| sma_crossover_qqq_rth | 69.88 | 0.0874 |
| rsi_oversold_spy | 159.65 | 0.1996 |
| volume_breakout_qqq | 86.94 | 0.1087 |
| macd_momentum_iwm | 120.96 | 0.1512 |
| tqqq_cot_combo | 160.00 | 0.2000 |
| allocator_blend | 58.62 | 0.0733 |
| **sum** | **800.00** | **1.0000** |

`book_ret[t] = Σ_i w_i · returns_matrix[t][i]`.

> **⚠️ EXPLICIT CONSTRUCTION ASSUMPTION (stated honestly).** The 8 per-strategy series are **not all the same leverage/notional convention**. The 6 event sleeves are zero-cost backtested signal-shape series at ~0.7–1.2% ann vol; the 2 levered sleeves already embed their leverage (tqqq_cot_combo ~20.5% ann vol, allocator_blend ~15.8%, per `_volaware_erc_result.json["annualized_vols"]`). The capital weights `w_i` are the **honest economic mixing weights** — how much of the $800 each sleeve controls — so **capital-weighting the return series is the correct book return.** Cross-check passed: the blended book's ann vol is **5.40%**, well below the two levered sleeves' individual vols (20.5% / 15.8%) thanks to diversification + the six ~1%-vol event sleeves dragging the blend down. This is the expected signature of an honest ERC blend, not a bug.

**Book standalone full-period stats (its own 2010-02-16 → 2026-06-18 span, 4,111 days):**

| metric | value |
|---|---:|
| continuous-span Sharpe (√252) | **0.9226** |
| CAGR | **+4.951%** |
| total return | +120.0% |
| maxDD | **−7.39%** |
| ann vol | 5.40% |

This is the **BASELINE to beat.**

### 1.2 Ingredient B — the core4-TSMOM diversifier daily return
Regenerated from the validated `_tsmom_engine.run_tsmom(["DBC","GLD","TLT","UUP"], lookback_m=12, skip_m=1, weighting="ew", start_date="2008-04-01")` — DBC/GLD/TLT/UUP, 12-1 momentum long/flat, equal-weight across in-trend names, monthly rebalance, 2 bps one-way cost, **0% on idle cash**. Daily net-return series (`res["net"]`) with dates (`res["dates"]`).

**Reproduction check — matches the standalone report essentially exactly:**

| metric | regenerated | report expected | ✓ |
|---|---:|---:|:--:|
| Full Sharpe | 0.3046 | ~0.3051 | ✓ |
| CAGR | +2.677% | ~+2.68% | ✓ |
| maxDD | −24.74% | ~−24.7% | ✓ |
| corr → SPY | −0.0139 | ~−0.01 | ✓ |
| 2020 COVID | +4.7% | +4.7% | ✓ |
| 2022 | +2.8% | +2.8% | ✓ |

Reproduction is within rounding (Sharpe 0.3046 vs 0.3051 — the standalone report's number was over the full 2008-05 → 2026-06-24 span; this run ends one bar earlier on cache state, immaterial). **Series validated — safe to blend.**

---

## 2. Alignment & the load-bearing correlation

Inner-join on date intersection. Book spans 2010-02-16 → 2026-06-18; core4 spans 2008-05 → 2026-06-2x. The book is the binding (later-starting, earlier-ending) series, so the overlap **is the book's full window**:

- **n_common = 4,111 days**, span **2010-02-16 → 2026-06-18** (book loses 0 days; core4 trimmed to the book window).

> ### corr(book, core4) = **+0.046**
The whole thesis rests on this being low, and it is — essentially uncorrelated, consistent with core4↔SPY ≈ −0.014 and the book being net long-equity-beta. (Slightly positive rather than negative because the book is a *diversified low-vol* equity book, not raw SPX, so its beta to a trend-following macro sleeve is near zero rather than mirror-image.)

On the aligned window, the two sleeves standalone:

| sleeve | Sharpe | CAGR | maxDD |
|---|---:|---:|---:|
| equity book | 0.9226 | +4.951% | −7.39% |
| core4-TSMOM | 0.4110 | +3.635% | −24.74% |

(core4's aligned Sharpe 0.41 > its full-history 0.30 because the 2010+ window excludes its rough 2008-09 GFC entry; it still drags raw CAGR vs the book and carries a 3× deeper drawdown.)

---

## 3. The X-sweep (X = fraction in EQUITY BOOK, 1−X in core4-TSMOM)

Monthly-rebalanced back to the target two-sleeve mix; **2 bps one-way charged on the sleeve-level turnover** `|w_book − X| + |w_core − (1−X)|` at each month-end (debited from that day's blend return; ~196 rebalances over the span; total lifetime sleeve-rebalance cost ≤ ~0.5% of NAV at the heaviest mixes — negligible). Crisis windows are **total return of the blended book** in each window.

| X | core% | Sharpe | CAGR% | maxDD% | annVol% | 2020 | 2022 | 2018-Q4 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1.00** | 0% | 0.9226 | 4.951 | −7.39 | 5.40 | −4.7% | −3.8% | −4.6% |
| 0.95 | 5% | 0.9534 | 4.914 | −7.18 | 5.17 | −4.2% | −3.4% | −4.8% |
| 0.90 | 10% | 0.9768 | 4.874 | −7.12 | 5.00 | −3.8% | −3.1% | −5.0% |
| 0.85 | 15% | 0.9904 | 4.831 | −7.05 | 4.88 | −3.3% | −2.8% | −5.2% |
| **0.80** | **20%** | **0.9920** | **4.785** | **−6.98** | **4.83** | **−2.9%** | **−2.4%** | **−5.4%** |
| 0.75 | 25% | 0.9808 | 4.736 | −6.92 | 4.84 | −2.4% | −2.1% | −5.6% |
| 0.70 | 30% | 0.9574 | 4.684 | **−6.91** | 4.91 | −1.9% | −1.8% | −5.8% |
| 0.60 | 40% | 0.8819 | 4.571 | −7.69 | 5.22 | −1.0% | −1.1% | −6.2% |
| 0.50 | 50% | 0.7870 | 4.445 | −8.51 | 5.74 | −0.1% | −0.4% | −6.6% |

**Per-sleeve crisis behavior (why the blend numbers move the way they do):**

| window | BOOK | core4 | read |
|---|---:|---:|---|
| 2020 COVID (Feb-19→Apr-30) | −4.70% | **+4.70%** | core4 fully offsets the book — genuine crisis alpha |
| 2022 full year | −3.76% | **+2.81%** | core4 offsets ~¾ of the book's loss — the headline case |
| 2018-Q4 (Oct→Dec) | −4.56% | **−8.71%** | **core4 HURTS** — trend got whipsawed; blend loss deepens with more core4 |

---

## 4. Best blends & deltas vs X=1.00 (book only)

- **Sharpe-maximizing X = 0.80** (20% core4) → Sharpe **0.9920**.
- **maxDD-minimizing X = 0.70** (30% core4) → maxDD **−6.91%**.

Both satisfy the "meaningful diversifier weight" floor (core ≥ 10%, i.e. X ≤ 0.90).

**Deltas at the best risk-adjusted blend (X=0.80, 20% core4) vs book-only:**

| Δ vs X=1.00 | value |
|---|---:|
| **ΔSharpe** | **+0.069** (0.9226 → 0.9920, +7.5% rel) |
| **ΔmaxDD** | **+0.41 abs pts** (−7.39% → −6.98%, shallower) |
| **ΔCAGR** | **−0.17 pts** (4.951% → 4.785%) |
| ΔannVol | −0.57 pts (5.40% → 4.83%) |

**At the maxDD-minimizing blend (X=0.70, 30% core4) vs book-only:**

| Δ vs X=1.00 | value |
|---|---:|
| ΔSharpe | +0.035 |
| ΔmaxDD | +0.48 abs pts (−7.39% → −6.91%) |
| ΔCAGR | −0.27 pts (4.951% → 4.684%) |

**Robustness check (not a knife-edge):** Sharpe rises monotonically 0.9226 → 0.9534 → 0.9768 → 0.9904 → **0.9920** as core4 goes 0→20%, then declines monotonically 0.9808 → 0.9574 → 0.8819 → 0.7870. The peak is a **broad plateau** (X=0.85/0.80/0.75 all within 0.011 Sharpe of each other), exactly the shape a real diversification benefit should have — no single-X spike.

---

## 5. Decision-rule application (stated explicitly, then applied)

**The mission bar is RAW RETURN vs SPX, but this book is the risk-adjusted/diversified sleeve by design, and core4 drags raw return (CAGR +2.68% vs the book's +4.95%). So judge on the risk-adjusted axis.**

Rule (verbatim from the task):
> The blend is WORTH IT only if a meaningful diversifier weight ((1−X) ≥ 10%) either **(a)** RAISES combined full-period Sharpe vs book-only, **OR (b)** cuts maxDD by ≥ ~3–4 absolute points WITHOUT giving back more than a small slice of CAGR — AND the improvement is robust (neighbors move monotonically).

Applying it:
- **(a) Sharpe lift — YES, and robust.** +0.069 at X=0.80 (20% core4), monotone plateau. ✅ The condition is technically met.
- **(b) maxDD cut ≥ 3–4 pts — NO.** Best maxDD improvement is only **+0.48 abs pts** (X=0.70). The book's drawdown is already shallow (−7.4%); core4's diversification can't cut what isn't there. ❌
- **Raw-return cost quantification:** the best risk-adjusted blend gives up **0.17 CAGR points** (4.951% → 4.785%) for the +0.069 Sharpe. Critically, **ann vol falls 0.57 pts (−10.6% relative) while CAGR falls 0.17 pts (−3.4% relative)** — so the Sharpe gain is NOT purely proportional de-risking (return falls *less* than vol, which is the signature of a *real* (if small) diversification benefit, not just scaling the book down). That nuance is what keeps this from being a flat "scale the book down instead" result… **but the absolute size of the edge is small** (+0.07 Sharpe, in-sample), and condition (b) clearly fails.

**Why AMBER, not GREEN:** condition (a) is met but the magnitude is modest and the mechanism is dominated by vol-trimming (maxDD essentially unmoved). A GREEN ("clear combined-Sharpe lift OR strong DD cut at low cost") would want either a larger Sharpe jump or the ≥3–4pt DD cut; we get neither convincingly. The lift is real and robust enough to **not** be RED, but it is **regime-contingent** (the entire crisis-offset value rode on 2020 + 2022, and reversed in 2018-Q4) and **in-sample**. → **shelf-with-trigger.**

**Why not RED:** there *is* a robust, monotone, plateau-shaped Sharpe improvement at a sensible weight with a sub-proportional return give-back and confirmed near-zero correlation. core4 is more than a standalone shelf curio here — it does measurably improve the combined book's efficiency. That clears the RED bar.

---

## 6. Honest caveats

1. **Book series are BACKTESTED, not live.** The 6 event sleeves are zero-cost backtested signal-shape series; the 2 levered sleeves use validated vol-target/COT/allocator harnesses. None of this is realized live P&L — it's the same in-sample construction the ERC work runs on.
2. **core4 is a conservative long/flat ETF-proxy floor for true managed-futures trend.** Long/flat only, no leverage, **0% on idle cash** (real managed futures would earn collateral yield on T-bills, materially lifting CAGR in a 2022-style rate regime). The diversifier's *return* contribution here is a floor; its *correlation/crisis* contribution is the honest part being tested.
3. **In-sample over 2010-2026, no 2008 for the book.** The book series starts 2010-02-16, so the blend never sees the 2008 GFC — the single environment where a trend-following diversifier earns its largest historical keep. The intersection deliberately excludes core4's worst standalone period (2008-09) AND its best diversification opportunity. This biases the test toward a *smaller* measured benefit than a full-cycle book would show; the AMBER could be conservative.
4. **The entire crisis-offset value is concentrated in 2 windows and reversed in a 3rd.** 2020 (+4.7%) and 2022 (+2.8%) carry the diversification story; 2018-Q4 (−8.7%) is a counterexample where trend got chopped. n=2 favorable crises is thin evidence — out-of-sample crisis behavior is the key thing to watch if paper-tracked.
5. **Blend rebalance cost modeled, small.** 2 bps one-way on monthly two-sleeve turnover; lifetime cost ≤ ~0.5% NAV at the heaviest mix. Does not change any verdict. (Within-sleeve turnover/cost is already embedded in each ingredient's series.)
6. **maxDD relief ≈ "scale the book down" alternative.** If the only objective is lower combined vol/DD, holding the existing book at 80% gross + 20% cash achieves most of the maxDD relief with zero added operational complexity. The blend only beats that to the extent core4's positive-carry crisis offsets recur — which is precisely the unproven, regime-contingent part.

---

## 7. Reproducibility & file hygiene

- **Scratch (workspace root):** `_ebtsmom_blend.py` (py_compiled clean before run), `_ebtsmom_blend_results.json` (full machine-readable sweep + deltas).
- **Inputs (read-only):** `reports/_volaware_series.json`, `reports/_erc_weights.json`, `reports/_volaware_erc_result.json`, `_tsmom_engine.py`, `_tsmom_eval.py`, `_tsmom_eval_results.json`.
- **✅ NO PROTECTED FILE MODIFIED.** mtime audit confirmed: `_tsmom_engine.py` (2026-06-24 17:12), `runner/backtest.py` (06-13), `runner/fp_sharpe.py` (06-02), `runner/lane_honesty.py` (06-23), `GATE.md` (06-07), `strategies/*` (≤06-24 16:05) **all predate this session (22:07 UTC)**. (`risk.py`/`params.json` do not exist at workspace root — listed defensively in the task.) Only `_ebtsmom_*` scratch files are fresh.

---

### One-line bottom line
**🟡 AMBER.** corr(book,core4)=+0.046; book-only Sharpe 0.923 / CAGR 4.95% / maxDD −7.4%. Best blend **X*=0.80 (20% core4)**: Sharpe **0.992**, CAGR 4.79%, maxDD −6.98% → **ΔSharpe +0.069, ΔmaxDD +0.41pts, ΔCAGR −0.17pts**. Raw-return cost ≈ **0.17 CAGR pts**. Real but modest, vol-trim-driven, regime-contingent, in-sample → **paper-track at 20%, don't wire live.**
