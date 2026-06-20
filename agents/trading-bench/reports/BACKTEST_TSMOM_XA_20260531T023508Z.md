# BACKTEST — TSMOM Cross-Asset Basket (`tsmom_xa_be0d7f`)

**Author:** trading-bench (subagent `tsmom-xa`)
**UTC:** 2026-05-31T02:35:08Z
**Archetype:** #2 Time-Series Momentum (Moskowitz/Ooi/Pedersen 2012), **cross-asset basket, long-only**
**Candidate:** `strategies_candidates/tsmom_xa_be0d7f/`
**Universe:** [SPY, EFA, TLT, VNQ, DBC, GLD] — identical to the PROMOTED cross-sectional winner `xsec_momentum_xa_38d2b2`, so the *only* changed variable vs that candidate is the **signal rule** (sign-of-own-trailing-return vs cross-sectional top-K rank).
**Verdict:** **REJECT** (razor's-edge near-miss; see discussion). Recommendation only — I do not promote.

---

## 0. What this strategy is (and how it differs from the promoted winner)

Both candidates share the exact same 6-asset cross-asset basket, monthly cadence, 252/21 (12-1) lookback, `alpaca_stocks` cost model, and `$100` notional cap. The single difference:

- **`xsec_momentum_xa_38d2b2` (PROMOTED):** *cross-sectional* — RANK the 6 legs by 12-1 return, hold the **top-K (fixed K=2)** regardless of sign. Always deploys ~$100 into the two "least-bad" legs even in a broad bear.
- **`tsmom_xa_be0d7f` (THIS):** *time-series* — judge each leg against **zero**. Hold a leg long iff its **own** trailing 12-1 return is strictly positive. `N_long` is variable: 0 (all assets trending down → fully flat/cash) up to 6. This is the canonical MOP-2012 sign-of-trailing-return rule applied per-asset.

The thesis-difference that matters: TSMOM *can go flat* in a broad risk-off regime and sidestep drawdown — the defensive long-only behavior the triage doc flagged. Cross-sectional momentum cannot.

**No SPY regime overlay** (PATTERNS.md Pattern #1, confirmed 3×). TSMOM's own sign-of-trailing-return rule *is* its risk-off filter; a redundant SPY-SMA gate would only subtract information. `use_regime_filter` is ignored in the strategy code even if set.

---

## 1. Bar A scorecard

| Bullet | Criterion | Result | PASS/FAIL |
|---|---|---|---|
| **#1** | Walk-forward pass on all 8 windows (amended, cap=1 on (b)-alt) | 3 windows fail: 2022-H1 bear (in-pos 18%<25%), 2022-Q3 chop (ret −1.09% < BH −0.85% AND in-pos 19%), 2023-Q3 chop (in-pos 18%<25%) | **FAIL** |
| **#2** | Held-out final regime (`2026-recent bull`) passes un-tuned | +0.56%, Sharpe 1.85, passes bullet-#1 (a) | **PASS** |
| **#3** | Full-period cost-aware Sharpe ≥ 0.5 | **0.983** | **PASS** |
| **#4** | Trade count ≥ 30 (walk-forward sum) | **36** | **PASS** |
| **#5** | Max drawdown ≤ 30% post-cost | worst window −1.34%; full-period −4.46% book ($44.57 abs) | **PASS** |
| **#6** | Code-review / AST gate | pure-Python, no imports beyond stdlib dataclass/typing; mirrors approved sibling | **PASS (expected)** |
| **#7** | Smoke test `./tick.sh --candidate` rc=0 | `SMOKE OK xsec` — actions `{SPY,EFA,VNQ,DBC,GLD = buy}` (TLT correctly excluded, trend ≤ 0) | **PASS** |

**Standard Bar A → FAIL** (bullet #1). The failure is structural, not a property of edge: the monthly-rebalance + variable-K design sits at **18–19% in-position** because occupancy is dominated by rebalance cadence + the warmup-zero-occupancy denominator contribution — the *exact* Pattern-#2 / fixed-cadence-rotator failure mode documented for the promoted sibling. The cross-asset universe does not change this; nothing about the universe could.

### Bar A bullet #5 fast-track (rare-strong-candidate)

| Clause | Criterion | Result | PASS/FAIL |
|---|---|---|---|
| **(a)** | Full-period Sharpe ≥ 1.0 | **0.9829** | **FAIL (by 0.017)** |
| **(b)** | Full-period MaxDD ≤ 2×MAX_NOTIONAL ($200) absolute | **$44.57** | **PASS** |
| **(c)** | Every window passes (V1 OR V2) AND no catastrophe | **all 8 windows OK** (V1 ✅ and V2 ✅ on every window; no window with s≤−1.5% AND s<BH) | **PASS** |

**#5 fast-track → NOT AVAILABLE.** The triple (a)+(b)+(c) is conjunctive; (a) fails by 0.017 Sharpe. (b) and (c) clear cleanly — including the catastrophe backstop (worst window 2022-Q3 is −1.09%, inside the −1.5% floor, so not a catastrophe despite mild BH-underperformance).

---

## 2. Per-regime walk-forward table (8 named windows, +400d warmup each)

| Window | Regime | Ticks | Trades | Return % | Sharpe | MaxDD % | In-pos % | BH-basket % | Beats BH | BarA#1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | 5 | −0.80 | −1.09 | −0.98 | 18 | −1.18 | ✅ | ❌ |
| 2022-Q3 chop | chop | 338 | 3 | −1.09 | −0.82 | −1.34 | 19 | −0.85 | ❌ | ❌ |
| 2023-H1 recovery | bull | 337 | 4 | +0.60 | 1.11 | −0.32 | 18 | +0.44 | ✅ | ✅ |
| 2023-Q3 chop | chop | 336 | 3 | −0.42 | −0.93 | −0.68 | 18 | −0.44 | ✅ | ❌ |
| 2024-Q2 bull | bull | 337 | 5 | +0.21 | 0.41 | −0.29 | 18 | +0.09 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 335 | 4 | +0.39 | 0.41 | −1.08 | 18 | +0.15 | ✅ | ✅ |
| 2025-Q3 bull | bull | 336 | 6 | +0.77 | 2.63 | −0.07 | 12 | +0.53 | ✅ | ✅ |
| 2026-recent bull | bull | 317 | 6 | +0.56 | 1.85 | −0.14 | 11 | +0.74 | ❌ | ✅ |

**Aggregate:** median ret **+0.30%** · 62% windows positive · **75% beat BH-basket** · median Sharpe 0.41 · worst −1.09% (2022-Q3) · best +0.77% (2025-Q3) · **36 trades**.
**Per-regime median:** bull **+0.58%** · chop **−0.76%** · bear **−0.21%**.

Note: the strategy beats BH-basket in 6 of 8 windows — including **both bears** (loses less, or turns positive) — exactly the defensive long-only profile TSMOM is supposed to deliver. The two BH-misses are a chop (−0.24pp) and the most-recent bull (−0.18pp), both tiny.

---

## 3. Full-period continuous backtest (2020-12-02 → 2026-05-22, single equity curve)

| Metric | Value |
|---|---|
| Span | 2020-12-02 → 2026-05-22 (1374 ticks) |
| Trades (continuous run) | 19 (11 buys / 8 closes) |
| Total return (book, $1000 base) | **+12.44%** (+$124.41) |
| BH-basket same period (book) | +6.28% |
| **Full-period Sharpe** | **0.983** |
| Max drawdown | **−4.46% book = $44.57 absolute** |
| Total costs | $0.13 |
| Basket clamps | 29 |

The strategy roughly **doubles** the equal-weight BH-basket return over the full period (+12.4% vs +6.3%) at a Sharpe just shy of 1.0, with a trivial ~$45 peak-to-trough drawdown on the deployed book. Per-leg P&L: GLD +$3.60, DBC +$3.89 carried the book; VNQ −$4.86, SPY −$3.57, EFA −$1.55 were the drags; TLT never qualified (long-bond downtrend the whole span).

### Sensitivity (pre-declared grid; NOT a promotion basis)

| lookback/skip | FP Sharpe | ret % | MaxDD % | trades |
|---|---|---|---|---|
| **252/21 (canonical)** | **0.983** | 12.44 | −4.46 | 19 |
| 252/0 | 0.929 | 11.73 | −4.45 | 21 |
| 252/42 | 0.956 | 12.15 | −4.52 | 15 |
| 189/21 | 0.759 | 4.41 | −1.83 | 37 |
| 126/21 | 0.638 | 2.86 | −1.58 | 67 |

The canonical 252/21 is the **best** point in the grid — no reasonable perturbation crosses Sharpe 1.0, and shortening the lookback degrades monotonically. The 0.98 near-miss is therefore **robust, not a knife-edge artifact**: the strategy genuinely lives at ~0.98 across sensible parameterizations. I did not search for a config that crosses 1.0, because that would be p-hacking a fast-track admission; the canonical lookback is already optimal among defensible choices.

---

## 4. Verdict: **REJECT**

Under **both** available paths the candidate falls short by a hair:
- **Standard Bar A** fails bullet #1 (3 windows below the 25% in-position floor — the same structural fixed-cadence-rotator failure the promoted sibling has, except the sibling had an honest path via bullet #5).
- **Bar A #5 fast-track** fails clause (a) by **0.017 Sharpe** (0.983 vs 1.0), while clearing (b) and (c) cleanly.

I am **not** recommending NEEDS_MORE_DATA: more data is not the blocker. The walk-forward already spans 8 regimes across 4 years with full history on all 6 legs, and the sensitivity grid shows the ~0.98 Sharpe is stable. The blocker is that the strategy's genuine edge, measured honestly on the canonical config, lands *just* under the pre-committed line. The gate did its job.

---

## 5. Honest discussion (2 paragraphs)

**What this result tells us about the universe-class effect.** The wave-4 thesis — that a cross-asset universe rescues a momentum strategy that died on sector-equity — partially holds here too. TSMOM on this 6-asset basket beats its BH benchmark in 6 of 8 windows, goes defensively flat-ish in bears (losing −0.80%/−0.21% median vs the basket's −1.18% and worse), and earns a +12.4% full-period book return at Sharpe 0.98 — a genuinely respectable, low-drawdown profile. That is *materially* better than single-symbol TSMOM (rejected for being almost never in-position) and confirms the universe-class lesson generalizes from cross-sectional to time-series momentum. But it lands a notch below its cross-sectional cousin: `xsec_momentum_xa_38d2b2` cleared #5(a) at Sharpe **1.13**, this clears at **0.98**. The likely reason is that the sign-vs-zero rule is *more conservative* than top-K ranking — it holds fewer legs on average (going fully flat in deep risk-off) and thus deploys less capital, trading a touch of Sharpe-generating exposure for drawdown protection it didn't strictly need given the tiny absolute drawdowns either way. Top-K's "always hold the 2 best" turns out to be the higher-Sharpe posture *within this bench's $100-cap, monthly-cadence sandbox*.

**Why REJECT is the right call and what would change it.** The candidate is a clean, well-behaved strategy that simply doesn't clear a pre-committed bar — and the bar was set first, so the 0.017-Sharpe miss is not negotiable without moving goalposts, which is exactly what GATE.md exists to prevent. I explicitly did **not** hunt for a parameter tweak to nudge Sharpe over 1.0; the canonical 252/21 is already the grid optimum, and any further search would be admitting a result the honest config rejects. The two things that could *legitimately* change the verdict, neither of which is a tuning hack: (1) a **harness-level** decision to exclude warmup-zero-occupancy ticks from the in-position denominator (which the promoted sibling's report also flagged as the structural fix for the 25% floor) — that would let standard bullet #1 admit fixed-cadence rotators on their merits rather than penalizing them for a denominator artifact; or (2) raising the deployed notional / loosening the monthly cadence, which alters the strategy's character and would need its own re-gate. As it stands, TSMOM-cross-asset is a **near-miss REJECT** — informative (the universe-class effect generalizes to TSMOM; sign-vs-zero is slightly lower-Sharpe than top-K here) but not promotable under the current gate.

---

## 6. Files created / touched

**Candidate (committed):**
- `strategies_candidates/tsmom_xa_be0d7f/strategy.py`
- `strategies_candidates/tsmom_xa_be0d7f/params.json`
- `strategies_candidates/tsmom_xa_be0d7f/__init__.py`

**This report:**
- `reports/BACKTEST_TSMOM_XA_20260531T023508Z.md`

**Driver / artifact scripts (workspace root, disposable — not in strategies/):**
- `_run_tsmom_xa_wf.py` (walk-forward driver) → `_wf_tsmom_xa_be0d7f.md`, `_wf_tsmom_xa_be0d7f.json`
- `_run_tsmom_xa_fp.py` (full-period continuous) → `_fp_tsmom_xa_be0d7f.json`
- `_eval_tsmom_xa.py` (Bar A + #5 scorer)
- `_sens_tsmom_xa.py` (sensitivity grid)

**Untouched (per hard constraints):** `runner/runner.py`, `runner/runner_xsec.py`, `runner/broker_alpaca.py`, `runner/risk.py`, `runner/safety_backstop.py`, `runner/backtest_xsec.py`, `runner/walk_forward_xsec.py`, `GATE.md`, and everything under `strategies/`.
