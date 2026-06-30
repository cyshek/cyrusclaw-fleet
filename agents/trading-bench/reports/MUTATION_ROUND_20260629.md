# MUTATION ROUND — Monday 2026-06-29

_Round ID: `20260629T205515Z` · seed 20260629 · LIVE LLM-mutation pass · paper-only_
_Worker: trading-bench subagent (run directly — no nested spawn, per cron-trap rule)_
_Result: **0 / 3 candidates pass the gate (honest clean round).**_

---

## TL;DR

Three candidates generated and evaluated against the mutation stability gate. **None pass.** All three land on already-documented CLOSED lanes, and the one apparent PROMOTE is a **false positive caused by a notional-mismatch bug in the gate's parent-baseline comparison** (candidate scored at notional=1000 vs parent at on-disk notional=100 → return % inflated ~10×). At apples-to-apples notional, every candidate's **out-of-sample full-period Sharpe is WORSE than its parent's.** Nothing promoted. Candidates remain quarantined in `strategies_candidates/` (untracked dir — not in live `strategies/`, not scheduled).

Protected hard-rail files: all 6 md5s match MEMORY (runner `0f763975`, risk `e303317e`, backtest `717c36e6`, backtest_xsec `d8927364`, walk_forward_xsec `8c3df32c`, safety_backstop `bccefaba`). No hard-rail touched.

---

## Parents + directives (3 pairs, seed 20260629)

| # | Parent | Family | Directive |
|---|---|---|---|
| 1 | `rsi_oversold_spy` | mean-reversion (SPY 1h) | Combine entry with a SECOND signal (OR/AND). → signal-fusion |
| 2 | `breakout_xlk` | Donchian breakout (XLK 1h) | Add PARTIAL EXIT (scale-out): sell HALF at +X% above entry, once. |
| 3 | `trend_follow_uup` | cross-asset trend / de-correlator (UUP 1d) | Add TRAILING STOP off running-max; X smaller than median runup. |

Authoring choices (grounded in each parent's empirical trade profile, not round numbers):
- **#1** — chose OR (more entries, per directive) by adding a Donchian-`20`-bar new-low pullback trigger alongside RSI<28, to catch sharp flushes RSI lags. Exit unchanged (RSI>70 OR 20-bar time-stop).
- **#2** — `scaleout_pct = 2.60%` = the parent's per-trade **median** max-runup (p25 +1.26 / median +2.60 / p75 +4.11), so it fires on ~half of winners. `_scaled_out` bool fires the half-sale once; parent Donchian-low close fires the remainder (close-logic first).
- **#3** — `trail_pct = 0.07%` (just under the +0.09% median runup). **Flagged in the docstring as a red flag**: UUP runups are an order of magnitude smaller than the equity parents this overlay suits, so a runup-grounded trail is pathologically tight (churn-or-inert).

---

## Per-candidate results

Full-period (FP) Sharpe = continuous-span (concatenate every window's per-tick equity returns into ONE series, annualize √252) per `runner/fp_sharpe.py` — the load-bearing ruler, NOT median-of-windows. FP-Sharpe is notional-invariant. IS/OOS = first-4-windows / last-4-windows chronological split. Cost model @2bps. Synthetic/backstop rows not present (clean walk-forward windows only).

### 1. `rsi_oversold_spy__mut_b58135` — 🔴 REJECT_GATE

| metric | candidate | parent |
|---|---:|---:|
| FP-Sharpe **full** | **−0.141** | +0.148 |
| FP-Sharpe **IS** | −0.435 | −0.164 |
| FP-Sharpe **OOS** | **+0.179** | **+0.505** |
| total trades | 183 | 67 |
| median return (WF) | −0.05% | — |
| median Sharpe (WF) | 0.02 | — |
| % beat BH-SPY | 38% | — |

**Verdict: FAIL.** The OR-pullback trigger added a LOT of entries (67→183 trades) but they are **low/negative expectancy** — median return −0.05%, full-period Sharpe goes NEGATIVE (−0.141 vs parent +0.148), and **OOS Sharpe +0.179 is well below parent's +0.505 (Δ −0.326)**. Widening the entry diluted the edge. Fails absolute gate (median Sharpe 0.02 ≤ 0.50; 38% beat BH < 50%) AND the parent comparison.
*+1-bar canary:* moot — a candidate that fails at zero execution-lag (negative FP-Sharpe, OOS below parent, negative median return) can only do worse with lag. Not separately built (no decision value; would only confirm REJECT).

### 2. `breakout_xlk__mut_232050` — 🔴 REJECT_GATE (corrects a false PROMOTE)

| metric | candidate @100 (apples-to-apples) | parent @100 |
|---|---:|---:|
| FP-Sharpe **full** | 0.378 | 0.431 |
| FP-Sharpe **IS** | +0.156 | −0.020 |
| FP-Sharpe **OOS** | **+0.596** | **+0.865** |
| median return (WF) | **0.3882%** | **0.3957%** |
| median Sharpe (WF) | 1.456 | 1.362 |
| total trades | 116 | 96 |

**The auto-round gate said 🟢 PROMOTE (medRet +3.88%, "beats parent by +3.49pp"). That is a FALSE POSITIVE.** Root cause: the candidate's `params.json` declares `notional_usd=1000.0` (per the generator prompt's "always 1000.0" instruction), but the gate's parent baseline (`_parent_wf_cached` → `walk_forward(parent)`) runs the parent at its **on-disk notional=100**. In this backtester return% scales linearly with notional (verified: candidate medRet @100 = 0.3882%, @1000 = 3.8818%, **ratio exactly 10.00**). So the "+3.49pp win" is 10× scaling, not alpha.

**At apples-to-apples notional (both 100):** candidate median return 0.3882% vs parent 0.3957% → **delta −0.0075pp** (need ≥+0.10pp) → **gate FAILS.** OOS FP-Sharpe +0.596 is BELOW parent's +0.865 (Δ −0.270). This exactly reproduces the 2026-06-26 deep-vet (`VET_BREAKOUT_XLK_MUT232050_V2`): scale-out raises *median* Sharpe purely by **shaving the upper tail** (mean return falls, bull regimes hurt), with no net return gain → KEEP-IN-QUARANTINE, never promote. **Confirmed CLOSED lane.**

### 3. `trend_follow_uup__mut_f111eb` — 🔴 REJECT_GATE

| metric | candidate | parent |
|---|---:|---:|
| FP-Sharpe **full** | 0.497 | 0.269 |
| FP-Sharpe **IS** | +0.774 | +0.270 |
| FP-Sharpe **OOS** | **−0.088** | **+0.349** |
| total trades | 43 | 11 |
| median Sharpe (WF) | 0.15 | — |

**Verdict: FAIL.** The 0.07% trailing stop churned (11→43 trades, barely over the 40 floor), but it's **IS-overfit / OOS-failure**: full-period Sharpe 0.497 looks > parent 0.269, but that's IS-driven (IS 0.774) and **collapses to −0.088 OOS** while parent holds +0.349 (Δ −0.437). Fails the absolute gate (median Sharpe 0.15 ≤ 0.50). Exactly the compressed-vol currency outcome MEMORY predicts for the UUP single-name lane — a runup-grounded trailing stop has no room to work on a low-vol dollar ETF. **Confirmed CLOSED lane.**

---

## Gate verdict summary

| # | Candidate | Code review | Trades ≥40 | OOS FP-Sharpe vs parent | Median Δret ≥+0.10pp | **GATE** |
|---|---|:--:|:--:|:--:|:--:|:--:|
| 1 | rsi_oversold_spy__mut_b58135 | ✅ pass | ✅ 183 | ❌ −0.326 | ❌ −0.05% | **FAIL** |
| 2 | breakout_xlk__mut_232050 | ✅ pass | ✅ 116 | ❌ −0.270 | ❌ −0.0075pp (apples-to-apples) | **FAIL** |
| 3 | trend_follow_uup__mut_f111eb | ✅ pass | ✅ 43 | ❌ −0.437 | ❌ (abs Sharpe 0.15) | **FAIL** |

**0 / 3 pass. Nothing promoted. Nothing scheduled.** All candidates remain in `strategies_candidates/` (untracked quarantine dir, NOT in live `strategies/`).

---

## ⚠️ Process finding for main (worth a closer look — not a strategy edge)

**The mutation gate's parent-baseline comparison is notional-asymmetric and can emit false PROMOTEs.** `runner/strategy_gen.py::evaluate` runs the candidate at its declared `notional_usd` (the prompt mandates 1000.0) but compares to `_parent_wf_cached(parent)` which runs the parent at its on-disk notional (many live parents = 100.0). Because backtest return% scales with notional, any candidate that merely matches its parent but declares 10× notional "beats" it by ~10× on the `MUTATION_MIN_DELTA_PCT` (median-return) check. This round's breakout_xlk candidate tripped exactly this.

The Sharpe rails (notional-invariant) and the trade-count floor are unaffected — but the **median-return delta gate is corrupted whenever candidate notional ≠ parent notional.** Suggested fix (a hard-rail-adjacent area — flagging, not patching): normalize candidate and parent to the SAME notional before the return-delta comparison (or compare return-per-dollar / use the notional-invariant FP-Sharpe as the promotion ruler). This is why MEMORY's "quote FULL-PERIOD continuous-span Sharpe, not median-of-windows" rule exists — the FP-Sharpe correctly showed all 3 candidates OOS-worse than parent regardless of notional. Recommend main decide whether to patch `evaluate`'s baseline.

---

## Provenance / caveats

- Pre-2022 hourly bars not on free tier; 8 NAMED_WINDOWS span 2022-H1 bear → 2026-recent bull (all 8 returned data). ≥3 distinct OOS regimes satisfied.
- Candidate names are deterministic hashes of (parent, directive) — `breakout_xlk__mut_232050` is the SAME pair vetted 2026-06-26; reproduced identically here (good determinism check).
- This report supersedes the auto-generated `TOURNAMENT_ROUND_20260629T205515Z.md` (which shows the uncorrected inflated +3.88% PROMOTE).
