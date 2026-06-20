# Backtest Report — Cross-Sectional Low-Volatility Anomaly (Ang-Hodrick-Xing-Zhang 2006) on SPDR Sectors

**Candidate:** `xsec_lowvol_c3783c`
**Archetype:** #3 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md` —
low-vol anomaly (Ang, Hodrick, Xing & Zhang 2006) on the 11 SPDR sector
ETFs.
**Author:** trading-bench (subagent, 2026-05-30 17:54 UTC).
**Wave 3 sibling task.** Sibling subagent simultaneously running #8
sector rotation; no shared file edits, distinct hash dir.
**Verdict (TL;DR):** **REJECT-WITH-CAVEATS** — both raw and regime-gated
variants fail amended Bar A, but for substantively different reasons than
#1 momentum. Headline (K=3, N=60, no regime): median return **+0.09%**
across 8 named regimes, **50%** windows positive, median Sharpe **0.11**,
full-period Sharpe **0.36**. Strictly better than #1 momentum's
-0.36% / 38% / -0.50 / 0.30, but still short of the Sharpe ≥ 0.5
threshold and BarA#1 still fails (the strategy underperforms BH-basket
in both chop windows by a meaningful margin). **Crucially: the
in-position floor is NOT the binding constraint** — low-vol sits at
**67% in-position** versus momentum's 14-19%, because defensive sectors
are persistent winners in the bottom-K so positions don't churn. Floor
sensitivity (20/15/10) does not change the verdict.

---

## 1. Strategy spec (as implemented)

| Field | Value |
|---|---|
| Universe | 11 SPDR sector ETFs: XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY |
| Signal | Trailing N-bar realized volatility per symbol: annualized stdev (sqrt(252)) of daily log returns. Primary N=60 (~3-month, AHXZ original). Sensitivity: N=21. |
| Allocation | Long-only **bottom-K** (lowest vol), equal-weight per leg. Primary K=3 of 11 (matches #1 momentum's top-3 for direct comparability). Sensitivities: K=2, K=5. |
| Per-leg notional | MAX_POSITION / K = $100 / 3 = $33.33 (basket fits the shared $100 cap) |
| Rebalance | Calendar-month boundary (first tick whose YYYY-MM ≠ stored month) |
| Cost model | `alpaca_stocks` (2 bps spread, 0 fee) applied per-symbol fill |
| Optional regime gate | `regime_uptrend(spy_closes, 50)` gates NEW buys only (closes still rotate on month-change) |
| Persistent state | `last_rebalance_month` (cross-flat YYYY-MM) |
| Warmup | 180 calendar days (~120 trading bars; covers N=60 with margin and a typical NAMED_WINDOW length) |

**Universe choice rationale.** Brief specifies the same 11 SPDR
sectors as #1 momentum so the only thing differing between the two
candidates is the ranking criterion (vol vs. 12-1 return). I considered
adding TLT/GLD for cross-asset low-vol but rejected: (a) it would
confound the comparison; (b) TLT/GLD historically dominate any vol-rank
basket because they're structurally lower-vol than equities, which turns
the strategy into "buy bonds and gold" — a different and less
interesting hypothesis than "does AHXZ work on sector ETFs."

**K choice.** K=3 keeps per-leg notional at $33.33 — same as #1
momentum. K=2 makes the strategy nearly binary (XLP+XLU most months);
K=5 dilutes the bottom-vol signal into half the basket. K=3 is the most
defensible primary, confirmed by sensitivity (§4): K=3 is the only
config with positive median return.

**N (vol-lookback) choice.** N=60 is AHXZ's canonical ~3-month window.
N=21 (1-month) is much noisier and trades 2x as much (144 vs 68
walk-forward trades), with strictly worse results (median -0.66%,
Sharpe -0.77). N=60 wins clean.

## 2. Bar A scorecard (per `GATE.md`, amended 2026-05-30)

Evaluated on the **K=3, N=60, no-regime-filter** primary variant.

| # | Bar A bullet | Result | Verdict |
|---|---|---|---|
| 1 | All 8 named regimes pass via (a) positive return OR (b) ≥ BH-basket + ≥25% in-position; (b) capped at 1 | 4/8 via (a), 1/8 via (b) (2022-H1 bear). 3 windows fail: 2022-Q3 chop, 2023-Q3 chop, 2025-Q1 tariff bear. In each failing window, return < BH-basket, so (b) is unreachable regardless of the floor. In-position is **67%** — well above the 25% floor. | **FAIL** |
| 2 | Held-out final regime (2026-recent bull) | +0.41% return, positive, no prior tuning | **PASS** |
| 3 | Cost-aware Sharpe ≥ 0.5 on full backtest period | Full-period (1237 bars, ~5y) Sharpe **0.36** | **FAIL** |
| 4 | Trade count ≥ 30 across backtest | 67 full-period; 68 across walk-forward windows | **PASS** |
| 5 | Max drawdown ≤ 30% post-cost | Full-period **-2.23%**; worst-window -1.85% | **PASS** |
| 6 | Code review pass via AST gate | Static imports only (math, dataclasses, typing); no eval/exec/network/file I/O | **PASS** |
| 7 | Smoke test via `./tick.sh --candidate xsec_lowvol_c3783c` | `rc=0`, action=`{XLC=buy, XLP=buy, XLF=buy}`, 3300 bars total, 3.7s | **PASS** |

**Bar A overall: FAIL** — bullet #1 fails on 3/8 windows (none rescuable
via (b) because the strategy underperforms BH-basket in those windows);
bullet #3 (Sharpe 0.36 < 0.50) is independently binding.

## 3. Walk-forward summary (8 named windows, +180d warmup per window)

### 3a. Without regime filter (K=3, N=60) — PRIMARY

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 187 | 7 | 1 | -0.80 | -0.91 | -1.71 | 0 | -1.49 | ✅ | 67 | ✅(b) |
| 2022-Q3 chop | chop | 187 | 9 | 0 | -1.47 | -1.57 | -1.85 | 0 | -0.62 | ❌ | 67 | ❌ |
| 2023-H1 recovery | bull | 188 | 7 | 2 | +0.22 | +0.27 | -1.07 | 50 | +0.45 | ❌ | 68 | ✅ |
| 2023-Q3 chop | chop | 186 | 9 | 1 | -0.59 | -1.23 | -0.90 | 33 | -0.41 | ❌ | 67 | ❌ |
| 2024-Q2 bull | bull | 184 | 5 | 1 | +0.65 | +1.55 | -0.58 | 100 | +0.07 | ✅ | 67 | ✅ |
| 2025-Q1 tariff bear | bear | 185 | 13 | 2 | -0.05 | -0.06 | -1.24 | 40 | -0.50 | ✅ | 67 | ❌ |
| 2025-Q3 bull | bull | 184 | 11 | 1 | +0.24 | +0.35 | -0.71 | 50 | +0.35 | ❌ | 67 | ✅ |
| 2026-recent bull | bull | 164 | 7 | 2 | +0.41 | +0.88 | -0.98 | 0 | +0.73 | ❌ | 63 | ✅ |

**Per-regime median:** bull = +0.33% · chop = -1.03% · bear = -0.43%

**Aggregate:** median ret +0.09% · 50% positive · 38% beat BH-basket ·
median Sharpe 0.11 · trades 68 · clamps 10/68 fills (15%).
**Fitness gate (shared single-symbol gate):** 🔴 FAIL — only 38% beat
BH-SPY (need ≥50%); median Sharpe 0.11 ≤ 0.50.
**Bar A #1 (amended, cap=1):** 🔴 FAIL — 3 windows fail (a) AND fail
(b); 2025-Q1 tariff bear has return > BH-basket but (b) already used
on 2022-H1 bear (cap=1).

### 3b. With regime filter (K=3, N=60)

| Window | Regime | Ticks | Trades | Clamps | Return % | Sharpe | MaxDD % | Win % | BH-Basket % | Beats BH? | In-Pos % | BarA #1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 187 | 5 | 0 | -0.47 | -0.68 | -1.12 | 0 | -1.49 | ✅ | 67 | ✅(b) |
| 2022-Q3 chop | chop | 187 | 7 | 0 | -1.33 | -1.84 | -1.71 | 0 | -0.62 | ❌ | 67 | ❌ |
| 2023-H1 recovery | bull | 188 | 4 | 0 | +0.27 | +0.45 | -0.70 | 100 | +0.45 | ❌ | 55 | ✅ |
| 2023-Q3 chop | chop | 186 | 9 | 1 | -0.59 | -1.23 | -0.90 | 33 | -0.41 | ❌ | 67 | ❌ |
| 2024-Q2 bull | bull | 184 | 5 | 1 | +0.65 | +1.55 | -0.58 | 100 | +0.07 | ✅ | 67 | ✅ |
| 2025-Q1 tariff bear | bear | 185 | 10 | 1 | -0.12 | -0.21 | -0.76 | 25 | -0.50 | ✅ | 67 | ❌ |
| 2025-Q3 bull | bull | 184 | 11 | 1 | +0.42 | +0.89 | -0.34 | 50 | +0.35 | ✅ | 57 | ✅ |
| 2026-recent bull | bull | 164 | 5 | 1 | +0.47 | +1.07 | -0.98 | 0 | +0.73 | ❌ | 63 | ✅ |

**Per-regime median:** bull = +0.44% · chop = -0.96% · bear = -0.30%

**Aggregate:** median ret +0.07% · 50% positive · 50% beat BH-basket ·
median Sharpe 0.12 · trades 56.
**Bar A #1 (amended):** 🔴 FAIL — same 3 chop+tariff-bear windows
fail; same (b) cap-1 collision.

**Regime gate verdict: MARGINAL — slightly better on a few axes but
still FAIL.** Unlike #1 momentum where the regime filter was strictly
worse, here it's roughly neutral-to-mildly-positive: cuts 2022-H1 bear
losses (-0.47% vs -0.80%) and 2025-Q1 bear losses (-0.12% vs -0.05%
— wait, that one's slightly worse on return but better on drawdown
-0.76% vs -1.24%); slightly improves 2023-H1, 2025-Q3, 2026-recent
bull returns by reducing exposure during early-window dips. Net:
bull-median +0.44% vs +0.33% noreg, bear-median -0.30% vs -0.43%
noreg. But the chop windows are essentially unchanged because SPY-SMA
doesn't flip during them. The regime-filter math is more sympathetic
to defensives than to momentum here because: (a) defensives lose less
when SPY drops below SMA so the gate has more "right calls"; (b) the
strategy is rotating between *defensives* not chasing *winners*, so
gating doesn't kill the alpha source. Conclusion: regime variant is
mildly preferable but doesn't rescue the gate failures.

## 4. K sensitivity (no regime filter, N=60)

| K | Median Ret % | % Positive | % Beat BH | Median Sharpe | Trades | Worst Window | Best Window | BarA #1 |
|---|---|---|---|---|---|---|---|---|
| 2 | -0.10 | 38 | 50 | -0.13 | 42 | -1.40 (2022-Q3) | +0.78 (2024-Q2) | FAIL |
| **3** | **+0.09** | **50** | **38** | **0.11** | **68** | **-1.47 (2022-Q3)** | **+0.65 (2024-Q2)** | **FAIL** |
| 5 | -0.11 | 38 | 75 | -0.11 | 88 | -1.69 (2022-Q3) | +0.60 (2025-Q3) | FAIL |

**K=3 is the U-shaped sweet spot.** K=2 over-concentrates into
XLP+XLU and misses some XLF/XLI rotation that helped. K=5 dilutes
into half the universe (5 of 11) and ends up holding higher-vol names
that drag the median negative. Interestingly K=5 beats BH-basket in 6/8
windows (75%) — its diversification helps relative performance — but
its absolute returns are still negative because chops & bears hurt
disproportionately. K=3 is the right primary.

## 5. Lookback (N) sensitivity (K=3, no regime filter)

| N | Median Ret % | % Positive | % Beat BH | Median Sharpe | Trades | Worst | Best | BarA #1 |
|---|---|---|---|---|---|---|---|---|
| 21 | -0.66 | 25 | 38 | -0.77 | 144 | -1.30 | +1.78 | FAIL |
| **60** | **+0.09** | **50** | **38** | **0.11** | **68** | **-1.47** | **+0.65** | **FAIL** |

**N=60 dominates N=21.** N=21 has 2x the trade count (144 vs 68)
because the 1-month vol rank is noisier and rotates more aggressively;
the extra trading bleeds cost and the noisier signal picks worse
sectors. N=21 does deliver the highest single-window upside (+1.78%
2024-Q2 bull, Sharpe 3.49) but pays for it everywhere else. N=60 is
clearly the right primary — consistent with AHXZ's own results that
longer vol windows are less noisy.

## 6. Floor sensitivity (would lowering the in-position floor save us?)

The amended Bar A #1 currently requires ≥25% bars-in-position for the
(b) alt-pass clause. Re-scoring under hypothetical floors of 20%, 15%,
and 10%:

| Floor | Passes (noreg) | Passes (regime) | Verdict change? |
|---|---|---|---|
| 25% (current) | 5/8 | 5/8 | baseline FAIL |
| 20% | 5/8 | 5/8 | **no change** |
| 15% | 5/8 | 5/8 | **no change** |
| 10% | 5/8 | 5/8 | **no change** |

**The floor is not what's killing this strategy.** Low-vol runs at 67%
in-position in every walk-forward window (because defensives dominate
the bottom-K and stay there — XLP/XLU/XLF rotate slowly), so even at
the most permissive 10% floor every window with negative return is
already (b)-eligible if (and only if) it beat BH-basket. The binding
constraints in the failing windows are:

- **2022-Q3 chop:** -1.47% vs BH-basket -0.62% → loses MORE than the
  basket → no (b) eligibility regardless of floor.
- **2023-Q3 chop:** -0.59% vs BH-basket -0.41% → same.
- **2025-Q1 tariff bear:** -0.05% vs BH-basket -0.50% → BEATS BH but
  the (b) slot is consumed by 2022-H1 bear (cap=1).

This is a substantively different failure mode than the #1 momentum
report. Momentum failed because *the structure of the harness* (low
notional + monthly rebalance + 3 of 11 legs) prevented the cross-sec
ranking from deploying. Low-vol fails because *the strategy itself
underperforms BH-basket in chops* — even with full exposure and good
in-position %.

**Implication for the bench-amendment discussion (flagged by #1
momentum):** the 25% floor is real and binding for cross-sec strategies
with high-rotation behavior (#1 momentum), but NOT for cross-sec
strategies with persistent-pick behavior (#3 low-vol). The two
cross-sec candidates form a useful pair for whoever scopes the amendment:
either the floor or the bench cap on (b)-alt-pass needs nuance, or
both. I am NOT proposing an amendment unilaterally; flagging for main
with concrete two-strategy data.

## 7. Full-period backtest (single contiguous run, ~5 years)

| Metric | Without regime | With regime |
|---|---|---|
| Window | 2021-06-25 → 2026-05-29 (1237 bars) | same |
| Starting equity | $1000 | $1000 |
| Notional per leg | $33.33 (K=3 of $100) | $33.33 |
| Total trades | 67 (35 buys / 32 closes) | 53 (28 / 25) |
| Basket clamps | 23 ticks | 16 ticks |
| Total return | **+1.78%** ($+17.84) | +1.56% |
| Sharpe (annualized) | **0.36** | 0.36 |
| Max drawdown | **-2.23%** | -1.80% |
| Total costs paid | $0.41 | $0.33 |

**Cross-comparison with #1 momentum full-period:**

| Metric | Low-vol (this) | #1 Momentum (peer) | Δ |
|---|---|---|---|
| Total return | **+1.78%** | +2.04% | -0.26% |
| Sharpe | **0.36** | 0.30 | **+0.06** |
| Max DD | **-2.23%** | -3.09% | **+0.86% (better)** |
| Trades | 67 | 63 | +4 |
| Clamps | 23 | 23 | flat |
| In-position % (per-window median) | **67%** | **19%** | **+48%!** |

**Low-vol is materially better on Sharpe and max-DD, materially worse
on raw return — but the in-position % gap is the headline.** Low-vol
deploys capital ~3x as densely as momentum on identical infrastructure.
This is the key finding: low-vol IS the cross-sec strategy that doesn't
hit the bench's in-position floor problem.

### Per-symbol full-period contribution (no regime filter):

| Symbol | Buys | Closes | Realized P&L | Final qty |
|---|---|---|---|---|
| XLF | 5 | 5 | **+$7.40** | 0 |
| XLU | 7 | 7 | **+$5.25** | 0 |
| XLP | 2 | 1 | +$1.58 | 0.455 (open) |
| XLB | 2 | 2 | +$0.47 | 0 |
| XLE | 0 | 0 | $0.00 | 0 |
| XLY | 0 | 0 | $0.00 | 0 |
| XLK | 1 | 1 | -$0.28 | 0 |
| XLRE | 2 | 1 | -$0.40 | 0.774 (open) |
| XLV | 3 | 3 | -$0.45 | 0 |
| XLC | 4 | 3 | -$0.63 | 0.235 (open) |
| XLI | 9 | 9 | -$1.55 | 0 |

**XLE and XLY are NEVER picked across 5 years.** Energy and consumer-
discretionary are structurally the highest-vol sectors; the bottom-3
vol set basically never includes them. XLF (financials, +$7.40) and
XLU (utilities, +$5.25) carry the strategy. XLI (industrials, -$1.55)
is the worst-net contributor — it's frequently in the bottom-K vol
ranking but its returns disappoint. Contrast #1 momentum: there XLY
was the WORST contributor (-$13.26) because the 12-1 signal kept buying
prior winners into 2022's rotation. The two strategies have completely
disjoint per-symbol P&L attributions, which is reassuring — they're
sorting on truly orthogonal signals.

## 8. Verdict: **REJECT-WITH-CAVEATS**

Strict Bar A: REJECT (bullets #1 and #3 fail under both regime variants).

**Why "with caveats" rather than "on floor only":** unlike #1 momentum,
this strategy's primary failure mode is NOT the in-position floor. It's
that the low-vol anomaly genuinely doesn't deliver positive expected
return in chop regimes on a sector-ETF universe — a known limitation
of the anomaly when the universe is narrow.

**What works.**
- 50% windows positive (vs 38% for #1 momentum).
- Full-period Sharpe 0.36 (vs 0.30 for #1 momentum). Better
  risk-adjusted return.
- Max-DD -2.23% (vs -3.09% for #1 momentum). Less risky.
- In-position 67% (vs 19% for #1 momentum). Capital actually deploys.
- Bear-window performance is genuinely defensive: -0.80% in 2022-H1
  bear vs BH-basket -1.49% (saves 69bps); -0.05% in 2025-Q1 tariff
  bear vs BH-basket -0.50% (saves 45bps). The defensive signal IS
  real.
- Held-out 2026-recent bull is positive (+0.41%) — passes Bar A #2.

**What doesn't work.**
- **Chop is murder.** Both 2022-Q3 (-1.47% vs BH -0.62%) and
  2023-Q3 (-0.59% vs BH -0.41%) underperform BH-basket meaningfully.
  Low-vol over-concentrates into defensives that lag in
  range-bound markets where capital is rotating between mid-vol
  sectors. This is the literature's known "defensives churn" problem.
- **Bull is mediocre.** 2023-H1 recovery, 2025-Q3 bull, 2026-recent
  bull all underperform BH-basket because the high-beta sectors
  (XLY, XLE, XLK) catch the rally and we're not in them.
- Sharpe 0.36 < 0.50 threshold. Not close.

**Why it's not a buy at the bench scale.** The strategy delivers what
AHXZ predicts: lower-vol portfolio, lower drawdown, defensive in bears
— but in a universe of 11 sector ETFs the cross-stock vol differential
that drove AHXZ's original cross-section findings is largely smoothed
out. XLP/XLU annualized vol is ~12-15%; XLE/XLY is ~25-30%. That 2x
ratio is real but flat compared to a CRSP single-stock universe where
the ratio is 10x+. The signal is honest; the universe is too narrow
to extract enough edge to clear the gate.

## 9. Honest discussion (compared to #1 momentum's edge)

**Direct comparison on identical infrastructure:**

| Dimension | #3 Low-vol | #1 Momentum | Winner |
|---|---|---|---|
| Median window return | +0.09% | -0.36% | **low-vol** |
| % windows positive | 50% | 38% | **low-vol** |
| Median Sharpe | 0.11 | -0.50 | **low-vol** |
| % beat BH-basket | 38% | 62% | momentum |
| Full-period Sharpe | 0.36 | 0.30 | **low-vol** |
| Full-period max DD | -2.23% | -3.09% | **low-vol** |
| In-position % | 67% | 19% | **low-vol (by 3.5x)** |
| Trades | 67 | 63 | flat |

Low-vol wins 6 of 8 dimensions. The one momentum wins handily ("%
beat BH-basket") is interesting: momentum loses on absolute return
but beats the basket because momentum at least IS in the winners
when they win — it just can't deploy enough capital to make absolute
returns work. Low-vol holds the right defensive picks but misses
the right cyclical picks in bull/chop.

**Does the low-vol anomaly actually appear in this small basket?**
**Partially, yes.** The defensive signal is real in bears
(strategy saves 50-70bps vs BH-basket). The full-period Sharpe
improvement (0.36 vs 0.30) is real. The drawdown reduction (-2.23%
vs -3.09%) is real. What's missing is the canonical low-vol "Sharpe
1.0+" result from the AHXZ original — because: (a) sector ETFs
already volatility-smooth the underlying stocks; (b) 5 years is too
short to capture a full vol-anomaly cycle; (c) the 11-name universe
is far too narrow.

**Verdict context.** If I had to rank the two wave-3 cross-sec
candidates by "interesting next step," low-vol is the more promising
direction. It already clears the in-position floor that's blocking
all xsec candidates; it has positive full-period Sharpe; and the
known fix (broaden the universe to e.g. top-100 SPY components, or
add international/style ETFs) is well-scoped. Momentum needs both
the floor amendment AND structural reworks to even become evaluable.
**I am not promoting; this candidate doesn't clear Bar A as-is and
shouldn't be promoted automatically.** But it's the better seed
for a wave-4 conversation than momentum.

## 10. Files created

| Path | Purpose |
|---|---|
| `strategies_candidates/xsec_lowvol_c3783c/{strategy.py, params.json, __init__.py}` | NEW — candidate. |
| `_run_xsec_lowvol_wf.py` | NEW — driver (warmup +180d walk-forward + full-period + K=2/5 and N=21 sensitivities). |
| `/tmp/xsec_lowvol_wf.md`, `/tmp/xsec_lowvol_wf.json` | Raw walk-forward outputs. |
| `reports/BACKTEST_XSEC_LOWVOL_20260530T175400Z.md` | This report. |

**No changes** to `runner/runner.py`, `runner/backtest.py`,
`runner/backtest_xsec.py`, `runner/walk_forward_xsec.py`,
`runner/candidate_smoke.py` (md5-verified pre/post).

**No changes** to `tests/` either — the candidate ships through
existing test infra unmodified. 182 tests passed pre, 182 post.

## 11. Verification

```
$ python3 -m pytest tests/ -q
182 passed in 4.96s

$ ./tick.sh --candidate xsec_lowvol_c3783c
[xsec_lowvol_c3783c] SMOKE OK xsec (3708ms) basket=[XLB,XLC,XLE,XLF,XLI,
XLK,XLP,XLRE,XLU,XLV,XLY] bars_total=3300 actions={XLC=buy, XLP=buy, XLF=buy}

$ md5sum runner/runner.py runner/backtest.py runner/backtest_xsec.py \
         runner/walk_forward_xsec.py runner/candidate_smoke.py
  (identical to pre-run snapshot)

$ python3 _run_xsec_lowvol_wf.py
  xsec_lowvol_c3783c__noreg:     K=3 N=60 regime=False:
    windows=8/8 medRet=+0.09% pos=50% beatBH=38% medSharpe=0.11
    trades=68 BarA#1=FAIL FIT=FAIL
  xsec_lowvol_c3783c__regime:    K=3 N=60 regime=True:
    windows=8/8 medRet=+0.07% pos=50% beatBH=50% medSharpe=0.12
    trades=56 BarA#1=FAIL FIT=FAIL
  xsec_lowvol_c3783c__noreg_k2:  K=2 N=60 regime=False:
    windows=8/8 medRet=-0.10% pos=38% beatBH=50% medSharpe=-0.13 trades=42 FAIL
  xsec_lowvol_c3783c__noreg_k5:  K=5 N=60 regime=False:
    windows=8/8 medRet=-0.11% pos=38% beatBH=75% medSharpe=-0.11 trades=88 FAIL
  xsec_lowvol_c3783c__noreg_n21: K=3 N=21 regime=False:
    windows=8/8 medRet=-0.66% pos=25% beatBH=38% medSharpe=-0.77 trades=144 FAIL
```

Numbers in this report match `/tmp/xsec_lowvol_wf.json` byte-for-byte.

---

**Final verdict: REJECT-WITH-CAVEATS.** Candidate stays in
`strategies_candidates/`. The low-vol anomaly partially appears in
this sector-ETF universe (defensive in bears, lower drawdown, positive
Sharpe) but doesn't clear Bar A's Sharpe-0.5 threshold or the
chop-window benchmark-beat requirement. **The headline data point for
main is:** low-vol runs at 67% in-position vs momentum's 19%, decisively
demonstrating that the in-position floor issue raised by #1 momentum is
a *behavioral* property of momentum (high churn) rather than a
*structural* property of xsec strategies. That feeds the bench-amendment
conversation with hard data: the floor is real but only binding for a
subset of xsec strategies.
