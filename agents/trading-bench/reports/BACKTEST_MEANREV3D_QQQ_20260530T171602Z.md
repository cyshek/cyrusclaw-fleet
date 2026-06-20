# Backtest — meanrev3d_qqq_cd3fbd (Short-Horizon Mean Reversion, Archetype #4)

**Date:** 2026-05-30 17:16 UTC
**Author:** trading-bench subagent
**Candidate dir:** `strategies_candidates/meanrev3d_qqq_cd3fbd/`
**Archetype source:** `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` §4 (Jegadeesh 1990; Lehmann 1990; Lo-MacKinlay 1990)
**Status:** Quarantined candidate. Not promoted. Not scheduled. No live trades.

---

## Strategy spec (as implemented)

- **Symbol / TF:** QQQ / 1Day (single-name, long-only)
- **Entry:** 3-day cumulative return on QQQ ≤ −3% **AND** SPY > SMA(50) (regime gate)
- **Exits (any one):**
  - 3-day cumulative return ≥ +1% (take profit), OR
  - Position held ≥ 5 trading days (max hold), OR
  - Unrealized PnL from entry ≤ −5% (stop loss)
- **Sizing:** Fixed $100 notional. Deliberately not vol-targeted (TSMOM peer's job)
- **State:** Persistent `strategy_state` dict for `entry_bar_index` + `entry_price` (harness-supported as of 2026-05-26)
- **Safety rail:** `safety_max_loss_pct: -50.0` (runaway-only, NOT a tuned exit)
- **Cost model:** `CostModel.alpaca_stocks()` (2 bps one-way, 0 fee)

## Files

- `strategies_candidates/meanrev3d_qqq_cd3fbd/strategy.py`
- `strategies_candidates/meanrev3d_qqq_cd3fbd/params.json`
- `strategies_candidates/meanrev3d_qqq_cd3fbd/__init__.py`
- `/tmp/mr_wf.md` (walk-forward markdown)
- `/tmp/mr_wf_details.json` (per-window JSON)
- `/tmp/mr_fullperiod.json` (full-period 2022-01 → 2026-05)
- `/tmp/run_meanrev3d.py`, `/tmp/run_mr_full.py` (driver scripts; can be re-run)

---

## Walk-forward results (8 named regimes, 2 bps stocks cost model)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 61 | 2 | −0.45 | −2.74 | −0.45 | −1.74 | ✅ |
| 2022-Q3 chop | chop | 63 | 4 | −0.19 | −1.70 | −0.38 | −0.65 | ✅ |
| 2023-H1 recovery | bull | 62 | 4 | +0.21 | +1.90 | −0.17 | +0.74 | ❌ |
| 2023-Q3 chop | chop | 63 | 0 | +0.00 | 0.00 | 0.00 | −0.38 | ✅ |
| 2024-Q2 bull | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.48 | ❌ |
| 2025-Q1 tariff bear | bear | 62 | 0 | +0.00 | 0.00 | 0.00 | −0.80 | ✅ |
| 2025-Q3 bull | bull | 62 | 0 | +0.00 | 0.00 | 0.00 | +0.65 | ❌ |
| 2026-recent bull | bull | 41 | 0 | +0.00 | 0.00 | 0.00 | +1.55 | ❌ |

**Aggregate:** median ret +0.00% · 12% windows positive · 50% beat BH-SPY · median Sharpe 0.00 · worst −0.45% (2022-H1 bear) · best +0.21% (2023-H1 recovery) · 10 total trades across all windows.

### Per-regime medians (Bar A bullet 1)

| Regime | n windows | Values | Median | PASS? |
|---|---|---|---|---|
| bear | 2 | −0.45 / 0.00 | −0.22% | ❌ |
| chop | 2 | −0.19 / 0.00 | −0.09% | ❌ |
| bull | 4 | +0.21 / 0.00 / 0.00 / 0.00 | +0.00% | ❌ |

**0 / 3 regimes have a positive median return.** Five of eight windows produced zero trades — the entry threshold rarely fires in benign tape.

---

## Full-period backtest (2022-01-06 → 2026-05-22, 1098 daily bars)

| Metric | Value |
|---|---|
| Trades | **28** (14 buys / 14 closes) |
| Total return | **−0.16%** |
| Sharpe | **−0.09** |
| Max drawdown | −1.06% |
| Win rate | 64.3% (9/14 closed) |
| Avg trade PnL | −$0.115 |
| Total costs | $0.560 (28 fills × ~2 bps) |
| Avg hold | 3.79 bars (min 2, max 5) |
| Win avg | +1.66% |
| Loss avg | −3.31% |
| Best trade | +2.29% |
| Worst trade | −4.47% (stop-loss territory) |

**Expectancy:** 0.643 × $1.66 − 0.357 × $3.31 = $1.07 − $1.18 = **−$0.11/trade**, matching observed.

---

## Bar A scorecard

| # | Bullet | Threshold | Observed | Verdict |
|---|---|---|---|---|
| 1 | Positive median return per regime (all 8 windows) | All 3 regime medians > 0 | bear −0.22%, chop −0.09%, bull 0.00% (0/3) | 🔴 **FAIL** |
| 2 | Held-out final regime (2026-recent bull) passes without tuning | Window must be net positive | 0 trades, 0.00% return | 🔴 **FAIL** (didn't fire — uninformative, but doesn't pass) |
| 3 | Cost-aware Sharpe ≥ 0.5 full period | Sharpe ≥ 0.5 | Sharpe = −0.09 (full period) | 🔴 **FAIL** |
| 4 | Trade count ≥ 30 across backtest window | ≥ 30 | 28 trades full-period; 10 across walk-forward windows | 🔴 **FAIL** (just barely; signal too inactive) |
| 5 | Max drawdown ≤ 30% post-cost | ≤ 30% | −1.06% full-period; worst window −0.45% | 🟢 **PASS** (trivially — under-exposed) |
| 6 | Code review pass (AST gate in `runner/strategy_gen.py`) | AST gate ok | Not run — candidate not generated via strategy_gen | ⚪ **N/A** for hand-written archetype implementation; would be invoked at promotion. Code reviewed manually: imports only `strategies._lib.indicators`, no I/O, no eval/exec, deterministic, follows existing `Action`/`decide` contract. |
| 7 | `./tick.sh` smoke test rc=0 | Live runner shim works | Not run — candidate not in `strategies/`; tick.sh hits live broker and would fail by design | ⚪ **N/A** at candidate stage |

**Final tally:** 1 PASS, 4 FAIL, 2 N/A → strategy fails Bar A.

**`passes_fitness_gate()` (looser bar):** 🔴 **FAIL** — median return +0.00% ≤ +0.00%; only 12% of windows positive (need ≥50%); median Sharpe 0.00 ≤ 0.50.

---

## Verdict: **REJECT**

Does not meet Bar A. Stays in `strategies_candidates/`. Do not schedule, do not promote, do not include in tournament leaderboard.

---

## Honest discussion

**Where it works.** The mechanism is real — full-period win rate is 64% (9W / 5L), the average winner is +1.66%, average hold is under 4 bars. The strategy is doing exactly what Jegadeesh/Lehmann/Lo-MacKinlay described: buying −3% pullbacks in an uptrend and capturing a 1–2% bounce most of the time. In the only walk-forward window where it fired meaningfully (2023-H1 recovery, 4 trades, +0.21% net, Sharpe 1.90), it beats BH-SPY on a risk-adjusted basis. The 2 trades in the 2022-H1 bear window cost only 0.45% of bench equity for the privilege of having SPY > SMA(50) flip false fast enough to gate out further entries — the regime filter is doing its job.

**Where it doesn't, and what to be suspicious of.** Three problems, in descending order of importance: (1) **The signal is too inactive.** Five of eight named windows produced zero trades. A −3% 3-day drop in QQQ inside an SPY uptrend is rare on the daily timeframe — full-period gives only 14 entries in 4.4 years (~3.2/year), and walk-forward windows are 60–90 days each so most of them simply don't see a qualifying event. The Bar A "trade count ≥ 30" bullet exists precisely to filter strategies that are too sparse to be statistically distinguishable from noise, and we land at 28 — just barely under, on the back of all 8 named windows. (2) **The expectancy is slightly negative even when it fires.** Loss size (−3.3% avg) is exactly 2× win size (+1.66% avg), which makes sense because the +1% take-profit caps winners aggressively while the −5% stop lets losers run further. Win rate of 64% isn't enough to overcome that asymmetry net of even 2 bps costs. This is the *classic* mean-reversion failure mode at this parameter point: the asymmetric exit ladder makes Kelly negative. (3) **Per-regime medians are 0/3 PASS.** Even ignoring the trade-count problem, bullet 1 of Bar A demands a positive median return *within each of bull/chop/bear*, and we have negative medians in bear and chop and a zero median in bull (because 3 of 4 bull windows didn't trade). This isn't another "long-only doesn't work in bear regimes" story — it's worse: it's "the signal almost never fires, and when it does, fee drag and exit asymmetry net it negative." Before any re-tuning is attempted, the threshold parameters need to be reconsidered jointly (probably loosen entry to −2% and widen take-profit to +2% to restore symmetry), but per spec I am NOT auto-tuning this candidate. A future iteration can grid-search those two parameters and re-evaluate.

---

## What I did NOT do (per task constraints)

- Did not write to `strategies/` — candidate stays in `strategies_candidates/`.
- Did not edit `runner.py`, `broker_alpaca.py`, or cron.
- Did not auto-promote.
- Did not tune parameters after seeing results.
- Did not run `tick.sh` (would attempt live paper submission inappropriate for failed candidate).
