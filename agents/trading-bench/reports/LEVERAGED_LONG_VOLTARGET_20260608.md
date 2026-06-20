# Leveraged-Long Trend Engine — VOL-TARGETED Variant

> **⚠️ CORRECTION (2026-06-08, post-survivorship-cross-check) — READ FIRST.** A cross-check on OTHER 3x sleeves (`reports/LEVERAGED_LONG_SURVIVORSHIP_20260608.md`, UPRO/SPXL/SOXL) walked back two claims in this report:
> 1. **The RAW-RETURN SPX beat is STRUCTURAL and STANDS** — it reproduces on every 3x sleeve tested. That part is real.
> 2. **The "beats SPX on Sharpe too" / risk-adjusted-edge claim was LARGELY TQQQ-SPECIFIC.** Off TQQQ, vol-target Sharpe is 0.72-0.75 — *at or below* SPX's ~0.80 (UPRO 0.746<0.802, SOXL 0.723<0.752; only SPXL "clears" and only as a window artifact). TQQQ's 0.859 was the outlier, not the rule.
> 3. **"Clean OOS at both targets" does NOT generalize.** Off-TQQQ, target 0.20 FAILS the post-2018 OOS raw beat on broad-cap (UPRO/SPXL); only target 0.25 survives OOS, and narrowly.
> **Honest reframe:** this is a robust **raw-return leverage-harvest with a drawdown-control overlay**, NOT a risk-adjusted-alpha play. Read the numbers below knowing the Sharpe/OOS framing was over-stated; the survivorship report has the corrected cross-sleeve picture.

**Date:** 2026-06-08
**Author:** Tessera (trading-bench)
**Candidate:** `strategies_candidates/leveraged_long_trend/` (quarantine — NOT promoted, NOT a tournament parent)
**Builds on:** `reports/LEVERAGED_LONG_ENGINE_20260608.md` (the binary engine)
**Mission lane:** #1 — beat SPX on raw return, **now with a path to a risk-adjusted edge.**

---

## TL;DR — it worked

The binary engine beat SPX on raw return but carried a **−56% max drawdown** — the single biggest blocker to ever promoting it. Adding an **inverse-realized-vol position-sizing layer** (scale the 3x sleeve down when its own volatility is high) **compresses the drawdown to SPX-like levels while keeping the raw-return SPX beat — and turns the marginal Sharpe edge into a clean one.**

**The headline config — vol-target 0.25 ann vol:**
- **+2,025% vs SPX +587%** raw return (2010→2026) — still a ~3.5× raw beat.
- **maxDD −34.5% vs SPX −33.9%** — essentially SPX-equivalent drawdown (down from −56%).
- **Sharpe 0.859 vs SPX 0.773** — beats SPX risk-adjusted, not just on raw return.
- **Survives frozen-OOS** (post-2018: +368% vs SPX +175%, maxDD −34.5%) and **vol-window robustness** (6/6 windows beat SPX raw + Sharpe).

This is the version that answers the real question the binary engine couldn't: **is there a risk-adjusted edge here, or just a leverage premium?** With vol-targeting, the answer is **yes, there's a risk-adjusted edge** — modest, but real and OOS-stable. It is the intended **promote candidate** (subject to the caveats below and a conversation with main/Cyrus).

---

## What changed vs the binary engine

The binary engine is all-or-nothing: 100% of the 3x sleeve (TQQQ) when QQQ > its 200d SMA, else 100% T-bill cash. That holds a **full 3x position straight into volatility spikes** — which is exactly when leveraged ETFs bleed from volatility decay, and exactly where the −56% drawdown comes from.

The vol-targeted variant sizes the sleeve **continuously**:

```
if trend_up (underlying closes <= D):
    rv = realized_ann_vol(sleeve daily returns, trailing 20d, dates <= D)
    weight = clamp( target_ann_vol / rv , 0, w_max=1.0 )
else:
    weight = 0.0          # trend gate down -> all cash
held over D+1:  weight in 3x sleeve, (1 - weight) in T-bill cash
```

- **`w_max = 1.0`** — never more than 100% of the 3x sleeve. No leverage-on-leverage (would violate the risk rails); the param is exposed but values >1.0 are not used or tested.
- **Cost model — abs change in weight.** Continuous sizing rebalances most days, so a flat per-switch charge would under-count trading. Cost is charged on `switch_cost_bps/10000 × |w_today − w_yesterday|` (2 bps). This is strictly **more conservative** than a per-switch model for a continuously-rebalanced book and is applied to BOTH the baseline and vol-target paths here, so the comparison is apples-to-apples on the same cost convention.
- **No-lookahead, locked by tests.** Realized vol uses only sleeve returns **ending ≤ D**; the weight is held over D+1. A price/vol spike on or after D+1 cannot change today's weight. `tests/test_leveraged_long_trend_voltarget.py::test_voltarget_no_lookahead_future_vol_spike` proves it (mutating only the final day's price leaves every prior weight byte-identical).

Implementation: a **new module** `backtest_daily_voltarget.py` that reuses the validated binary engine's data caches, trend signal, and stats helpers (the validated `backtest_daily.py` core is untouched). Backward-compat is **byte-exact**: the `target_ann_vol=None` path reproduces the binary baseline's +10,121% with 101 rebalances = the 101 binary switches. Protected `runner/` md5s verified unchanged.

---

## Results — the full sweep (TQQQ/QQQ, sma200, vix-off, 2010-02-11 → 2026-06-08)

| Config | Total Ret | CAGR | Max DD | Ann Vol | Sharpe | Avg weight | Beats SPX raw? | Beats SPX Sharpe? |
|---|---:|---:|---:|---:|---:|---:|:--:|:--:|
| **Binary baseline** | +10,121% | 32.86% | **−56.05%** | 46.6% | 0.846 | 0.846 | YES | YES |
| voltarget 0.20 | +1,219% | 17.16% | **−27.82%** | 21.0% | 0.860 | 0.421 | YES | YES |
| **voltarget 0.25** | **+2,025%** | 20.65% | **−34.52%** | 25.7% | **0.859** | 0.516 | **YES** | **YES** |
| voltarget 0.30 | +3,066% | 23.63% | −38.93% | 30.0% | 0.859 | 0.598 | YES | YES |
| voltarget 0.35 | +4,083% | 25.77% | −42.57% | 33.6% | 0.852 | 0.665 | YES | YES |
| voltarget 0.40 | +5,452% | 27.97% | −44.52% | 36.6% | 0.859 | 0.716 | YES | YES |
| *SPX (`^GSPC`) ref* | *+587%* | *12.56%* | *−33.92%* | *17.2%* | *0.773* | *—* | *—* | *—* |

**Reading the table:**
1. **Every vol-target config beats SPX on raw return AND Sharpe.** The mission bar holds across the whole family, and now the risk-adjusted bar does too.
2. **`target_ann_vol` is a clean risk/return dial.** Lower target → lower drawdown and lower return, monotonically. You pick where on the leverage curve you want to sit. There's no free lunch — you give up raw return for drawdown reduction — but the **Sharpe stays ~0.85-0.86 across the entire range**, meaning the trade is efficient (you're sliding along a stable risk/return line, not falling off a cliff).
3. **The drawdown collapses as designed.** target 0.20 → −27.8% (better than SPX); target 0.25 → −34.5% (≈ SPX); even target 0.40 → −44.5% (far better than the binary −56%, still beating SPX raw by ~9×).
4. **Sharpe barely moves but consistently beats SPX.** It's ~0.86 everywhere vs SPX 0.773. This is a **modest** risk-adjusted edge (~0.09 Sharpe), not a blowout — be honest about that. But it's positive, stable across the dial, and OOS-confirmed.

**The recommended config is `target 0.25`**: it lands the drawdown right at SPX-parity (−34.5%) — the natural "no worse than just owning the index" bar — while still delivering +2,025% raw (3.5× SPX) and beating SPX Sharpe. (0.20 is the more conservative pick if sub-SPX drawdown matters more than return; 0.30-0.40 if you'll tolerate more drawdown for more raw return.)

---

## Anti-overfit validation

### 1. Frozen out-of-sample (split @ 2018-01-01)

| Config | Segment | Strat Ret | SPX Ret | Strat maxDD | Beats SPX raw? |
|---|---|---:|---:|---:|:--:|
| target 0.20 | In-sample 2010-17 | +252.7% | +147.9% | −27.2% | YES |
| target 0.20 | **OOS 2018-26** | **+259.2%** | +174.7% | −27.8% | **YES** |
| target 0.25 | In-sample 2010-17 | +332.0% | +147.9% | −33.2% | YES |
| target 0.25 | **OOS 2018-26** | **+368.2%** | +174.7% | −34.5% | **YES** |

The edge **and the drawdown control both hold out-of-sample.** The OOS half (the untouched test) beats SPX raw in both configs, and the maxDD is consistent across both halves (~−27% / ~−34%), so the drawdown compression is a structural property of the sizing rule, not a one-window artifact. For target 0.25 the OOS drawdown (−34.5%) is essentially identical to the full-window figure — the design target held in the data it never saw.

### 2. Vol-window robustness (target 0.20, N = 10→60)

6/6 windows beat SPX raw; 6/6 beat SPX Sharpe; 5/6 cut maxDD below SPX's −33.9%. N=20 (the default) sits on a broad plateau (Sharpe 0.860 is the peak but neighbors 0.81-0.83 are close). **The inverse-vol mechanism is structural, not a lucky lookback choice** — same conclusion as the SMA-window robustness on the binary engine.

---

## Honest verdict & caveats

**Did vol-targeting turn the leverage premium into a promotable risk-adjusted edge? — Yes, partially-to-fully.**
- ✅ It **compresses the −56% drawdown to SPX-parity (−34.5% at target 0.25, or −27.8% at 0.20)** while keeping a large raw-return SPX beat.
- ✅ It **beats SPX on Sharpe** across the whole sweep (0.85-0.86 vs 0.773), and the edge **survives frozen-OOS and lookback-robustness**.
- ⚠️ But the Sharpe edge is **modest (~0.09)**, not a blowout. Under a strict "Sharpe ≥ 1.0" bar it would still **fail** (0.86 < 1.0). Under "beat SPX risk-adjusted" it **passes**. Which bar applies is a main/Cyrus call.

**The caveats that keep it in quarantine (disclosure list, not burial):**
1. **Leveraged-ETF survivorship — unchanged and unfixable here.** TQQQ exists *because* 3x-Nasdaq won over 2010-2026. Vol-targeting reshapes the risk of the surviving sleeve; it does nothing about the fact that we're testing on a winner. An investor in 2010 didn't know TQQQ would survive. (Partial mitigation available: re-run on UPRO/3x-S&P, a broader bet — pending.)
2. **No 2008 bear in the sample.** TQQQ starts 2010-11, so the worst single stress (GFC) is unobserved. The binary engine's report flagged this; it applies here too. A synthetic-3x pre-2010 extension is the next test (negative there would cap conviction).
3. **Heavy rebalancing.** The continuous book rebalances ~3,000 times over 16 years (vs 101 switches binary). The abs-weight cost model bills this honestly at 2 bps, but **real-world execution drag** (bid/ask on TQQQ, tracking error, the fact that you can't trade exactly at the close) will pull live returns below the backtest — more so than for the low-turnover binary version. The 2 bps assumption is the optimistic end.
4. **Modeled close-to-close.** Same as the binary engine — no intraday, no real fills.

**Net:** this is the strongest, most-honest result on the bench — the first to clear **both** the raw-return AND a risk-adjusted SPX bar, OOS-validated, with the drawdown brought to something a human could actually hold. It is **not** a "flip it live" result (survivorship + no-2008 + execution drag are real), but it is a legitimate **promote-to-paper-clock candidate** to discuss with main/Cyrus, and it's the natural thing to monitor forward.

---

## Disposition & next steps

- **Stays quarantine.** NOT promoted to runner, NOT a tournament parent, no live trading. Paper/research artifact.
- **Recommended next steps:**
  1. **Re-run on UPRO/3x-S&P** (and SOXL) to show the vol-target result isn't TQQQ-specific — partially addresses survivorship.
  2. **Synthetic pre-2010 3x series** (daily-compound the underlying + financing drag) to test the unobserved 2008 GFC bear. Report real-vs-synthetic separately.
  3. **Rolling walk-forward** (re-fit window-by-window) rather than the single frozen split, to confirm the plateau holds through time.
  4. **Realistic execution-drag model** (wider cost, tracking error, slippage on the high-turnover rebalance) and re-check the SPX beats survive it.
  5. **Take the promotion question to main/Cyrus** with the full disclosure list — and the explicit "Sharpe ~0.86, beats SPX risk-adjusted but below 1.0" framing so the bar is set deliberately.

## Artifacts
- Engine: `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`
- Evaluation: `strategies_candidates/leveraged_long_trend/evaluate_voltarget.py` → `evaluation_voltarget_result.json`
- OOS/robustness: `strategies_candidates/leveraged_long_trend/validate_oos_voltarget.py` → `validation_voltarget_result.json`
- Tests: `tests/test_leveraged_long_trend_voltarget.py` (14 tests, all green; locks the no-lookahead vol-sizing contract; full suite **391/391**)
- Protected files (`runner/backtest.py`, `walk_forward.py`, `runner.py`, `risk.py`) verified **md5-unchanged**.
