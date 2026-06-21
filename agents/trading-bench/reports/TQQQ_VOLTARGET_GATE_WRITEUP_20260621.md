# TQQQ Vol-Target Sleeve — Real-Money Gate Write-Up

**Strategy:** `leveraged_long_trend_paper`
**Date:** 2026-06-21
**Author:** Tessera (trading-bench)
**Status:** Live PAPER candidate (cron since 2026-06-13). **NOT real-money. This document is the decision packet for whether to allocate real capital — it does not authorize it.**
**Verdict source:** `reports/VOLTARGET_SLEEVE_VERDICT_20260613.md` · **Backtest engine:** `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py` · **Live adapter:** `strategies/leveraged_long_trend_paper/strategy.py`

---

## 1. Executive Summary

**What it is.** A single-instrument, long-only sleeve that holds **TQQQ** (3× Nasdaq-100) behind two risk layers:

1. **SMA-200 trend gate (on QQQ, the underlying — not TQQQ, not SPY):** hold the sleeve only when QQQ's last close is above its 200-day simple moving average. When QQQ is below its SMA-200, the sleeve goes **flat to cash** (T-bill). This is the regime filter that kept it *out* of the worst of 2022.
2. **Inverse-realized-vol position sizing (the actual innovation):** instead of holding 100% TQQQ whenever the gate is up, scale the sleeve weight to target a fixed **25% annualized volatility**:
   > `weight(D+1) = clamp( 0.25 / realized_vol₂₀(TQQQ returns through D), 0, 1.0 )`, **but 0 if QQQ ≤ SMA-200.**

   `realized_vol₂₀` = annualized stdev of the trailing 20 daily returns of TQQQ, using only returns ending on/before the decision day. Weight is **capped at 1.0 — no leverage is added** on top of the ETF's own 3×.

**The mechanism, in one sentence:** when TQQQ gets volatile (which is when 3× ETFs bleed from volatility decay and gap risk), the sleeve automatically shrinks; when it's calm and trending, it sizes up — and it's entirely in cash whenever QQQ's primary trend is down.

**The honest framing.** This is a **risk-managed leverage premium, not pure alpha.** Most of the outperformance over SPX is still levered Nasdaq beta — the vol-target layer compresses the tail without manufacturing a new source of return. The Sharpe edge over SPX is real but **modest** (0.842 vs 0.773). What makes it interesting is not the Sharpe; it's that **for the first time the bench has a candidate that beats SPX on raw return *with an investable drawdown*** (≈SPX's, down from the raw −56% of the ungated leveraged-trend lead). And critically — **the edge is TQQQ-specific** (see §4); it is *not* a universal "lever any index" law.

---

## 2. Performance — Full Period, OOS, and the 2022 Bear

**Backtest window:** 2010-02-11 → 2026-06-08 (16.3 yrs, 4,105 trading days). Benchmark = SPX (^GSPC) total return on the same path. Underlying data = Yahoo split/div-adjusted closes (leveraged-ETF volatility decay is already baked into adjclose; only the explicit expense ratio is added on top — no double-count).

### Headline (vol-target 0.25, net of realistic costs) — the canonical verdict numbers

| Metric | Raw lead (no sleeve) | **TQQQ vol-target sleeve** | SPX |
|---|---|---|---|
| Total return | +10,121% | **+1,881%** | +587% |
| CAGR | 32.9% | **20.1%** | 12.6% |
| Max drawdown | **−56%** (uninvestable) | **−34.8%** | −33.9% |
| Sharpe | 0.846 | **0.842** | 0.773 |

The sleeve **beats SPX on raw return (+1,881% vs +587%) AND on Sharpe (0.842 vs 0.773)**, while bringing the drawdown down from the raw −56% to ≈SPX's −33.9%. That drawdown compression — at no cost to beating SPX raw — was the entire go/no-go, and it passed.

### Out-of-sample (frozen split 2018-01-01; the OOS window was never seen during tuning)

| | TQQQ vol-target sleeve | SPX | Margin |
|---|---|---|---|
| OOS total return (2018→2026) | **+368%** | +175% | **+193pp** |
| (verdict rounds this to) | +354% | +175% | +179pp |
| OOS max drawdown | −34.5% | — | — |

OOS beats SPX raw. The verdict report's "+354% vs +175%" is the realistic-cost rounding; the raw frozen-OOS engine figure is +368.2% vs +174.7%. Either way the OOS margin is large and positive — TQQQ is the *fat* case (unlike UPRO/SPXL, see §4).

### The 2022 bear (calendar year, cost-free, lookahead-safe — computed fresh for this write-up)

| Calendar 2022 | TQQQ vol-target sleeve | SPX (B&H) |
|---|---|---|
| Return | **−17.8%** | −20.0% |
| Max drawdown | **−17.8%** | −25.4% |

**This is the most reassuring single number in the packet.** 2022 was the worst environment for a leveraged-Nasdaq strategy in the sample (TQQQ buy-and-hold fell ~−79% that year). The vol-target sleeve **lost *less* than SPX** — because the SMA-200 gate flipped QQQ off early and parked the sleeve in cash through the bulk of the decline, and the vol-target layer had already shrunk the weight as vol rose into the top. A 3× instrument that beats the S&P *in the bear* is the behavior that makes the whole thing investable rather than a 2010s-bull artifact. (This subwindow is cost-free; costs would shave a few tenths but cannot flip a +2.2pp relative outperformance driven by being in cash.)

### Cost-robustness ladder (full period, vol-target 0.25) — the honest spread

The canonical headline (+1,881% / 20.1% / 0.842) sits at the **"ER-only"** cost rung (2bps/rebalance + 0.95%/yr expense ratio). The stricter "realistic" rung (5bps/rebalance + 0.95% ER) is modestly lower. The strategy beats SPX raw at **every** rung tested — it is not a thin/optimistic-only edge:

| Cost level | Total ret | CAGR | maxDD | Sharpe | OOS margin vs SPX |
|---|---|---|---|---|---|
| optimistic (2bps, no ER) | +2,026% | 20.7% | −34.5% | 0.859 | — |
| **er_only (2bps + 0.95% ER)** ← headline | **+1,863%** | **20.1%** | −35.1% | **0.840** | — |
| realistic (5bps + 0.95% ER) | +1,794% | 19.8% | −35.1% | 0.832 | **+170pp** |
| pessimistic (12bps + 0.95% ER) | +1,644% | 19.2% | −35.6% | 0.812 | **+155pp** |

> **Note for the reader:** the verdict report labels its headline "net of realistic costs." Strictly, +1,881%/20.1%/0.842 matches the *er_only* rung; the fully-loaded *realistic* rung is +1,794%/19.8%/0.832. The difference is immaterial to the conclusion (beats SPX raw + Sharpe at both, OOS-positive at +170pp even at realistic), but it is named here so the number is honest rather than rounded-up.

---

## 3. Live code mirrors the backtest (verified)

The whole value of this strategy is its risk layer, so the live adapter must reproduce the engine's gate, vol window, and sizing **exactly**. I re-read `strategy.py` against `backtest_daily_voltarget.py`:

- ✅ **Gate math** (`trend_is_up_sma200`, `_sma`) is a verbatim mirror of the engine; gate is on **QQQ** closes through D, flat if QQQ ≤ SMA-200.
- ✅ **Realized vol** (`realized_ann_vol`) is verbatim: population stdev of trailing-20 daily simple returns × √252, on the **sleeve's own (TQQQ)** returns.
- ✅ **Target weight** (`target_weight`) is verbatim: `clamp(0.25 / rv, 0, 1.0)`, 0 when gate down.
- ✅ **No-lookahead:** weight is decided from data with date ≤ D and applied into D+1 (same D→D+1 convention as the engine); never peeks at the forming bar.
- ✅ **No added leverage:** `w_max = 1.0` — at most one full $1,000 TQQQ position, or flat.
- ✅ **`params.json`** matches the validated config: `target_vol 0.25`, `vol_window 20`, `sma_window 200`, `w_max 1.0`.

**Two faithful, documented divergences (both bias conservative or are no-ops live):**

1. **QQQ-underlying plumbing** — the gate needs QQQ closes, which the runner originally injected as SPY-only. The adapter **refuses to proxy** QQQ with SPY/TQQQ (that would be a different, unvalidated strategy) and fails *safe to flat* if QQQ is missing. ✅ **This plumbing has since been wired** into both `runner/runner.py` (injects `market_state["underlying"]` for any strategy declaring `underlying`) and `runner/candidate_smoke.py` — confirmed present. The live decisions below show the gate firing correctly (`gate=ON(QQQ 721.31 vs SMA200 625.36)`), so the plumbing is working in production.
2. **No partial-trim primitive** — the runner supports `BUY notional` and `CLOSE-to-flat` only, not a partial down-trim while staying long. The continuously-rebalanced engine trims most days; the live adapter quantizes honestly (full CLOSE on gate-off/weight≈0, BUY when adding, HOLD when it wants to reduce-but-not-exit). This biases the live sleeve **slightly hotter** on vol-spike days, bounded at w_max=1.0 (never more than one full $1,000 position). Documented in `RUNNER_PLUMBING_GAP.md`; not a correctness bug, a known bounded divergence.
3. **VIX overlay off** — `vix_gate=false`. The engine sets it true, but the runner can't supply VIX/VIX3M term structure and the engine's own `_vix_risk_off` *passes* (permissive) on missing data, so live == engine-with-VIX-missing. (Prior research found VIX-off ≥ VIX-on for raw return on TQQQ anyway — SMA-200 does the heavy lifting; VIX is a DD tool, not a return enhancer here.)

---

## 4. Honest Caveats — what could be wrong / what this is NOT

1. **TQQQ survivorship.** TQQQ has *survived* and *thrived* across the exact 2010→2026 window we backtest. A 3× ETF is a path-dependent instrument that can be wiped out by a single fast crash (a −33% one-day index move zeroes a 3× fund). We are fitting on the one leveraged-Nasdaq vehicle that happened to live through the largest tech bull in history. The SMA-200 gate mitigates this (it's the mechanism that *limited* the 2022 damage), but it cannot fully insure against an overnight gap that opens past the gate. **This is the single biggest reason to keep it on paper longer.**

2. **The edge is TQQQ-specific — do NOT generalize.** The *same* sleeve on **UPRO and SPXL (3× S&P)** beats SPX only at *optimistic* cost and **flips negative at realistic cost** (UPRO −6.8pp, SPXL −5.8pp OOS). So the sleeve rides on **QQQ's (Nasdaq-100) trend/vol character**, not on "lever any index." **SOXL (3× semis) was excluded** outright — −84% to −89% drawdown even *with* the gate. If we ever try to diversify this archetype across underlyings, the backtest says it breaks. One instrument, one regime-gate.

3. **No short / no inverse / cash is the only defense.** In a down market the sleeve's *only* move is to sit in cash (gate off). It does not short, does not buy puts, does not rotate to a defensive asset. That's why 2022 was "lose 17.8% / lose less than SPX" rather than "make money" — being flat is the whole downside playbook. A grinding, choppy market that whipsaws QQQ around its SMA-200 (gate flickering on/off, each flip paying costs) is the environment most likely to underperform the backtest.

4. **Concentration risk.** This is **one ticker.** No diversification, no basket, no idle-cash sleeve diluting the blow. When it's on, ~$300–$1,000 of notional is in a single 3× ETF. A real-money allocation here is a concentrated bet on (a) QQQ continuing to trend and (b) TQQQ continuing to track 3× without a structural blowup.

5. **Leverage premium, not alpha.** Restating the framing because it matters for sizing expectations: the Sharpe edge over SPX is +0.069 (0.842 vs 0.773). Most of the +1,294pp return gap over SPX is levered beta with the tail compressed — a legitimate, holdable thing, but **not** a market-neutral edge. Size it as "a risk-controlled aggressive long," never as "free Sharpe."

---

## 5. Paper-clock progress so far (live data from `tournament.db`)

**Live since:** 2026-06-13 (cron: `*/30 7-13 * * 1-5` via `cron_tick.sh`). As of 2026-06-20 (Sat): **~1 week / 5 market sessions traded.**

**Decision tally (71 ticks logged):** 67 `skip_market_closed` (cron fires every 30 min incl. pre-market; only RTH ticks act), **3 `buy`**, **1 `hold`**. Zero errors, zero rejects, gate firing correctly on real QQQ data.

**The 3 fills (building the position; each tick capped at the runner's $100 MAX_NOTIONAL, so it stepped in over 3 days toward its ~$300 target weight):**

| Date | Action | Price | Qty | Gate / sizing reason |
|---|---|---|---|---|
| 2026-06-15 | BUY $100 | $82.72 | 1.209 | `w=0.33 rv=76.7% gate=ON(QQQ 721.31 > SMA200 625.36)` tgt $326 |
| 2026-06-16 | BUY $100 | $83.96 | 1.191 | `w=0.31 rv=81.1% gate=ON(QQQ 743.81 > 626.21)` tgt $308 |
| 2026-06-17 | BUY $100 | $81.46 | 1.228 | `w=0.30 rv=83.7% gate=ON(QQQ 729.87 > 626.98)` tgt $299 |
| 2026-06-18 | HOLD | — | — | `w=0.30 tgt $297 cur $297 \|Δ\|=$1 < $50 deadband` (at target, no churn) |

**Current position:** 3.627 shares TQQQ, **avg entry $82.70, cost basis $299.97.**
**Mark (last close 2026-06-18 = $82.87):** market value **$300.58 → unrealized P&L +$0.61 (+0.20%).**
**Realized P&L:** $0.00 (no round-trips closed yet — it's been long-only-building for one week).

**What the week demonstrates (and doesn't):**
- ✅ **Plumbing works end-to-end:** gate reads real QQQ closes (721→744, all > SMA-200 ≈ 626 → ON), vol sizing computes live (rv ~77–84% → w ~0.30–0.33), fills execute, deadband suppresses churn at target. The thing the adapter was *blocked* on (QQQ injection) is resolved and live.
- ✅ **Sizing behaves as designed:** with TQQQ realized vol running hot (~80% annualized), the vol-target correctly held weight down to ~0.30 (≈$300) rather than going to a full $1,000 — exactly the risk layer doing its job.
- ❌ **Nothing about edge is proven yet.** One week, zero closed round-trips, $0.61 of unrealized P&L is *noise*. This week is a **plumbing/execution smoke test that passed**, not evidence the backtest replicates live. The gate has not yet flipped off; we have not seen a single sell, a single down-tick rebalance, or a single regime change live.

---

## 6. Verdict — what must happen before real-money consideration

**This is the strongest, most investable lead the bench has produced — and it is nowhere near ready for real capital.** One week of long-only position-building proves the wiring, not the edge.

**The bar before I would bring a real-money request to Cyrus** (mapping to the *spirit* of GATE.md Bar E, which is formally suspended under explore-first mode but remains the right discipline for an actual money decision):

| # | Requirement | Status now | Target |
|---|---|---|---|
| 1 | **Live paper duration** | ~1 week | **≥ 8–12 weeks** — long enough to see ≥1 gate-off → cash → re-entry cycle and at least one meaningful vol-spike rebalance. A 3× strategy *must* be observed through a real drawdown before real money, not just a calm uptrend. |
| 2 | **Round-trip trades** | **0 closed** | **≥ 15–20 round-trips** (gate-off CLOSEs + re-entries). This is what validates the execution-cost model on real fills — the actual job of the paper soak. |
| 3 | **Live cost model vs backtest** | unmeasured (no closes) | **realized per-trade slippage+fees ≤ 2× the backtest assumption** (5bps/side realistic rung). n≈20 can answer this; it cannot answer "does return match backtest" (underpowered). |
| 4 | **Backtest Sharpe (full + held-out OOS)** | 0.832–0.842 | ✅ already clears ≥0.5 candidate bar; **borderline vs the 1.0 real-money bar** — this is a leverage premium, so Sharpe will not hit 1.0. Real-money case rests on *raw-return-beats-SPX-with-investable-DD*, not on a 1.0 Sharpe. Cyrus must explicitly accept that framing. |
| 5 | **Max drawdown** | backtest −34.8% | Exceeds the old 20% real-money DD ceiling. **Must be a conscious, accepted risk** — this is a 3× sleeve; −35% peak-to-trough is *by design* and is the price of +1,881%. Size the allocation so −35% on it is tolerable. |
| 6 | **Gate-off behavior observed live** | not yet seen | At least one clean **QQQ-crosses-below-SMA-200 → full CLOSE to cash → later re-entry** cycle executed correctly live, with no attribution desync. |
| 7 | **Explicit per-request Cyrus approval** | — | **Never standing.** Real money is Cyrus's call at the time. Initial allocation if approved: **$100** (fail-fast, cheap experiment). |

**Recommended disposition:** **Keep on the paper clock, let it run, and re-evaluate at the ~8-week mark (≈mid-August 2026) or the first time the gate flips off — whichever comes first.** The first gate-off → cash → re-entry cycle is the single most informative event we're waiting for; it's the part the one-week record can't show and the part most likely to surface a live-vs-backtest divergence (cost on the round-trips, attribution on the CLOSE).

**Bottom line for Cyrus:** the math is real and honestly the best the bench has — beats SPX raw + Sharpe, OOS-positive, and (the part I trust most) *lost less than SPX in 2022*. But it's a concentrated, TQQQ-specific, survivorship-exposed 3× leverage premium with a −35% by-design drawdown, and it has exactly **5 days and zero round-trips** of live evidence. Worth real money *eventually*, on a small fail-fast $100 ticket, **after** it survives a real regime change on paper — not yet.

---

*Numbers reconciled live from `recost_voltarget_result.json`, `validation_voltarget_result.json`, `evaluation_voltarget_result.json`, and `tournament.db` (decisions + trades), 2026-06-21. 2022 subwindow computed fresh from Yahoo adjclose, lookahead-safe. Live adapter re-read against the backtest engine and confirmed to mirror gate/vol/sizing.*
