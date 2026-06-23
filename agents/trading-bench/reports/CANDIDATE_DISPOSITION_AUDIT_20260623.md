# Candidate Disposition Audit — 16 candidate dirs

**Date:** 2026-06-23 · **Type:** READ-ONLY audit (no code/promotion/cron changes) · **Author:** trading-bench subagent `cand_disposition_audit`
**Question:** Does any `strategies_candidates/` strategy have SOLID backtest numbers (beats SPX on raw return AND continuous-span Sharpe, OOS-frozen-2018, net of realistic cost) but NO disposition on file (promote / close / needs-more-data)?

**MISSION bar:** beat SPX on RAW cumulative return AND continuous-span Sharpe, OOS-frozen at 2018, net of realistic costs, on a continuous (non-cherry-picked) span. A clean "close" is a valid, valuable verdict.

---

## BOTTOM LINE

**⭐ ZERO missing-verdict-but-solid candidates. The backlog is CLEAN.**

Every one of the 16 dirs is either (a) already PROMOTED/LIVE, (b) carries a verdict report on disk and/or in MEMORY.md, or (c) is a correctly-CLOSED clean negative with a documented killer number. **The only candidate with numbers that actually clear the dual bar (raw return + OOS Sharpe vs SPX) is `leveraged_long_trend` — and it is ALREADY PROMOTED** (live `leveraged_long_trend_paper` + the TQQQ sleeve inside the live allocator_blend). Nothing promotable is sitting un-dispositioned.

**Bucket counts (16 total):**
| Bucket | Count | Dirs |
|---|---|---|
| PROMOTED/LIVE | 2 | leveraged_long_trend, allocator_blend_hardening |
| DECIDED (verdict on file / in MEMORY.md) | 6 | overnight_drift, macro_regime_allocator, credit_stress, fx_lane, xsec_momentum_revival_b16, sma_crossover_qqq_macrogate |
| CLOSE (numbers in, miss the bar / artifact) | 7 | intraday_meanrev, smallcap_momentum, pead_real, pead_neutral, pead_smallmid, pead_finnhub, macro_regime_long |
| DECIDED — Tier-2 floor-fail (in MEMORY.md) | 1 | regime_gated_xsec_momentum_xa_c87bbf |
| NEEDS-MORE-DATA | 0 | — |
| ⭐ MISSING-VERDICT-BUT-SOLID | **0** | **none** |

---

## Summary table

| Candidate | Bucket | Key number | Where decided / why |
|---|---|---|---|
| **leveraged_long_trend** | PROMOTED/LIVE | **OOS Sharpe 0.855 vs SPX 0.722; full +2078.6% vs SPX +592.8%; OOS +379.9% vs SPX +177.1%; maxDD −34.5%; 2bps/side; n=4114** | The promoted TQQQ vol-target sleeve. Live as `leveraged_long_trend_paper` + the TQQQ leg of live allocator_blend. Hardening sweep (`hardening_param_sweep_result.json`) re-confirms the live config (sma200/volw20/tgt0.25). Overlay experiments in this dir (skew/vixterm/breadth) all separately CLOSED. **Clears the bar — already promoted, not missing.** |
| **allocator_blend_hardening** | PROMOTED/LIVE | Robustness study on the live blend (Sharpe 1.01 full / 1.14 OOS anchor) | Hardening/walk-forward + GLD/TLT haven-break stress on the already-PROMOTED, paper-live allocator_blend. Report `reports/ALLOCATOR_HARDENING_20260622.md` + in `GO_LIVE_DECISION_PACKET.md`. Measurement script, not a new strategy. |
| **overnight_drift** | DECIDED | Breakeven ~0.5–1.4 bps/side; at realistic 5 bps/side CAGR −11% to −15% | `reports/OVERNIGHT_DRIFT_VERDICT_20260622.md` → **CLOSE** (real gross anomaly, untradeable net of its own daily turnover; loses B&H on ret AND Sharpe IS+OOS). MEMORY.md "overnight-drift closed." |
| **macro_regime_allocator** | DECIDED | OOS ret +258.6% (lag+1) < blend +276.2%; OOS Sharpe 1.14→1.19-1.23 | `reports/MACRO_REGIME_VERDICT_20260622.md` → **TAIL-HEDGE-ONLY, not promoted**. Improves DD/Sharpe but return-neutrality is knife-edge on NFCI publication lag. Flagged to Cyrus as optional hedge. |
| **credit_stress** | DECIDED | Every config LOSES SPY-BH; beats in only 8–25% of 12 WF windows; best Sharpe 0.86 but closet-long (corr 0.65–0.85) | `reports/CREDIT_STRESS_20260609.md` → **CLOSE as return engine** (crisis-hedge value only). MEMORY.md "credit-spread/FRED (no edge)." |
| **fx_lane** | DECIDED | 0/5 series beat SPX raw, 0/5 reach Sharpe>0.8; best OOS Sharpe 0.39 (USDJPY) vs SPX 0.72; best full +32.7% vs SPX +421% | `reports/FX_LANE_20260621.md` → **CLOSE** (3rd concordant FX evaluation). MEMORY.md "FX lane closed, 3x concordant." No-leverage FX long/flat structurally can't out-return a 16.8%-vol equity index. |
| **xsec_momentum_revival_b16** | DECIDED | 16-asset 12-1 @ $1000: best OOS Sharpe (K=3) 0.635 vs SPX 0.805; loses SPX raw in EVERY window/K | `reports/XSEC_MOMENTUM_REVIVAL_20260622.md` → **CLOSE**. MEMORY.md "price-based xsec momentum closed, confirmed 06-22." Broadening universe + $1000 made it WORSE (rotation churn, not diversifying alpha). |
| **sma_crossover_qqq_macrogate** | DECIDED | Quarantine candidate; orthogonal-macro entry gate adds no gate-clearing edge | `reports/MACROGATE_V2_20260608.md` + MEMORY.md (06-08): "candidate stays quarantine, NOT promoted, NOT a parent." |
| **regime_gated_xsec_momentum_xa_c87bbf** | DECIDED | Phase-1 floor FAIL (same Bar-A fails as parent; LLM gate hurts under SPY-50 stand-in) | `reports/TIER2_REGIME_GATED_XSEC_PHASE1_20260531...md` + MEMORY.md (05-31): Phase-2 LLM replay judged marginal/not-worth-$9. Parent itself was DEMOTED (`DEMOTE_xsec_momentum_xa_38d2b2`). |
| **intraday_meanrev** | CLOSE | OOS Sharpe 0.859 BUT OOS CAGR 3.65% (<8%); edge → 0 at 4bps (Sharpe 0.004); train Sharpe −2.877 (backfit); OOS driven entirely by 2022 | `GATE_RESULT.md` → REJECT. Edge = transaction cost; one-off 2022 regime fluke, negative in-sample. |
| **smallcap_momentum** | CLOSE | OOS Sharpe 0.28 vs SPY 0.80; OOS +30.7% vs SPY +212.5% | `GATE_RESULT.md` → REJECT. 6-ETF cross-sectional momentum has low statistical power; catastrophic OOS underperformance. |
| **pead_real** | CLOSE | OOS Sharpe 0.583 (<0.7); OOS CAGR 10.83% vs SPY 14.95%; best v2 combo OOS Sharpe 0.498 | `GATE_RESULT.md` + `GATE_RESULT_V2.md` → REJECT. Signal real (56.3% win on 21K trades) but =diversified long-equity fund below index; SPY gate hurts. MEMORY.md "PEAD closed." |
| **pead_neutral** | CLOSE | OOS Sharpe 0.226; OOS CAGR 2.02%; short side OOS Sharpe −0.285 (drag) | `GATE_RESULT.md` → REJECT. Beta-neutral construction destroys the long-only alpha (short book loses money). MEMORY.md "beta-hedged loses edge." |
| **pead_smallmid** | CLOSE | Best unhedged OOS s>15 H10 Sharpe 0.757 BUT beta 0.876 (levered long, not alpha); hedged collapses to 0.394 | `backtest_results.json` + `sweep_results.json`. The single >0.7 cell is a high-beta artifact; every dollar-neutral (true-alpha) variant is Sharpe ≤0.39 / negative. Same closed-lane conclusion. |
| **pead_finnhub** | CLOSE (detour) | Data-source smoke test only — no backtest | `SMOKE_RESULT.md` → "DETOUR: use Nasdaq calendar." Pure data-feasibility scout; the actual PEAD backtests (pead_real/neutral/smallmid) all closed. No standalone strategy here. |
| **macro_regime_long** | CLOSE | Median window return +0.00%, only 25% of windows positive, 7 trades total on 1Hour QQQ | `reports/_macro_regime_long_eval.json` → gate FAIL. v1 of orthogonal-macro experiment; sat in cash through 2023-24 QT bull (superseded by macrogate v2, also not promoted). |

---

## ⭐ MISSING-VERDICT-BUT-SOLID candidates

**NONE.**

The audit specifically hunted for a strategy whose numbers plausibly clear the dual bar (raw return + continuous-span OOS Sharpe vs SPX, net of cost) yet has no promote/close/needs-more-data decision on file. There is no such candidate.

The closest things to "solid numbers" in the tree are:
1. **leveraged_long_trend** — genuinely clears the bar (OOS Sharpe 0.855 > SPX 0.722; +2078.6% full / +379.9% OOS, both crushing SPX). **But it is already PROMOTED and paper-live** — it has the strongest disposition possible. Not missing.
2. **pead_smallmid OOS s>15 H10 (Sharpe 0.757)** and **intraday_meanrev V1 (OOS Sharpe 0.859)** — both *look* tempting on a single Sharpe number, but each is correctly disqualified, not un-decided:
   - pead_smallmid's 0.757 carries **beta 0.876** → it's a leveraged long-equity book, not alpha; the true-alpha (dollar-neutral) version is Sharpe 0.394, and it does NOT beat SPX raw return on a clean continuous span. Guilty-until-proven thin-cell beauty → correctly closed.
   - intraday_meanrev's 0.859 **evaporates to Sharpe 0.004 at 4bps**, has a **−2.877 in-sample Sharpe** (backfit tell), and its entire OOS edge is the one-off 2022 bear year. Correctly REJECTed in its GATE_RESULT.

No data is "inconclusive / needs more" — every lane that ran reached a clean verdict; the unfinished-looking dirs (pead_finnhub = data scout; macro_regime_long = superseded v1) are also resolved.

---

## Method / evidence basis

- Read every result JSON, `GATE_RESULT*.md`, `SMOKE_RESULT.md`, and skimmed each main backtest `.py` header for what-it-tests + obvious lookahead.
- Cross-referenced against the 9 named existing verdict reports + MEMORY.md closed-lane ledger + the `memory/2026-06-23.md` post-market review (which independently lists the same "no PROMOTE flags" disposition status).
- Anti-lookahead spot-checks confirmed in-dir (NFCI first-release/ALFRED vintage handling in credit_stress + macro_regime_allocator; macro release-lag in the macro/macrogate dirs; D+1 adjclose-both-legs fix in pead_real). No disqualifying leakage found that wasn't already caught by the owning report.
- Numbers cited are pulled from the JSONs/reports, not estimated.

*No strategy code modified, nothing promoted, crontab untouched. Only this report written.*
