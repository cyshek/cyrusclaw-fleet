# Single-Stock MOMENTUM, Monthly/Quarterly Cadence — Lower-Turnover-By-Construction Swing

**UTC timestamp:** 20260602T002021Z
**Author:** single-stock momentum subagent (depth 1), trading-bench
**Ruler:** CORRECTED (√252 Sharpe annualization + GATE #5(b) binds on `worst_instrument_dd_pct` deployed-capital DD, per HARNESS_INTEGRITY_AUDIT + RULING 2).
**Parent improved:** `strategies_candidates/xsec_ss_momentum_lc20` (had the **$100 hardcode bug** — `max_notional_usd`/`notional_usd` = 100 against a $1000 rail).
**Candidate written:** `strategies_candidates/xsec_ss_momentum_lc20_v2` (fixes the $100 bug → $1000; adds `rebalance_months` cadence + lookback/skip/K sweep plumbing; hold-overlap inherited from parent).
**Suite at finish:** `237 passed in 7.65s` (unchanged vs 237 baseline; ZERO edits to any protected runner file — mtimes all ≤ 2026-05-31 19:11, predate this session).
**Promotions to `strategies/`:** ZERO. (Subagent has no promotion authority.)
**Front-door verdict:** **REJECT — all 6 variants.** Decisive, honest reject. No soft-pass, no median mirage to debunk (median-window Sharpe is also near zero), no return-floor side door.

---

## TL;DR

The driving hypothesis was sound in principle: **momentum holds winners longer than reversal re-ranks them, so it's lower-turnover by construction** — and the trade counts confirm it (canonical 12-1 monthly = 100 round-trips vs the reversal parent's 946). The turnover profile is genuinely better.

**But the signal has no risk-adjusted edge on this universe/period.** Single-stock momentum on the 20-name blue-chip basket over 2020-07→2026 earns a **full-period continuous-span Sharpe between −0.13 and +0.21** across every lookback × cadence × K combination tested — an order of magnitude short of the 1.0 clause-(a) bar. The two variants that clear the 8%/yr return floor (6-1 and 3-1 monthly) do so with FP-Sharpe ≈ +0.20: **enough return, no risk-adjusted edge** — the mirror image of the lowvol barbell (which had Sharpe but no return). Param-jitter shows the whole neighborhood is a **basin near zero (FP-Sharpe 0.15–0.28)**, not a knife-edge ridge — robust evidence there is no edge to find, not a tuning miss.

The most striking structural finding: the **canonical, lowest-turnover 12-1 monthly variant is the WORST** (FP-Sharpe −0.11, −5.2%/yr). The classic Jegadeesh-Titman lookback that holds winners longest simply did not pay on mega-cap blue-chips this period; only the faster, higher-turnover 3-1/6-1 versions made money, and they made it without Sharpe.

---

## The $100 → $1000 bug fix (what the task flagged)

The parent `xsec_ss_momentum_lc20/params.json` hardcoded `max_notional_usd: 100` and `notional_usd: 100`. The strategy computes `per_leg = max_notional / top_k`, so K=5 deployed only **$20/leg = $100 basket against the $1000 equity** — a 10%-deployed mini-basket. Verified the harness rail: `runner/risk.py` and `runner/backtest.py` both carry `MAX_NOTIONAL = MAX_POSITION = $1000` (paper bump 2026-05-31); `_clamp_basket` enforces the $1000 cap.

v2 sets `max_notional_usd: 1000` / `notional_usd: 1000` → **$200/leg, full $1000 basket.** Two consequences confirmed in the numbers:
- **Cost-survivability is UNCHANGED** (cost is a percentage — 4bps RT on $1000 = $0.40, same fraction as $0.04 on $100). The task's framing is correct: bigger notional does not change cost-survivability; edge must come from the signal, not account size.
- **The deployed-notional denominator is restored** for clause (f) / ann-on-deployed. The corrected sizing also made `worst_instrument_dd_pct` reflect the real single-leg DD (e.g. −27.81% on the 252-bar variant's 2025-Q1 tariff leg), not a diluted mini-leg number.

---

## Universe (identical to parent — directly comparable, survivorship-safe)

```
AAPL MSFT JNJ XOM JPM PG KO WMT CVX HD MRK PEP CSCO VZ DIS MCD NKE UNH BA CAT
```
Same fixed mid-2020 large-cap set. No IPO bias (all listed for decades pre-2020). Mild/flagged delisting bias (all 20 survived; a mid-window blow-up would be absent — but these are blue-chips). **NOT hindsight-selected:** BA and DIS are notable laggards, deliberately retained to avoid winner-cherry-picking. Sector-diversified for cross-sectional dispersion.

**Cost model: ACTIVE, non-zero — asserted.** `CostModel.alpaca_stocks()` = 2bps one-way spread → **4bps round-trip**, 0 fee. Driver asserts `spread_bps==2.0 and fee_bps==0.0` before every run (no `--no-costs` sneak). Verified: `RT cost on $1000 = $0.40 = 4bps`. Smoke confirmed real fills path.

---

## Levers tested

| Lever | Mechanism | Code change? |
|---|---|---|
| **1. Lookback** | `lookback_bars` 252 (12-1) / 126 (6-1) / 63 (3-1), skip 21 | No (parent param) |
| **2. Cadence** | `rebalance_months` 1 (monthly, Jegadeesh-Titman holding period) / 3 (quarterly) | **Yes** — v2 adds month-aware cadence (parent was monthly-only via `_month_key`) |
| **3. Basket size K** | `top_k` 5 (quintile) / 3 (concentrated) / 8 (diversified) | No (parent param) |
| **4. Hold-overlap / no-churn** | Only close names rotating OUT of top-K; only buy names not already held. **ALREADY structural in the parent's `decide_xsec`** — confirmed by reading the code. The single biggest turnover cut is baked in. Cutting further (partial-rebalance bands) needs protected rebalance mechanics → **SKIPPED per constraint, as instructed.** | n/a (inherited) |

Lever 2 note: the parent only supported monthly (it keyed off `YYYY-MM` change). v2's `rebalance_months` generalizes to quarterly **without touching any protected file** — the cadence gate lives entirely inside the candidate's `decide_xsec`.

---

## Results — full 8-window walk-forward (corrected ruler, $1000 deployed)

Warmup 420d (primes the 252-bar lookback; avoids the `ZeroTradesError` warmup-starvation trap). `instrDD` = worst single-leg deployed-capital DD-from-entry (the #5(b)-binding number). `A#1` = amended Bar A bullet #1 per-window pass.

### 1. 12-1 monthly K5 (baseline-corrected, canonical) — REJECT
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 11 | −4.56 | −0.21 | −20.80 | −11.22 | ✅ | ❌ |
| 2022-Q3 chop | chop | 15 | −3.47 | −0.24 | −12.82 | −6.91 | ✅ | ❌ |
| 2023-H1 recovery | bull | 15 | −6.39 | −0.54 | −13.79 | +2.23 | ❌ | ❌ |
| 2023-Q3 chop | chop | 15 | −5.27 | −0.67 | −12.56 | −3.75 | ❌ | ❌ |
| 2024-Q2 bull | bull | 9 | −0.32 | −0.01 | −12.02 | −1.32 | ✅ | ❌ |
| 2025-Q1 tariff bear | bear | 15 | −4.33 | −0.18 | −27.81 | −6.14 | ✅ | ❌ |
| 2025-Q3 bull | bull | 11 | +9.79 | 1.37 | −6.47 | +4.07 | ✅ | ✅ |
| 2026-recent bull | bull | 9 | +0.85 | 0.13 | −17.37 | +7.09 | ❌ | ✅ |

**Agg:** FP-cont Sharpe **−0.11** · medWin Sharpe −0.20 · medRet −3.90% · 25% pos · 62% beat BH · **100 trades** · worstInstrDD −27.81% · **ann −5.24%/yr**.

### 2. 6-1 monthly K5 — REJECT (best FP-Sharpe + clears return floor)
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 31 | −2.47 | −0.05 | −26.77 | −11.22 | ✅ | ✅ |
| 2022-Q3 chop | chop | 27 | −11.35 | −0.45 | −26.77 | −6.91 | ❌ | ❌ |
| 2023-H1 recovery | bull | 33 | +5.35 | 0.35 | −15.23 | +2.23 | ✅ | ✅ |
| 2023-Q3 chop | chop | 35 | −1.06 | −0.01 | −18.17 | −3.75 | ✅ | ❌ |
| 2024-Q2 bull | bull | 39 | +11.12 | 0.96 | −21.59 | −1.32 | ✅ | ✅ |
| 2025-Q1 tariff bear | bear | 31 | −5.54 | −0.21 | −28.96 | −6.14 | ✅ | ❌ |
| 2025-Q3 bull | bull | 35 | +3.40 | 0.24 | −28.96 | +4.07 | ❌ | ✅ |
| 2026-recent bull | bull | 25 | +26.88 | 1.64 | −25.52 | +7.09 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.21** · medWin Sharpe +0.12 · medRet +1.17% · 50% pos · 75% beat BH · **256 trades** · worstInstrDD −28.96% · **ann +8.91%/yr**.

### 3. 3-1 monthly K5 — REJECT (clears return floor)
| Window | Reg | Trd | Ret% | Sharpe | instrDD% | BH% | Beat | A#1 |
|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 59 | +8.82 | 0.51 | −26.77 | −11.22 | ✅ | ✅ |
| 2022-Q3 chop | chop | 59 | −2.93 | −0.06 | −26.77 | −6.91 | ✅ | ✅ |
| 2023-H1 recovery | bull | 55 | +2.38 | 0.18 | −21.27 | +2.23 | ✅ | ✅ |
| 2023-Q3 chop | chop | 51 | −5.38 | −0.17 | −23.34 | −3.75 | ❌ | ❌ |
| 2024-Q2 bull | bull | 55 | −8.86 | −0.55 | −22.48 | −1.32 | ❌ | ❌ |
| 2025-Q1 tariff bear | bear | 41 | −0.76 | 0.04 | −26.68 | −6.14 | ✅ | ❌ |
| 2025-Q3 bull | bull | 45 | +0.33 | 0.09 | −26.68 | +4.07 | ❌ | ✅ |
| 2026-recent bull | bull | 35 | +31.01 | 1.86 | −16.11 | +7.09 | ✅ | ✅ |

**Agg:** FP-cont Sharpe **+0.20** · medWin Sharpe +0.06 · medRet −0.21% · 50% pos · 62% beat BH · **400 trades** · worstInstrDD −26.77% · **ann +8.36%/yr**.

### 4. 12-1 quarterly K5 — REJECT (lowest turnover)
**Agg:** FP-cont Sharpe **+0.06** · medWin −0.19 · medRet −2.58% · 38% pos · 62% beat BH · **80 trades** · worstInstrDD −27.81% · **ann +1.80%/yr**. Per-window: 2024-Q2 +7.80%/Sh1.01, 2025-Q3 +12.21%/Sh1.64, 2026 +12.84%/Sh1.37 carried it; the four 2022–2023 windows all negative.

### 5. 12-1 monthly K3 — REJECT (concentrated)
**Agg:** FP-cont Sharpe **+0.02** · medWin +0.08 · medRet +0.60% · 50% pos · 62% beat BH · **72 trades** · worstInstrDD **−17.08%** (best DD of the set) · **ann −0.84%/yr**.

### 6. 12-1 monthly K8 — REJECT (diversified)
**Agg:** FP-cont Sharpe **−0.13** · medWin −0.23 · medRet −3.32% · 25% pos · 62% beat BH · **136 trades** · worstInstrDD −27.81% · **ann −4.57%/yr**.

---

## Continuous-span vs median-window Sharpe (side by side)

The load-bearing comparison — clause (a) binds on the LEFT column. (For these variants there is no median mirage: even the generous median-window number is near zero.)

| Variant | **FP-cont Sharpe (clause a)** | median-window Sharpe (generous) | ann/deployed | trades | instrDD |
|---|---|---|---|---|---|
| 12-1 monthly K5 (canonical) | **−0.11** | −0.20 | −5.24% | 100 | −27.81 |
| **6-1 monthly K5** (best a) | **+0.21** | +0.12 | +8.91% | 256 | −28.96 |
| 3-1 monthly K5 | **+0.20** | +0.06 | +8.36% | 400 | −26.77 |
| 12-1 quarterly K5 | **+0.06** | −0.19 | +1.80% | 80 | −27.81 |
| 12-1 monthly K3 | **+0.02** | +0.08 | −0.84% | 72 | −17.08 |
| 12-1 monthly K8 | **−0.13** | −0.23 | −4.57% | 136 | −27.81 |

**Not one variant reaches FP-cont Sharpe ≥ 1.0; the best is +0.21, a full 0.79 short.** Unlike the prior reversal swing (where median-window 1.17 masked a true 0.73), here even the generous median-window figure never clears 0.4 — there is no inflated number to debunk. The signal is simply weak.

---

## Front-door verdict per variant

| Variant | FP-Sharpe (a) | ann/deployed (f) | instrDD (5b) | Fitness | BarA#1 | **VERDICT** |
|---|---|---|---|---|---|---|
| 12-1 monthly K5 | −0.11 ❌ | −5.24% ❌ | −27.81 🟢 | ❌ | ❌ | **REJECT** (a, f, #1) |
| 6-1 monthly K5 | +0.21 ❌ | +8.91% 🟢 | −28.96 🟢 | ❌ | ❌ | **REJECT** (a, #1) |
| 3-1 monthly K5 | +0.20 ❌ | +8.36% 🟢 | −26.77 🟢 | ❌ | ❌ | **REJECT** (a, #1) |
| 12-1 quarterly K5 | +0.06 ❌ | +1.80% ❌ | −27.81 🟢 | ❌ | ❌ | **REJECT** (a, f, #1) |
| 12-1 monthly K3 | +0.02 ❌ | −0.84% ❌ | −17.08 🟢 | ❌ | ❌ | **REJECT** (a, f, #1) |
| 12-1 monthly K8 | −0.13 ❌ | −4.57% ❌ | −27.81 🟢 | ❌ | ❌ | **REJECT** (a, f, #1) |

**No PROMOTE-eligible candidate.** The standard front door fails (Fitness + BarA#1 — the buys-winners book underperforms equal-weight BH in v-shaped recoveries / chop, the mirror of the reversal lane's structural issue). The #5 fast-track fails decisively at **clause (a)**: FP-cont Sharpe never exceeds +0.21. Note **#5(b) deployed-capital DD passes everywhere** (−17% to −29%, under the 30% ceiling) — but that's irrelevant when the risk-adjusted return is the failure. Exactly the result the corrected ruler is designed to produce: no DD side-door rescue, no Sharpe inflation.

---

## Param-jitter robustness — the apparent "best" is a basin, not a ridge

No variant passed, but I stress-tested the closest one (6-1 monthly K5, best FP-Sharpe + clears the return floor) by jittering ONE knob at a time. The task asked: plateau or knife-edge? Here there is no edge, and the jitter confirms the whole neighborhood is a **basin near zero** — which is itself robust (uniformly failing, not a fragile argmax):

| Jitter (1 knob from 6-1 mo K5) | FP-cont Sharpe | medWin Sharpe | ann%/yr | trades | ≥1.0? |
|---|---|---|---|---|---|
| center (6-1 monthly K5) | +0.21 | +0.12 | +8.9 | 256 | ❌ |
| lookback 105 (5-1) | +0.28 | +0.28 | +12.4 | 302 | ❌ |
| lookback 147 (7-1) | +0.20 | +0.28 | +7.5 | 198 | ❌ |
| K=4 | +0.24 | +0.19 | +10.5 | 228 | ❌ |
| K=6 | +0.23 | +0.27 | +8.7 | 282 | ❌ |
| skip 10 | +0.17 | +0.03 | +7.0 | 272 | ❌ |
| skip 42 | +0.24 | +0.37 | +9.7 | 238 | ❌ |
| quarterly (reb_months 3) | +0.15 | −0.06 | +5.2 | 162 | ❌ |

**Every cell lands FP-cont Sharpe 0.15–0.28.** No knob, in any direction, moves it toward 1.0. The best return cell (5-1, +12.4%/yr) still has Sharpe 0.28. This is the cleanest possible evidence that the reject is structural (no risk-adjusted edge in single-stock momentum on this universe/period), not a tuning miss or an overfit argmax.

---

## The turnover / lookback / cadence tradeoff found (stated plainly)

- **Turnover IS lower by construction** (hypothesis confirmed): canonical 12-1 monthly = 100 round-trips vs the reversal parent's 946 — a ~9× reduction from holding winners. The diagnosis that momentum is structurally lower-turnover than reversal is **correct**.
- **But lower turnover ≠ edge here.** The lowest-turnover variants (12-1 quarterly 80 trades, 12-1 monthly K3 72 trades) earn the WORST returns (+1.8%, −0.8%/yr). The signal is so weak that cutting turnover just locks in a non-edge.
- **Shorter lookback = more return but no Sharpe.** 3-1 and 6-1 (faster signal, 256–400 trades) are the only variants that clear the 8% return floor — but at FP-Sharpe ~0.20. They make money by taking more shots at a low-hit-rate, high-variance signal, not by having a real risk-adjusted edge. The return floor (clause f) catches this only partially; **clause (a) Sharpe is the guard that correctly rejects them.**
- **The canonical Jegadeesh-Titman 12-1 is the worst cell** — the textbook lookback that holds winners longest delivers −0.11 Sharpe / −5.2%/yr on mega-cap blue-chips this period. Cross-sectional momentum among 20 large, correlated, sector-diversified blue-chips over 2020-2026 (a period of sharp regime whipsaws — 2022 bear, 2023 recovery, 2025 tariff shock) had no exploitable dispersion edge net of 4bps.
- **The honest verdict:** the cost-strangle is NOT the binding constraint for momentum (turnover is naturally low). The binding constraint is that **the signal itself has no risk-adjusted edge on this universe** — a cleaner, more fundamental reject than the reversal lane's "real signal, but too weak vs cost."

---

## Survivorship / lookahead / sparse-signal / integrity notes

- **Lookahead:** uses the audited-clean `walk_forward_xsec`/`backtest_xsec` path unchanged (strategy sees `bars[:cur+1]`, fills only `if has_bar_at_t` at that bar's close, regime SPY slice gated on `st[:10] <= tick_date`). The momentum signal reads only trailing closes (`bars[-1-skip]` back to `bars[-1-skip-lookback]`); no same-bar leak.
- **Warmup-starvation:** ran with 420d warmup so the 252-bar lookback primes inside each window. No `ZeroTradesError` fired; every variant traded in all 8 windows (min 72 total trades). The guard that forced the original `xsec_momentum_xa` correction was respected, not bypassed.
- **Sparse-signal:** all variants ≥ 72 round-trips (well over GATE #4's 30-trade floor); no degenerate near-flat run.
- **Survivorship:** identical fixed mid-2020 large-cap universe; no IPO bias; mild/flagged delisting bias; laggards retained, not hindsight-selected.
- **Cost model:** alpaca_stocks 4bps round-trip, asserted `spread_bps==2.0/fee_bps==0.0` before every run. No zero-cost path.
- **FP-Sharpe methodology:** clause (a) computed as continuous concatenated-equity √252 Sharpe across all 8 windows (matching the `xsec_momentum_xa` promotion record + the prior reversal subagent's `_lowturn_fpsharpe`), NOT median-of-windows. 2776 per-tick returns in the concatenated series. This is the decisive, load-bearing number.

---

## Artifacts & integrity

- **Candidate written:** `strategies_candidates/xsec_ss_momentum_lc20_v2/` (`strategy.py` + `params.json`). Fixes the $100→$1000 hardcode bug; adds `rebalance_months` (1=monthly default, 3=quarterly) and lookback/skip/K sweep plumbing. Hold-overlap (lever 4) inherited structurally from the parent's rotate-out/open-new-only loop. STAYS in `strategies_candidates/` — ZERO promotion.
- **Driver scripts (research-only, in `reports/`, no `test_` prefix so pytest ignores them):**
  - `_ss_momentum_driver.py` — loads v2 `decide_xsec` from `strategies_candidates/`, runs full 8-window WF, asserts cost model active, computes FP-continuous Sharpe + median-window Sharpe + ann-on-deployed (deployed basis read from params.notional_usd) + worst_instrument_dd + BarA#1.
  - `_ss_momentum_jitter.py` — one-knob-at-a-time param jitter around the best variant (6-1 monthly K5).
- **Tests:** `237 passed in 7.65s` after the candidate was added — no regression vs the 237 baseline.
- **Smoke test:** `./tick.sh --candidate xsec_ss_momentum_lc20_v2` → `SMOKE OK xsec`, rc=0, actions `{XOM=buy, CVX=buy, JNJ=buy, CSCO=buy, CAT=buy}`, no DB errors.
- **Cost model verified ACTIVE:** `CostModel.alpaca_stocks()` spread_bps=2.0, fee_bps=0.0 → RT cost on $1000 = $0.40 = 4bps. Asserted before every WF run. No `--no-costs` path used.
- **Protected files UNTOUCHED — verified by mtime:** `runner/runner.py`, `runner/risk.py`, `runner/runner_xsec.py`, `runner/backtest.py`, `runner/backtest_xsec.py`, `runner/walk_forward.py`, `runner/walk_forward_xsec.py`, `runner/safety_backstop.py` all carry mtimes ≤ 2026-05-31 19:11 UTC, predating this session (2026-06-02 ~00:20 UTC). Only the new candidate dir + the two `reports/_ss_momentum_*.py` driver scripts are dated today. Evaluation used the `decide_xsec_fn`+`params` override path into `walk_forward_xsec` — the same no-protected-edit pattern the two prior rejection reports used.
- **Lever 4 (hold-the-winners overlap):** confirmed already present in the parent's `decide_xsec` (rotate-out + open-new-only). No further turnover cut available without touching protected rebalance mechanics → skipped per constraint, as instructed.

---

## Recommendation

**Do not promote — close the single-stock momentum lane at $1000/4bps.** The turnover hypothesis was correct (momentum is structurally ~9× lower-turnover than the reversal parent), but it does not matter: single-stock cross-sectional momentum on this 20-name blue-chip universe over 2020-2026 has **no risk-adjusted edge** — full-period continuous-span Sharpe never exceeds +0.21 across the entire lookback × cadence × K grid, and the whole param neighborhood is a flat basin near zero, not a tunable ridge. The canonical 12-1 monthly variant is the single worst cell. The two variants that earn ≥8%/yr do so purely by taking more high-variance shots (Sharpe ~0.20), exactly the kind of return-without-edge that clause (a) exists to reject.

Combined with the two prior single-stock rejects (cross-sectional sweep, low-turnover reversal), the evidence now points to a **lane-level conclusion**: cross-sectional signals on a 20-name large-cap blue-chip universe at 4bps do not clear the corrected front door. The blue-chips are too correlated / too efficient for cross-sectional dispersion to pay risk-adjusted. If the cross-sectional lane is revisited, the structural lever is a **wider, more dispersed universe** (more names, more idiosyncratic dispersion — the Jegadeesh-Titman setting was hundreds of NYSE/AMEX names, not 20 mega-caps) or a **different signal class entirely** — not more parameter tuning of momentum on this universe. The tournament still has ZERO legitimate single-stock promotions; this is a clean, honest reject, not a near-miss.
