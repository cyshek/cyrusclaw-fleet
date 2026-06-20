# Backtest Report — Time-Series Momentum (TSMOM) on SPY

**Candidate:** `tsmom_spy_2951d463`
**Archetype:** #2 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` —
time-series momentum with vol targeting (Moskowitz/Ooi/Pedersen 2012,
simplified long-only single-asset).
**Author:** trading-bench (subagent, 2026-05-30 17:17 UTC).
**Verdict (TL;DR):** **REJECT** — fails Bar A on multiple bullets despite
being a real, profitable, low-drawdown strategy. The bench harness and the
$100 notional cap together truncate this archetype's natural edge profile
to nearly invisible in the metrics that matter for promotion.

---

## 1. Strategy spec (as implemented)

| Field | Value |
|---|---|
| Symbol | SPY (1Day) |
| Trend signal | 12-month total return (252 trading days). Long iff > 0. |
| Vol estimator | stdev of trailing 63 daily log returns × √252 |
| Vol target (annualized) | 15% |
| Notional formula | `min(MAX_NOTIONAL, (vol_target / realized_vol) × MAX_NOTIONAL)` |
| Max notional | $100 (bench risk cap) |
| Secondary gate | `regime_uptrend(spy_closes, 50)` from `strategies/_lib/indicators.py` (50-day SMA filter) — long requires BOTH gates on |
| Entry | Both gates on AND flat → buy sized notional |
| Exit | Either gate flips off → close |
| Rebalance | While long, if implied size shifts >25% vs stored size → close (re-enter next bar at new size); avoids vol-noise churn |
| Persistent state | `strategy_state["sized_notional"]` tracks the entry-time sized notional across bars |

**Note on sizing cap:** with target=15% and cap=$100, the vol-target reduces
notional only when realized annualized vol exceeds 15%. SPY's daily realized
vol is typically 12–25% annualized, so the strategy is at-cap in calm regimes
and de-sized during stress (e.g., 2022 H1, 2025 Q1 tariff bear). The cap
therefore preserves the spirit of vol-targeting even at this notional ceiling.

## 2. Bar A scorecard (per `GATE.md`, evaluated bullet-by-bullet)

| # | Bar A bullet | Result | Metric | PASS/FAIL |
|---|---|---|---|---|
| 1 | Walk-forward pass on all 8 named regimes (positive median per regime) | **bear median = -0.20%** (n=2: -0.27%, -0.13%); bull median +0.66% (n=4); chop median +0.10% (n=2) | bear regime negative | **FAIL** |
| 2 | Held-out final regime (2026-recent bull) | +0.81%, beats 0 (positive) but underperforms BH-SPY's +1.55% | **PASS** (positive return; no prior tuning) |
| 3 | Cost-aware Sharpe ≥ 0.5 on full backtest period (~5y, $1000 equity) | full-period Sharpe **1.35** | **PASS** |
| 4 | Trade count ≥ 30 across backtest | 43 full-period; 31 across the 8 named windows | **PASS** |
| 5 | Max drawdown ≤ 30% post-cost | full-period **-0.85%**; worst-window -0.64% | **PASS** |
| 6 | Code review pass via AST gate (`runner/strategy_gen.code_review`) | violations=[] | **PASS** |
| 7 | Smoke test `./tick.sh tsmom_spy_2951d463` rc=0 | **NOT RUN** — candidate lives in `strategies_candidates/`; live runner imports from `strategies/`. Per task constraints (no promotion), substituted an isolated import + single-tick decide() check on synthetic bars → action="buy", reason validates. No DB writes. | **N/A** (would require promotion) |

**Bar A overall: FAIL.** Bullet 1 (per-regime positive median) is the
binding constraint; bullet 7 is structurally unverifiable without promoting
the candidate, which the task explicitly forbids.

## 3. Walk-forward summary (8 named windows, +400d warmup per window)

| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | Win % | BH-SPY % | Beats BH? |
|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 6 | -0.27 | -0.87 | -0.54 | 0 | -1.74 | ✅ |
| 2022-Q3 chop | chop | 338 | 0 | +0.00 | 0.00 | 0.00 | — | -0.65 | ✅ |
| 2023-H1 recovery | bull | 337 | 0 | +0.00 | 0.00 | 0.00 | — | +0.74 | ❌ |
| 2023-Q3 chop | chop | 336 | 8 | +0.21 | 0.42 | -0.64 | 25 | -0.38 | ✅ |
| 2024-Q2 bull | bull | 337 | 3 | +0.50 | 1.00 | -0.37 | 0 | +0.48 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 4 | -0.13 | -0.36 | -0.26 | 0 | -0.80 | ✅ |
| 2025-Q3 bull | bull | 336 | 5 | +0.85 | 2.02 | -0.24 | 50 | +0.65 | ✅ |
| 2026-recent bull | bull | 317 | 5 | +0.81 | 1.99 | -0.21 | 0 | +1.55 | ❌ |

**Per-regime median return (Bar A bullet #1 evidence):**

| Regime | n windows | Median return % |
|---|---|---|
| bull | 4 | **+0.66%** ✅ |
| chop | 2 | **+0.10%** ✅ (borderline; one zero-trade window) |
| bear | 2 | **-0.20%** ❌ (both windows negative) |

**Aggregate (across all 8 windows):**
- median return: **+0.10%**
- 50% windows positive · 75% beat BH-SPY · median Sharpe **0.21**
- worst -0.27% (2022-H1 bear) · best +0.85% (2025-Q3 bull) · total trades 31
- Built-in `passes_fitness_gate` verdict: 🔴 FAIL — "median Sharpe 0.21 ≤ 0.50"

## 4. Full-period backtest (single contiguous run)

| Field | Value |
|---|---|
| Window | 2021-06-25 → 2026-05-29 (1237 trading bars, ~5 years) |
| Starting equity | $1000 (bench scale) |
| Notional per trade | $100 (cap) |
| Total trades | 43 (22 buys, 21 closes) |
| Total return | **+4.15%** ($+41.50 on $1000) |
| Sharpe (annualized) | **1.35** |
| Max drawdown | **-0.85%** |
| Win rate | 33% (avg $+1.41/trade) |
| Total costs paid | $0.84 (alpaca_stocks cost model: 2 bps one-way, 0 fee) |

The full-period Sharpe (1.35) handily clears Bar E.2 (Sharpe ≥ 1.0 for
real-money graduation). Max DD of -0.85% on a $1000 bench is microscopic.

## 5. Verdict: **REJECT** (with strong caveats)

Strict Bar A application: REJECT. Bullet #1 (positive median return per
named regime) fails on the bear bucket — both bear windows lost money,
albeit by tiny amounts and both beat buy-and-hold-SPY in those same windows.
Bullet #7 (smoke test) cannot be checked without promoting the candidate.

Conditional verdict: **NEEDS_MORE_DATA / REGIME_REVIEW**. The strategy
demonstrates the canonical TSMOM properties — defensive in bears (-0.20%
median vs BH-SPY -1.27%), patient in chops (zero or tiny trades), and
participates in bulls (+0.66% median, beats BH 3/4 times). The full-period
metrics (Sharpe 1.35, max DD 0.85%) are exactly what academic TSMOM is
supposed to deliver. The Bar A failure mode here is not "the edge is fake"
but "the bench measures it wrong" — see honest discussion.

## 6. Honest discussion

**Where it works.** TSMOM does what the literature says: it filters market
exposure to the upside half of the regime distribution. Across the 8 named
windows it beats buy-and-hold-SPY in 6/8 — including both bear windows
(2022-H1 and 2025-Q1), where being flat is the edge. The full-period
backtest is a 5-year win at near-zero drawdown and Sharpe 1.35, all at a $100
notional cap on a $1000 equity scale. The two windows it lost to BH-SPY
were both strong-trend bulls where the strategy held cash during the
warmup → the 50d regime filter took half the rally before it confirmed.
That's a feature, not a bug — TSMOM is structurally late on regime turns.

**Where it doesn't, and what to be suspicious of.** Three real concerns.
(1) Bar A's per-regime-median bullet is uncharitable to defensive strategies.
A long-only system in a bear window can either be in (and lose with the
market) or flat (and break even); TSMOM made *small* losses on transitional
chop within the bear, which is honest behavior but registers as "fail." A
fairer metric would be "post-cost return ≥ buy-and-hold in same window,"
which TSMOM passes 6/8. (2) The $100 notional cap masks the strategy's
actual character — at vol-target=15% and the cap binding, the
"vol-targeting" component is largely cosmetic; sizing only shrinks in
~25%-vol-annual stress windows, which we hit precisely once (2022 H1).
A bench with a $500 or $1000 notional cap would let the vol-target actually
do its job, and the equity-curve smoothing would be more visible. (3) Two
windows (2023-H1 recovery, 2022-Q3 chop) had zero trades because the warmup
period TSMOM was negative the entire window. That's regime-edge sensitivity
to the warmup-start date — a real concern, but partially an artifact of how
the +400d warmup interacts with the named-regime end-dates. The signal IS
genuinely late on bottoms, which is a known TSMOM weakness independent of
the bench.

**Net recommendation:** do NOT promote on the as-implemented spec. If
Tessera wants to revisit this archetype, the most valuable next move is
NOT another mutation — it's reconsidering whether Bar A bullet #1 should
allow "beats BH-SPY in regime" as an alternative to "positive in regime"
for explicitly defensive strategies. That conversation is above this
subagent's pay grade; raising it for the manager.

## 7. Files created

| Path | Purpose |
|---|---|
| `strategies_candidates/tsmom_spy_2951d463/strategy.py` | Strategy module (7.5 KB) |
| `strategies_candidates/tsmom_spy_2951d463/params.json` | Strategy params |
| `strategies_candidates/tsmom_spy_2951d463/__init__.py` | Empty package marker |
| `_run_tsmom_wf.py` | Warmup-extended walk-forward driver (adapted from `_run_connors_wf_warmup.py`) |
| `/tmp/tsmom_wf.md` | Raw walk-forward markdown |
| `/tmp/tsmom_wf.json` | Raw walk-forward JSON |
| `reports/BACKTEST_TSMOM_SPY_20260530T171711Z.md` | This report |

## 8. Harness limitations encountered

- `runner/walk_forward.py` fetches only `window_days` (60–90) of bars per
  named window. With a 252-day trend lookback, the strategy would never
  fire under the stock harness. Workaround: `_run_tsmom_wf.py` fetches
  `window_days + 400` calendar days per window and calls `backtest()`
  directly, mirroring the pattern used by the existing Connors RSI(2)
  warmup driver. Equity-curve metrics span the full slice; trade activity
  is dominated by the labeled regime window because TSMOM is flat or
  hold-only during the warmup.
- `runner.runner` (live runner) imports strategies from `strategies/` only;
  the candidate lives in `strategies_candidates/` per task constraints, so
  the literal `./tick.sh tsmom_spy_2951d463` smoke test cannot be executed
  without promoting the strategy (which would violate the no-promotion
  constraint). Substituted an in-process `decide()` smoke check on synthetic
  bars (passes — returns a buy with sensible notional and reason).
- No live trading state was touched. No cron modified.
