# Backtest: Overnight-Drift SMALL-CAP BASKET (archetype #7, academically-correct)

**UTC:** 20260602T071633Z
**Author:** trading-bench subagent (`overnight small-cap basket on event harness`)
**Candidate:** `strategies_candidates/overnight_basket_d6cde5/`
**Harness:** `runner/backtest_event.py` (event-driven, shared-cash) + NEW opt-in `exit_fill="next_open"` path
**Archetype:** #7 — overnight vs intraday drift, Lou/Polk/Skouras 2019 ("A Tug of War: Overnight Versus Intraday Expected Returns", JFE 134).
**Gate evaluated:** GATE.md Bar A (front door: clause (a) fp-cont Sharpe ≥ 1.0; clause (f) ≥ 8%/yr net on deployed).

> Status: report written INCREMENTALLY. Sections appended as computed. Final verdict at bottom.

---

## 0. Why this run exists (and why the 5/30 SPY test couldn't answer it)

The 2026-05-30 overnight-SPY test (`reports/BACKTEST_OVERNIGHT_SPY_20260530T171621Z.md`) reproduced the *direction* of the Lou/Polk/Skouras finding (gross overnight returns positive) but FAILED Bar A: it was (a) single-symbol SPY — the published effect lives in **small-caps**, not mega-cap indices; (b) on an isolated-$1000 single-symbol harness with no shared-cash portfolio Sharpe; (c) forced onto 1Hour bars whose "MOO proxy" washed in ~30 min of intraday drift; and (d) cost-strangled at $100 notional on one name. The 5/30 report's own §"Should we revisit?" named the fix: **a small-cap BASKET held purely overnight with shared cash** on a harness that supports next-bar-OPEN exits. That harness (`backtest_event.py`) now exists; this run builds the missing open-fill path and runs the correct test.

---

## 1. Harness-honesty disclosure (read first) — which fill path, and why

The economic intent is **buy market-on-close (MOC), sell next-session market-on-open (MOO)** — the pure overnight (close→open) hold, with ZERO intraday exposure.

**What I added (additive, opt-in, default-off):** a new `exit_fill` param on `backtest_event.backtest_event`:
- `exit_fill="close"` (DEFAULT, legacy, bit-for-bit unchanged) — exit fills at the triggering bar's CLOSE.
- `exit_fill="next_open"` (NEW, opt-in) — exit fills at the triggering bar's OPEN.

With `holding_bars=1`, the hold-horizon exit fires on the bar *after* entry; filling that exit at the bar's OPEN == selling at the next session's market-open. Entry is the buy at the entry bar's CLOSE (MOC). So the realized trade is **close(D+1) → open(D+2)**: one clean overnight hold, no intraday wash. This is the precise MOC→MOO formulation the 5/30 report said the harness would need (it estimated "~30-line change"; the actual change is ~20 LOC, fully additive).

**Change scope & safety:**
- Touched ONLY `runner/backtest_event.py` (the harness, NOT a protected file).
- ~20 LOC, default `"close"` preserves legacy path exactly (pinned by `test_explicit_close_equals_default`).
- 6 new pinning tests in `tests/test_backtest_event.py` (`TestNextOpenExitFill`): open-vs-close fill, default-unchanged, explicit-close==default equity-curve identity, bad-value fallback, sell-spread-applied-to-open, window-end-still-close.
- Full suite: **283 → 289 passed (+6), 0 regressions.**
- Protected files (`runner/runner.py`, `runner/risk.py`, `runner/backtest.py`, `runner/backtest_xsec.py`) md5-unchanged (verified end of report).

**The test I ran is therefore the PURE overnight test** (`exit_fill="next_open"`), not the close→close lower-bound. I additionally ran the close→close legacy path as a control to show how much the intraday tail matters.

---

## 2. Universe + survivorship note

Reused the **29 hand-picked small/mid-cap US names** from the PEAD lane (`strategies_candidates/pead_event_smallcap/earnings_universe.py`), across consumer/industrial/tech/materials/restaurants: CROX, DECK, BLDR, RMBS, SMCI, CELH, ELF, ANF, PLAB, FSLR, WING, TXRH, CALM, MTH, SHAK, CVNA, UPWK, FIVN, DOCN, AAON, ATKR, CRS, KFRC, SPSC, NSSC, UFPT, POWL, TGLS, SHLS.

**Survivorship bias (POSITIVE, disclosed):** currently-listed names only, NOT delisting-aware. Reported edge is an **UPPER bound**. An honest REJECT under this generous universe is a STRONG reject (same disclosure as the PEAD lane). Same direction-of-bias argument as PEAD: the tailwind only makes a reject more robust.

---

## 3. Fixed construction params (set BEFORE seeing results)

| param | value | rationale |
|---|---|---|
| signal | overnight = hold every name from each session close to the next session open | unconditional (every trading day is an "event"), per Lou/Polk/Skouras |
| holding_bars | 1 | pure overnight (one night per event) |
| exit_fill | `next_open` | MOC→MOO; no intraday wash |
| stop_pct / take_pct | −0.99 / +9.9 | intentionally disabled so ONLY the 1-bar hold fires (testing the pure premium, not a stop overlay) |
| notional / book | $100 per position / $1000 shared cash | equal-weight, shared-cash basket |
| max_concurrent | 10 | book fully deployed at 10 names/night; declines counted |
| cost model | harness default (~4 bps round-trip equities, spread 2 bps one-way) | NOT weakened — cost drag is the whole question for a daily-trading strategy |
| regime ablation | SPY > 200SMA (no-lookahead) | tested as ablation only, not headline |

Results appended below as computed.

---

## 4. Results

Run: `python3 -m strategies_candidates.overnight_basket_d6cde5.run_lane --days 900`
Span: 615 shared-clock ticks (~2.4yr of Alpaca IEX daily bars), 29 names, 17,777 day-events resolved (17,748 genuinely in-window). Book fully deployed (max_concurrent hit 10; ~11k events declined-for-cap, counted not dropped — the basket is cap-bound as designed).

### Headline: UNCONDITIONAL pure-overnight (MOC→MOO), shared-cash basket

| metric | NET (real cost model) | GROSS (zero-cost) |
|---|---|---|
| n trades | 6099 | 6099 |
| **fp-continuous Sharpe** | **0.543** | **1.054** |
| total return (on $1000 book) | +21.95% | +47.23% |
| **ann. return on deployed** | **+9.49%** | +21.50% |
| win rate | 52.1% | — |
| portfolio max-DD | −22.39% | — |
| **worst-instrument DD** | **−83.72%** | — |
| total costs | $244.03 | $0.00 |
| BH-SPY same-path | +61.59% | +61.59% |
| **beats BH-SPY?** | **No** | No |

### Ablations / controls

| variant | Sharpe (NET) | total ret (NET) | ann-deployed (NET) | Sharpe (GROSS) | win | notes |
|---|---|---|---|---|---|---|
| **Unconditional, next_open (headline)** | **0.543** | +21.95% | +9.49% | **1.054** | 52.1% | the pure overnight test |
| Regime SPY>200SMA, next_open | 0.332 | +8.36% | +6.03% | 0.794 | 50.7% | filter HURT (cut Sharpe, halved trades) |
| Close→close control, next_open=off | 0.415 | +19.66% | +8.44% | — | 49.7% | intraday-washed lower bound |

**Two clean findings:**
1. **The gross overnight edge is REAL and meaningfully positive in this small-cap basket — gross Sharpe 1.054, +21.5%/yr-on-deployed.** This is the strongest gross signal the overnight archetype has produced (the 5/30 SPY test was gross-barely-positive). The published small-cap effect reproduces: the basket form + small-cap universe is where the premium lives, exactly as Lou/Polk/Skouras predict.
2. **Costs cut it roughly in half: net Sharpe 0.543, net +9.49%/yr-on-deployed.** Trading 29 names every night = ~6,100 round trips → $244 of costs on a $1000 book. The cost drag is the whole story, identical conclusion to the 5/30 SPY report — just now on the academically-correct construction where the gross edge is much larger and *almost* survives.
3. **The 200SMA regime filter HURT** (net Sharpe 0.543 → 0.332). It halved the trade count without improving Sharpe-per-trade enough to compensate — consistent with the 5/30 SPY finding that the filter's benefit is marginal-to-negative on median. NOT used in the headline.
4. **Pure-overnight (next_open) beats the close→close control** (net Sharpe 0.543 vs 0.415; the control's portfolio max-DD is also worse at −27.5% vs −22.4%). Isolating the overnight leg from the intraday wash genuinely helps — validating both the harness feature and the economic thesis (intraday drift is a drag).

---

## 5. Front-door verdict vs GATE.md Bar A

| clause | bar | result | pass? |
|---|---|---|---|
| (a) fp-cont Sharpe ≥ 1.0 | ≥ 1.0 | **0.543 NET** | ❌ FAIL |
| (f) ≥ 8%/yr net on deployed | ≥ 8.0% | **+9.49% NET** | ✅ pass |
| #5(b) worst-instrument DD ≤ 30% | ≤ 30% | **−83.72%** | ❌ FAIL (hard) |
| beats BH-SPY risk-adjusted | — | BH-SPY +61.6% vs +21.95% | ❌ No |

**VERDICT: HONEST REJECT.** Stays in `strategies_candidates/`. Do NOT promote. Zero promotions made.

Two independent primary guards fail: clause (a) Sharpe (0.543, ~half the bar) and #5(b) worst-instrument drawdown (−83.7% — a single small-cap leg can crater on an overnight gap; the basket-of-volatile-small-caps eats catastrophic single-name overnight moves, which the deployed-capital DD correctly surfaces and the diluted portfolio-NAV DD of −22% would have hidden — exactly the bug RULING 2 fixed). Clause (f) passes at +9.49%, but (a) is a co-primary AND guard, so passing (f) alone does not graduate. It also loses outright to buy-and-hold SPY over the same span.

This is the **best** overnight result to date (gross Sharpe 1.054 vs the 5/30 SPY's gross-barely-positive), and it is the *correct* test (small-cap basket, shared cash, pure MOC→MOO). The reject is therefore high-confidence and final for this archetype at retail (Alpaca ~4bps round-trip) cost: **the gross small-cap overnight premium is real but does not survive retail transaction costs at $100 notional traded daily.** Same economic wall the 5/30 report hit, now confirmed on the academically-correct construction with the gross edge much larger and still not enough. Net edge would need either institutional execution (tighter spreads) or far larger notional to amortize the per-trade friction — neither available without real-money approval. **Archetype #7 is a documented null at retail cost; do not re-open without a cheaper execution venue.**

---

## 6. No-lookahead confirmation

- Entry bar is strictly `reaction_bar + 1` (`require_gap_after_event=True`), pinned by existing harness tests. Buy fills at the entry bar's close.
- `exit_fill="next_open"` sells at the *next* bar's OPEN (the bar where the 1-bar hold-horizon fires) — that bar is strictly after entry; no future close is ever used for the fill. Pinned by `tests/test_backtest_event.py::TestNextOpenExitFill` (6 tests).
- Regime filter uses SPY 200SMA computed no-lookahead (SMA at date X uses only closes with t ≤ X); dates before 200 bars are conservatively flat.
- `decide_event` receives only `bars[t ≤ clock_t]` (existing pin `test_decide_event_never_sees_future`).

## 7. Protected files UNCHANGED (md5, captured 20260602T07xxZ, post-run)

```
4be185e4bdcb6f432d99b71b21a4859c  runner/runner.py
e4c227e019c99e7e52224eb2f91389b8  runner/risk.py
9444ee5be64d9fd2639fd8cb0a28e002  runner/backtest.py
2278a4c8d8a66703da5cd6f2a0880061  runner/backtest_xsec.py
```
Identical to the pre-run baseline. Only `runner/backtest_event.py` (the harness, non-protected) gained the additive opt-in `exit_fill` path; `tests/test_backtest_event.py` gained 6 pins. **Zero promotions. No cron edits. No STOP_TRADING changes. Paper/backtest only.**

## 8. Deliverables

- `strategies_candidates/overnight_basket_d6cde5/` — `strategy.py` (decide_event), `params.json`, `run_lane.py`, `earnings_universe`-style universe inline, `last_run.json` (headline=unconditional NET + `_comparison` block for all 5 runs).
- `runner/backtest_event.py` — NEW opt-in `exit_fill="next_open"` path (~20 LOC, default-off, legacy-identical).
- `tests/test_backtest_event.py` — `TestNextOpenExitFill` (+6 tests). Suite 283 → **289 green, 0 regressions**.
- This report.

**Bottom line:** the academically-correct small-cap overnight basket reproduces the published gross edge (gross Sharpe 1.054) on a now-correct harness, but **rejects net of retail costs** (net Sharpe 0.543, worst-instrument DD −83.7%, loses to BH-SPY). A clean, high-confidence REJECT with a sound test — the ruler works.
