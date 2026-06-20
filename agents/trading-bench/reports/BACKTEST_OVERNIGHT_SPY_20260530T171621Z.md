# Backtest: Overnight-Drift SPY (archetype #7)

**Date:** 2026-05-30 17:16 UTC
**Author:** trading-bench subagent
**Candidates:**
- `strategies_candidates/overnight_spy_31408d4a/` (regime-filtered, primary)
- `strategies_candidates/overnight_spy_unfiltered_31408d4a/` (no regime gate, ablation)
**Archetype:** #7 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` — overnight vs intraday drift, Lou/Polk/Skouras 2019 ("A Tug of War: Overnight Versus Intraday Expected Returns").
**Gate evaluated:** Bar A from `GATE.md`.

---

## ⚠️ Harness Honesty Disclosure (read first)

The economic intent of this strategy is **buy market-on-close (MOC), sell next-session market-on-open (MOO)** on SPY, in order to capture the overnight equity premium while avoiding intraday drift.

Our backtester (`runner/backtest.py`) only models **one fill price per bar: the bar's CLOSE**, modified by a `CostModel` spread. It does NOT support "buy at this bar's close, sell at next bar's open" in a single bar step.

### What this means on daily bars

If we ran this on `1Day` SPY bars, the cleanest harness interpretation would be: buy at close_T, close at close_{T+1}. That captures the **entire 24-hour return** — exactly washing out the overnight-vs-intraday split this strategy is designed to test. Such a backtest would not be a test of the published edge; it would be a slightly-leveraged buy-and-hold. **I refuse to ship that.**

### What I did instead

Operate on **1Hour SPY bars** (Alpaca IEX). The 1Hour bars are timestamped by their START in UTC. Specifically:

- The **last RTH hour bar** (timestamp `19:00Z` in EDT / `20:00Z` in EST, covering 15:00–16:00 ET) **closes AT the official 4 pm ET close**. A BUY filled at this bar's close is *exactly* the MOC fill we want. ✅
- The closest harness analogue to MOO is the **first bar of the next session** (timestamp `13:00Z` in EDT, covering 9:00–10:00 ET). That bar's CLOSE is ~10:00 ET — **30 to 60 minutes after the official 9:30 ET open.** A SELL at that bar's close captures `(overnight gap) + (first ~30 min of intraday)`.

Per Lou/Polk/Skouras, intraday drift is on average ~zero or slightly negative. So our 30-minute intraday tail is a small **drag** on captured return relative to the pure MOC→MOO trade. **This makes the backtest CONSERVATIVE** — a positive result here is a *lower bound* on the pure-overnight strategy. A null or slightly-negative result is ambiguous: it could be (a) the published edge has decayed, (b) our 30-min-intraday tail ate the edge, (c) cost-model drag, or (d) both. We discuss which it appears to be below.

### What the harness would need to model the strategy precisely

To backtest pure MOC→MOO on daily bars cleanly, the harness would need to support **two fill prices per bar** (or equivalently, expose `bar.o` as the next-bar fill price for limit-on-open orders). Specifically, an `Action.fill_at_next_open=True` field, executed as `qty = notional / bar[i+1].o`, with the bar[i+1] fill consuming that bar's open price. That's a ~30-line change in `backtest.py`'s fill loop plus a contract bump for `runner/runner.py`. Out of scope for this subagent; flagging for future work if archetype #7 ever shows enough promise to be worth the harness change.

---

## Strategy spec (as implemented)

State machine, evaluated on every 1Hour SPY bar at bar-close:

1. **Exit (MOO proxy):** if `bars[-1].session_date != bars[-2].session_date` AND long → CLOSE. (First bar of new session; we exit at its hourly close ≈ 10 am ET.)
2. **Entry (MOC):** if it's the **last RTH hour** (`et.hour == 15`, i.e. 3 pm–4 pm ET bar) AND flat AND regime filter passes → BUY $100 notional at bar close (= 4 pm ET MOC).
3. Otherwise: hold.

Long-only. We skip the academic strategy's short-intraday leg.

Regime filter (filtered variant only): `regime_uptrend(spy_closes, period=50)` — only enter when SPY > its 50-day SMA. Uses the regime panel that `runner/backtest.py` pre-loads.

Holidays / weekends fall out for free: with no bars between Fri 19:00Z and Mon 13:00Z, the "new session date" check correctly fires the close on the first Monday bar.

---

## Bar A scorecard

| Bar A criterion | Filtered variant | Unfiltered variant |
|---|---|---|
| (1) Walk-forward positive median per regime, post-cost | ❌ median across windows **negative** | ❌ median across windows **negative** |
| (2) Held-out final regime (`2026-recent bull`) passes | ⚠️ +0.13% (positive but does not beat BH-SPY) | ⚠️ +0.38% (positive but does not beat BH-SPY) |
| (3) Cost-aware Sharpe ≥ 0.5 (full period) | ❌ median Sharpe **−1.96** | ❌ median Sharpe **−0.73** |
| (4) Trade count ≥ 30 | ✅ 534 across 8 windows | ✅ 938 across 8 windows |
| (5) Max drawdown ≤ 30% post-cost | ✅ worst window DD −0.86% (tiny — single-night exposure) | ✅ worst window DD −1.86% |
| (6) AST code-review gate | (not yet run — strategy stays in candidates regardless) | — |
| (7) `./tick.sh` smoke test | (not run — Bar A is failed on metrics first) | — |

**Verdict: BOTH VARIANTS FAIL Bar A.** Stays in `strategies_candidates/`.

---

## Walk-forward summary

### Filtered variant (`overnight_spy_31408d4a`)

```
windows=8/8  medRet=-0.102%  pos=38%  beatBH=50%  medSharpe=-1.96
worst=-0.518% (2023-H1 recovery)   best=+0.272% (2025-Q3 bull)
total trades across all windows: 534
```

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear        | bear | 532 |  16 | −0.091 | −2.03 | −0.28 | −1.711 | ✅ |
| 2022-Q3 chop        | chop | 531 |  62 | −0.338 | −3.35 | −0.53 | −0.429 | ✅ |
| 2023-H1 recovery    | bull | 516 |  75 | **−0.518** | −5.39 | −0.86 | +0.653 | ❌ |
| 2023-Q3 chop        | chop | 502 |  72 | +0.054 | +0.73 | −0.24 | −0.359 | ✅ |
| 2024-Q2 bull        | bull | 492 |  93 | −0.113 | −1.89 | −0.25 | +0.511 | ❌ |
| 2025-Q1 tariff bear | bear | 494 |  30 | −0.343 | −6.34 | −0.34 | −0.827 | ✅ |
| 2025-Q3 bull        | bull | 526 | 121 | +0.272 | +3.96 | −0.25 | +0.709 | ❌ |
| 2026-recent bull    | bull | 363 |  65 | +0.125 | +2.61 | −0.18 | +1.453 | ❌ |

### Unfiltered variant (`overnight_spy_unfiltered_31408d4a`)

```
windows=8/8  medRet=-0.138%  pos=50%  beatBH=25%  medSharpe=-0.73
worst=-1.313% (2025-Q1 tariff bear)   best=+0.375% (2026-recent bull)
total trades across all windows: 938
```

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear        | bear | 532 | 121 | −0.774 | −4.16 | −0.79 | −1.711 | ✅ |
| 2022-Q3 chop        | chop | 531 | 125 | −0.548 | −3.52 | −0.77 | −0.429 | ❌ |
| 2023-H1 recovery    | bull | 516 | 123 | −0.388 | −2.91 | −0.98 | +0.653 | ❌ |
| 2023-Q3 chop        | chop | 502 | 123 | +0.164 | +1.82 | −0.39 | −0.359 | ✅ |
| 2024-Q2 bull        | bull | 492 | 123 | +0.112 | +1.45 | −0.23 | +0.511 | ❌ |
| 2025-Q1 tariff bear | bear | 494 | 121 | **−1.313** | −6.24 | −1.86 | −0.827 | ❌ |
| 2025-Q3 bull        | bull | 526 | 121 | +0.272 | +3.96 | −0.25 | +0.709 | ❌ |
| 2026-recent bull    | bull | 363 |  81 | +0.375 | +4.43 | −0.19 | +1.453 | ❌ |

(Note: 2025-Q3 numbers match identically across variants — the regime filter happened to be ON the entire window, so filtered = unfiltered there. Sanity check passes.)

---

## Full-period stats

Aggregated across all 8 named windows (treating each window's $1000 starting equity independently):

| Stat | Filtered | Unfiltered |
|---|---|---|
| Sum of returns (pp) | −1.05 | −2.10 |
| Mean return / window (pp) | −0.131 | −0.262 |
| Median return / window (pp) | **−0.102** | **−0.138** |
| Stdev across windows (pp) | 0.272 | 0.580 |
| Median Sharpe | **−1.96** | **−0.73** |
| Worst window DD | −0.86 | −1.86 |
| Round-trip cost per trade (bps round-trip, alpaca_stocks) | ~4 bps | ~4 bps |
| Implied cost drag per window (estimate) | ~−0.13% to −0.48% | ~−0.49% on average |

**The cost-drag estimate explains essentially all of the negative median.** Filtered variant: median ~67 trades/window × 4 bps round-trip × ($100/$1000 scaling) ≈ −0.27% cost drag per window. Median return is −0.10%, so gross-of-cost median is ~+0.17% — *barely* positive. Unfiltered variant: 121 trades × 4 bps × 0.1 = −0.48% cost drag, vs −0.14% median return, so gross-of-cost ~+0.34% per window.

So the strategy has **a weak positive signal pre-cost** but **costs eat it post-cost** on Alpaca stocks (2bps one-way).

---

## Verdict

**FAIL Bar A. Both variants stay in `strategies_candidates/`. Do NOT promote.**

The strategy reproduces the *direction* of the Lou/Polk/Skouras finding (gross overnight returns are positive on average) but **does not survive transaction costs** at our backtest scale ($100 notional, ~4bps round-trip on SPY). The 50-day SMA regime filter halves the trade count and improves Sharpe-per-trade modestly (best window Sharpe goes from +4.43 unfiltered to +3.96 filtered, but median improves from −0.73 to a worse −1.96 because the filter creates concentration risk — when it's wrong it's wrong on most of the window). Neither variant beats buy-and-hold SPY in the recent bull regimes (2023-H1, 2024-Q2, 2025-Q3, 2026-recent), which is the whole point of an alpha strategy.

Real money would lose here. Killing the candidates from the live-promotion path; archiving as a documented null-result for archetype #7.

---

## Discussion

**Why didn't it work?** Two compounding issues. First, our cost model (2 bps one-way, 4 bps round-trip on SPY) is realistic for Alpaca stocks but the academic overnight premium is small — Lou/Polk show ~5–7 bps per night gross on broad-market indices in their sample, with massive variation around that. At our 4-bps cost ceiling, the post-cost edge is ~1–3 bps per night, which is well inside the noise band of daily SPY moves (SPY's daily stdev is ~100 bps). You'd need either a much larger trade size to amortize the per-trade $0.04 friction floor, a tighter spread (institutional execution, not Alpaca retail), or a higher-vol underlying (small-caps, tech ETFs) where the overnight premium has historically been larger in absolute terms. Second, our 30-min-intraday tail eats a real-but-small chunk of the edge as discussed in the disclosure; this is a harness limitation, not a strategy flaw, but it makes our number worse than the true MOC→MOO would be.

**Should we revisit?** Three plausible follow-ups, in priority order: (1) **upgrade the harness** to support next-bar-open fills (~30-line change in `backtest.py` per the disclosure section) and re-test on `1Day` bars — this would let us back-test the pure MOC→MOO formulation cleanly and isolate whether the failure is cost-driven or harness-tail-driven; (2) try the same strategy on a **higher-vol overnight-premium-richer ETF** (XLK, ARKK, IWM) where the absolute overnight gap is larger and the percent-cost is the same; (3) **basket version** — Lou/Polk find the overnight premium is much stronger in small-caps than in SPY, so a long-IWM-overnight version is the academically-correct test, not SPY. None of these is worth doing *now* — the cost-vs-edge math is the dominant constraint on Alpaca retail and won't change without (a) a bigger trade size which requires real-money approval, or (b) a venue with tighter spreads which we don't have. Re-open the archetype if either changes.
