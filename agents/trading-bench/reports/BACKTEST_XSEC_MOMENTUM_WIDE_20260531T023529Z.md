# Backtest Report — Universe-Expansion Sensitivity on the PROMOTED 12-1 Cross-Asset Momentum Strategy

**Task:** universe-expansion (wider/more-dispersed basket) sensitivity on the promoted wave-4 winner `xsec_momentum_xa_38d2b2`. EXACT same Jegadeesh-Titman 12-1 cross-sectional momentum logic; vary ONLY the universe + `top_k`. Question: **does more cross-asset dispersion monotonically improve risk-adjusted return, or does it plateau/degrade?**

**Author:** trading-bench backtest-IC subagent (`xsec-momentum-wide`), 2026-05-31 02:35 UTC.
**Promoted parent:** `xsec_momentum_xa_38d2b2` (6-asset cross-asset, K=2). Memo: `reports/PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`. Backtest: `reports/BACKTEST_XSEC_MOMENTUM_XA_20260530T180628Z.md`.
**Candidate created:** `strategies_candidates/xsec_momentum_wide_7c4a1f/` (params = best wide universe, U9_K2).

---

## Verdict (TL;DR)

**DO NOT RE-PROMOTE with a wider basket.** Wider cross-asset dispersion does **NOT** monotonically improve risk-adjusted return — it **plateaus at N=9/K=2 and degrades at N=12**.

- Best wider universe found (**U9_K2**: promoted 6 + IWM/HYG/EEM, K=2) is a **statistical tie** with the promoted 6-asset version: full-period Sharpe **1.05 vs 1.04** (+0.014), **identical** walk-forward median Sharpe (0.487), **identical** 28 WF trades, **identical** 18-19% in-position floor.
- Pushing to **N=12** (add SLV/UUP/TIP) *degrades* every config: FP Sharpe **0.70–0.92**; U12_K3 doubles max drawdown to −4.31%.
- Adding names at the **N/3 rule-of-thumb K** (U9_K3, U12_K4/K5) is *worse* than holding K=2 — the wider basket over-diversifies and dilutes the concentrated momentum bet.

Honest answer: **the cross-asset benefit saturates at ~6 assets / K=2.** The promoted strategy is already at the efficient point on the N-vs-Sharpe curve. A 9-asset re-promotion adds 3 ETFs of operational surface for **zero** measurable edge. **The promoted 6-asset version stands.**

Nuance: U9_K2 *does* clear GATE.md Bar A bullet #5 fast-track (same path the parent was promoted on) — §4. It is *promotable*; it is just *not worth promoting* because it is indistinguishable from the incumbent.

---

## 1. Method

- **Strategy:** byte-identical `decide_xsec` to `xsec_momentum_xa_38d2b2` (verified `diff` clean). 12-month-minus-1-month (252-bar lookback, 21-bar skip) per-symbol total return → rank → long top-K, equal-weight, monthly rebalance, `alpaca_stocks` cost model. Only `basket` and `top_k`/`xsec_basket_size` changed.
- **Harness:** unmodified `runner/backtest_xsec.py` (full-period) + `runner/walk_forward_xsec.py` (8 NAMED_WINDOWS, +400d warmup). md5 verified unchanged pre/post (§7).
- **Full-period span:** the actual contiguous Alpaca cache span **2020-07-27 → 2026-05-28 (1467 bars, ~5.8y)**, same for every config (apples-to-apples).

  > **Data-availability note (honest):** the parent report/memo cite a span starting "2010-01-04"/"2018-11-01". The current `bars_cache` holds history only from **2020-07-27** for every basket leg (SPY alone reaches 2018-11-01). I could not reproduce a pre-2020 span, so my recomputed U6_K2 full-period Sharpe is **1.04** vs the parent report's **1.13** — same strategy, shorter window. This does not affect any conclusion here because *every* config is scored on the identical span. Flagging the parent-report span discrepancy for Tessera/main as a separate data-provenance item.

- **Inception-date constraint:** task warned DBC=2006 etc. is binding. **Within the bench cache it is NOT** — all 12 candidate ETFs (SPY EFA TLT VNQ DBC GLD IWM HYG EEM SLV UUP TIP) have first-bar **2020-07-27** (~1467 bars). No window-skipping; earliest WF window (2022-H1 bear, start ~2021-05 after warmup) has full history for all symbols.

### Universes tested

| Tag | N | Basket | Added vs promoted |
|---|---|---|---|
| **U6** | 6 | SPY EFA TLT VNQ DBC GLD | — (promoted baseline) |
| **U9** | 9 | U6 + IWM HYG EEM | US small-cap, high-yield credit, EM equity |
| **U12** | 12 | U9 + SLV UUP TIP | silver, dollar, inflation-linked bonds |

---

## 2. Comparison table (headline result)

| Config | N | top_k | FP Sharpe | FP Ret % | FP MaxDD % | FP trades | WF medRet % | WF medSharpe | WF pos% | WF BarA#1 |
|---|---|---|---|---|---|---|---|---|---|---|
| **U6_K2 (promoted)** | 6 | 2 | **1.04** | +8.10 | −2.05 | 34 | +0.34 | **0.49** | 62 | FAIL |
| **U9_K2 (best wide)** | 9 | 2 | **1.05** | +7.87 | −2.08 | 44 | +0.37 | **0.49** | 62 | FAIL |
| U9_K3 (N/3 rule) | 9 | 3 | 1.01 | +7.01 | −1.96 | 63 | −0.01 | 0.06 | 50 | FAIL |
| U12_K4 (N/3 rule) | 12 | 4 | 0.92 | +6.14 | −1.79 | 64 | +0.08 | 0.16 | 62 | FAIL |
| U12_K3 | 12 | 3 | 0.73 | +7.92 | −4.31 | 68 | +0.17 | 0.29 | 62 | FAIL |
| U12_K5 | 12 | 5 | 0.70 | +5.83 | −3.10 | 75 | +0.05 | 0.12 | 50 | FAIL |

**Shape of the curve:** Sharpe is **flat from N=6 to N=9 at K=2** (1.04 → 1.05), then **falls monotonically** as you either raise K to the N/3 rule or push to N=12. Every config that obeyed the N/3 rule (U9_K3, U12_K4) underperformed the same-universe K=2.

**Why N/3 stops working:** the 12-1 signal's edge comes from *concentrating* on the top-2 strongest assets. A wider basket gives the ranker more candidates for the best 2 (mildly helpful — U9_K2 ≥ U6_K2 by a hair), but *forcing* it to hold 3-5 names (N/3) drags lower-conviction assets into every basket and Sharpe falls. **On a wider universe, keep K low (2); do not scale K with N.**

---

## 3. Per-regime + per-window detail — best wide universe (U9_K2)

| Window | Regime | Ticks | Ret % | Sharpe | MaxDD % | BH-basket % | Beats BH? | In-Pos % | BarA#1 |
|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | 339 | −0.40 | −0.41 | −1.03 | −1.27 | ✅ | 19 | ❌ |
| 2022-Q3 chop | chop | 338 | −0.38 | −0.44 | −1.01 | −0.79 | ✅ | 19 | ❌ |
| 2023-H1 recovery | bull | 337 | +0.28 | +0.44 | −0.63 | +0.39 | ❌ | 19 | ✅ |
| 2023-Q3 chop | chop | 336 | −0.51 | −0.94 | −0.81 | −0.43 | ❌ | 18 | ❌ |
| 2024-Q2 bull | bull | 337 | **+0.56** | +1.03 | −0.34 | +0.09 | ✅ | 19 | ✅ |
| 2025-Q1 tariff bear | bear | 335 | +0.47 | +0.53 | −0.88 | −0.04 | ✅ | 18 | ✅ |
| 2025-Q3 bull | bull | 336 | +1.13 | +2.84 | −0.20 | +0.56 | ✅ | 18 | ✅ |
| 2026-recent bull | bull | 317 | +0.87 | +0.87 | −0.59 | +0.88 | ❌ | 14 | ✅ |

**Per-regime median (U9_K2):** bull = **+0.71%** · chop = −0.45% · bear = +0.04%
**Aggregate:** median ret +0.37% · 62% positive · 62% beat BH-basket · median Sharpe 0.49 · 28 WF trades.

**vs promoted U6_K2 per-regime:** bull +0.41% · chop −0.45% · bear +0.04%. The **only** material difference: U9's bull median rises (+0.41% → +0.71%) because IWM (2024-Q2) and EEM/GLD (2026-recent) occasionally win the top-2 in bull windows. Chop and bear are **identical** — the strategy picks the same defensive legs (GLD/DBC) there regardless of the wider menu. Net WF medSharpe is unchanged at 0.49 (the per-window-median statistic is dominated by the unchanged chop/bear windows).

**Bar A #1 (25% in-position floor):** still **FAIL**, identical structural reason as the parent — the 18-19% in-position floor is K-invariant and universe-invariant (monthly-fixed-K rotation property, per `PATTERNS.md` #2). Widening did nothing to it, as theory predicts.

### Per-symbol attribution (U9_K2, full period)

| Symbol | Asset class | Buys | Closes | Realized P&L | Final MV | Selected? |
|---|---|---|---|---|---|---|
| SPY | US equity | 6 | 6 | **+$20.66** | $0 | heavily |
| DBC | commodities | 1 | 1 | **+$13.12** | $0 | yes |
| GLD | gold | 6 | 5 | **+$9.21** | $57.82 | heavily |
| EFA | intl equity | 3 | 3 | +$4.40 | $0 | yes |
| **IWM** | **US small-cap (NEW)** | 4 | 4 | **+$3.63** | $0 | **yes** |
| **EEM** | **EM equity (NEW)** | 2 | 1 | **+$1.71** | $56.47 | **yes (held)** |
| VNQ | REITs | 1 | 1 | −$6.66 | $0 | rarely |
| **HYG** | **high-yield (NEW)** | 0 | 0 | $0.00 | $0 | **never** |
| TLT | long bonds | 0 | 0 | $0.00 | $0 | never |

**The three new legs split the difference:** IWM and EEM *were* selected and added modest positive P&L (+$3.63, +$1.71); HYG (like TLT in the parent) was **never** picked — its 12-1 momentum never beat equities/gold this window. The wider basket genuinely *uses* 2 of 3 new names, but their contribution is small enough that net full-period Sharpe is a tie. Consistent with the parent's "effectively SPY + GLD with occasional tourism" — widening just adds two more occasional-tourism destinations.

---

## 4. Bar A scorecard — best wide universe (U9_K2)

Scored on the **same GATE.md Bar A bullet #5 fast-track** the parent was promoted on (#1 and #3 bypassed per clause (d); the parent fails #1's in-position floor structurally, and so does this).

| Bar A bullet | Requirement | U9_K2 result | Verdict |
|---|---|---|---|
| #5(a) | FP Sharpe ≥ 1.0 | **1.049** | ✅ PASS |
| #5(b) | FP MaxDD ≤ $200 abs | **−$20.78** (−2.08%) | ✅ PASS (10% of ceiling) |
| #5(c) | every window (V1 OR V2) AND no catastrophe | **8/8 windows pass** | ✅ PASS |
| #2 | held-out final regime (2026-recent bull) positive | +0.87% | ✅ PASS |
| #4 | trade count ≥ 30 | **44** | ✅ PASS |
| #5(old) | MaxDD ≤ 30% | −2.08% | ✅ PASS |
| #6 | code review / AST | identical to promoted parent (human-authored) | ✅ PASS |
| #7 | smoke `tick.sh --candidate` rc=0 | ✅ rc=0, `{EEM=buy, DBC=buy}`, 2700 bars, 3.05s | ✅ PASS |
| #1 | per-window 25% in-position floor | 18-19% (structural, K-invariant) | ❌ FAIL → bypassed by #5(d) |

**#5(c) per-window detail:**

| Window | strat r% | BH-basket r% | V1 | V2 | catastrophe | pass |
|---|---|---|---|---|---|---|
| 2022-H1 bear | −0.40 | −1.27 | ✅ | ✅ | no | ✅ |
| 2022-Q3 chop | −0.38 | −0.79 | ✅ | ✅ | no | ✅ |
| 2023-H1 recovery | +0.28 | +0.39 | ✅ | ✅ | no | ✅ |
| 2023-Q3 chop | −0.51 | −0.43 | ✅ | ✅ | no | ✅ |
| 2024-Q2 bull | +0.56 | +0.09 | ✅ | ✅ | no | ✅ |
| 2025-Q1 tariff bear | +0.47 | −0.04 | ✅ | ✅ | no | ✅ |
| 2025-Q3 bull | +1.13 | +0.56 | ✅ | ✅ | no | ✅ |
| 2026-recent bull | +0.87 | +0.88 | ✅ | ✅ | no | ✅ |

**Bar A #5 overall: U9_K2 PASSES the fast-track** — exactly like the parent. So the wider universe is *gate-promotable*. **The reason NOT to re-promote is not a gate failure — it's that the candidate is statistically indistinguishable from the incumbent** (§5).

---

## 5. Honest discussion — does wider beat the promoted 6-asset version?

**No, not meaningfully.** Head-to-head on the identical 2020-07-27→2026-05-28 span:

| Metric | U6_K2 (promoted) | U9_K2 (best wide) | Δ | Material? |
|---|---|---|---|---|
| Full-period Sharpe | 1.035 | 1.049 | **+0.014** | No — within noise |
| Full-period return | +8.10% | +7.87% | −0.23pp | No |
| Full-period MaxDD | −2.05% | −2.08% | −0.03pp | No |
| WF median return | +0.34% | +0.37% | +0.03pp | No |
| WF median Sharpe | 0.487 | 0.487 | **0.000** | No — identical |
| WF % positive | 62% | 62% | 0 | No |
| WF trades | 28 | 28 | 0 | No |
| In-position floor | 18.5% | 18.5% | 0 | No — structural |
| Bar A #5 fast-track | PASS | PASS | tie | — |

**A +0.014 full-period Sharpe gain on a 5.8-year run, with identical walk-forward statistics, is noise.** It does not justify the operational cost of re-promotion: 3 more ETFs to wire into the (not-yet-built) `runner_xsec.py`, 3 more legs to monitor, 3 more feeds to keep healthy, and a re-run of the full promotion/audit cycle. The promoted 6-asset basket captures essentially all available cross-asset momentum edge under bench constraints.

**Why the saturation happens (mechanistic):**
1. The 12-1 signal concentrates into the top-2. With 6 names spanning 4 asset classes, the top-2 are usually already genuinely uncorrelated (SPY+GLD, EFA+DBC). The new names IWM/HYG/EEM are *correlated to legs already present* (IWM≈0.9β SPY, EEM≈0.85β EFA, HYG≈equity-credit-β). They rarely produce a *more dispersed* top-2 than U6 already had.
2. N=12 adds SLV (≈GLD), UUP (dollar — independent but rarely selected), TIP (≈TLT). More *redundant* candidates, not more *independent* ones → top-2 doesn't improve, and the larger universe adds basket-clamp churn and drawdown noise (U12_K3 DD −4.31%).
3. **Dispersion that matters is asset-CLASS dispersion, not asset COUNT.** U6 already spans 6 distinct classes. U9/U12 mostly add *more instruments within classes already represented*; the marginal genuinely-new class (EM, HY-credit, dollar, TIPS) was either not selected (HYG, TLT, UUP) or duplicated an existing exposure (IWM↔SPY, SLV↔GLD, TIP↔TLT).

**Reusable finding:** for cross-asset 12-1 momentum under these bench constraints, **breadth helps only up to ~one instrument per distinct asset class (~6); beyond that you add correlated redundancy, and the right knob is K (keep low, ~2), not N.** Candidate `PATTERNS.md` datum (n=1; per Pattern #2, hold for a 2nd within-class confirmation — e.g., same N-sweep on low-vol or sector-rotation — before durable framing).

### What I did NOT do (per constraints)
- Did NOT add a SPY regime overlay (`PATTERNS.md` #1 — parent already refuted it for cross-asset; re-testing would be redundant).
- Did NOT modify the promoted strategy, any runner, GATE.md, or risk/safety files (md5-verified §7).
- Did NOT write to `strategies/`. Candidate lives in `strategies_candidates/` only.

---

## 6. Recommendation

1. **Keep the promoted 6-asset `xsec_momentum_xa_38d2b2` as-is. Do NOT re-promote a wider basket.** The cross-asset momentum edge saturates at ~6 assets / K=2; wider is a tie at best (N=9), a degradation at worst (N=12).
2. **If a marginally-wider variant is ever wanted for data-feed-diversification reasons** (not edge), U9_K2 is the only wide config that ties the incumbent AND clears Bar A #5 — but the case for it is operational, not performance.
3. **Record the saturation finding as a candidate PATTERNS.md datum** (breadth saturates at ~1 instrument/asset-class; tune K not N). Hold for a 2nd within-class confirmation per Pattern #2.
4. **Data-provenance flag for Tessera/main:** the parent report's full-period span ("2010"/"2018" start) is not reproducible from the current `bars_cache` (all basket ETFs start 2020-07-27). Parent FP Sharpe 1.13 vs my recomputed 1.04 is a window-length artifact, not a regression. Worth confirming what data the parent run used.

---

## 7. Verification & file integrity

**Protected files md5 — unchanged pre/post:**
```
runner/runner.py            4be185e4bdcb6f432d99b71b21a4859c  UNCHANGED
runner/backtest.py          e1a64a4fc02be2aaf0b159cf7152a72d  UNCHANGED
runner/backtest_xsec.py     d94e823b4bb6b330b505ca9129026fc0  UNCHANGED
runner/walk_forward_xsec.py 2d416571fcbff20a018284d198d950ea  UNCHANGED
runner/risk.py              2e471e0446f73f1e0cc5a3ccb5f238da  UNCHANGED
runner/safety_backstop.py   bccefabab4403b4226ff5caa4c8db3b8  UNCHANGED
GATE.md                     41c64c4e00698b5c8a613d78f0b7ebf5  UNCHANGED
```
**Promoted strategy in `strategies/` — NOT touched** (read-only this run).

**Test suite:** `python3 -m pytest tests/ -q` → **213 passed** in 22.2s.

**Smoke:** `./tick.sh --candidate xsec_momentum_wide_7c4a1f` → `rc=0`, `SMOKE OK xsec`, basket=9, actions `{EEM=buy, DBC=buy}`, 2700 bars, 3.05s.

**Driver run (stderr):**
```
U6_K2_promoted   N=6 K=2  | FP Sharpe=1.04 ret=+8.10% DD=-2.05% tr=34 | WF medRet=+0.34% medSh=+0.49 pos=62% BarA1=F FIT=F
U9_K3            N=9 K=3  | FP Sharpe=1.01 ret=+7.01% DD=-1.96% tr=63 | WF medRet=-0.01% medSh=+0.06 pos=50% BarA1=F FIT=F
U9_K2            N=9 K=2  | FP Sharpe=1.05 ret=+7.87% DD=-2.08% tr=44 | WF medRet=+0.37% medSh=+0.49 pos=62% BarA1=F FIT=F
U12_K4           N=12 K=4 | FP Sharpe=0.92 ret=+6.14% DD=-1.79% tr=64 | WF medRet=+0.08% medSh=+0.16 pos=62% BarA1=F FIT=F
U12_K3           N=12 K=3 | FP Sharpe=0.73 ret=+7.92% DD=-4.31% tr=68 | WF medRet=+0.17% medSh=+0.29 pos=62% BarA1=F FIT=F
U12_K5           N=12 K=5 | FP Sharpe=0.70 ret=+5.83% DD=-3.10% tr=75 | WF medRet=+0.05% medSh=+0.12 pos=50% BarA1=F FIT=F
```

## 8. Files created / modified

| Path | Status | Purpose |
|---|---|---|
| `strategies_candidates/xsec_momentum_wide_7c4a1f/strategy.py` | NEW | Byte-identical `decide_xsec` to promoted parent (copied). |
| `strategies_candidates/xsec_momentum_wide_7c4a1f/params.json` | NEW | Best wide universe found (U9_K2: 9-asset, K=2). Verdict embedded: do-not-re-promote. |
| `strategies_candidates/xsec_momentum_wide_7c4a1f/__init__.py` | NEW | Package marker (empty). |
| `_run_xsec_momentum_wide_wf.py` | NEW | Driver: 6 (universe × K) configs, full-period + walk-forward. Consumer-only. |
| `reports/BACKTEST_XSEC_MOMENTUM_WIDE_20260531T023529Z.md` | NEW | This report. |
| `/tmp/xsec_wide_wf.json` | TEMP | Raw driver output. |
| `runner/*`, `GATE.md`, `strategies/xsec_momentum_xa_38d2b2/*` | UNCHANGED | md5-verified §7. Not touched. |

---

**Final verdict: DO NOT RE-PROMOTE.** Wider cross-asset dispersion plateaus at N=9/K=2 (statistical tie with the promoted 6-asset version) and degrades at N=12. The cross-asset momentum edge saturates at ~6 assets / K=2; the right tuning knob beyond that is K (keep low), not N. The promoted `xsec_momentum_xa_38d2b2` stands.