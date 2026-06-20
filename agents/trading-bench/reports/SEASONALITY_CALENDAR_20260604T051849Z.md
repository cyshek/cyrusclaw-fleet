# SEASONALITY / CALENDAR STRUCTURE — Lane 3 Research Report

**UTC timestamp:** 20260604T051849Z
**Lane:** #3 of `reports/RESEARCH_SLATE_20260603.md` — Seasonality / calendar structure
**Author:** research subagent (Tessera trading-bench)
**Scratch dir:** `strategies_candidates/seasonality_calendar/`
**Evaluator:** EXISTING `runner/sweep.py` → `runner/walk_forward.py` → `runner/backtest.py` + `runner/fp_sharpe.py`. No protected file edited.
**Protected-file md5 (verified unchanged at finish):**
`runner.py=4be185e4bdcb6f432d99b71b21a4859c` · `backtest.py=9444ee5be64d9fd2639fd8cb0a28e002` · `backtest_xsec.py=2278a4c8d8a66703da5cd6f2a0880061` · `risk.py=e4c227e019c99e7e52224eb2f91389b8`

---

## VERDICT: **REJECT** (conclusive across all five pre-registered calendar families)

Headline number: the single best front-door-passing cell across the entire grid —
**Tuesday-only (`dow_in=[1]`), FP-cont Sharpe +1.17** — is **auto-flagged KNIFE_EDGE** by the
robustness classifier and **collapses to Sharpe 0.46 on the continuous full span** (vs
buy-and-hold-SPY 0.945). Every other calendar family is sub-1.0 FP-cont Sharpe, mostly
**negative**, and no family produces a robust PLATEAU. **No calendar-structure signal beats
buy-and-hold-SPY on a risk-adjusted basis net of 2bps cost.** An honest REJECT.

---

## 1. Thesis (falsifiable, restated)

Does any calendar-structure signal — turn-of-month, day-of-week, pre-holiday drift, FOMC-day
drift, sell-in-May/seasonal — beat buy-and-hold SPY on a RISK-ADJUSTED basis (FP-continuous-span
Sharpe ≥ 1.0) net of realistic cost, on a **robust PLATEAU** of definitions rather than one
cherry-picked window?

Why this lane: calendar effects are orthogonal to the (conclusively dead) price-momentum lanes.
But they are ALSO the single easiest place to overfit via multiple comparisons, so the trust bar
is high: a lone passing cell is presumed a dredging artifact unless neighbors confirm it.

## 2. Pre-registered windows / grids (LOCKED before viewing any returns)

These grids were written into `sweep_driver.py` **before** any return was inspected. Each family
is swept as a grid and demands a PLATEAU (≥1 passing ±1-step neighbor), not a knife-edge.

| Family | Mode | Pre-registered grid |
|---|---|---|
| Turn-of-month | `tom` | `tom_pre ∈ {1,2,3}` × `tom_post ∈ {1,2,3,4}` (12 cells) |
| Day-of-week | `dow` | `dow_in ∈ {[Mon],[Tue],[Wed],[Thu],[Fri],[Mon,Tue],[Tue,Wed],[Mon,Fri],all}` (9 cells) |
| Pre-holiday | `preholiday` | `preh_days ∈ {1,2,3}` (3 cells) |
| FOMC drift | `fomc` | `fomc_pre ∈ {0,1,2}` × `fomc_post ∈ {0,1,2}` (9 cells) |
| Sell-in-May / Halloween | `sellinmay` | `sim_in_months ∈ {Nov–Apr, Nov–Mar, Oct–Apr, Nov–May}` (4 cells) |

**Construction guarantees (anti-leak, anti-p-hack):**
- The signal is a pure function of the **current daily bar's calendar date** — zero price/momentum
  input, so it is orthogonal-by-construction to every rejected price lane.
- Holiday and FOMC date tables are **static date lists** (no price look-ahead). Classification
  for bar `i` uses only `bars[:i+1]`; the action fills at bar `i`'s close (same fill contract as
  `buy_and_hold_spy`). One-bar entry/exit lag at window edges is REAL and is paid through the
  `CostModel` on every transition.
- Cost model: `CostModel.alpaca_stocks()` = **2.0 bps one-way** (asserted ACTIVE by the sweep; no
  zero-cost path). `notional_usd=1000` on a `$1000` book → fully-deployed when long, so FP-cont
  Sharpe is a clean read of the long-or-flat timing series and deployed-return == bench-return.
- Data: SPY daily bars, IEX free-tier, deepest continuous history available = **2020-07-27 →
  2026-05-22 (~1464 bars, ~5.8 yr)**. Windowed eval uses the 8 named regime windows in
  `runner/walk_forward.py::NAMED_WINDOWS` (5 bull / 2 chop / 3 bear) + the legacy 60-day window.
  FP-cont Sharpe is the canonical concatenated-tick number from `runner/fp_sharpe.py` (clause-a bar).

## 3. Sweep grid — honest FP-cont Sharpe per cell

Primary rank key = full-period continuous-span Sharpe (clause a). med-win Sharpe is the
SECONDARY/generous mirage number, shown only for contrast. Front-door PASS = fitness gate + Bar A
#1 + #5(b)-DD all pass (FP-cont < 1.0 is also recorded as a clause-(a) reject reason).

### 3.1 Turn-of-month — REJECT (uniform fail, no plateau)
Best cell FP-cont Sharpe **−0.06** (`tom_pre=1,tom_post=4`); every one of 12 cells negative.
Heavy cost drag (~53 round-trips). The famous "med-win" numbers go as high as +0.98 — a textbook
illustration of why median-of-windows is a mirage; clause-a kills all of them. **0/12 pass.**

### 3.2 Day-of-week — REJECT (lone Tuesday cell is KNIFE_EDGE, does not replicate)
| cell | FP-cont Sharpe (a) | med-win | ann/deployed% | round-trips | verdict | robustness |
|---|---|---|---|---|---|---|
| `dow_in=[Tue]` | **+1.17** | +1.03 | +7.61 | 195 | PASS | **KNIFE_EDGE** |
| `dow_in=[Mon,Tue]` | +0.78 | +1.08 | +6.25 | 197 | PASS(a) | KNIFE_EDGE |
| `dow_in=[Tue,Wed]` | +0.33 | +0.08 | +2.96 | 196 | REJECT(a) | — |
| `dow_in=[all]` (=BH) | −0.04 | +0.45 | −0.47 | 8 | REJECT(a) | — |
| `dow_in=[Mon,Fri]` | −0.40 | +1.19 | −2.85 | 197 | REJECT(a) | — |
| `dow_in=[Mon]` | −0.52 | — | −2.78 | 174 | REJECT(a) | — |
| `dow_in=[Thu]` | −0.73 | — | −5.54 | 197 | REJECT(a) | — |
| `dow_in=[Wed]` | −1.05 | — | −6.74 | 193 | REJECT(a) | — |

Only `[Tue]` clears FP-cont ≥1.0, and the harness flags it **KNIFE_EDGE**: its ±1 neighbors fall
to +0.78 and +0.33. The "Tuesday effect" is a well-known data-dredging artifact (1-of-5 days × many
specs = guaranteed false positive). The classifier caught it automatically. **No plateau.**

### 3.3 Pre-holiday — REJECT (uniform fail)
All 3 cells negative FP-cont Sharpe (−0.52, −0.52, −0.84). The classic pre-holiday drift does not
survive cost on this span. **0/3 pass.**

### 3.4 FOMC drift — REJECT (the two "PLATEAU" tags are negative-Sharpe)
Best cell FP-cont Sharpe **+0.13** (`fomc_pre=1,fomc_post=2`). Two cells are robustness-tagged
PLATEAU (`pre=1,post=0` and `pre=1,post=1`) but at FP-cont **−0.03 and −0.09** — they only earn the
tag because they pass the fitness gate while still failing clause-a. A negative-Sharpe plateau is
not an edge. **0/9 clear the 1.0 bar.**

### 3.5 Sell-in-May / Halloween — REJECT (near-zero)
Best cell FP-cont Sharpe **+0.22** (`Nov–May`), the rest ≤+0.15 or negative. Only 5–8 round-trips
over 5.8yr → tiny n, wide worst-instrument DD (−19%). No plateau, no edge. **0/4 pass.**

## 4. Plateau-vs-knife-edge classification (summary)

| Family | cells | front-door pass | PLATEAU | KNIFE_EDGE | best FP-cont Sharpe (a) |
|---|---|---|---|---|---|
| Turn-of-month | 12 | 0 | 0 | 0 | −0.06 |
| Day-of-week | 9 | 2 | **0** | 2 | +1.17 (knife-edge) |
| Pre-holiday | 3 | 0 | 0 | 0 | −0.52 |
| FOMC | 9 | 2 | 2 (both neg-Sharpe) | 0 | +0.13 |
| Sell-in-May | 4 | 0 | 0 | 0 | +0.22 |

**No family produced a single robust, clause-a-passing PLATEAU.** The only cells that clear the
clause-a Sharpe-≥1.0 bar (Tuesday-only and its Mon+Tue neighbor) are explicitly auto-flagged
KNIFE_EDGE — precisely the overfit signature this lane was warned to expect.

## 5. SPX-relative comparison (the decisive cross-check)

The windowed FP-cont +1.17 for Tuesday-only is a **seam artifact** of concatenating 8 disjoint
90-day windows. Re-run on the **single continuous 2020→2026 span** (no seams) and against
buy-and-hold, the "edge" evaporates:

| Symbol | Tuesday-only Sharpe | Tuesday-only ret% | Buy&Hold Sharpe | Buy&Hold ret% |
|---|---|---|---|---|
| SPY | **0.464** | +21.4 | **0.945** | +130.6 |
| QQQ | 0.503 | +32.5 | 0.889 | +175.8 |
| XLK | 0.675 | +49.8 | 0.476 | +68.7 |
| XLF | 0.399 | +18.3 | 0.788 | +115.8 |
| IWM | 0.141 | +5.8 | 0.613 | +93.1 |

On the continuous span Tuesday-only is **below buy-and-hold on 4 of 5 liquid ETFs** (the lone
XLK "win" is itself a knife-edge — one symbol, one weekday). The supposed +1.17 does **not**
replicate out of the specific windowed concatenation. Buy-and-hold-SPY (Sharpe 0.945) beats every
calendar subset on a risk-adjusted basis. **There is no SPX-relative calendar edge here.**

## 6. Why REJECT is the right call

1. **No robust plateau exists.** Across 37 pre-registered cells in 5 families, zero clause-a-passing
   PLATEAUs. The only ≥1.0 cells are auto-classified KNIFE_EDGE.
2. **The one positive (Tuesday) fails replication** — collapses to 0.46 on the continuous span and
   loses to buy-and-hold on 4/5 ETFs. It is a multiple-comparisons artifact, not signal.
3. **Cost kills the high-frequency calendar modes** (TOM, DoW pairs: ~50–200 round-trips/yr at 2bps
   one-way). The low-frequency modes (sell-in-May, pre-holiday, FOMC) have too few trades and no
   risk-adjusted edge.
4. **Buy-and-hold-SPY is the cleaner risk-adjusted bet** on this span — calendar timing only
   subtracts exposure and adds friction.

This is consistent with the slate's prior pattern: orthogonal-but-sub-bar. Calendar structure joins
the rejected lanes. **It was worth testing cheaply (the lane is genuinely orthogonal), and it failed
honestly.**

## 7. What could change the verdict (undetermined-needs-X — NOT claimed here)

- **Longer history.** IEX free-tier caps at ~2020-07. Several documented calendar effects (TOM,
  Halloween) are estimated on 40–90yr samples; 5.8yr is underpowered for the low-frequency modes
  (sell-in-May ran on n=6 cycles). A paid daily-history feed back to ~1993 (SPY inception) would
  give a real test of the seasonal modes — but the day-frequency modes (TOM/DoW) already had ample
  n here and still failed net of cost, so more history is unlikely to rescue them.
- This is logged as a **data-depth caveat**, not a reason to withhold the REJECT. On the data we
  have, the verdict is unambiguous.

## 8. Reproduction

```
cd <workspace>
python3 strategies_candidates/seasonality_calendar/sweep_driver.py   # full grid → sweep_out.txt
```
Artifacts (all in `strategies_candidates/seasonality_calendar/`, isolated scratch — NOT promoted):
`strategy.py` (calendar decide fn), `params.json`, `sweep_driver.py`, `sweep_out.txt` (raw sweep tables).

**Promotion authority: NONE.** Candidate stays in `strategies_candidates/`. Tessera reviews/merges.
