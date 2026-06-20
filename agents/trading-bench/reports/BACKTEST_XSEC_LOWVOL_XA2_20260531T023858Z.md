# Backtest Report — Cross-Sectional Low-Volatility Anomaly (AHXZ 2006), Cross-Asset — WAVE-5 push past the wave-4 REJECT

**Candidate:** `xsec_lowvol_xa2_440761`
**Parent:** `xsec_lowvol_xa_38a206` (wave-4, FP Sharpe 0.97 K=3 / 0.76 K=2-regime — REJECTED).
**Archetype:** #3 (Ang-Hodrick-Xing-Zhang low-vol) on a cross-asset ETF basket.
**Author:** trading-bench (subagent, 2026-05-31 02:38 UTC).
**Mandate:** push the low-vol cross-asset anomaly past the wave-4 REJECT; specifically try to clear **Bar A bullet #5 fast-track** (FP Sharpe ≥1.0, MaxDD ≤$200, every window passes V1/V2 with no catastrophe). Verdict is a **recommendation only** — no promote (promotion is main's call).

---

## TL;DR verdict — **RECOMMEND PROMOTE-ELIGIBLE via Bar A #5** (best variant clears all three clauses), but LOW CONVICTION — see §5

The single highest-leverage change was **swapping TLT (20y+ Treasury) → SHY (1-3y Treasury)** in the wave-4 universe and keeping **equal-weight at the tightest cut K=2**. That variant:

| Bar A #5 clause | Requirement | Result | Verdict |
|---|---|---|---|
| (a) | Full-period Sharpe ≥ 1.0 | **1.23** | ✅ |
| (b) | Full-period MaxDD ≤ $200 | **$13.96** (-1.36%) | ✅ |
| (c) | Every window passes V1 OR V2 **AND** no catastrophe | **8/8 pass, 0 catastrophes** | ✅ |
| #2 | Held-out final regime (2026-recent bull) positive | **+0.27%** | ✅ |
| #4 | Trade count ≥ 30 | **54** full-period | ✅ |
| #6 | Code review (security AST checks) | imports/forbidden/loops/docstring all clean | ✅ (see §7) |
| #7 | `./tick.sh --candidate` rc=0 | **rc=0**, actions `{SHY=buy, SPY=buy}` | ✅ |

**This clears the wave-4 bar that the parent missed** (parent K=3 hit Sharpe 0.97 < 1.0 AND had a 2022-Q3 catastrophe; parent K=2 hit Sharpe 0.76).

**But read §5 before promoting.** The win has an honest structural caveat: at K=2 on a 6-asset basket, **SHY is held 100% of months** — the strategy is effectively "always park 50% in 1-3y Treasuries, rotate the other 50% into the lowest-vol risk asset." That's a real, defensible portfolio (and it's *why* the Sharpe is high — half the book sits in a low-vol anchor), but it's closer to a **50/50 cash-anchor + low-vol-risk-rotation** than a pure 2-leg AHXZ rotation. Whether that counts as "the low-vol anomaly working" or "a barbell that games a vol-ranked Sharpe metric" is a judgment call I flag explicitly for main.

---

## 1. What I tried — levers and the critical negative finding

The brief named three levers. I tested all three. **One of them (universe expansion) actively backfired, and that is itself the most important finding in this report.**

### Lever (a) — Universe expansion: **BACKFIRES badly. Do not do the naive version.**

I built an expanded 10-asset universe `[SPY, EFA, TLT, IEF, SHY, LQD, USMV, VNQ, DBC, GLD]` adding the obvious low-vol candidates (IEF 7-10y UST, SHY 1-3y UST, LQD IG credit, USMV min-vol equity). **Every expanded-universe variant collapsed to a NEGATIVE Sharpe** (-0.37 to -0.74) with only ~17 trades over 5.8 years.

Holding-frequency replay shows why:

| Symbol | Expanded-univ K=3 holding freq |
|---|---|
| SHY (1-3y UST) | **100.0%** |
| IEF (7-10y UST) | **98.5%** |
| LQD (IG credit) | **88.1%** |
| USMV | 13.4% |
| everything else | 0% |

The strategy parked permanently in `SHY + IEF + LQD` and never rotated. **This is the deep lesson: the low-vol anomaly is an *intra-asset-class* effect (low-vol stocks beat high-vol stocks). Applied *across* asset classes, "lowest realized volatility" simply means "most cash-like instrument," and cash-like instruments have low return by construction.** A vol ranking across asset classes is a duration/risk-of-loss sort, not an alpha sort. Adding genuinely-low-vol assets doesn't strengthen the anomaly — it lets the ranking discover that short Treasuries are quiet and sit there earning ~nothing while paying spread cost. This is the wave-4 author's "always own bonds" worry, fully realized and then some.

**Implication:** the cross-asset low-vol basket only works when the universe is curated to *force dispersion among risk assets* — you cannot let it choose between a risk asset and a cash proxy, because it will always pick cash.

### Lever (a′) — the **single SHY-for-TLT swap** (the one that worked)

Instead of *adding* low-vol assets, I *replaced* the one broken leg. The wave-4 report's per-symbol attribution showed TLT bled **-$15.18** (held 50.7% of months, lost on 4 of 5 trades) because long-duration Treasuries got crushed in the 2022-23 rate-hike cycle while *still scoring low realized vol* — its low-vol score was a duration-risk illusion. Swapping `TLT → SHY` (1-3y, minimal duration risk) keeps a genuinely stable defensive anchor without the bleed, while the other 5 legs (SPY/EFA/VNQ/DBC/GLD) remain genuine risk assets competing for the bottom-K. This is the "right dose": one swap, not a flood.

### Lever (b) — Inverse-vol weighting: **HURTS on this universe.**

Inverse-vol sizing (`weight_mode="inv_vol"`, weight each leg by 1/realized-vol) was a clean idea — low-vol both in selection *and* sizing — but it **lowered Sharpe everywhere** (wave-4 univ: 0.95→0.92 at K=3; and catastrophically on the SHY universe: 1.24→-0.22). Reason: inverse-vol over-weights the calmest leg, which after the SHY swap is *always SHY*, dragging the whole book toward cash. Equal-weight keeps the risk-asset leg sized enough to actually earn. **Inverse-vol weighting and a cash-like anchor asset are mutually destructive.** Equal-weight wins.

### Lever (c) — Vol-lookback sensitivity (21 / 42 / 60 / 63 / 90 / 126 day): robust plateau at the short end.

On the winning SHY universe, FP Sharpe ≥1.0 holds for **N ∈ {42, 60, 63}** at K=2; longer lookbacks (90, 126) decay to ~0.87-0.91 (signal too slow to react). N=60 (the AHXZ ~3-month default, same as the parent) is the peak (1.23) and avoids the appearance of lookback-tuning.

---

## 2. Variant comparison table (full sweep)

All full-period, single contiguous backtest, 2018-11 → 2026-05 (SPY span; other legs from 2020-07), $1000 start, alpaca_stocks cost (2bps). `(c)` = passes Bar A #5 clause-(c) on all 8 windows.

| Variant | Universe | K | N | Weight | FP Sharpe | FP Ret | MaxDD$ | Trades | (c) clean? | #5? |
|---|---|---|---|---|---|---|---|---|---|---|
| **V0 (wave-4 repro)** | wave-4 | 3 | 60 | equal | 0.95 | +4.88% | $30.0 | 93 | ❌ (2 cat) | no |
| V1 | wave-4 | 3 | 60 | inv_vol | 0.92 | +4.52% | $27.2 | 93 | ❌ | no |
| V2 | wave-4 | 2 | 60 | inv_vol | 0.62 | +3.22% | $28.6 | 78 | ❌ | no |
| V9 | wave-4+USMV | 3 | 60 | inv_vol | 0.78 | +3.51% | $20.8 | 79 | ❌ | no |
| V10 | wave-4+USMV | 3 | 60 | equal | 0.84 | +3.85% | $19.4 | 79 | ❌ | no |
| V_expanded (×6) | 10-asset | 2-4 | 21-126 | both | **−0.74…−0.09** | negative | ~$13 | ~17 | ✅* | no |
| **V11** | **SHY-for-TLT** | **3** | **60** | **equal** | **1.24** | **+5.34%** | **$21.8** | 83 | ❌ (1 cat: Q3) | no |
| V12 | SHY-for-TLT | 3 | 60 | inv_vol | −0.22 | −0.30% | $11.1 | 83 | ✅* | no |
| **★ WINNER** | **SHY-for-TLT** | **2** | **60** | **equal** | **1.23** | **+4.45%** | **$13.96** | **54** | **✅ (0 cat)** | **✅** |
| (alt) | SHY-for-TLT | 2 | 42 | equal | 1.21 | +4.33% | $14.0 | 68 | ✅ | ✅ |
| (alt) | SHY-for-TLT | 2 | 63 | equal | 1.16 | +4.20% | $14.0 | 54 | ✅ | ✅ |

`*` expanded/inv-vol variants "pass" clause-(c) only because they barely trade and barely move — they pass on technicality while failing clause-(a) Sharpe. Not real passes.

**Why K=2, not K=3.** The K=3 SHY-swap (V11) has a marginally higher FP Sharpe (1.24 vs 1.23) but **fails clause-(c) on 2022-Q3 chop** (-1.52%, a catastrophe). K=3 holds half the 6-asset universe, forcing a third leg that drags during sideways rotation. **K=2 is the only catastrophe-free family** AND ties for the top Sharpe. The fix is structural, not tuned: tighter bottom-K = cleaner low-vol cut = no forced-in dragging leg. K=2 at N∈{42,60,63} all clear #5, so the result is a plateau, not a knife-edge.

---

## 3. Winning variant — full Bar A #5 scorecard & per-window detail

**Config:** universe `[SPY, EFA, SHY, VNQ, DBC, GLD]`, K=2, N=60, equal-weight, no regime filter.

### Walk-forward, 8 named windows (warmup +180d):

| Window | Regime | Strat Ret | BH-Basket | Sharpe | MaxDD% | Trades | V1 | V2 | Catastrophe | Pass |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022-H1 bear | bear | **-0.17%** | -0.98% | -0.39 | -0.81 | 2 | ✅ | ✅ | no | ✅ |
| 2022-Q3 chop | chop | **-0.85%** | -0.68% | -2.40 | -1.06 | 2 | ✅ | ✅ | no | ✅ |
| 2023-H1 recovery | bull | +0.69% | +0.38% | +1.55 | -0.52 | 4 | ✅ | ✅ | no | ✅ |
| 2023-Q3 chop | chop | +0.05% | -0.22% | +0.17 | -0.33 | 6 | ✅ | ✅ | no | ✅ |
| 2024-Q2 bull | bull | +0.14% | +0.10% | +0.44 | -0.42 | 8 | ✅ | ✅ | no | ✅ |
| 2025-Q1 tariff bear | bear | +0.06% | +0.14% | +0.15 | -0.70 | 6 | ✅ | ✅ | no | ✅ |
| 2025-Q3 bull | bull | +0.89% | +0.49% | +1.93 | -0.34 | 6 | ✅ | ✅ | no | ✅ |
| 2026-recent bull (HELDOUT) | bull | +0.27% | +0.77% | +0.89 | -0.63 | 6 | ✅ | ✅ | no | ✅ |

**Per-regime median:** bull **+0.48%** · chop **-0.40%** · bear **-0.05%**.

The SHY swap's specific contribution to clearing (c): **2022-H1 bear went from -1.65% (catastrophe in V0) to -0.17%** (beats BH, no longer a catastrophe), and **2022-Q3 chop from -2.18% to -0.85%** (above the -1.5% catastrophe line and a smaller miss vs BH). SHY simply doesn't lose money in a rate-shock the way TLT did, so the defensive leg stops being a liability in exactly the windows that killed the parent.

### Full-period (contiguous, 2018-11 → 2026-05):

| Metric | Value |
|---|---|
| FP Sharpe | **1.23** |
| FP Return | +4.45% |
| FP MaxDD | -1.36% / **$13.96** |
| Trades | 54 (28 buys / 26 closes) |
| Basket clamps | 0 |
| Total costs | $0.57 |

---

## 4. Per-symbol attribution (full-period) — the TLT bleed is fixed

| Symbol | Buys | Closes | Realized P&L | Note |
|---|---|---|---|---|
| EFA | 8 | 8 | **+$16.90** | intl-equity low-vol slot |
| SPY | 8 | 8 | **+$16.01** | US-equity low-vol slot |
| DBC | 4 | 4 | +$7.79 | commodity, when vol compressed |
| GLD | 5 | 5 | +$5.25 | gold defensive |
| VNQ | 2 | 1 | +$0.73 | rarely selected (high vol) |
| SHY | 1 | 0 | **+$0.00** | the anchor — never sold, never bled |

**Contrast the parent:** TLT was the parent's single biggest drag at **-$15.18**. Here SHY contributes ~$0 P&L (it's a stable anchor, not a profit center) but, crucially, **it doesn't bleed**. The strategy's positive P&L now comes cleanly from the equity/commodity/gold legs rotating through the second slot, instead of being half-eaten by a duration loss. This is exactly the fix the wave-4 design note #2 predicted.

---

## 5. Honest discussion — is this a real edge, and should low-vol cross-asset stay in the pipeline?

### 5.1 The structural caveat: SHY is held 100% of months.

Holding-frequency over 67 rebalance months:

| Symbol | Holding freq |
|---|---|
| **SHY** | **100.0%** |
| GLD | 31.3% |
| SPY | 31.3% |
| EFA | 22.4% |
| DBC | 11.9% |
| VNQ | 3.0% |

SHY is *always* one of the two legs. So the strategy is mechanically: **50% permanently parked in 1-3y Treasuries (a cash proxy) + 50% rotating into the single lowest-vol risk asset.** That is a 50/50 cash-anchor barbell, not a pure 2-leg AHXZ rotation. The *second* leg rotates genuinely (GLD/SPY/EFA/DBC/VNQ all appear), so there's real signal in the risk sleeve — but the bond sleeve is static.

**Is the high Sharpe "real edge" or "metric gaming"?** Honest answer: **partly the latter.** A 50% allocation to a near-cash asset mechanically halves portfolio volatility, which inflates Sharpe almost regardless of the risk-sleeve's skill. The +4.45% total return over 5.8 years (~0.75%/yr on the $1000 base, ~7.5%/yr on the $100 deployed notional) is modest; the Sharpe is high mainly because the denominator is small. This is the same phenomenon that makes "60/40 with the 40 in T-bills" look great on Sharpe in a calm decade. **The walk-forward per-window returns are mostly small positives (+0.05% to +0.89%), which is consistent with "low-vol-low-return barbell" rather than "found alpha."**

### 5.2 So is the low-vol cross-asset anomaly worth keeping in the pipeline?

**My recommendation: it clears the gate honestly, but I'd flag it as a LOW-CONVICTION promote and lean toward CLOSING OUT the archetype after this.** Reasoning:

1. **The winning config technically satisfies every Bar A #5 clause** — the gate was pre-committed and this isn't goalpost-moving; the numbers are real. If main promotes it, it will behave as a low-drawdown, low-return defensive sleeve, and the execution-cost soak (Bar E) is cheap. There's no catastrophe risk: worst window -1.06% MaxDD.

2. **But the edge is thin and partly mechanical.** The high Sharpe is driven by a permanent cash-anchor, not by the cross-asset low-vol *selection* being especially smart. The selection's contribution is the rotating second leg, whose per-window P&L is small.

3. **The naive universe-expansion finding (§1) is the real publishable result:** *the low-vol anomaly does not generalize across asset classes — vol-ranking across asset classes degenerates to "own the most cash-like thing," which has no return.* This closes the archetype's interesting question. We now know the only way to make cross-asset low-vol "work" on a Sharpe basis is to hand-curate the universe so the ranking is forced to choose among risk assets plus exactly one cash anchor — at which point you've essentially hand-built a barbell and the "anomaly" is doing very little selection work.

4. **The chop-window weakness is strategy-class and persists.** Even the winning K=2 config has chop as its weakest regime (median -0.40%). The SHY swap mitigated the *catastrophe* but not the underlying lag. This is consistent with the parent's and wave-3's findings: AHXZ low-vol is structurally weak in sideways rotation regardless of universe.

**Bottom line for main:** The candidate is **promote-eligible under Bar A #5 as written** (I'd not block a promotion — it's safe and the gate is met). But I'd characterize the archetype as **effectively closed**: we've established that (i) genuine cross-asset low-vol expansion collapses to cash, (ii) the only winning variant is a hand-curated cash-anchor barbell whose Sharpe is denominator-driven, and (iii) the chop weakness is strategy-class and unfixable by universe choice. There is little remaining headroom worth a wave-6. If the bench wants a defensive low-return sleeve, this is a fine one; if it wants *alpha*, cross-asset low-vol isn't where it lives.

---

## 6. Comparison vs parent (wave-4) and the gate the parent missed

| Metric | Parent K=3 (wave-4) | Parent K=2-regime | **This winner (K=2 SHY-swap)** |
|---|---|---|---|
| Universe | SPY/EFA/**TLT**/VNQ/DBC/GLD | same | SPY/EFA/**SHY**/VNQ/DBC/GLD |
| FP Sharpe | 0.97 | 0.76 | **1.23** |
| FP MaxDD | -2.92% | -2.63% | **-1.36% ($13.96)** |
| Bar A #5 (a) Sharpe≥1.0 | ❌ (0.97) | ❌ (0.76) | ✅ (1.23) |
| Bar A #5 (c) no catastrophe | ❌ (2022-Q3 -1.84% cat) | ❌ | ✅ (8/8 clean) |
| TLT/SHY leg P&L | TLT **-$15.18** | -$15.18 | SHY **+$0.00 (no bleed)** |
| **Bar A #5 verdict** | **REJECT** | **REJECT** | **PASS** |

The parent failed #5 on *both* (a) Sharpe-by-0.03 and (c) the 2022-Q3 catastrophe. The SHY swap fixes the catastrophe (defensive leg stops bleeding in rate shocks) and the tighter K=2 cut plus the de-risked anchor lifts Sharpe over 1.0.

---

## 7. Notes on Bar A bullets #6 (code review) and #7 (smoke)

- **#7 smoke:** `./tick.sh --candidate xsec_lowvol_xa2_440761` → **rc=0**, `actions={SHY=buy, SPY=buy}`, no DB writes. ✅
- **#6 code review:** the AST gate `runner/strategy_gen.code_review` reports one "violation": *"missing top-level decide(...)"*. **This is the expected xsec-contract mismatch, identical for the parent `xsec_lowvol_xa_38a206` and the PROMOTED `xsec_momentum_xa_38d2b2`** — all three export `decide_xsec` (the cross-sectional contract) rather than `decide`, and run through `runner_xsec.py` / `load_xsec_strategy`, which require `decide_xsec`. The **security-relevant** AST checks all PASS identically to the parent: `imports=[] forbidden=[] loops=[] docstring=ok` (verified for both files side-by-side). No `os/sys/subprocess/socket/urllib`, no `eval/exec/open/__import__`, no `while True`, no recursion. The candidate is static-imports-only (`math`, `dataclasses`, `typing`).

---

## 8. Files created (candidate dir + report ONLY — no runner/gate/promoted edits)

| Path | Purpose |
|---|---|
| `strategies_candidates/xsec_lowvol_xa2_440761/strategy.py` | NEW — wave-5 candidate (configurable basket, weight_mode, K, N). Exports `decide_xsec`. |
| `strategies_candidates/xsec_lowvol_xa2_440761/params.json` | NEW — winning config: SHY-for-TLT universe, K=2, N=60, equal-weight. |
| `strategies_candidates/xsec_lowvol_xa2_440761/__init__.py` | NEW. |
| `reports/BACKTEST_XSEC_LOWVOL_XA2_20260531T023858Z.md` | THIS report. |
| `_run_lowvol_xa2_sweep.py` | NEW driver — 12-variant full sweep (universe/weight/K). |
| `_run_lowvol_xa2_final.py` | NEW driver — winner's full Bar A #5 scorecard + per-symbol + holding-freq. |
| `_shy_sweep.py` | NEW driver — SHY-universe K×N grid (found the catastrophe-free K=2 family). |
| `_replay_holds.py` | NEW driver — holding-frequency replay (proved the expanded-universe cash collapse). |
| `/tmp/lv2_sweep.json`, `/tmp/lv2_final.json` | Raw outputs. |

**No edits** to `runner/runner*.py`, `runner/backtest_xsec.py`, `runner/walk_forward_xsec.py`, `runner/broker_alpaca.py`, `runner/risk.py`, `runner/safety_backstop.py`, `runner/candidate_smoke.py`, `GATE.md`, or the promoted `strategies/xsec_momentum_xa_38d2b2`. (md5 snapshot pre/post identical — see §9.)

---

## 9. Verification

```
$ python3 -m pytest tests/ -q
225 passed in 6.93s   (pre and post identical)

$ ./tick.sh --candidate xsec_lowvol_xa2_440761
[xsec_lowvol_xa2_440761] SMOKE OK xsec (2119ms)
  basket=['SPY','EFA','SHY','VNQ','DBC','GLD'] bars_total=1800 actions={SHY=buy, SPY=buy}

$ python3 _run_lowvol_xa2_final.py
  FULL-PERIOD: Sharpe=1.230 ret=+4.45% DD$=13.96 trades=54
  BAR A #5: (a)FPSharpe>=1.0=True (1.23)  (b)DD<=$200=True ($13.96)  (c)all-windows=True  => PASS
```

Runner/gate/promoted-strategy md5 checksums captured at `/tmp/md5_post.txt`; no files outside the candidate dir + this report + the four scratch drivers were modified.

---

## 10. Final verdict

**RECOMMEND: promote-eligible under Bar A #5 (all clauses met), LOW CONVICTION.** The candidate `xsec_lowvol_xa2_440761` (SHY-for-TLT, K=2, N=60, equal-weight) is the first cross-asset low-vol variant to clear the fast-track bar: FP Sharpe 1.23, MaxDD $13.96, 8/8 windows catastrophe-free, held-out window positive. If main promotes it, it behaves as a safe, low-return defensive sleeve.

**But the archetype is effectively closed.** The headline science from this wave is the *negative* result: cross-asset low-vol doesn't generalize — vol-ranking across asset classes degenerates to owning the most cash-like instrument, which has no return (every genuine-expansion variant went Sharpe-negative, SHY held 100% of months). The only winning config is a hand-curated cash-anchor barbell whose Sharpe is denominator-driven, not selection-driven. There is no obvious wave-6 lever with real alpha headroom. I recommend main either (a) promote this as a defensive sleeve and close the archetype, or (b) close the archetype outright as "tops out at a barbell" — and **not** spend another wave on it.

**One pattern datum for PATTERNS.md (flagging, not writing — n=1, per Pattern #2):** *"Cross-asset low-vol vol-ranking collapses to the most cash-like asset when the universe contains a cash proxy; the anomaly is intra-asset-class and does not transfer across asset classes without hand-curation."* This is a strong, refute-tested finding (the expanded universe COULD have improved Sharpe and instead went negative), but it's one within-class data point — main should decide whether it earns a durable PATTERNS.md entry.
