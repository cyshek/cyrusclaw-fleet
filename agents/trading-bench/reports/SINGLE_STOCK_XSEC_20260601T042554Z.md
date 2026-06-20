# Single-Stock Cross-Sectional Lane — Corrected-Ruler Swing

**UTC timestamp:** 20260601T042554Z
**Author:** single-stock xsec research subagent (depth 1), trading-bench
**Ruler:** CORRECTED (√252 Sharpe annualization fix + GATE #5(b) now binds on `worst_instrument_dd_pct` deployed-capital DD, per HARNESS_INTEGRITY_AUDIT_20260531T190026Z + RULING 2).
**Suite at finish:** `237 passed in 8.12s` (unchanged; no code edits to any runner file).
**Promotions to `strategies/`:** ZERO. (Subagent has no promotion authority.)
**Front-door verdict:** **REJECT — all 3 variants.** No PROMOTE-eligible candidate. Honest reject; reported as-is, no soft-pass.

---

## TL;DR

This is the **first genuine single-stock cross-sectional lane** in the bench — every prior xsec candidate (`xsec_momentum_236b86`, `xsec_momentum_xa_38d2b2`, `xsec_lowvol_xa2_440761`, `xsec_meanrev_xa_8e5a3f`, the sector-rot and wide variants) used **ETF baskets** (11 sector SPDRs or 6-9 cross-asset ETFs). The $1000 notional bump unlocked individual-stock baskets, so I built a real 20-name large-cap universe and ran the three canonical cross-sectional archetypes on it through the **corrected** ruler.

**All three REJECT cleanly through the front door.** None clears the shared fitness gate, none clears Bar A bullet #1, and none clears clause (f)'s 8%/yr return floor — every one earns a **negative** annualized return on deployed notional. The deployed-capital DD gate (#5(b)) actually PASSES for all three (worst instrument DD −21% to −28%, under the 30% ceiling) — but that's irrelevant because the returns are the failure, not the risk. This is exactly the kind of result the corrected ruler is supposed to produce: no return-floor side door, no Sharpe inflation rescuing a barbell.

---

## Universe (survivorship-safe by construction)

**20 mega/large-cap US stocks, single fixed basket, identical across all 3 variants:**

```
AAPL MSFT JNJ XOM JPM PG KO WMT CVX HD MRK PEP CSCO VZ DIS MCD NKE UNH BA CAT
```

- **All 20 fetch full history from the 2020-07-27 data floor** (verified: each returns ~1461-1464 daily bars, first bar = 2020-07-27). No window-skipping, no phantom span (Pattern #4 clean).
- **Listing/IPO survivorship: none.** Every name was already an established mega/large-cap, publicly listed for decades before mid-2020. There is no IPO-timing or new-listing bias at backtest start.
- **Delisting survivorship: mild, flagged, mitigated.** All 20 survived the full 2020→2026 window (none delisted). A name that blew up and delisted mid-window would be absent — but these are blue-chips with negligible delisting probability over the period. Critically, the set was **NOT chosen by 2026 hindsight performance**: BA and DIS were notable *laggards* and were deliberately retained precisely to avoid winner-cherry-picking. The universe is sector-diversified (tech, energy, financials, staples, healthcare, industrials, discretionary, telecom) to give the cross-sectional ranking real dispersion.
- **Cost model: ACTIVE, non-zero.** `CostModel.alpaca_stocks()` = 2bps one-way spread → **4bps = $0.04 round-trip on $100 notional**, 0 commission (matches audit §5). No `--no-costs` / zero-cost path was used. The 946-trade mean-reversion variant's net annualized return (−8.07%/yr) vs its gross-positive windows is direct evidence the cost drag was applied.

---

## Variants tested

| # | Candidate | Archetype | Signal | K | Cadence | Warmup |
|---|---|---|---|---|---|---|
| 1 | `xsec_ss_momentum_lc20` | XSec momentum (Jegadeesh-Titman 12-1) | trailing 252d return, skip 21d | top-5 | monthly | 400d |
| 2 | `xsec_ss_lowvol_lc20` | XSec low-vol (Ang-Hodrick-Xing-Zhang) | trailing 60d realized vol | bottom-5, equal-wt | monthly | 120d |
| 3 | `xsec_ss_meanrev_lc20` | XSec short-horizon reversal (Lehmann/Lo-MacKinlay) | trailing 5d return | bottom-5 | weekly | 40d |

K=5 of 20 ≈ N/4 (top/bottom quintile) for all three. `decide_xsec` logic is the **proven, unmodified** code from the existing candidates (momentum from `xsec_momentum_xa_38d2b2`, lowvol from `xsec_lowvol_xa2_440761`, meanrev from `xsec_meanrev_xa_8e5a3f`) — only the basket changed to single stocks. Full 8 NAMED_WINDOWS walk-forward via `walk_forward_xsec`.

---

## Results — full walk-forward (corrected ruler)

### 1. `xsec_ss_momentum_lc20` — REJECT

| Window | Regime | Trades | Return % | Sharpe | BH-Basket % | Beats BH? | BarA#1 |
|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 11 | -0.80 | -0.49 | -1.12 | ✅ | ❌ |
| 2022-Q3 chop | chop | 15 | +0.06 | 0.06 | -0.69 | ✅ | ✅ |
| 2023-H1 recovery | bull | 15 | -0.33 | -0.34 | +0.22 | ❌ | ❌ |
| 2023-Q3 chop | chop | 11 | -0.67 | -0.95 | -0.37 | ❌ | ❌ |
| 2024-Q2 bull | bull | 7 | -0.47 | -0.62 | -0.13 | ❌ | ❌ |
| 2025-Q1 tariff bear | bear | 13 | -0.82 | -0.53 | -0.61 | ❌ | ❌ |
| 2025-Q3 bull | bull | 9 | +0.60 | 0.91 | +0.41 | ✅ | ✅ |
| 2026-recent bull | bull | 7 | +0.55 | 0.70 | +0.71 | ❌ | ✅ |

**Aggregate:** median ret **−0.40%** · 38% windows positive · 38% beat BH · **median Sharpe −0.41** · trades 88 · **worst_instrument_dd −28.28%** · **ann. return on deployed −1.78%/yr**.
- Fitness gate: 🔴 FAIL (median ret ≤0, <50% positive, <50% beat BH, median Sharpe −0.41 ≤ 0.50).
- Bar A #1: 🔴 FAIL (4 windows fail; in-position only ~19% — monthly 5-of-20 basket under-deploys vs the 25% floor).
- #5(b) deployed-DD: 🟢 PASS (−28.28% < 30% ceiling) — but moot; returns fail.
- Clause (f) floor: 🔴 FAIL (−1.78%/yr < 8%/yr).

### 2. `xsec_ss_lowvol_lc20` — REJECT

| Window | Regime | Trades | Return % | Sharpe | BH-Basket % | Beats BH? | BarA#1 |
|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 13 | -0.19 | -0.21 | -1.12 | ✅ | ✅(b) |
| 2022-Q3 chop | chop | 13 | -1.54 | -2.05 | -0.69 | ❌ | ❌ |
| 2023-H1 recovery | bull | 7 | -0.22 | -0.43 | +0.22 | ❌ | ❌ |
| 2023-Q3 chop | chop | 9 | -0.17 | -0.36 | -0.37 | ✅ | ❌ |
| 2024-Q2 bull | bull | 13 | -0.12 | -0.26 | -0.13 | ✅ | ❌ |
| 2025-Q1 tariff bear | bear | 19 | -0.03 | -0.03 | -0.61 | ✅ | ❌ |
| 2025-Q3 bull | bull | 13 | -0.27 | -0.59 | +0.41 | ❌ | ❌ |
| 2026-recent bull | bull | 7 | -0.83 | -1.76 | +0.71 | ❌ | ❌ |

**Aggregate:** median ret **−0.20%** · **0% windows positive** · 50% beat BH · **median Sharpe −0.40** · trades 94 · worst_instrument_dd −21.62% · **ann. return on deployed −7.50%/yr**.
- Fitness gate: 🔴 FAIL (0% windows positive, median Sharpe −0.40). #5(b): 🟢 PASS (−21.62%). Clause (f): 🔴 FAIL (−7.50%/yr).
- The low-vol large-caps just bled slowly in every regime — the calmest names (staples/healthcare) didn't fall much but didn't make money net of cost either. This is the single-stock analogue of the cash-park failure, without even the Sharpe flattery (Sharpe is also negative).

### 3. `xsec_ss_meanrev_lc20` — REJECT (most interesting near-miss)

| Window | Regime | Trades | Return % | Sharpe | BH-Basket % | Beats BH? | BarA#1 |
|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 129 | -0.61 | -0.62 | -1.12 | ✅ | ✅(b) |
| 2022-Q3 chop | chop | 125 | -1.94 | -2.40 | -0.69 | ❌ | ❌ |
| 2023-H1 recovery | bull | 119 | -0.50 | -0.79 | +0.22 | ❌ | ❌ |
| 2023-Q3 chop | chop | 117 | +0.13 | 0.32 | -0.37 | ✅ | ✅ |
| 2024-Q2 bull | bull | 123 | +0.64 | **1.42** | -0.13 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 119 | +0.11 | 0.13 | -0.61 | ✅ | ✅ |
| 2025-Q3 bull | bull | 127 | +0.71 | **1.62** | +0.41 | ✅ | ✅ |
| 2026-recent bull | bull | 87 | -0.77 | -1.59 | +0.71 | ❌ | ❌ |

**Aggregate:** median ret **−0.19%** · 50% windows positive · 62% beat BH · **median Sharpe −0.25** · **trades 946** · worst_instrument_dd −24.37% · **ann. return on deployed −8.07%/yr**.
- Fitness gate: 🔴 FAIL (median ret ≤0, median Sharpe −0.25). #5(b): 🟢 PASS (−24.37%). Clause (f): 🔴 FAIL (−8.07%/yr).
- **Why it's the interesting one:** 5 of 8 windows are gross-positive, two with strong Sharpe (1.42, 1.62) — short-horizon single-name reversal *does* show a signal in calm/trending tapes (consistent with Lehmann/Lo-MacKinlay). **But** (a) the two chop windows (2022-Q3 −1.94%, 2026-recent −0.77%) gut it, and (b) at **946 round-trips** the 4bps + spread cost drag is enormous — gross edge is real but small, and turnover eats it. Net −8%/yr. This is the textbook "reversal alpha exists but is smaller than transaction costs at this notional/cadence" outcome. An honest REJECT, not a near-promote.

---

## Front-door verdict summary

| Candidate | Median Sharpe | Ann.Ret/deployed | worst_instr_DD | Fitness | BarA#1 | #5(b) | Clause(f) | **VERDICT** |
|---|---|---|---|---|---|---|---|---|
| `xsec_ss_momentum_lc20` | −0.41 | −1.78%/yr | −28.28% | 🔴 | 🔴 | 🟢 | 🔴 | **REJECT** |
| `xsec_ss_lowvol_lc20` | −0.40 | −7.50%/yr | −21.62% | 🔴 | 🔴 | 🟢 | 🔴 | **REJECT** |
| `xsec_ss_meanrev_lc20` | −0.25 | −8.07%/yr | −24.37% | 🔴 | 🔴 | 🟢 | 🔴 | **REJECT** |

**No PROMOTE-eligible candidate.** Not via the standard gate, not via the #5 fast-track. Every variant fails the Sharpe ≥1.0 leg (median Sharpe is *negative*) AND the clause (f) 8%/yr floor (every one is *negative* return). The #5(b) deployed-capital DD gate passes for all three — confirming the corrected DD ruler isn't what blocks these; the returns are. No return-floor side door was used or available (the floor is what kills them).

---

## Survivorship / lookahead / integrity notes

- **Lookahead:** uses the audited-clean `walk_forward_xsec` / `backtest_xsec` path (audit §4 PASS — strategy sees `bars[:cur+1]`, fills at that bar's close only `if has_bar_at_t`; regime SPY slice is `t[:10] <= date`). The 12-1 momentum signal explicitly *skips* the most recent 21 bars (no same-bar leak). No custom fill logic introduced.
- **Warmup:** momentum primed with 400d (>252+21 lookback) so the signal computes inside each labeled window; lowvol 120d (>60); meanrev 40d (>5). No window hit the `ZeroTradesError` warmup-starvation guard (trade counts 88/94/946 all > 0).
- **Survivorship:** addressed above — fixed mid-2020 large-cap universe, no IPO bias, mild-and-flagged delisting bias, laggards (BA/DIS) deliberately retained, not hindsight-selected.
- **Cost realism:** `alpaca_stocks` 4bps round-trip active; the mean-reversion result is the proof-of-life that costs bit (gross-positive windows → net −8%/yr at 946 trades).
- **Sharpe annualization:** corrected √252 path (the equity-class branch in `backtest_xsec`, since the basket has no `/USD` legs). All Sharpes above are post-fix.

---

## Candidate dirs written (ALL to `strategies_candidates/` — zero to `strategies/`)

```
strategies_candidates/xsec_ss_momentum_lc20/   (params.json + strategy.py)
strategies_candidates/xsec_ss_lowvol_lc20/     (params.json + strategy.py)
strategies_candidates/xsec_ss_meanrev_lc20/    (params.json + strategy.py)
```

Verified: `ls strategies/ | grep -c xsec_ss` → **0**.

## Protected files — UNTOUCHED (confirmed)

`runner.py`, `risk.py`, `runner_xsec.py`, `backtest.py` — not modified. Also did not touch `walk_forward_xsec.py` or `backtest_xsec.py` (the Bar A evaluators). No runner-logic edits of any kind. A throwaway driver `_drive_ss_xsec.py` was written to the workspace root to load candidates from `strategies_candidates/` and run the existing walk-forward (it only *calls* the harness; it does not modify it). Full suite: **237 passed**.

---

## Recommendation

**REJECT the single-stock cross-sectional lane at this notional/cadence — for now.** The three canonical archetypes (momentum, low-vol, short-reversal) on a clean 20-name large-cap universe all fail honestly. The most promising *signal* is short-horizon reversal (gross-positive in 5/8 windows, Sharpe up to 1.62 in calm tapes), but it is **cost-strangled** at 946 trades — the edge is real but smaller than the round-trip cost at $100 deployed. The lane is not dead, but the obvious parameterizations don't clear the corrected bar. The tournament's ZERO-live-promotions state is unchanged by this work, which is the correct outcome under the corrected ruler: an honest reject is a good result.
