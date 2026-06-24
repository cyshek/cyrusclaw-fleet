# Haven Rate-Shock Patch — Can a Hardened Haven Convert the Partial-Pass to a Full Pass?

**Date:** 2026-06-23 (UTC stamp 20260623T174616Z)
**Assignment:** main subagent — determine whether a RATE-SHOCK-RESISTANT haven sleeve can patch the failure mode found in today's GLD/TLT haven prototype (`reports/HAVEN_SLEEVE_PROTOTYPE_20260623T173537Z.md`), turning it from a PARTIAL PASS into a full PASS.
**The hole being patched:** the GLD/TLT haven hedges 6/8 risk-off windows but **FAILS rate-shock regimes** — 2022 full-yr **-14.9%**, 2013 taper-tantrum **-10.2%** — because rising real rates hit BOTH bonds AND gold at once, exactly the years equities also fall.
**Scratch/engine:** `_haven_rateshock_tests.py` (extends `_haven_sleeve_tests.py`; reuses `_allocator_blend_tests.build_sleeves/blend_portfolio/report_blend` verbatim). Result JSON: `reports/_haven_rateshock_result.json`. No protected/live files / crontab / paper clock touched. TIP fetched fresh from Yahoo v8 (browser UA, query1; **Yahoo was NOT throttling today** — n=5670, 2003-12 to 2026-06) and cached.

---

## TL;DR — VERDICT: YES, a hardened haven converts the killer-battery to a FULL PASS. The spec is **GLD/TLT/DBC/UUP, inverse-vol parity 4-way.**

Adding **commodities (DBC) + the dollar (UUP)** to the GLD/TLT haven is the patch. `GLD_TLT_DBC_UUP` is the **first and only sleeve tested that is non-negative-to-near-flat across ALL 8 stress windows** — it closes the rate-shock hole *without* breaking the equity-crash hedge:

| | 2022 full-yr | 2013 taper | covid | GFC | 2011 | 2018-Q4 | 2025 tariff |
|---|---:|---:|---:|---:|---:|---:|---:|
| **plain GLD/TLT** (partial pass) | **-14.9%** FAIL | **-10.2%** FAIL | +5.4% | +15.2% | +18.6% | +5.9% | +10.3% |
| **GLD/TLT/DBC/UUP** (hardened) | **+1.3%** PASS | **-2.9%** near | -0.8% | +2.5% | +8.7% | +0.5% | -0.1% |

The two rate-shock failures flip from deep-negative to **positive (2022) / near-flat (2013)**, and the five equity-crash windows all stay positive or near-flat. It is also the **most independent leg in stress** (corr-to-equity-book in 2022 +0.19 vs plain +0.37; in covid +0.28 vs plain +0.53), carries the **highest eff-N (1.495 -> 2.323)**, and has by far the best standalone risk-adjusted profile (Sharpe 0.82 full / **1.23 OOS**, maxDD only **-14.4%** vs plain -30.4%).

**The honest tradeoff (stated up front, not buried):** adding DBC/UUP **mutes the magnitude** of the growth-scare hedge — plain GLD/TLT printed +15% in the GFC and +18.6% in 2011; the hardened haven prints +2.5% and +8.7%. It converts a *"big-positive-in-equity-crash / big-negative-in-rate-shock"* sleeve into a *"reliably-flat-in-ALL-stress"* sleeve. For a haven whose job is **crash insurance and de-concentration**, flat-in-every-regime is arguably the better shape than large-positive-sometimes / large-negative-other-times — but it is a genuine character change, not a free lunch.

**At the live-book level the win is INCREMENTAL, not dramatic**, because the haven is only a 10% sleeve: the 3-sleeve fixed-10% blend with the hardened haven gives **raw 833%** (still +245pp over SPX's 588%), Sharpe 1.027, **OOS Sharpe 1.160 (best of all candidates)**, maxDD -21.5%, and a **2022-specific maxDD of -17.7% — the shallowest of every candidate** (plain GLD/TLT 10% was -19.5%). So diluted to 10% the sleeve buys ~2pp shallower 2022 drawdown and a slightly better OOS Sharpe for a ~31pp raw-return cost. The dramatic transformation lives at the *sleeve* level; the book-level effect is a modest, real improvement.

**As insurance it is still NEGATIVE on raw standalone return** (CAGR 4.66%, raw 141% vs SPY 658% on its window) — expected and correct; a haven is a drawdown/decorrelation instrument, not a return engine.

---

## What was tested

Five hardened-haven recipes (plus the plain baseline and a managed-futures variant), each addressing the rate-shock channel by a different mechanism. All built on the **identical honest machinery** as the prototype: adjusted-close daily returns, **2bps one-way cost** on inter-asset turnover, **monthly rebalance with intramonth drift**, **inverse-vol parity from PAST-only trailing vol** (or fixed SHY floor), **OOS split 2018-12-31**, **SPX (^GSPC) / SPY on the SAME traded path**, **no lookahead**.

| Recipe | Mechanism | Common window |
|---|---|---|
| `plain_GLD_TLT` | baseline (the partial pass) | 2004-11 -> 2026-06 |
| `GLD_TLT_DBC` | + broad commodities (inflation beta) | 2006-02 -> 2026-06 |
| **`GLD_TLT_DBC_UUP`** | **+ commodities + dollar (Fed-hike beta)** | **2007-03 -> 2026-06** |
| `GLD_TLT_TIP` | + TIPS (realized-inflation principal) | 2004-11 -> 2026-06 |
| `GLD_TLT_SHYfloor25/40` | park 25/40% in SHY (~0-duration floor) | 2004-11 -> 2026-06 |
| `GLD_TLT_DBMF` | + managed-futures CTA (**2019+ only**) | 2019-05 -> 2026-06 |

---

## (B) Killer battery — BEFORE (plain GLD/TLT) vs AFTER (each hardened recipe)

Standalone sleeve return in each named stress window (`OK` >= -1%, `near` -1 to -4%, `FAIL` < -4%). The two columns that decide the verdict are **2022 full-yr** and **2013 taper** (the rate-shock failures); the rest must STAY hedged.

| Recipe | 2022 yr | 2013 taper | covid | GFC | 2011 | 2018-Q4 | 2025 | all 8 OK/near? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| plain GLD/TLT | -14.9 FAIL | -10.2 FAIL | +5.4 | +15.2 | +18.6 | +5.9 | +10.3 | NO (2 fails) |
| GLD/TLT/DBC | -7.3 FAIL | -5.5 FAIL | -3.8 | -2.4 | +9.0 | -0.3 | +4.2 | NO (2 fails) |
| **GLD/TLT/DBC/UUP** | **+1.3 PASS** | **-2.9 near** | -0.8 | +2.5 | +8.7 | +0.5 | -0.1 | **YES PASS** |
| GLD/TLT/TIP | -13.7 FAIL | -8.9 FAIL | +1.5 | +6.5 | +10.4 | +2.1 | +5.7 | NO (2 fails) |
| GLD/TLT + SHY 25% | -12.2 FAIL | -7.7 FAIL | +4.5 | +12.5 | +13.9 | +4.7 | +8.2 | NO (2 fails) |
| GLD/TLT + SHY 40% | -10.5 FAIL | -6.2 FAIL | +4.1 | +10.9 | +11.2 | +4.0 | +6.9 | NO (2 fails) |
| GLD/TLT/DBMF *(2019+)* | -3.5 near | n/a | +2.8 | n/a | n/a | n/a | +3.6 | partial (short win) |

**Read — which mechanism actually patches the hole:**
- **DBC (commodities) alone closes about HALF the gap** (2022 -14.9->-7.3, 2013 -10.2->-5.5). Commodities rise with the inflation that drives rate shocks, so they offset — but only partially, and DBC *hurts* the growth-scare windows (covid -3.8, GFC -2.4) because commodities crash in liquidity panics. Net: DBC trades rate-shock protection for equity-crash protection — a wash, not a fix.
- **Adding UUP (the dollar) is what fully closes it.** The dollar is the cleanest rate-shock hedge: when the Fed hikes, the USD rallies, and UUP gains in *exactly* the 2022/2013 regimes where bonds+gold+commodities can all be soft. UUP also rallies in liquidity panics (covid: flight-to-dollar), which is why it *rescues the covid/GFC windows that DBC alone broke*. DBC and UUP are complementary: DBC handles the inflation leg, UUP handles the rate / flight-to-USD leg. Together they flatten every window.
- **TIPS (TIP) does NOT patch it.** This is the counter-intuitive clean negative: TIPS *principal* rises with realized CPI, but TIPS are still **duration instruments** — in 2022/2013 the real-yield spike crushed TIP prices faster than the inflation accrual helped (2022 -13.7%, 2013 -8.9%, barely better than plain). TIPS hedge *expected*-inflation surprises, not the *real-rate* shock that defines a taper/hike regime. A clean, valuable negative.
- **SHY floor does NOT patch it either** — it only *dilutes* the drawdown proportionally (40% cash floor -> 2022 -14.9->-10.5). Parking in cash reduces the loss but never turns it positive, because the remaining 60% GLD/TLT still takes the full rate-shock hit. Mechanically obvious in hindsight; confirmed empirically.
- **DBMF (managed futures) genuinely helps** (2022 -3.5%) and is the *only* trend-style patch — CTAs go short bonds in a rate-shock and profit. **But its data starts 2019-05**, so it has NO read on GFC / 2011 / 2018-Q4 (the table shows `n/a`). It cannot be verified as an all-weather patch on this history; flagged as a short-window-only result.

---

## (C) Standalone economics — still NEGATIVE on raw (expected; it's insurance)

Each hardened haven on its own deep window, vs SPY buy-and-hold on the same window:

| Recipe | Full Sharpe | CAGR | maxDD | Raw | OOS Sharpe | OOS maxDD | SPY raw (same win) | Beats SPX raw? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| plain GLD/TLT | 0.658 | 7.31% | -30.4% | 357% | 0.682 | -30.4% | 824% | NO |
| GLD/TLT/DBC | 0.589 | 5.78% | -32.1% | 213% | 0.816 | -22.2% | 756% | NO |
| **GLD/TLT/DBC/UUP** | **0.821** | 4.66% | **-14.4%** | 141% | **1.225** | **-7.6%** | 658% | NO |
| GLD/TLT/TIP | 0.687 | 5.19% | -20.0% | 198% | 0.691 | -20.0% | 824% | NO |
| GLD/TLT + SHY 25% | 0.696 | 6.06% | -24.7% | 255% | 0.714 | -24.7% | 833% | NO |
| GLD/TLT + SHY 40% | 0.732 | 5.28% | -21.1% | 203% | 0.743 | -21.1% | 833% | NO |
| GLD/TLT/DBMF *(2019+)* | 0.914 | 8.09% | -12.0% | 74% | 0.914 | -12.0% | 188% | NO |

**Read:** every haven fails the raw-return bar **by design** (insurance, not an engine). But `GLD_TLT_DBC_UUP` has a **materially better risk-adjusted standalone profile than any other recipe** — Sharpe 0.82 full / **1.225 OOS**, and a maxDD of only **-14.4%** (less than half the plain haven's -30.4%). It is the cleanest low-vol (5.8%) all-weather sleeve of the set. (DBMF shows a high 0.914 Sharpe but only on its 2019+ window, which excludes every pre-2019 crash — not comparable.)

---

## (D) eff-N as a 3rd sleeve — the hardened haven is MORE independent, especially in stress

Each hardened haven added as a 3rd leg to the validated 2-sleeve book (TQQQ vol-target + sector-rotation), full common window 2010-02 -> 2026-06. **2-leg baseline eff-N = 1.495.**

| Recipe (3rd sleeve) | eff-N | corr->TQQQ-leg | corr->SPX | corr->blend (full) | corr->blend 2022 | corr->blend covid |
|---|---:|---:|---:|---:|---:|---:|
| plain GLD/TLT | 2.265 | -0.074 | -0.145 | +0.171 | +0.368 | +0.525 |
| GLD/TLT/DBC | 2.224 | +0.052 | +0.071 | +0.271 | +0.380 | +0.568 |
| **GLD/TLT/DBC/UUP** | **2.323** | -0.013 | -0.024 | +0.169 | **+0.189** | **+0.277** |
| GLD/TLT/TIP | 2.282 | -0.066 | -0.118 | +0.163 | +0.400 | +0.516 |
| GLD/TLT + SHY 25% | 2.266 | -0.076 | -0.147 | +0.169 | +0.372 | +0.519 |
| GLD/TLT + SHY 40% | 2.267 | -0.078 | -0.148 | +0.167 | +0.375 | +0.514 |
| GLD/TLT/DBMF *(2019+)* | 2.043* | +0.204 | +0.104 | +0.448 | +0.191 | +0.676 |

\* DBMF on its 2019+ overlap only.

**Read — the single most important structural finding:** `GLD_TLT_DBC_UUP` carries the **highest eff-N (2.323, > plain's 2.265)** AND is the **only recipe that stays decorrelated from the equity book *in the crash itself*** — its corr-to-blend collapses to **+0.189 in 2022** and **+0.277 in covid**, roughly *half* the plain haven's +0.368 / +0.525. The plain haven's known weakness (it correlates UP to +0.5-0.6 in fast crashes, because gold gets sold for liquidity) is **exactly the weakness the dollar leg fixes** — UUP catches the flight-to-dollar bid precisely when gold is being dumped. So the hardened haven is not just a rate-shock patch; it is a *better* de-concentrator than the plain haven on the metric (stress-conditional independence) that the original study flagged as the plain haven's soft spot.

---

## (E) 3-sleeve blend at fixed 10% haven — raw still beats SPX, with the shallowest 2022 drawdown

TQQQ vol-target + sector-rotation + hardened-haven, haven fixed at **10%**, rest split TQQQ/ROT by inv-vol, full window 2010-02 -> 2026-06. **SPX raw = 588%.** Baseline from the prototype: plain GLD/TLT 10% -> raw 864%, Sharpe 1.032, maxDD -21.7%, 2022 maxDD -19.5%.

| 3-sleeve fixed-10% | Raw | Sharpe | OOS Sharpe | maxDD | 2022 maxDD | 2022 ret | Beats SPX raw? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| plain GLD/TLT *(baseline)* | 864% | 1.032 | 1.149 | -21.7% | -19.5% | -13.8% | YES |
| GLD/TLT/DBC | 842% | 1.019 | 1.151 | -21.4% | -18.7% | -13.0% | YES |
| **GLD/TLT/DBC/UUP** | **833%** | 1.027 | **1.160** | -21.5% | **-17.7%** | **-12.3%** | YES |
| GLD/TLT/TIP | 835% | 1.026 | 1.142 | -21.4% | -19.3% | -13.7% | YES |
| GLD/TLT + SHY 25% | 846% | 1.028 | 1.146 | -21.4% | -19.2% | -13.5% | YES |
| GLD/TLT + SHY 40% | 834% | 1.025 | 1.145 | -21.2% | -19.0% | -13.4% | YES |
| GLD/TLT/DBMF *(full-pad)* | 821% | 1.016 | 1.147 | -21.7% | -18.1% | -12.7% | YES |
| GLD/TLT/DBMF *(2019+ restricted)* | 228% (1) | 1.141 | — | -20.3% | — | — | YES (1) |

(1) DBMF restricted to its 2019-05 -> 2026-06 window vs SPX-restricted 160% raw on the same window.

**Read:**
- **Every hardened-haven 3-sleeve still beats SPX raw** (821-846% vs 588%), so the rate-shock patch costs nothing against the headline raw-return mandate beyond what the plain haven already cost.
- **`GLD_TLT_DBC_UUP` delivers the shallowest 2022 drawdown of all** — **-17.7% vs plain's -19.5%** (and 2022 return -12.3% vs -13.8%) — which is the precise thing the patch was meant to achieve: a softer book drawdown in the rate-shock year. It also posts the **best OOS Sharpe (1.160)**.
- **But the book-level magnitude is modest.** At a 10% sleeve weight the dramatic sleeve-level transformation (2022 -14.9% -> +1.3%) dilutes to a ~1.8pp shallower book maxDD in 2022 and +0.011 OOS Sharpe, for a ~31pp raw-return giveup (864% -> 833%, still +245pp over SPX). **This is a real improvement, not a step-change.** To get more of the all-weather benefit at the book level you would raise the haven weight (the prototype's cap-sweep showed 15-25% trades raw return for Sharpe/maxDD), and the hardened haven is a *better* candidate to size up precisely because it doesn't have the rate-shock blow-up the plain haven does.

---

## VERDICT

**Does a rate-shock-resistant haven convert the partial pass to a full pass? — YES, on the killer battery, at spec `GLD/TLT/DBC/UUP` inverse-vol parity 4-way.**

- **Full-PASS on the killer battery (the assignment's bar):** it is the **only** sleeve tested that is non-negative-to-near-flat across **all 8** stress windows. 2022 -14.9% -> **+1.3%**, 2013 taper -10.2% -> **-2.9%**, and every equity-crash window (covid/GFC/2011/2018-Q4/2025) stays positive or near-flat. The rate-shock hole is closed without breaking the growth-scare hedge.
- **Better de-concentrator than the plain haven:** highest eff-N (2.323), and — critically — the **lowest stress-conditional correlation to the equity book** (2022 +0.19, covid +0.28, ~half the plain haven), fixing the plain haven's "correlates up in a fast crash" weakness via the flight-to-dollar leg.
- **Best standalone risk-adjusted insurance:** Sharpe 1.225 OOS, maxDD -14.4% (half the plain haven).
- **Honest qualifications (non-negotiable rails):**
  1. **It mutes the growth-scare hedge magnitude** (GFC +15% -> +2.5%, 2011 +18.6% -> +8.7%). It is an *all-weather-flat* sleeve, not a *big-positive-in-equity-crash* sleeve. Whether that is an upgrade depends on the mandate (de-concentration/insurance: yes; "I want a leg that prints +15% in the next GFC": no).
  2. **At a 10% book weight the live-book gain is INCREMENTAL** — ~1.8pp shallower 2022 maxDD, +0.011 OOS Sharpe, -31pp raw return. The transformation is dramatic at the sleeve level, modest once diluted.
  3. **Still NEGATIVE raw standalone** (insurance, expected) — it does not, and is not meant to, beat SPX raw on its own.
  4. **DBC/UUP add a 2006/2007 inception floor** (vs GLD's 2004): the 4-way common window is 2007-03+. The GFC read survives (Sep-2008 is in-window); there is no pre-2007 read.
  5. **The clean negatives are real and reported:** TIPS does *not* patch it (real-rate duration dominates the inflation accrual), and a SHY cash floor only dilutes the loss (never flips it positive). DBMF genuinely helps but only on a post-2019 window with no GFC/2011/2018 evidence — not verifiable as all-weather.

**Recommended spec (pre-registered, candidate-only):** if the haven is ever deployed, use **`GLD/TLT/DBC/UUP`, inverse-vol parity (63d, past-only), monthly rebalance, 2bps**, as a fixed 10% 3rd sleeve. Operating point: 3-sleeve raw **833%** (+245pp over SPX), Sharpe 1.027, **OOS 1.160**, maxDD -21.5%, **2022 maxDD -17.7%** (shallowest), eff-N **2.323**. This is the version of the haven that protects BOTH the growth-scare channel AND the rate-shock channel — a genuine all-weather hedge, which the plain GLD/TLT haven was not.

---

*Numbers cross-checked console vs JSON. Engine `_haven_rateshock_tests.py` extends `_haven_sleeve_tests.py` and reuses the validated `_allocator_blend_tests` engine (build_sleeves / blend_portfolio / report_blend) verbatim. Full numeric dump: `reports/_haven_rateshock_result.json`. TIP fetched once from Yahoo v8 and cached to `data_cache/yahoo/TIP_parsed.json`. Candidate research only — no protected/live files, crontab, paper clock, or .db touched.*
