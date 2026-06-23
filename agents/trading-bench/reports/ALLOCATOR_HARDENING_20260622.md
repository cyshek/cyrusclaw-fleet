# ALLOCATOR_BLEND HARDENING STUDY — 2026-06-22

**Subject:** Stress-test of the LIVE `allocator_blend` paper strategy
(`runner/allocator_paper_tracker.py`, `BLEND_NAME="invvol_63d"`,
`VOL_LOOKBACK_DAYS=63`). This protects real capital *before* it is committed.

**Two questions:**
1. Is the 63-day inverse-vol lookback a **robust plateau** or an **overfit lucky pick**?
2. How badly does the blend break in a **GLD/TLT haven-failure** scenario (the live tail risk)?

**Script (reproducible from cold cache):**
`strategies_candidates/allocator_blend_hardening/wf_and_havenbreak.py`
**Raw JSON:** `reports/_allocator_hardening_result.json`
**Engine reuse:** calls `_allocator_blend_tests.build_sleeves()` / `blend_portfolio()` /
`annualized_vol()` / `stats_from_returns()` directly; Sharpe via the canonical
`_stats_from_equity` (continuous-span, population stdev, √252 — the same ruler the
promoted blend report used). **No protected/live file modified.**

---

## TL;DR VERDICT

| Question | Verdict | Key numbers |
|---|---|---|
| **Q1 — Is 63d robust?** | **ROBUST** (broad plateau; mild free improvement available) | Full-Sharpe spread over entire 21→252d grid = **0.053** (0.977→1.031). WF-selected (0.986) ≈ static-63d (0.984) ≈ best-static-hindsight lb=84 (0.993), all within **0.01**. |
| **Q2 — Does the blend survive a haven-break?** | **SURVIVES / DEGRADES-GRACEFULLY** | Even with havens fully → cash, blend **S=0.868, DD −23.1%** still beats TQQQ-alone (**S=0.863, DD −34.5%**) on Sharpe AND cuts the drawdown by ~11pp. The edge does not evaporate. |

**Anchor reproduced?** ✅ `invvol_63d` full Sharpe **1.012** / CAGR **15.9%** / maxDD **−23.9%** / OOS **1.142** — matches the promoted 1.014 / 15.9% / −23.9% / 1.147 within rounding (drift = one extra fresh bar, 2026-06-22).

**Actionable flag (do NOT auto-applied — Cyrus's call):** 84d or 126d is *mildly* better than 63d on every axis (full Sharpe +0.016–0.019, ~0.4–0.6pp lower maxDD, comparable/better OOS), and the walk-forward process organically prefers **126d** in 12 of 14 blocks. This is a *plateau-interior* improvement, not a knife-edge — switching 63d→84d is defensible but optional. See §1.3.

---

## 0. Measurement hygiene (bench laws applied)

- **No lookahead:** monthly inv-vol weights computed from sleeve realized vols *strictly through the prior month-open index* (the engine enforces this; the WF layer only ever selects a lookback from PAST in-sample data and applies it FORWARD to the next block).
- **Same path / same window / same cost** for every comparison: common window **2010-02-12 → 2026-06-22 (4,113 trading days)**, 2bps one-way inter-sleeve monthly rebalance cost (intra-sleeve costs already baked into each sleeve's return stream — no double-count). 196 blend rebalances.
- **Sharpe:** continuous-span, population stdev, √252 (`_stats_from_equity`). OOS = frozen-2018 (2019-01-01 → today) quoted alongside full.
- **Engine-equivalence proof:** my haven-break rotation builder (`run_rotation_with_override`) with `override=None` reproduces the validated `_sigimprove_tests.run_sector_rotation` **byte-identically** (max equity diff 0.000e+00, Sharpe 0.9140 both, 122 rebalances, identical holdings log). So the cash-substitution is a clean, honest swap of *only* the held GLD/TLT returns — every other mechanic matches the live engine.

---

## 1. STUDY 1 — Walk-forward / robustness of the 63d lookback

### 1.1 Static lookback sweep (full / IS-2010-2018 / OOS-2019-today)

| Lookback | Full Sharpe | Full CAGR | Full maxDD | IS Sharpe | OOS Sharpe | OOS maxDD | sleeve mix tqqq/rot |
|---:|---:|---:|---:|---:|---:|---:|:--:|
| 21d | 0.977 | 15.1% | −25.8% | 0.858 | 1.107 | −23.2% | 0.35 / 0.65 |
| 42d | 1.007 | 15.8% | −24.0% | 0.896 | 1.128 | −22.4% | 0.35 / 0.65 |
| **63d (LIVE)** | **1.012** | **15.9%** | **−23.9%** | **0.892** | **1.142** | **−21.9%** | **0.35 / 0.65** |
| 84d | 1.028 | 16.3% | −23.3% | 0.921 | 1.144 | −21.6% | 0.35 / 0.65 |
| 126d | **1.031** | 16.4% | −23.5% | 0.936 | 1.134 | −19.7% | 0.35 / 0.65 |
| 189d | 0.990 | 15.7% | −23.7% | 0.918 | 1.067 | −23.7% | 0.36 / 0.64 |
| 252d | 1.001 | 16.0% | −25.2% | 0.935 | 1.072 | −25.2% | 0.35 / 0.65 |

**Plateau-vs-peak diagnostics:**
- Full-Sharpe **range over the ENTIRE grid = 0.053** (min 0.977 @ 21d, max 1.031 @ 126d).
- The **42d → 126d band is a flat plateau**: all four lookbacks land in **[1.007, 1.031]**. 63d (1.012) sits comfortably inside it.
- 63d's neighbors are *not* worse — they're slightly **better** (84d +0.016, 126d +0.019). This is the opposite of an overfit peak (where neighbors collapse).
- The sleeve mix is **near-invariant to lookback** (~35% TQQQ / ~65% rotation for every value 21→252). The inv-vol weighting is dominated by the large, stable vol gap between the wild TQQQ sleeve (~26% ann vol) and the calm rotation sleeve (~14%) — changing the *window* barely moves the *weights*. **This is the structural reason 63d is robust: the choice is nearly a no-op.**

### 1.2 TRUE walk-forward (expanding IS, pick-best-lookback, apply forward)

Expanding in-sample window (≥3yr), choose the lookback with the best IS continuous-Sharpe, apply it to the next ~12-month OOS block, step forward. **14 OOS blocks, span 2013-02-14 → 2026-06-22 (3,357 OOS days).**

| Strategy (same WF span) | Sharpe | CAGR | maxDD | Total ret |
|---|---:|---:|---:|---:|
| **WF-selected (adaptive lookback)** | **0.986** | 15.7% | −23.5% | +594% |
| Static-63d (LIVE config) | 0.984 | 15.5% | −23.9% | +582% |
| Best static lookback in hindsight (lb=84) | 0.993 | 15.8% | −23.3% | +602% |

- **WF-selection beats naive static-63d by +0.002 Sharpe** — i.e. **essentially nothing.** Adaptively re-picking the lookback every year does not help; the choice doesn't matter.
- Even the *hindsight-optimal* single static lookback (84d) beats static-63d by only **+0.009 Sharpe**. The entire dispersion between "do nothing", "adapt every year", and "cheat with hindsight" is **< 0.01 Sharpe**.
- **Walk-forward selection frequency: 126d chosen in 12 of 14 blocks, 252d in 2.** The adaptive process consistently *prefers a longer lookback than 63d* — never once picked 63d or shorter. (It still doesn't matter for the curve, but it's a consistent tell that the longer end of the plateau is marginally preferred.)

**This is the textbook signature of a ROBUST hyperparameter, not an overfit one:** flat neighbors, WF ≈ static, sub-0.01-Sharpe dispersion.

### 1.3 Actionable flag (optional, Cyrus's call — NOT auto-applied)

63d is *not* the single best point on the plateau; **84d and 126d dominate it weakly on every axis**:

| | Full Sharpe | Full maxDD | OOS Sharpe | OOS maxDD |
|---|---:|---:|---:|---:|
| 63d (live) | 1.012 | −23.9% | 1.142 | −21.9% |
| 84d | 1.028 (+0.016) | −23.3% | 1.144 | −21.6% |
| 126d | 1.031 (+0.019) | −23.5% | 1.134 | −19.7% |

Switching the live `VOL_LOOKBACK_DAYS` 63→84 (or 126) would be a *plateau-interior* nudge: it buys a tiny Sharpe bump and a slightly tighter drawdown, the walk-forward organically prefers it, and because it's mid-plateau it carries ~zero overfit risk. **I did not change anything** — flagging for your decision. If you'd rather not touch a working live config for a ~0.02-Sharpe gain, leaving 63d is perfectly defensible (it's inside the plateau). **Either choice is fine; that's the whole point of "robust".**

---

## 2. STUDY 2 — GLD/TLT haven-break stress

The blend's downside protection leans on the rotation sleeve fleeing to GLD/TLT when equities fall. We characterize what happens when that property fails.

### 2.1 What the rotation sleeve ACTUALLY held in 2022 (the real-world haven test)

2022 was the in-sample worst case for the haven thesis (TLT −31%, GLD ~flat, stocks down). Month-by-month rotation top-2 holdings (lookahead-safe, ranked on prior month-end):

| Month | Held | Read |
|---|---|---|
| Jan | SPY, QQQ | still risk-on entering the year |
| **Feb–Jun** | **SPY, GLD** | half-fled: dumped QQQ for GLD, but **kept SPY (a falling equity)** |
| Jul | GLD, TLT | full haven flight (the textbook behavior) — for ONE month |
| Aug | SPY, TLT | partial re-risk |
| Sep–Oct | SPY, QQQ | re-risked into the Q4 bottom |
| Nov–Dec | SPY, GLD | back to half-haven |

**Honest finding: the rotation sleeve did NOT cleanly flee to havens in 2022.** It sat in **SPY + GLD for most of the year** — i.e. it held a falling equity (SPY) paired with a flat haven (GLD), and only reached the full GLD/TLT flight for a single month (July). Momentum rotation is too slow to dodge a grinding, choppy bear like 2022.

### 2.2 2022 sleeve decomposition (the blend still cushioned despite a weak haven)

| 2022 (common window) | Return | maxDD |
|---|---:|---:|
| **Blend (live invvol_63d)** | **−14.4%** | **−19.6%** |
| TQQQ vol-target sleeve alone | −17.8% | −17.8% |
| Rotation sleeve alone | −17.8% | −27.3% |
| (SPX buy&hold 2022, ref) | ≈ −18% | ≈ −24% |

Even though *neither* sleeve had a good 2022 (both ≈ −17.8%) and the haven flight barely fired, **the blend lost LESS than either sleeve (−14.4% vs −17.8%)** and had a **shallower drawdown than the rotation sleeve** (−19.6% vs −27.3%). The mechanism wasn't "havens saved us" — it was that the ~65/35 inverse-vol tilt toward the calmer sleeve plus imperfectly-correlated *daily* paths (the two sleeves' worst days didn't fully coincide) delivered a modest diversification benefit *even with the haven property mostly absent*. That's reassuring: the blend's 2022 cushion did **not** actually depend on havens working.

### 2.3 COUNTERFACTUAL haven-break table (full / OOS)

Three rotation variants, each re-blended with the **identical** TQQQ vol-target sleeve via the **identical** inv-vol-63d weighting, vs the TQQQ sleeve held alone:

- **REAL** — validated rotation (real GLD/TLT returns) — anchor.
- **CASH-SUB** — whenever the rank picks GLD/TLT, those legs earn **T-bill cash** instead of their real return ("havens don't work, best case you're in cash"). *The honest, defensible counterfactual.*
- **EQTY-SYNTH (pessimistic, synthetic)** — picked GLD/TLT legs forced to **track SPY down** ("havens become equity-correlated in the crash"). An explicit pessimistic upper bound on pain — clearly labeled synthetic.
- **TQQQ-ALONE** — the vol-target sleeve with no rotation at all.

| Variant | Full Sharpe | Full CAGR | Full maxDD | OOS Sharpe | OOS maxDD | 2022 ret | 2022 maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **REAL blend (anchor)** | **1.012** | 15.9% | **−23.9%** | **1.142** | −21.9% | −14.4% | −19.6% |
| **CASH-substituted blend** | **0.868** | 12.1% | **−23.1%** | 0.925 | −21.3% | −16.7% | −19.6% |
| EQTY-synth blend (pessimistic) | 0.968 | 17.6% | −29.2% | 1.096 | −29.2% | −18.7% | −21.4% |
| **TQQQ vol-target ALONE** | **0.863** | 20.8% | **−34.5%** | 1.009 | −24.4% | −17.8% | −17.8% |

### 2.4 Reading the haven-break

**The load-bearing comparison is CASH-SUB vs TQQQ-ALONE** (the honest "havens fully fail, does the blend still earn its keep?" test):

- **Full-period Sharpe:** cash-sub blend **0.868** vs TQQQ-alone **0.863** → the blend **still edges TQQQ-alone (+0.005)** even with havens completely neutralized to cash.
- **Full-period maxDD:** cash-sub blend **−23.1%** vs TQQQ-alone **−34.5%** → the blend cuts the worst drawdown by **~11.4pp** even when havens provide zero protection. *This is where the diversification value actually lives.*
- **OOS Sharpe:** here TQQQ-alone (1.009) slightly *beats* the cash-sub blend (0.925) on a risk-adjusted basis — but TQQQ-alone does it with a meaningfully deeper OOS drawdown (−24.4% vs −21.3%) and far higher leverage/CAGR (24.9% vs 13.4%). So even in the regime where the cash-broken blend lags on Sharpe, it's the *lower-risk* book.
- **Cost of a full haven-break:** the blend's full Sharpe drops **1.012 → 0.868 (−0.144)** and CAGR **15.9% → 12.1%** if havens become worthless cash. That's a real haircut — **but the drawdown barely moves (−23.9% → −23.1%)**, and the resulting book is still competitive with (Sharpe) and far safer than (DD) the alternative of just holding the TQQQ sleeve.
- **Pessimistic synthetic (EQTY-SYNTH):** if havens don't just fail but actively *track equities down*, the blend's maxDD blows out to **−29.2%** (vs −23.9% real) and full Sharpe falls to 0.968. Still **not catastrophic** — it remains shallower-drawdown than TQQQ-alone's −34.5% and higher-Sharpe than TQQQ-alone's 0.863. Even the deliberately-pessimistic synthetic doesn't make the blend worse than its own components.

**Q2 verdict: SURVIVES / DEGRADES-GRACEFULLY.** The blend's whole edge does **not** evaporate without working havens. In the honest cash-substitution counterfactual the blend still (a) matches/beats TQQQ-alone on Sharpe and (b) keeps a ~11pp shallower maximum drawdown. The diversification benefit is **primarily drawdown reduction, secondarily Sharpe** — and the drawdown benefit is exactly the part that *survives* a haven-break (cash-sub maxDD −23.1% ≈ real −23.9%). What you lose in a haven-break is **CAGR/return** (15.9% → 12.1%), not safety.

---

## 3. Actionable caveats for the LIVE position

1. **63d is safe to keep as-is.** It is mid-plateau, walk-forward-robust, and the lookback choice moves full Sharpe by < 0.02 across the whole sensible grid. No fragility here.
2. **Optional, your call:** nudging `VOL_LOOKBACK_DAYS` 63 → **84 (or 126)** weakly dominates on full Sharpe, OOS, and maxDD, and the walk-forward organically prefers 126d (12/14 blocks). Zero overfit risk (plateau interior). I did **not** change the live config — flag only.
3. **The haven thesis is a return-enhancer, not the survival mechanism.** Stress shows the blend's *drawdown* protection mostly comes from the inverse-vol tilt to the calm sleeve + imperfect daily correlation, which **survive a haven-break**. What a haven-break costs you is **CAGR (~3.8pp)**, not blow-up risk. So if 2022-style "bonds-and-stocks-fall-together" repeats, expect the blend to under-*return* but **not** to fail catastrophically — and it should still beat holding the TQQQ sleeve alone on a risk-adjusted, drawdown-aware basis.
4. **Known live behavior to expect:** momentum rotation is slow — in a choppy grinding bear it will likely sit in SPY+GLD (half-haven) rather than cleanly flee to GLD/TLT, as it did for most of 2022. Don't expect a clean haven flight; expect a partial cushion.

---

## 4. Reproduce

```bash
cd /home/azureuser/.openclaw/agents/trading-bench/workspace
set -a && source .env && set +a
python3 strategies_candidates/allocator_blend_hardening/wf_and_havenbreak.py
# -> reports/_allocator_hardening_result.json  (+ console tables)
```

Cold-cache safe (re-fetches via `daily_bars_cache`); ~2–3 min runtime. Anchor self-checks against the promoted 1.014/−23.9% headline and prints a MISMATCH warning if it ever drifts > 0.03 Sharpe / 1pp DD.
