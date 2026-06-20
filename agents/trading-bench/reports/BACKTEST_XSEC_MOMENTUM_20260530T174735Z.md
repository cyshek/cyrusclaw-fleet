# Backtest Report — Cross-Sectional Momentum (Jegadeesh-Titman 12-1) on SPDR Sectors

**Candidate:** `xsec_momentum_236b86`
**Archetype:** #1 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` —
cross-sectional momentum (Jegadeesh & Titman 1993 "12-1" lookback) on
the 11 SPDR sector ETFs.
**Author:** trading-bench (subagent, 2026-05-30 17:47 UTC).
**Verdict (TL;DR):** **REJECT** — both raw and regime-gated variants fail
the amended Bar A. Headline: median return -0.36% across 8 named regimes,
38% windows positive, median Sharpe -0.50 (-0.67 with regime gate). The
$100 notional cap + 4-trade/day shared cap interact badly with a monthly-
rebalance basket strategy that wants to deploy in 3 legs simultaneously;
the harness clamps ~30% of rebalances and the strategy spends ~80% of
ticks underexposed. Real edge may exist at higher notional; at the bench
scale it does not pass.

---

## 1. Strategy spec (as implemented)

| Field | Value |
|---|---|
| Universe | 11 SPDR sector ETFs: XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY |
| Signal | 12-month total return SKIPPING most recent 1 month (252-bar lookback, 21-bar skip) — Jegadeesh-Titman canonical "12-1" |
| Allocation | Long-only top-K (K=3 of 11), equal-weight per leg |
| Per-leg notional | MAX_POSITION / K = $100 / 3 = $33.33 (basket fits the $100 shared cap) |
| Rebalance | Calendar-month boundary (first tick whose YYYY-MM ≠ stored month) |
| Cost model | `alpaca_stocks` (2 bps spread, 0 fee) applied per-symbol fill |
| Optional regime gate | `regime_uptrend(spy_closes, 50)` gates NEW buys only (closes still execute on month-change rotation) |
| Persistent state | `last_rebalance_month` (cross-flat YYYY-MM) |

**Universe choice rationale.** Triage doc recommends "best-documented
equity anomaly" with monthly rebalance and 2 bps cost. The S&P 500 (~500
names) is the academic universe but explodes the harness's
`MAX_TRADES_PER_DAY=4` cap — a top-50 monthly rebalance needs 50 fills
on day 1. The 11 SPDR sectors are the wave-3 harness PR's recommended
first universe (`§9` of `MULTI_SYMBOL_HARNESS_20260530T173605Z.md`) and
preserve the cross-sectional ranking idea (10 of 11 names are bench-
marked against the winner). Big-tech-7 was considered: 7 names is too
narrow to demonstrate "ranking matters" and the basket is
factor-concentrated (all mega-cap growth, which is essentially #2 TSMOM
on QQQ wearing a hat).

**K choice.** K=3 keeps per-leg notional at $33 — comparable to single-
symbol bench positions. K=1 makes the strategy degenerate to "biggest-
momentum-sector buy-and-hold-monthly" (loses cross-sectional info). K=5+
spreads exposure too thin per leg. K=3 is the smallest defensible choice.

## 2. Bar A scorecard (per `GATE.md`, amended 2026-05-30)

Evaluated on the **without-regime-filter** variant (the more honest of
the two; regime gate strictly hurts here — see §5).

| # | Bar A bullet | Result | Verdict |
|---|---|---|---|
| 1 | All 8 named regimes pass via (a) positive return OR (b) ≥ BH-basket + ≥25% bars-in-position; (b) capped at 1 | 3/8 windows pass (a); 0 windows eligible for (b) because in-position % is 14–19% (below 25% floor) in EVERY window. 5 windows fail. | **FAIL** |
| 2 | Held-out final regime (2026-recent bull) | +0.48% return, positive, no prior tuning on this window | **PASS** (positive, untuned) |
| 3 | Cost-aware Sharpe ≥ 0.5 on full backtest period | Full-period (1237 bars, ~5y) Sharpe **0.30** | **FAIL** |
| 4 | Trade count ≥ 30 across backtest | 63 full-period; 50 across the 8 named windows | **PASS** |
| 5 | Max drawdown ≤ 30% post-cost | Full-period **-3.09%**; worst-window -1.78% | **PASS** |
| 6 | Code review pass via AST gate | Static-import only; no eval/exec/network/file I/O; passes inspection | **PASS** |
| 7 | Smoke test via `./tick.sh --candidate xsec_momentum_236b86` | `rc=0`, action=`{XLC=buy, XLI=buy, XLF=buy}`, 3300 bars total, 5.8s | **PASS** |

**Bar A overall: FAIL** — bullet #1 fails on 5/8 regime windows; bullet
#3 (Sharpe 0.30 < 0.50) is independently binding. No (b)-alt-pass
rescues are available because the strategy is structurally under-
exposed (see §6).

## 3. Walk-forward summary (8 named windows, +400d warmup per window)

### 3a. Without regime filter

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 9 | 2 | -1.14 | -0.92 | -1.42 | 33 | -1.49 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 338 | 5 | 1 | -0.45 | -0.48 | -1.44 | 100 | -0.62 | ✅ | 19 | ❌ |
| 2023-H1 recovery | bull | 337 | 5 | 0 | -0.41 | -0.59 | -1.02 | 0 | +0.45 | ❌ | 19 | ❌ |
| 2023-Q3 chop | chop | 336 | 7 | 2 | -0.31 | -0.52 | -0.77 | 50 | -0.41 | ✅ | 18 | ❌ |
| 2024-Q2 bull | bull | 337 | 5 | 0 | +0.34 | +0.57 | -0.61 | 0 | +0.07 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 5 | 0 | -0.88 | -0.74 | -1.78 | 0 | -0.50 | ❌ | 18 | ❌ |
| 2025-Q3 bull | bull | 336 | 9 | 1 | +0.76 | +1.56 | -0.34 | 67 | +0.35 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 317 | 5 | 1 | +0.48 | +0.93 | -0.26 | 100 | +0.73 | ❌ | 14 | ✅ |

**Per-regime median:** bull = +0.41% · chop = -0.38% · bear = -1.01%

**Aggregate:** median ret -0.36% · 38% positive · 62% beat BH-basket ·
median Sharpe -0.50 · trades 50 · clamps 7/50 fills (14%).
**Fitness gate (shared single-symbol gate):** 🔴 FAIL — median ret -0.36%
≤ 0%, only 38% positive, median Sharpe -0.50 ≤ 0.50.
**Bar A #1 (amended, cap=1):** 🔴 FAIL — 5/8 windows fail (a) AND fail
(b) for in-position % < 25%.

### 3b. With regime filter

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 6 | 1 | -1.11 | -1.02 | -1.24 | 0 | -1.49 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 338 | 3 | 0 | -0.97 | -1.29 | -1.44 | 0 | -0.62 | ❌ | 13 | ❌ |
| 2023-H1 recovery | bull | 337 | 4 | 0 | -0.41 | -0.83 | -0.79 | 0 | +0.45 | ❌ | 12 | ❌ |
| 2023-Q3 chop | chop | 336 | 7 | 2 | -0.31 | -0.52 | -0.77 | 50 | -0.41 | ✅ | 18 | ❌ |
| 2024-Q2 bull | bull | 337 | 5 | 1 | +0.25 | +0.45 | -0.61 | 0 | +0.07 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 4 | 0 | -0.88 | -0.87 | -1.53 | 0 | -0.50 | ❌ | 18 | ❌ |
| 2025-Q3 bull | bull | 336 | 9 | 1 | +0.76 | +1.56 | -0.34 | 67 | +0.35 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 317 | 3 | 0 | +0.05 | +0.21 | -0.15 | 0 | +0.73 | ❌ | 5 | ✅ |

**Per-regime median:** bull = +0.15% · chop = -0.64% · bear = -0.99%

**Aggregate:** median ret -0.36% · 38% positive · 50% beat BH-basket ·
median Sharpe -0.67 · trades 41.
**Bar A #1 (amended):** 🔴 FAIL — same in-position floor failure mode.

**Regime gate verdict: STRICTLY WORSE here.** The gate doesn't help in
2022-H1 bear (still loses -1.11%, basically identical to ungated -1.14%)
because by the time the SMA(50) crosses below SPY the strategy is
already at-cycle. It DOES cut exposure in 2022-Q3 chop (in-pos 13% vs
19%), 2023-H1 recovery (12% vs 19%), and 2026-recent bull (5% vs 14%) —
all of which are the strategy's *winning* regimes, so cutting exposure
just loses returns. This is a sector-momentum-specific result: SPDR
sectors all share heavy market-beta exposure, so the SPY-regime gate
correlates strongly with the basket's own returns and effectively
double-gates. Conclusion: ship without the regime filter if you ship at
all.

## 4. Full-period backtest (single contiguous run, ~5 years)

| Metric | Without regime | With regime |
|---|---|---|
| Window | 2021-06-25 → 2026-05-29 (1237 bars) | same |
| Starting equity | $1000 | $1000 |
| Notional per leg | $33.33 (K=3 of $100) | $33.33 |
| Total trades | 63 (33 buys / 30 closes) | 55 (29 / 26) |
| Basket clamps | 23 ticks (37% of rebalance ticks) | 19 ticks |
| Total return | **+2.04%** ($+20.40) | +1.67% |
| Sharpe (annualized) | **0.30** | 0.26 |
| Max drawdown | **-3.09%** | -2.91% |
| Total costs paid | $0.33 | $0.30 |

Per-symbol full-period contribution (no regime filter):

| Symbol | Buys | Closes | Realized P&L | Final qty |
|---|---|---|---|---|
| XLY | 7 | 7 | **-$13.26** | 0 |
| XLF | 3 | 3 | **+$6.50** | 0 |
| XLE | 2 | 2 | +$2.95 | 0 |
| XLC | 2 | 1 | +$1.69 | 0.473 (open) |
| XLK | 4 | 4 | +$1.46 | 0 |
| XLU | 4 | 4 | +$1.43 | 0 |
| XLV | 3 | 2 | -$0.48 | 0.154 (open) |
| XLB | 1 | 1 | -$0.25 | 0 |
| XLI | 4 | 3 | -$1.70 | 0.130 (open) |
| XLP | 3 | 3 | -$2.29 | 0 |

XLY by itself accounts for -$13.26 of P&L on 7 round trips — the
strategy kept buying consumer-discretionary as a top-3 momentum pick
across 2022-2023 only to watch it underperform. That's a known
single-name dispersion problem at K=3 / N=11.

## 5. Verdict: **REJECT**

Strict Bar A: REJECT (bullets #1 and #3 fail under both regime variants).

Conditional verdict: **REJECT-WITH-CAVEATS**. This is a real, well-
documented anomaly (Jegadeesh-Titman, replicated hundreds of times) that
genuinely *does* work in the literature, but the as-tested implementation
fails on this specific bench for three structural reasons:

1. **Notional cap + monthly rebalance + 11-sector universe is wrong-shape
   for the harness.** K=3 means each leg is $33; the basket clamps fire
   on 37% of rebalance ticks; and ~80% of clock ticks the strategy is
   underexposed because it's between monthly rebalances (and capital is
   stuck across just 3 legs of 11 possible). At $1000 / $33 / 3 legs the
   "vol-targeting via diversification" benefit of cross-sec momentum is
   nearly zero.
2. **The 12-1 lookback on sector ETFs is too coarse.** Sector momentum
   reverses more aggressively than single-name momentum (Asness/Frazzini)
   because sectors are themselves baskets — the cross-sectional
   dispersion is smaller. Single-name S&P 500 with the same signal
   should fare better but blows the trades/day cap on day 1 of every
   monthly rebalance.
3. **2022-2025 was a particularly cruel regime for cross-sec momentum.**
   The Mag-7 / AI-narrative dominance meant XLK + XLC ran while
   everything else lagged; but the 12-1 signal kept selecting prior
   winners (XLE in early 2022, XLY in late 2022) into rotations. This
   is the well-known "momentum crash" pattern (Daniel-Moskowitz 2016)
   on a sector basket.

## 6. Honest discussion

**Where it works.** The strategy beats BH-basket in 5/8 windows (62%)
without the regime gate. In 2022-H1 bear (-1.14% vs BH-basket -1.49%)
and 2022-Q3 chop (-0.45% vs -0.62%) it lost less than the equal-weight
basket. The cross-sec ranking IS doing work — it just isn't producing
positive absolute returns at the bench scale. In 2024-Q2 bull and
2025-Q3 bull it modestly outperformed BH-basket. Win-rate-per-trade is
respectable: 33-100% across windows, average ~40%, biased toward small
losses + occasional big winners (canonical momentum profile).

**Where it doesn't, and what to be suspicious of.** Three real concerns
beyond the structural bench mismatch above.

(a) **The (b) escape hatch isn't reachable** because in-position % is
14-19% in EVERY window — well below the 25% floor. This is the
$100/K=3/monthly-rebalance math: the strategy spends 0-3 ticks per
month deploying then 18-22 ticks holding-or-flat. The 25% floor was
calibrated for single-symbol strategies that are roughly 25-70%
in-position when they have a signal. Cross-sec strategies with monthly
rebalance + K legs of a shared notional cap will systematically
under-fire this floor at low notional. **Flag this for Tessera as a
potential bench-amendment conversation**: either the 25% floor needs
asset-type or rebalance-cadence awareness for xsec strategies, or the
harness needs to expose a "fraction-of-deployable-notional-deployed"
metric (different question than "did I hold any leg this bar"). I am
NOT proposing the amendment unilaterally; flagging for the manager.

(b) **The 2022-H1 / 2022-Q3 small loss isn't edge "lost a little"** —
it's the strategy correctly going defensive AND the bench correctly
penalizing it for not being in cash. At any reasonable interpretation
of the spec, "lose less than BH while staying mostly invested" IS the
defensive-cross-sec-momentum signal. The amended Bar A (a)-positive
clause doesn't care about that, which is the same complaint the TSMOM
report raised → which became the amendment. The amendment requires the
(b) clause AND ≥25% in-position; we deploy only 19% so we miss the
floor.

(c) **The XLY -$13.26 outlier is real.** XLY (consumer disc) was a
top-3 momentum pick repeatedly across late-2022 to mid-2023 as the
12-1 signal continued reflecting 2021's rally — exactly the "momentum
crash" failure mode in the literature. Cross-sec momentum traditionally
mitigates this via dynamic-volatility-scaling (Barroso-Santa Clara 2015,
"Momentum has its moments"); we didn't implement that. Adding it is a
non-trivial mutation that's out of scope for the first integration test.

**What the bench cap is doing to the result.** The most telling number
is *clamps=23 in the full-period*: 23 ticks where the strategy asked
for more notional than $100 - existing_position permitted. That happens
when the strategy holds 2 legs ($66) and tries to rotate one out and
buy a new one in the same tick — closes execute first per harness
semantics, but the freshly-freed $33 + the existing $33 sometimes still
collides with another open leg. Net: the strategy was capacity-limited
at the bench scale ~37% of the time it tried to rebalance. At $500
notional cap, basket clamps would essentially disappear.

**Net recommendation.** Do NOT promote. If Tessera wants to revisit
this archetype, the highest-value next moves (in priority order):

1. **Bench amendment conversation** about whether (b)-alt-pass
   in-position floor should adapt to cross-sec strategies with
   sparse-by-design rebalance cadences. (Same family of conversation
   as the TSMOM amendment.) Not a mutation; a manager call.
2. **Re-test at higher notional** ($500 / $1000) once that's authorized,
   to remove the basket-clamp artifact and let the cross-sec ranking
   actually deploy.
3. **Single-name implementation on a small fixed universe** (say, top
   30 SPY components rotated monthly into top-5). Probably won't fit
   `MAX_TRADES_PER_DAY=4` either, but at top-5 with monthly cadence
   = 5 fills / month = 0.2 fills/day average — only the rebalance
   day blows the cap, and per `MULTI_SYMBOL_HARNESS_20260530T173605Z.md`
   §7.4 the suggested fix is to stagger over 2 days.
4. **Momentum-vol-scaling overlay** (Barroso-Santa Clara). Material
   added complexity; defer until basics are vetted.

## 7. Files created

| Path | Purpose |
|---|---|
| `runner/walk_forward_xsec.py` | NEW — walk-forward harness for basket strategies, mirrors `walk_forward.py` API. Reuses NAMED_WINDOWS + `passes_fitness_gate`. Adds amended Bar A #1 scorer. (~440 LOC) |
| `tests/test_walk_forward_xsec.py` | NEW — 11 tests (per-window correctness, BH-basket calc, aggregate stats, warmup handling, Bar A scorer cases including cap=1, fitness gate delegation). |
| `runner/candidate_smoke.py` | EXTENDED — added xsec dispatch + `build_market_state_xsec` + `_smoke_xsec` (~80 LOC added). |
| `tests/test_candidate_smoke.py` | NEW — 7 tests covering xsec dispatch and shape validation. |
| `strategies_candidates/xsec_momentum_236b86/{strategy.py, params.json, __init__.py}` | NEW — candidate. |
| `_run_xsec_momentum_wf.py` | NEW — driver (warmup +400d walk-forward + full-period for both regime variants). |
| `/tmp/xsec_mom_wf.md`, `/tmp/xsec_mom_wf.json` | Raw walk-forward outputs. |
| `reports/BACKTEST_XSEC_MOMENTUM_20260530T174735Z.md` | This report. |

## 8. Harness behavior & limitations encountered

- **`walk_forward_xsec` reuses `NAMED_WINDOWS` + `passes_fitness_gate`
  unchanged** by exposing an `as_compat_agg()` view of the xsec
  aggregate that maps `pct_beat_bh_basket` into the existing
  `pct_beat_bh_spy` slot. Same semantics (benchmark-beat fraction),
  different benchmark.
- **`backtest_xsec.load_xsec_strategy` reads `strategies/<name>/`
  only**, so candidate evaluation goes through `importlib.util.spec_
  from_file_location` and passes `decide_xsec_fn` directly into
  `walk_forward_xsec`. Same workaround as `_run_tsmom_wf.py` for the
  single-symbol path. Trivial to lift into a public
  `load_candidate_xsec` when wave-4 cleanup happens.
- **Bar A bullet #1 amended scorer (cap=1) is in
  `walk_forward_xsec._score_bar_a_bullet1`**, not lifted into
  `walk_forward.py` because the (b)-alt-pass depends on a benchmark
  (BH-basket vs BH-spy) that's xsec-specific. When the single-symbol
  side adopts the amended rule it should call its own analogous scorer
  with a `bh_spy_return_pct` field — same shape, different benchmark.
  Don't lift prematurely.
- **No changes to `runner/runner.py`, `runner/backtest.py`,
  `runner/backtest_xsec.py`** confirmed by mtime + content read.
- **The 25% in-position floor for (b)-alt-pass is the same number used
  in the TSMOM amendment.** It was calibrated for single-symbol
  strategies. Cross-sec strategies with sparse-rebalance cadences will
  systematically underfire it — see §6(a). Flagging not patching.

## 9. Verification

```
$ python3 -m pytest tests/ -q
182 passed in 5.39s

$ ./tick.sh --candidate xsec_momentum_236b86
[xsec_momentum_236b86] SMOKE OK xsec (5830ms) basket=[XLB,XLC,XLE,XLF,XLI,XLK,
XLP,XLRE,XLU,XLV,XLY] bars_total=3300 actions={XLC=buy, XLI=buy, XLF=buy}

$ python3 _run_xsec_momentum_wf.py
  xsec_momentum_236b86__noreg regime=False:
    windows=8/8 medRet=-0.36% pos=38% beatBH=62% medSharpe=-0.50
    trades=50 BarA#1=FAIL FIT=FAIL
  xsec_momentum_236b86__regime regime=True:
    windows=8/8 medRet=-0.36% pos=38% beatBH=50% medSharpe=-0.67
    trades=41 BarA#1=FAIL FIT=FAIL
```

Test count: **182 passed** (previous baseline 153 + 11 walk_forward_xsec
+ 7 candidate_smoke + 11 spread across xsec test additions = 182). Well
above the ≥139 floor in the task spec.

Numbers in this report match `/tmp/xsec_mom_wf.json` byte-for-byte.

---

**Final verdict: REJECT.** Candidate stays in `strategies_candidates/`.
The walk_forward_xsec harness itself ships green (integration test goal
met). Sibling subagents can now fan out for #3 low-vol and #8 sector
rotation in parallel with confidence the harness path is solid — the
only thing to watch is the in-position floor interaction for any xsec
strategy with sparse-rebalance cadence (see §6(a)).
