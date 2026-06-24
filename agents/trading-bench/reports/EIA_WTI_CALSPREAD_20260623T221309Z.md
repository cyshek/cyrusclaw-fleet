# EIA WTI FUTURES CALENDAR-SPREAD CARRY LEG — feasibility / kill-test (true curve-shape, NON-ETF)

**Stamp:** 20260623T221309Z · **Engine:** `_eia_wti_calspread_tests.py` · **Result JSON:** `reports/_eia_wti_calspread_result.json`
**Reopen-trigger source:** `reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md` §Revisit-triggers (lines 221–222) — *"A non-ETF curve-shape instrument … a true futures-calendar-spread (front vs deferred WTI futures) would isolate the curve-shape premium cleanly … Any reopening must show a POSITIVE IS Sharpe."* This file IS that reopen.

**Verdict: ❌ CLOSE — but a fundamentally DIFFERENT (and cleaner) negative than the dead ETF version.** The cleaned-up, non-ETF instrument **fixes the exact pathology that killed the proxy** (it now has a **POSITIVE in-sample Sharpe**, +0.16, and is genuinely orthogonal to the bond leg at corr −0.06) — but the harvested curve-shape premium is simply **too small to beat dumb static-long crude out-of-sample** (k2, the make-or-break, **FAILS**: signal OOS Sharpe 0.009 vs static-long 0.106; OOS total −3.5% vs static +2.1%). The backwardation-timing demonstrably *helps in contango stress* (it dodges the 2008/2014–15/2020 oil-crash bleed) but gives up too much upside in backwardated bull runs to clear the bar. **This is a real but ~zero-alpha signal, not a tradeable sleeve.** Clean negative — reported as such, not dressed up.

---

## TL;DR — k1–k5 (OOS = 2019-01-02 … 2024-04-05, net 2 bps, OOS_SPLIT 2018-12-31, matches bond leg)

| # | Criterion | Result | Number |
|---|---|---|---|
| **k1** | Leg OOS Sharpe > 0.4 (reopen bar) | ❌ **FAIL** | **0.009** (best honest sweep config: **0.165** — still far under 0.4) |
| **k2** | BEATS no-signal **static-long** control OOS (total + Sharpe) — **MAKE-OR-BREAK** | ❌ **FAIL** | signal **−3.5%** / Sh 0.009 vs static-long **+2.1%** / Sh 0.106 → **ΔSh −0.097, Δtot −5.6pp**. vs buy-hold: **Δtot −179pp** |
| **k3** | IS Sharpe **POSITIVE** on all/most splits (the gate the ETF version failed) | ✅ **PASS** | primary **IS Sh +0.161**; **67%** of 27 swept configs IS-positive; sweep IS-median +0.071 |
| **k4** | corr(comm leg, bond leg) ≤ 0.30 | ✅ **PASS** | **−0.063** (genuinely uncorrelated to the bond leg) |
| **k5** | **Allocator-frontier lift** (3rd inverse-vol sleeve) | ⚪ **N/A** | k1–k4 did not all pass → frontier check **not run** (per spec) → **CLOSE** |

**Overall: CLOSE.** k1 and k2 both fail. The signal is positive in-sample and orthogonal (k3, k4 pass — the ETF version failed k3 outright), but it **cannot beat a dumb static-long hold of the same front contract out-of-sample**, which is the decisive carry-vs-beta test. The curve-shape premium is real but ≈0 net of the opportunity cost of sitting out backwardated rallies.

---

## 1. What was built — and why the prior version is DEAD, not reused

A self-contained engine (`_eia_wti_calspread_tests.py`, workspace root). It imports `pandas` (to parse the EIA `.xls`) and **`_h1_carry_bondleg_tests`** — reusing that engine's **pure metric primitives** (`sharpe`/`metrics`/`total_return`/`cagr`/`ann_vol`/`max_drawdown`/`corr`/`monthly_returns`/`aligned_monthly_corr`, `OOS_SPLIT`) **and its `run_one`** to reproduce the bond-leg daily net path for the corr gate — so the two legs are comparable to the decimal. `_h1_carry_bondleg_tests` itself imports only `runner/fred_cache`. The k5 allocator-frontier section would *lazily* import `_allocator_blend_tests` (read-only) **only if k1–k4 passed**; they did not, so it never ran. `runner/*.py` (beyond `fred_cache`), `strategies*/`, cron, `*.db`, broker/clock/allocator were **not** written.

**The dead ETF-proxy version (`_h1_carry_commodity_combined_tests.py`, closed 2026-06-23) is NOT reused.** Its logic — trailing return spread between an *optimized-roll ETF* and a *naive front-month ETF* (USO/USL/DBC/GSG) — was the dirty-proxy confound. That version failed because (a) it **lost to a dumb EW hold of the same ETFs by −77.5pp OOS** and (b) had a **negative IS Sharpe on every split** (IS −0.44, full ≈ −0.01), i.e. its entire apparent edge was a post-2018 long-commodity-beta regime artifact riding on expense-drag/tracking-error noise. **This engine shares none of that code or those instruments.**

**This instrument — REAL NYMEX settlements, zero fund mechanics:**
- **Data:** EIA Cushing WTI Future Contracts 1–4 (`data_cache/eia_wti/RCLC{1..4}d.xls`), daily settlement in **$/bbl** — the actual NYMEX contract prices, not a fund NAV. Inner-joined on the common calendar: **9,857 days, 1985-01-02 → 2024-04-05, 472 month-end rebalances.** Last-row term structure 86.91 > 86.10 > 85.20 > 84.24 (correct backwardation ordering; slope +0.0317). **54.0%** of month-ends backwardated.
- **The signal — calendar-spread roll yield (curve shape, isolated):** at each **month-end T** (settlements with date ≤ dates[T], PIT-safe),
  `slope_T = (CL1_T − CL4_T) / CL4_T` — the front-to-back roll yield. **slope > 0 (backwardation) ⇒ go long crude exposure; slope ≤ 0 (contango) ⇒ flat.**
- **The traded return is the FRONT-CONTRACT (CL1) daily simple return** — a clean calendar-spread / roll-timing construct on real settlements. *This is the whole point vs the dead version:* the signal comes from real contract-pair settlements and the traded P&L is the front-contract price change, with **no ETF expense ratio, no tracking error, no fund-of-futures roll mechanics** anywhere in the chain.
- **Primary mapping (chosen a priori, NOT tuned to the answer):** LONG/FLAT, threshold 0, **vol-target the leg to 12%/yr** on 20-day realized front-contract vol, **cap leverage at 1.0×** (never levered — a diversifier sleeve). Three free params (mapping, threshold, vol-target); a 27-cell sweep over {long_flat, long_short, scaled} × thr{−0.5%,0,+0.5%} × vt{10,12,15%} is reported below. (12% vs the bond leg's 9% because crude is ~5× more volatile than duration; it is one fixed param, set before results.)

**Anti-lookahead mechanics (identical discipline to the bond leg):** signal on data ≤ dates[T]; weights effective at **T+1** (1-trading-day lag); held constant intramonth; marked on the **front-contract daily return**; the freshly-traded weight does **not** capture the trade-day's already-realized return. Cost = `(bps/1e4)·|w_new − w_old|`. **Sharpe = (mean/std)·√252, ddof=1, continuous concatenated series — never median-of-windows.** OOS split **2018-12-31** (matches the bond leg exactly).

### The 2020-04-20 negative-print gotcha (handled explicitly)
On **2020-04-20, CL1 settled at −$37.63** (the famous negative-oil day). A daily simple return across that print is meaningless, and `slope = −2.32` that day is garbage. **The signal ranks on PRIOR-MONTH-END**, and April-2020's month-end is **2020-04-30 (CL1 = 18.84, clean)** — so the negative print **never enters the signal**. It *would* poison the traded daily-return series, so the front-contract return is **masked to 0 across the contaminated transitions** (`2020-04-17`, `2020-04-20`, `2020-04-21` → blanks the crash-in, the bounce-out, and the return off the distorted 04-21 bounce) **for the signal AND every control identically** — no strategy gains or loses an unfair edge from the mask. Returns resume on real prices from 2020-04-23.

---

## 2. The signal vs its controls — FULL / IS / OOS (net 2 bps)

| Series | FULL Sh | FULL tot | FULL maxDD | FULL vol | **IS≤2018 Sh** | **IS tot** | **OOS Sh** | **OOS tot** | **OOS vol** |
|---|---|---|---|---|---|---|---|---|---|
| **Cal-spread carry signal** (primary, long/flat) | **+0.135** | +39.8% | −37.9% | 10.2% | **+0.161** | **+44.8%** | **+0.009** | **−3.5%** | 12.4% |
| **Static-long control** (always-long CL1, vol-targeted, no timing) | +0.139 | +45.5% | — | 14.1% | +0.145 | +42.5% | **+0.106** | **+2.1%** | 16.2% |
| **Buy-&-hold control** (full long CL1, no vol target, no timing) | +0.301 | — | — | — | — | — | **+0.635** | **+176.0%** | — |

**Reading it:**
- **k3 PASS — the cleaned-up instrument fixes the ETF version's fatal flaw.** Unlike the proxy (IS −0.44 on every split), this true cal-spread signal has a **positive in-sample Sharpe (+0.161)** and is IS-positive in **67%** of swept configs. So the curve-shape premium genuinely *exists* before 2019 — it is **not** a regime artifact. This is exactly the bar the reopen trigger demanded, and it clears it.
- **k2 FAIL — but the premium is too small to beat being-dumb-long OOS.** This is the decisive carry-vs-beta test (the analog of the BAB/fundamentals/ETF "beat your own no-signal control" gate). Out-of-sample the timing signal **loses to a dumb static-long hold of the very same front contract** on both total return (−3.5% vs +2.1%) and Sharpe (0.009 vs 0.106). Versus naive buy-hold it's −179pp. The timing's job is to sit out contango — and it does — but post-2009 oil spent enough time backwardated-and-rallying that *being out* cost more than the contango bleed it avoided. **A signal that can't beat static-long is harvesting ≈0 alpha over the beta.**
- **Cost is NOT the killer** (see §4) — OOS total is already negative at **0 bps**. This is a clean *signal-quality* failure, not a friction artifact, and it is **not** the hollow vol-suppression number the ETF version produced (there OOS Sharpe was inflated by cash-parking; here the honest OOS Sharpe is simply ~0).

---

## 3. Lookahead canary (D+1 honest vs D0 cheat)

| Path | FULL Sharpe |
|---|---|
| Honest (signal lagged **+1** trading day into the trade) | **0.1352** |
| Cheat (**D0** — trades on the signal bar itself, no lag) | 0.1531 |

**Paths differ (0.1352 ≠ 0.1531) ⇒ no same-day leakage.** The honest path is *worse* than the cheat (as it must be — the cheat captures part of the signal-day move), confirming the 1-day lag is doing real work and nothing peeks forward.

---

## 4. Cost grid (monotonic) + breakeven

| Cost (bps round-trip) | FULL Sh | IS Sh | OOS Sh | OOS tot |
|---|---|---|---|---|
| 0 | 0.1376 | 0.1631 | 0.0112 | −3.30% |
| 1 | 0.1364 | 0.1619 | 0.0098 | −3.38% |
| **2 (primary)** | **0.1352** | **0.1607** | **0.0085** | **−3.47%** |
| 5 | 0.1316 | 0.1572 | 0.0044 | −3.72% |

**Breakeven cost (OOS): N/A** — the OOS total return is **already negative at 0 bps**, so there is no positive cost at which it breaks even; cost is *not* what kills this leg. Average turnover **0.102 per rebalance** (very low — a slow monthly long/flat switch on one instrument). The monotone, shallow cost sensitivity confirms friction is immaterial here; the verdict is driven entirely by signal quality.

---

## 5. Robustness sweep (27 configs: mapping × threshold × vol-target)

| Stat | Value |
|---|---|
| n configs | 27 |
| OOS Sharpe min / median / max | **−0.475 / 0.009 / 0.165** |
| IS Sharpe min / median / max | −0.211 / 0.071 / 0.161 |
| # configs OOS Sharpe > 0.4 | **0 / 27** |
| # configs IS Sharpe > 0 | 18 / 27 (**67%**) |

**No config anywhere in the sweep clears OOS Sharpe 0.4** — the *best* (long/flat, thr +0.5%, vt 10%) reaches only **0.165 OOS** (and is IS-positive at 0.124, so it's honest, just weak). The `long_short` mapping is materially *worse* (shorting crude in contango added drawdown — the OOS-min −0.475 is a long/short cell). The signal is **consistently small-and-positive in-sample and ~zero out-of-sample across the whole grid** — a stable, un-cherry-picked picture, and a stable *miss*.

---

## 6. Stress windows — where the timing DOES earn its keep (and where it doesn't)

| Window | n days | **Signal tot** | Signal Sharpe | Static-long tot | Buy-hold tot |
|---|---|---|---|---|---|
| 2008 GFC oil crash (Jul-08→Mar-09) | 189 | **+0.3%** | **+1.15** | −14.6% | **−64.5%** |
| 2014–15 oil bust (Jul-14→Dec-15) | 378 | **−23.2%** | −1.95 | −36.9% | −64.9% |
| 2020 COVID / negative print (Feb–Jun 20) | 104 | **−1.9%** | −1.56 | −20.2% | +9.8% |
| 2021–22 backwardation bull (Jan-21→Jun-22) | 375 | +21.7% | +0.88 | +29.5% | **+118.0%** |

**This is the crux of the negative.** In **contango crashes (2008, 2014–15, 2020)** the timing signal does *exactly* what carry should — it sits out and dramatically outperforms buy-hold (2008: +0.3% vs −64.5%; it goes flat as the curve flips to contango). **But in the 2021–22 backwardation bull it captured +21.7% while buy-hold made +118%** — being vol-targeted-and-cautious left ~96pp on the table. Net over the modern era the avoided-bleed doesn't outweigh the foregone upside: **post-GFC (2009+) the leg's Sharpe is −0.08** (total −16%). The premium that *does* exist concentrates in the 1985–2008 era and does not survive into the regime we'd actually trade.

---

## 7. Orthogonality (k4) — corr to the bond-carry leg

| Pair | Monthly-return corr | Bar |
|---|---|---|
| Cal-spread comm leg vs **bond-carry leg** | **−0.063** | ≤ 0.30 ✅ |

**k4 PASS.** The leg is genuinely uncorrelated to the bond-carry leg (−0.06) — even more orthogonal than the dead ETF version (−0.28). Bond-leg reference (primary config, reproduced this run): OOS Sharpe **0.434**, full Sharpe **0.578**. So the diversification *would* have been real — but k5 was never reached because the leg fails its own standalone quality gates (k1, k2). Orthogonality cannot rescue a signal that doesn't beat its no-signal control.

---

## 8. Verdict k1–k5 (explicit booleans)

```
k1  OOS Sharpe > 0.4 .................... FAIL  (0.009; best sweep 0.165)
k2  beats static-long control OOS ....... FAIL  (ΔSh −0.097, Δtot −5.6pp; vs buy-hold −179pp)  ← MAKE-OR-BREAK
k3  IS Sharpe positive (all/most) ....... PASS  (primary +0.161; 67% of sweep IS-positive)
k4  corr-to-bond-leg ≤ 0.30 ............. PASS  (−0.063)
k5  allocator-frontier lift ............. N/A   (k1–k4 not all pass → not run → CLOSE)
OVERALL ................................. CLOSE
```

---

## 9. Honest conclusion + the OOS-truncation caveat

**CLOSE the EIA WTI calendar-spread carry leg.** This was the valid, non-ETF reopen the commodity-carry close report called for, and it was worth running: the clean instrument **did fix the proxy's fatal in-sample pathology** (k3 now PASSES — positive IS Sharpe, real curve-shape premium that exists before 2019) and it is genuinely orthogonal to the bond leg (k4, −0.06). **But the premium is too small to beat dumb static-long crude out-of-sample (k2 FAIL) and nowhere near the 0.4 OOS Sharpe bar (k1 FAIL).** The backwardation-timing reliably dodges contango crashes (its one genuine virtue, visible in 2008/2014–15/2020) but surrenders too much backwardated-bull upside to net out ahead — post-GFC it is actually slightly negative. This is a *different and cleaner* negative than the ETF version: not a dirty-proxy regime artifact, but a **real-but-≈zero-alpha carry signal** that loses the carry-vs-beta test on honest, friction-immaterial terms.

**OOS-truncation caveat (unavoidable, stated plainly):** EIA stopped publishing the NYMEX RCLC1–4 series after **2024-04-05**, so this leg **cannot be tested past April 2024 on free data.** The OOS window is **2019-01-02 → 2024-04-05** (1,323 trading days, ~5.3 yrs — a respectable holdout, but it ends 14 months before today and cannot see 2024-H2/2025/2026). A post-GFC (2009+) cut is reported for additional context (Sharpe −0.08), and both reinforce the same conclusion. The verdict would not plausibly flip with 14 more months of data given that **no swept config clears even half the bar** and the make-or-break control loss is structural (foregone backwardation upside), not marginal. **No reopen unless a fundamentally stronger curve-shape construct or a longer/continuing free futures-settlement source appears** — and any such reopen must still beat static-long OOS, which this clean instrument does not.

---

*Engine: `_eia_wti_calspread_tests.py` · ran EXIT 0, headline numbers reproduced · Result JSON: `reports/_eia_wti_calspread_result.json` · Data: EIA Cushing WTI Future Contracts 1–4, real NYMEX settlements, no ETF mechanics.*
