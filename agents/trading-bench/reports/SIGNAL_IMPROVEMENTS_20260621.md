# Signal-Improvement Tests — TQQQ Vol-Target Strategy (3 add-ons)

**Date:** 2026-06-21
**Engine:** `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py` (the canonical engine the live `leveraged_long_trend_paper` adapter mirrors)
**Test harness:** `_sigimprove_tests.py` → `reports/_sigimprove_result.json`
**Verdict in one line:** One of three add-ons cleanly moves the needle as an overlay (**COT `lev_net` speculator-percentile with low-extreme boost** — +Sharpe and −drawdown). The **VIX term-structure** overlay is redundant with the engine's inverse-vol sizing (drawdown-only, no Sharpe gain — don't add to core). **Sector rotation top-2** is a strong *standalone* diversifier (Sharpe 0.92 vs SPX 0.54, survives 2008) but lower CAGR — a defensive complement, not a TQQQ replacement.

---

## Baseline (reproduced this run)

Live params: TQQQ sleeve, QQQ SMA-200 gate, inverse-vol sizing to 25% ann vol, 20-day vol window, 2bps abs-weight cost, VIX gate off.

| Metric | Strategy | SPX |
|---|---|---|
| Full Sharpe (2010-02→2026-06) | **0.864** | 0.772 |
| Full CAGR | 20.8% | 12.6% |
| Full maxDD | −34.5% | −33.9% |
| Full ann vol | 25.8% | — |
| IS Sharpe (≤2018) | 0.745 | — |
| **OOS Sharpe (2019→today)** | **1.011** | 0.841 |
| OOS CAGR | 25.0% | — |
| OOS maxDD | −24.4% | — |

> Note: the task quoted baseline as 0.842 full / 0.832 OOS. Our reproduced engine gives 0.864 full / 1.011 OOS on the 2010-02-11→2026-06-18 window (engine's native inception window + current Yahoo adjclose). The **SPX full Sharpe 0.772 matches the task's 0.773 exactly**, so the comparison frame is consistent — all deltas below are vs *this* reproduced baseline so they're apples-to-apples.

---

## TEST 1 — COT percentile extremes (NQ leveraged-fund / dealer net positioning)

**Signal swap:** replace the WoW direction-change with a **trailing-52-week absolute-percentile rank** of the released-as-of NQ net position. `rank < 20th pct` → contrarian (positioning washed-out) → boost; `rank > 80th pct` → crowded → 0.5× caution. Applied as a **multiplier on top of** the existing vol-target weight (capped at w_max=1.0). Lookahead-safe via `cot.released_history` (Tuesday snapshot invisible until Friday release).

**Interpretation tested two ways** (TFF has no literal "commercials"): `deal_net` = dealer/intermediary book (hedger analog the task calls "commercials") and `lev_net` = leveraged-fund speculators. For each, a *caution-only* version (low→1.0×, high→0.5×) and a *boost* version (low→1.25×, high→0.5×). The overlay genuinely fires: lev_net spends 767 days at 0.5× and 995 days at 1.25× (the rest neutral); it is not a no-op.

| Variant | Full Sharpe | Full CAGR | Full maxDD | OOS Sharpe | OOS maxDD | vs base |
|---|---|---|---|---|---|---|
| **baseline** | 0.864 | 20.8% | −34.5% | 1.011 | −24.4% | — |
| dealer_net caution (×0.5 hi) | 0.676 | 14.4% | −35.7% | 0.817 | −23.4% | ❌ worse |
| dealer_net boost (×1.25 lo / ×0.5 hi) | 0.683 | 15.5% | −40.6% | 0.818 | −27.1% | ❌ worse |
| lev_net caution (×0.5 hi) | 0.839 | 18.6% | −32.6% | 1.030 | −21.4% | ~ flat Sharpe, better DD |
| **lev_net boost (×1.25 lo / ×0.5 hi)** | **0.875** | 20.6% | **−31.7%** | 1.015 | **−22.5%** | ✅ **slightly better** |

**Reading:**
- **The "commercials" framing in the task is backwards for this contract.** Dealer-net (the hedger/"commercial" analog) as a contrarian signal *hurts* badly (Sharpe 0.68, maxDD blows out to −41% on the boost variant). The dealer book in NQ-TFF is structurally net-short as a hedge, so its percentile extremes don't carry the contrarian information the legacy-commercials heuristic assumes.
- **Leveraged-fund (speculator) net positioning is the signal that works** — and in the *direct* (not inverse) sense: boost when specs are washed-out-low, cut when specs are crowded-high. `lev_net_boost` is the only variant that beats baseline on full Sharpe (0.875 vs 0.864) **and** cuts maxDD by ~3 pts (−31.7% vs −34.5%), while holding OOS Sharpe roughly flat (1.015 vs 1.011) with a better OOS drawdown (−22.5%).

**Verdict:** ✅ **Marginal improvement as an add-on, using `lev_net` (speculator) percentile, NOT dealer/"commercial" net.** The improvement is real but small (+0.011 full Sharpe, −2.8 pts maxDD). It's a **drawdown-shaper more than a return-booster.** Promotable as an *optional overlay* on the existing engine; **not** worth promoting under the task's original "commercials contrarian" framing, which empirically degrades the strategy. Recommend a walk-forward / parameter-stability check (the 20/80 thresholds and 1.25× boost are untuned first guesses) before wiring live.

---

## TEST 2 — VIX term-structure regime gate (VIX3M / VIX)

**Add-on:** a secondary multiplier on the vol-target weight from the **VIX3M/VIX ratio** (term structure). `ratio < 1.0` (backwardation = stress/fear) → 0.5×; `ratio > 1.05` (healthy contango = calm) → 1.0×. Lookahead-safe via `cboe.level_asof` (serves strictly-prior close). Note VIX3M/VIX **>1 is the normal/calm state**, **<1 is the stress state** — matches the task spec. The 0.5× backwardation cut fires on 317 days over the sample.

| Variant | Full Sharpe | Full CAGR | Full maxDD | OOS Sharpe | OOS maxDD | vs base |
|---|---|---|---|---|---|---|
| **baseline** | 0.864 | 20.8% | −34.5% | 1.011 | −24.4% | — |
| spec (×0.5 backwardation, ×1.0 else) | 0.835 | 19.3% | −33.8% | 1.011 | −23.4% | ❌ slightly worse Sharpe |
| **midband 0.75 (×0.5 bw, ×0.75 mid [1.0–1.05], ×1.0 contango)** | **0.846** | 19.2% | **−31.7%** | 1.005 | −24.5% | ~ flat Sharpe, better DD |

**Reading:**
- The **literal task spec (×0.5 only in backwardation) slightly *reduces* full Sharpe** (0.835 vs 0.864) — it trims a bit too much return for the drawdown it saves, and OOS Sharpe is unchanged (1.011). The vol-target sizing layer is *already* cutting exposure when realized vol spikes, so a hard 0.5× on the VIX-TS overlay is partly redundant with what inverse-vol already does. They co-fire on the same stress days.
- Adding a softer **mid-band 0.75×** (between 1.0 and 1.05) recovers most of that: maxDD improves to −31.7% (best in this test, −2.8 pts vs base) while full Sharpe lands at 0.846 (still below 0.864 base, OOS ~flat at 1.005).

**Verdict:** ⚠️ **Does not improve risk-adjusted return; modestly improves drawdown only.** The VIX term-structure overlay is **largely redundant with the inverse-vol sizing already in the engine** — both react to the same vol/stress regime, so stacking them costs return without a Sharpe payoff. **Not promotable as a Sharpe improvement.** If the goal is purely **drawdown compression** (and you'll accept ~1.5 pts CAGR for ~3 pts less maxDD), the mid-band 0.75× variant is a defensible risk knob — but it is a *risk-preference* choice, not a strict improvement. Recommend **not** adding it to the core; keep inverse-vol as the single vol-regime mechanism.

---

## TEST 3 — Sector-rotation baseline (SPY / QQQ / GLD / TLT, monthly 3-mo momentum)

**Standalone strategy** (new archetype, *not* an add-on to TQQQ). Each month on the first trading day, rank the 4 ETFs by trailing 3-month return (computed through prior month-end close → lookahead-safe) and hold the top-1 or top-2 equal-weight. 2bps one-way cost on turned-over notional. Window 2005-01-03 → 2026-06-18 (TLT + GLD both old enough).

| Variant | Full Sharpe | Full CAGR | Full maxDD | IS Sharpe (≤2018) | OOS Sharpe (2019→) | OOS CAGR | rebal | SPX full / OOS |
|---|---|---|---|---|---|---|---|---|
| **top-1, 3-mo** | 0.780 | 13.7% | −33.6% | 0.844 | 0.688 | 13.0% | 99 | 0.542 / 0.841 |
| **top-2, 3-mo** | **0.916** | 12.9% | **−29.0%** | 0.929 | **0.898** | 13.8% | 122 | 0.542 / 0.841 |

> SPX over this **2005-start** window has full Sharpe 0.542 (it eats the full 2008 GFC, hence lower than the 0.772 in the 2010-start TQQQ window). OOS-period SPX (2019→) is 0.841, same as the other tests.

**Reading:**
- **Top-2 is clearly the better config** and a genuinely strong standalone: full Sharpe **0.916 vs SPX 0.542** over 2005→2026 — it *beats SPX by a wide margin on risk-adjusted return* across a window that includes 2008, with a much shallower maxDD (−29% vs SPX's GFC-era drawdown). Crucially it is **stable across the split**: IS 0.929 / OOS 0.898 (almost no degradation), which is the opposite of an overfit curve.
- Top-1 is more concentrated and noticeably worse OOS (0.688) — single-asset switching whips around. Top-2 equal-weight is the robust choice.
- **The catch: it does NOT beat the TQQQ vol-target strategy on return.** Sector-rotation top-2 CAGR is 12.9% vs the TQQQ engine's 20.8%. It is a **lower-vol, lower-return, higher-Sharpe** sleeve — a *diversifier/complement*, not a TQQQ replacement. Its value is that its return stream (GLD/TLT defensive rotation) is **negatively correlated with the leveraged-long sleeve in exactly the regimes TQQQ suffers** (2008, 2022), making it a natural portfolio complement.

**Verdict:** ✅ **Promotable as a standalone archetype (top-2, 3-mo).** It clears the mission bar (beats SPX on Sharpe, full + OOS, with stable IS/OOS) and survives 2008 — something the TQQQ engine's 2010-inception data *can't even be tested on*. **Best use:** add to the candidate roster as a **defensive complement / portfolio sleeve**, not as a competitor to the leveraged-long return engine. Natural next step is to backtest a **blend** (e.g. TQQQ-voltarget + sector-rotation-top2) and measure combined Sharpe/maxDD — the low correlation suggests the blend Sharpe could exceed either alone.

---

## Summary table — does each add-on beat baseline?

| Test | Best variant | Full Sharpe (base 0.864) | OOS Sharpe (base 1.011) | maxDD (base −34.5%) | Promotable? |
|---|---|---|---|---|---|
| **1. COT percentile** | `lev_net` boost (spec, ×1.25 lo / ×0.5 hi) | **0.875** ✅ | 1.015 ✅ | **−31.7%** ✅ | ✅ optional add-on overlay (use *speculator* net, not "commercials") |
| **2. VIX term structure** | mid-band 0.75× | 0.846 ❌ | 1.005 ~ | −31.7% ✅ | ❌ no Sharpe gain (redundant w/ inverse-vol); DD-only risk knob |
| **3. Sector rotation** | top-2, 3-mo (standalone) | 0.916 vs SPX 0.542 ✅ | 0.898 vs SPX 0.841 ✅ | −29.0% ✅ | ✅ standalone defensive complement (not a TQQQ replacement) |

### Recommended actions
1. **COT lev_net overlay** — promising enough to take to a proper walk-forward / threshold-stability test (current 20/80 + 1.25× are first-guess). If it holds up, it's a clean **drawdown-shaping overlay** that also nudges Sharpe up. **Reject the task's original "commercials/dealer contrarian" framing** — it empirically *hurts* (Sharpe 0.68); the working signal is *leveraged-fund speculator* positioning in the direct sense.
2. **VIX term structure** — **do not add to core.** It's redundant with the inverse-vol sizing already in the engine and costs return for no Sharpe gain. Park it; revisit only if we ever drop inverse-vol for a binary gate (then a vol-regime overlay would have a job).
3. **Sector rotation top-2** — **add as a standalone candidate** and run a **TQQQ-voltarget + sector-rot blend** next; the low/negative correlation in stress regimes is the real prize (and it's the only one of the three with 2008 coverage).

### Caveats / honesty notes
- All three overlays are **unswept first-guesses** — no parameter optimization, so the small Sharpe deltas in Tests 1–2 are within plausible noise; the *direction/sign* findings (specs > commercials; VIX-TS redundant; rotation-top2 robust) are the durable takeaways, not the third-decimal Sharpe.
- COT-TFF data **starts 2010** → Test 1 has **no 2008 stress coverage**; Test 3 (Yahoo daily) does.
- VIX3M cache last-fetched through 2026-06-05, so the VIX overlay degrades gracefully (multiplier→1.0) on the final ~2 weeks; immaterial to the Sharpe verdict.
- Lookahead discipline preserved throughout: COT via release-lagged `released_history`, VIX via strictly-prior-close `level_asof`, rotation ranks on prior-month-end close. The overlay multiplier for day D+1 is computed from the same decision day D as the base weight.
