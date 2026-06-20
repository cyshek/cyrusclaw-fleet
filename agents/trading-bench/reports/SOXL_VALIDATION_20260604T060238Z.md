# SOXL leveraged_trend — GATE Bar A VALIDATION

**UTC timestamp:** 2026-06-04T06:02:38Z
**Validator:** Tessera validation subagent (label: soxl-validation) — ZERO promotion authority.
**Candidate:** `strategies_candidates/leveraged_trend/` — SOXL 3x-semis trend-follower.
**Screen report under review:** `reports/LEVERAGED_TREND_20260604T055554Z.md`
**Driver (throwaway):** `reports/_soxl_val_driver.py` · raw: `reports/_soxl_val_results.json`

## VERDICT: ❌ FAILS-BAR-A

Two independent binding failures, on BOTH admissible promotion paths:
- **#5 fast-track clause (a):** full-span FP-cont Sharpe **0.973 < 1.0** — misses by 0.027.
- **Standard bullet #1:** requires the (b) BH-crutch escape on **2** regime windows; **cap is 1**. Chronic-underperformance failure.

Everything else (trade count, instrument DD, return floor, code review, smoke, held-out non-collapse) PASSES — but the gate binds on the two failures above. A near-miss is still a miss; reporting it as such per the pre-committed bar.

---

## VALIDATED CELL (selection corrected)

The screen's literal best cell — `sma slow=150 fast=20 reg=True`, FP 1.12 — has **only 17 trades**, failing Bar A #4 (≥30). Per task instruction I did **NOT** validate that cell. I validated the ≥30-trade plateau neighbor the screen itself recommends:

`{filter_mode: sma, slow: 100, fast: 20, regime_filter: true, symbol: SOXL, notional: 1000}`

`params.json` originally held a stale placeholder (`symbol: TQQQ, regime_filter: false`); I corrected it to the validation cell above before running. (Protected files untouched — only the candidate's own params.json.)

---

## STEP-BY-STEP

### Step 1 — Held-out final regime (Bar A #2): **PASS** (edge does NOT collapse OOS)
MEMORY's <2-symbol xsec-walk-forward skip was avoided exactly as instructed: composed PUBLIC `backtest_xsec` + canonical `fp_continuous_sharpe` directly over explicit train/held-out splits. No protected file edited.

| Split | Span | FP-cont Sharpe | Ret | Trades |
|---|---|---:|---:|---:|
| In-sample | 2020-12 .. 2024-12-31 | **0.705** | +156% | 28 |
| **Held-out** | 2025-01 .. 2026-06 | **1.57** | +470%* | 15 |

Held-out FP is robust across warmup-head choices (1.42–1.62) and is **higher** than in-sample, not lower → no out-of-sample collapse; no in-sample overfit signature. Final-window-alone (2026-recent bull) FP = 1.83.
*Held-out return is dominated by the 2025–26 semis super-run — path-specific magnitude, as the screen caveated. The Sharpe (not the +470%) is the durable claim. This step PASSES on the non-collapse criterion.

### Step 2 — Trade count (Bar A #4): **PASS**
Full real span 2020-12-14 → 2026-06-03: **43 trades** (22 buys / 21 closes) ≥ 30. ✓

### Step 3 — Absolute return floor (Bar A #5 clause (f)): **PASS**
Net-of-cost (alpaca_stocks CostModel applied on every fill), on **deployed notional** ($1000 committed when risk-on), full 5.47-yr span: total +625.9% → **annualized 43.7%/yr** ≫ 8.0% floor. Clears with enormous margin. ✓ (Note: clause (f) only becomes operative for a candidate that has already cleared clause (a); it does not rescue an (a)-failure.)

### Step 4 — Code review (Bar A #6): **PASS — no leak found**
Read `strategy.py` line by line; suspicious-by-default:
- **No lookahead.** `decide_xsec` reads only harness-provided visible bars (t ≤ clock_t contract). `_trend_on` uses `closes[-1]` (current close) vs trailing `_sma` of prior closes — causal. Donchian path excludes current bar from the channel (`prior = closes[:-1]`) — causal (not used by this cell). Regime double-confirm slices the SOXX proxy to dates `<= as_of` (current bar date) before its trailing SMA — causal. No future-index peeking anywhere.
- **Exposure ≤ cash.** Risk-on → single `buy notional_usd=1000` (= MAX_NOTIONAL, full book); risk-off → `close`. Never exceeds cash; leverage is INSIDE the ETF only. No margin / short / borrow / derivative. `risk.py` invariant untouched.
- **NaN/empty handling.** Guards: `if not bars: return {}`; `_sma` returns None when under-primed → caller stays flat; `if not sv.get("has_bar"): return {}` blocks stale bars.
- **Trend filter is causal/trailing** throughout.
- Minor note (not a leak): regime confirm does a live `bars_cache.get_bars` for SOXX inside decide(), sliced to `as_of` — a live data dependency but causal and correct.
**No red flags.**

### Step 5 — Smoke (Bar A #7): **PASS**
`./tick.sh --candidate leveraged_trend` → `SMOKE OK xsec (640ms) basket=['SOXL'] bars_total=300 actions={SOXL=buy}`, **rc=0**, no DB errors, read-only, sane action (buy = currently risk-on). ✓

---

## THE TWO BINDING FAILURES

### A. #5 fast-track clause (a): full-span Sharpe ≥ 1.0 — **FAIL (0.973)**
Full continuous-span FP-cont Sharpe = **0.9727**, stable (single continuous run, warmup-insensitive). The gate text for #5(a) is "Full-period Sharpe ≥ 1.0 over the complete walk-forward span." 0.973 < 1.0. Matches the screen's own 0.97 for this cell. The screen pitched this as a #5(a)≥1.0 candidate; on the ≥30-trade cell it does not clear it.

(The screen's 8-window panel FP is additionally **fragile**: I measured it swing from 0.93→0.72 as warmup grows 200→400 bars — a non-robust number. The binding full-span FP is the stable one, and it's 0.973.)

### B. Standard bullet #1: ≤1 BH-crutch window — **FAIL (needs 2)**
Per-window strat vs BH-SOXL (full panel, cost-aware):

| Window | Regime | Strat | BH-SOXL | #1 status |
|---|---|---:|---:|---|
| 2022-H1 bear | bear | +12.7% | −97.8% | (a) positive ✓ |
| 2022-Q3 chop | chop | +15.1% | −77.0% | (a) ✓ |
| 2023-H1 recovery | bull | +34.6% | −73.3% | (a) ✓ |
| **2023-Q3 chop** | chop | **−6.0%** | −24.2% | (a) ✗ → needs (b) |
| 2024-Q2 bull | bull | +113.3% | +280.5% | (a) ✓ |
| **2025-Q1 tariff bear** | bear | **−31.5%** | −62.4% | (a) ✗ → needs (b) |
| 2025-Q3 bull | bull | +38.0% | −31.3% | (a) ✓ |
| 2026-recent bull | bull | +295.7% | +505.1% | (a) ✓ |

Two windows are negative and each would only pass via the (b) escape (beat BH-SOXL while deployed). **(b) is capped at AT MOST 1 window per strategy** (the cap=1 guardrail added 2026-05-30). Two (b)-windows ⇒ bullet #1 FAILS — the same chronic-underperformance signature that (correctly) rejected TSMOM. Note 2025-Q1 is a real **−31.5% loss in a tariff-bear** — exactly the kind of window the cap exists to refuse rescuing.

**Both doors are shut:** #5 fast-track fails (a); standard path fails #1. No admissible route to promotion.

---

## OVERALL: ❌ FAILS-BAR-A

| Bar A item | Result |
|---|---|
| #2 held-out final regime | ✅ PASS (held-out FP 1.57 > in-sample 0.705, no collapse) |
| #4 trade count ≥30 | ✅ PASS (43) |
| #5(f) return floor ≥8%/yr | ✅ PASS (43.7%/yr) |
| #6 code review | ✅ PASS (no leak, exposure≤cash) |
| #7 smoke | ✅ PASS (rc=0) |
| **#5(a) Sharpe ≥1.0** | ❌ **FAIL (0.973)** |
| **#1 walk-forward (≤1 BH-crutch)** | ❌ **FAIL (needs 2)** |

A genuinely strong-LOOKING candidate that just misses: clean code, real held-out persistence, monster return, tolerable −26.6% instrument DD — but it does **not** clear the pre-committed risk-adjusted bar (Sharpe 0.973, three-hundredths short) and it leans on the BH-crutch in 2 regime windows where the gate allows only 1. Per the bar locked before results were seen, this is a FAIL, not a promote. A failed validation is a clean, valuable outcome — the gate held.

**Recommendation (advisory only, zero authority):** do NOT promote. If Tessera wants to revisit, the honest levers are (i) a different ≥30-trade plateau cell that clears full-span FP ≥1.0 AND ≤1 (b)-window — none in the screen's top-24 obviously does both (the FP≥1.0 cells are the low-trade 7–17-trade ones), or (ii) an explicit, audit-logged gate discussion with main/Cyrus about the 0.973-vs-1.0 boundary — which is a goalpost-move and should be treated as such, not waved through.

---

## PROTECTED-FILE INTEGRITY (verified unchanged at finish)
```
runner.py        = 4be185e4bdcb6f432d99b71b21a4859c  ✓
backtest.py      = 9444ee5be64d9fd2639fd8cb0a28e002  ✓
backtest_xsec.py = 2278a4c8d8a66703da5cd6f2a0880061  ✓
risk.py          = e4c227e019c99e7e52224eb2f91389b8  ✓
```
Only edit made anywhere: `strategies_candidates/leveraged_trend/params.json` (stale TQQQ placeholder → validated SOXL cell). No evaluator/runner file touched.
