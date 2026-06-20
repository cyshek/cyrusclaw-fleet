# Backtest — xsec_meanrev_xa_8e5a3f (Short-Horizon Cross-Sectional Mean-Reversion, CROSS-ASSET basket, Archetype #4)

**Date:** 2026-05-31 02:34 UTC
**Author:** trading-bench subagent (label: xsec-meanrev-xa)
**Candidate dir:** `strategies_candidates/xsec_meanrev_xa_8e5a3f/`
**Archetype source:** `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` §4 (Jegadeesh 1990; Lehmann 1990; Lo-MacKinlay 1990)
**Sibling (promoted):** `strategies/xsec_momentum_xa_38d2b2/` — same 6-ETF cross-asset universe, opposite signal (buy winners, 12-1 monthly). This is its counter-cyclical complement.
**Prior single-symbol reject:** `reports/BACKTEST_MEANREV3D_QQQ_20260530T171602Z.md`
**Status:** Quarantined candidate. Not promoted. Not scheduled. No live trades.

---

## Strategy spec (as implemented)

- **Universe:** [SPY, EFA, TLT, VNQ, DBC, GLD] / 1Day. Identical cross-asset basket to the promoted momentum winner — same universe-class-dispersion thesis (4 asset classes), opposite signal.
- **Signal:** trailing N-day total return per symbol, ranked **ascending** (biggest recent loser first). N = `lookback_bars` (base 5).
- **Allocation:** long-only **bottom-K** (biggest losers; K=2 of 6, ~N/3, mirroring the momentum sibling). $50/leg, $100 basket cap enforced by harness `_clamp_basket`.
- **Cadence:** rebalance every `rebalance_bars` trading days (base 5 ≈ weekly). **Hold-until-next-rebalance.** No take-profit, no stop-loss, no max-hold ladder — deliberately symmetric (the asymmetric +1%/−5% ladder is exactly what made the QQQ single-symbol version Kelly-negative).
- **Sizing:** fixed $50/leg notional. Not vol-targeted.
- **Regime overlay:** **NONE** (per task). This is the counter-cyclical leg; gating buys on SPY>SMA would defeat the buy-losers-in-any-tape thesis.
- **State:** persistent `bars_since_rebalance` counter + `initialized` flag.
- **Safety rail:** `safety_max_loss_pct: -50.0` (runaway-only, never fires at cross-asset vol).
- **Cost model:** `CostModel.alpaca_stocks()` — 2 bps one-way spread, 0 fee, applied per leg.

## Files created

- `strategies_candidates/xsec_meanrev_xa_8e5a3f/strategy.py`
- `strategies_candidates/xsec_meanrev_xa_8e5a3f/params.json`
- `strategies_candidates/xsec_meanrev_xa_8e5a3f/__init__.py`
- `reports/BACKTEST_XSEC_MEANREV_XA_20260531T023408Z.md` (this file)
- `/tmp/run_mrxa.py` (driver — walk-forward + full-period + sensitivity grid; re-runnable)
- `/tmp/mrxa_grid.json`, `/tmp/mrxa_wf_base.md`, `/tmp/mrxa_wf_base_wstats.json` (raw outputs)

---

## Walk-forward results — BASE config (lookback=5, rebalance=5), 8 named regimes, 2 bps stocks cost model

| Window | Regime | Ticks | Trades | Return % | Sharpe | MaxDD % | In-Pos % | Turnover (trades/tick) | Cost $ | BH-Basket % | Beats BH? | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 61 | 34 | −0.32 | −0.79 | −1.02 | 90 | 0.56 | 0.34 | −1.18 | ✅ | ✅(b) |
| 2022-Q3 chop | chop | 63 | 32 | −0.84 | −2.51 | −1.36 | 90 | 0.51 | 0.32 | −0.85 | ✅ | ❌ |
| 2023-H1 recovery | bull | 62 | 30 | +0.01 | +0.04 | −1.01 | 90 | 0.48 | 0.30 | +0.44 | ❌ | ✅ |
| 2023-Q3 chop | chop | 63 | 34 | −0.11 | −0.44 | −0.80 | 90 | 0.54 | 0.34 | −0.44 | ✅ | ❌ |
| 2024-Q2 bull | bull | 62 | 30 | −0.14 | −0.63 | −0.38 | 90 | 0.48 | 0.30 | +0.09 | ❌ | ❌ |
| 2025-Q1 tariff bear | bear | 62 | 30 | +0.03 | +0.07 | −1.41 | 90 | 0.48 | 0.30 | +0.15 | ❌ | ✅ |
| 2025-Q3 bull | bull | 62 | 32 | +0.70 | +4.42 | −0.17 | 90 | 0.52 | 0.32 | +0.53 | ✅ | ✅ |
| 2026-recent bull (HELD-OUT) | bull | 41 | 18 | +0.57 | +3.60 | −0.27 | 85 | 0.44 | 0.18 | +0.74 | ❌ | ✅ |

**Aggregate:** median ret −0.05% · 50% windows positive · 50% beat BH-basket · median Sharpe −0.20 · worst −0.84% (2022-Q3 chop) · best +0.70% (2025-Q3 bull) · **240 trades** · **total cost $2.40**.

### Per-regime medians (Bar A bullet #1 (a))

| Regime | n windows | Values | Median | Positive? |
|---|---|---|---|---|
| bull | 4 | +0.01 / −0.14 / +0.70 / +0.57 | **+0.29%** | ✅ |
| chop | 2 | −0.84 / −0.11 | **−0.47%** | ❌ |
| bear | 2 | −0.32 / +0.03 | **−0.15%** | ❌ |

**1 / 3 regimes positive median.** The contrarian buys losers; in **chop and bear** those losers keep falling (no bounce) → negative. Only in bull tape does buy-the-dip pay. This is the opposite regime-profile from the promoted momentum leg — which is the diversification point — but it is not a *passing* profile on its own.

---

## Full-period backtest — BASE config (2021-12 → 2026-05-22, 1132 daily ticks)

| Metric | Value |
|---|---|
| Trades | **582** (291 buys / 291 closes) |
| Total return | **+0.89%** (+$8.89 on $1000 bench equity) |
| Sharpe | **+0.16** |
| Max drawdown | −3.24% |
| Total costs | **$5.82** (582 fills × ~2 bps on $50 legs) |
| In-position | ~90% of ticks (fully deployed) |
| **BH-basket (equal-weight, same period)** | **+3.58%** |
| **Strategy − BH gap** | **−2.69 pp** (strategy destroys value vs just holding) |

**Cost-drag accounting (base config):** gross return before costs ≈ +0.89% + ($5.82/$1000) = **+1.47%**; costs of **$5.82 erase 40% of gross**. At a higher 3-day cadence (below) costs roughly double to $10.06 and erase a comparable slice. This is the structurally expensive archetype the triage flagged (§"cost sensitivity ranking: high-turnover #4").

---

## Sensitivity grid (lookback × rebalance cadence)

| Config | WF median ret | WF med Sharpe | WF %pos | WF bull/chop/bear med | WF trades | WF cost $ | FP return | FP Sharpe | FP MaxDD | FP cost $ | FP vs BH(+3.58%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **lb=5 rb=5 (base)** | −0.05% | −0.20 | 50% | +0.29 / −0.47 / −0.15 | 240 | 2.40 | +0.89% | 0.16 | −3.24% | 5.82 | −2.69 pp |
| lb=3 rb=3 | +0.03% | +0.14 | 50% | +0.20 / −0.32 / −0.51 | 390 | 3.90 | +2.84% | 0.50 | −1.99% | 10.06 | −0.75 pp |
| lb=3 rb=5 | −0.24% | −0.77 | 38% | +0.54 / −0.43 / −0.72 | 240 | 2.40 | +3.19% | 0.55 | −2.80% | 5.82 | −0.39 pp |
| lb=5 rb=3 | +0.08% | +0.34 | 62% | +0.32 / −0.54 / −0.57 | 302 | 3.02 | +1.94% | 0.35 | −3.17% | 7.62 | −1.65 pp |

**Read:** Shorter lookback (3d) + the BH benchmark gap narrows on full-period (lb=3/rb=5 gets within −0.39 pp of BH) but **never beats it**, and the best full-period Sharpe across the whole grid is **0.55** (lb=3/rb=5) — still below the 0.5→1.0 bar region and far below the promoted momentum sibling's 1.13. Faster cadence (rb=3) lifts walk-forward %positive to 62% but at ~1.5–2× the cost and no full-period edge over BH. **No grid point clears Bar A bullet #1 or the fitness gate; none reaches the #5 fast-track FP-Sharpe≥1.0 floor.** Reporting the base (lb=5/rb=5) as the headline because it is the lowest-turnover / lowest-cost-drag point and the sensitivity shows the archetype is not rescued by re-tuning cadence.

---

## Bar A scorecard (base config)

| # | Bullet | Threshold | Observed | Verdict |
|---|---|---|---|---|
| 1 | Per-window pass (a) positive OR (b) ≥BH & ≥25% in-pos, (b) cap=1 | All 8 windows pass | 5/8 pass; needs (b) on 2 chop windows (cap=1) + 2024-Q2 bull fails outright (−0.14% < BH +0.09%) | 🔴 **FAIL** |
| 2 | Held-out final regime (2026-recent bull) passes w/o tuning | net positive | +0.57% (positive ✅ on bullet-#1 (a)) but underperforms BH +0.74% | 🟡 passes-#1-(a), **but does not beat BH** — uninspiring hold-out |
| 3 | Cost-aware Sharpe ≥ 0.5 full period | ≥ 0.5 | **0.16** (base); best grid point 0.55 | 🔴 **FAIL** (base); marginal at one tuned point |
| 4 | Trade count ≥ 30 | ≥ 30 | 582 full-period / 240 walk-forward | 🟢 **PASS** (signal fires every rebalance by construction — the QQQ sparsity problem is solved) |
| 5 | Max drawdown ≤ 30% post-cost | ≤ 30% | −3.24% full-period; worst window −1.41% | 🟢 **PASS** |
| 6 | Code review (AST gate) | ok | Manual review: imports only stdlib + dataclass; no I/O, no eval/exec; deterministic; follows `Action`/`decide_xsec` contract; reads `strategy_state` per cross-flat protocol | 🟢 **PASS** (manual) |
| 7 | `./tick.sh --candidate` rc=0 | rc=0, no DB errors | `SMOKE OK xsec (2183ms) actions={DBC=buy, VNQ=buy}` rc=0 | 🟢 **PASS** |

**Fast-track #5 check:** (a) FP Sharpe ≥1.0 → **FAIL** (0.16 base, 0.55 best). #5 unavailable. Not applicable.

**Final tally (base):** 4 PASS, 2 FAIL, 1 borderline-holdout → **fails Bar A** (bullets #1 and #3 both fail; #5 fast-track not reachable).

---

## Verdict: **REJECT**

Does not meet Bar A. Fails bullet #1 (chop/bear regime medians negative, needs the (b) BH-crutch on 2 windows against a cap of 1), fails bullet #3 (full-period Sharpe 0.16 ≪ 0.5), and cannot use the #5 fast-track (FP Sharpe never reaches 1.0). Stays in `strategies_candidates/`. Do not schedule, do not promote, do not add to tournament leaderboard.

**However** — see discussion: unlike the QQQ reject, this is a *clean* reject of a *fully-deployed, frequently-firing* strategy, and it carries genuine diversification information for the promoted momentum leg.

---

## Honest discussion

**What this fixed vs the QQQ reject, and what it tells us.** The single-symbol meanrev3d_qqq REJECT failed for mechanical reasons — the signal almost never fired (5/8 windows had zero trades) and an asymmetric +1%/−5% exit ladder made expectancy negative even at 64% win rate. This basket version surgically removes both failure modes: it is cross-sectional, so it **always** deploys into the bottom-K losers every rebalance (240 walk-forward / 582 full-period trades, ~90% in-position, trade-count bullet #4 passes comfortably), and it has **no exit ladder at all** — it holds until the next re-rank, so there is no win/loss asymmetry baked into the exits. With those two confounds gone, what remains is a clean measurement of the *signal itself*. And the signal's verdict is unambiguous: short-horizon cross-asset reversal does NOT carry edge net of cost over this 4.5-year span. Full-period the strategy returns +0.89% while equal-weight buy-and-hold of the same 6 ETFs returns +3.58% — it **underperforms the do-nothing benchmark by 2.7 percentage points**, and no point in the lookback×cadence grid closes that gap to positive. The per-regime split is the tell: positive median only in bull (+0.29%), negative in chop (−0.47%) and bear (−0.15%). Buying the biggest 3–5 day loser in a cross-asset basket mostly means buying whichever asset class is in a genuine downtrend (TLT in a rate-rise, DBC in a commodity slump), and on the daily horizon those losers continue rather than revert — the reversal premium Jegadeesh/Lehmann documented for single US stocks in the 1980s does not survive transplant to a 6-asset-class daily basket under a 2 bps cost regime. This is itself a useful datum: the universe-class dispersion that *made the momentum sibling work* (Sharpe 1.13) actively *hurts* the contrarian, because cross-asset moves are more trend-persistent than mean-reverting at this horizon.

**Cost drag, and why I still think this earns its place in the candidate library.** Cost is a first-order term here, not a rounding error. Base config burns $5.82 of costs to net +$8.89 — costs erase 40% of gross return (gross ≈ +1.47%). The 3-day cadence variant doubles costs to ~$10 for a comparable gross, confirming the triage's "high-turnover #4 worst-for-2bps" ranking: every halving of the rebalance interval roughly doubles the cost line without a compensating edge bump, so faster trading strictly loses here. At a real-money 2-bps venue this would be even less forgiving. That said, the *diversification* logic in the task brief is real and partly borne out: the strategy's regime profile is the photographic negative of the promoted momentum leg — it makes its best windows (2025-Q3 +0.70% Sharpe 4.42, 2026-recent +0.57% Sharpe 3.60) in late-cycle bull tape, and its worst in chop, which is roughly when a 12-1 momentum book is most exposed to whipsaw. A modest-Sharpe-but-negatively-correlated sleeve can still raise a *portfolio's* Sharpe even when it fails a *standalone* gate. But "diversification value" is not a Bar A criterion, and admitting a strategy that underperforms its own buy-and-hold benchmark on the strength of a correlation argument would be exactly the kind of post-hoc rescue GATE.md's cap=1 (b)-crutch and the audit-trail discipline exist to prevent. So: clean REJECT on the merits, logged honestly, with the diversification observation flagged for a future *combinator* study (pair the momentum leg + this contrarian leg in one book and measure the blended Sharpe) rather than used to wave this candidate through.

---

## What I did NOT do (per task constraints)

- Did not write to `strategies/` — candidate stays in `strategies_candidates/`.
- Did not touch `runner/runner.py`, `runner/runner_xsec.py`, `runner/broker_alpaca.py`, `runner/risk.py`, `runner/safety_backstop.py`, `runner/backtest_xsec.py`, or `GATE.md`.
- Did not add an SPY regime overlay (explicitly excluded by task).
- Did not auto-promote, did not schedule, did not create cron, did not pip install.
- Did not tune parameters to chase a pass after seeing results — the sensitivity grid was pre-specified (lookback {3,5} × cadence {3,5}) and all four points are reported regardless of outcome.
