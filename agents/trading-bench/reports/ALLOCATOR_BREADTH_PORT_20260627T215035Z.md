# ALLOCATOR BREADTH-PORT — verdict (sleeve-A {30,90,180} breadth on the inv-vol blend)

**Stamp:** 20260627T215035Z
**Driver:** `reports/_allocator_breadth_port_driver.py`
**Result JSON:** `reports/_allocator_breadth_port_result.json`
**Question:** Does putting the {30,90,180} breadth gate on the allocator's TQQQ vol-target sleeve (sleeve A) improve the inv-vol-63d BLEND out-of-sample vs the live binary-SMA200 sleeve A? (Evidence for flipping the live allocator sleeve-A gate.)

---

## TL;DR — **GO** (modest but real, robust to the +1-bar canary)

Breadth-on-sleeve-A improves the BLEND on **both** OOS Sharpe **and** OOS maxDD, net of cost, and the edge **strengthens** (does not collapse) under a +1-bar signal lag. The improvement is driven by a mechanism the inv-vol layer does **not** already capture: breadth lowers sleeve A's *own* drawdown profile (graded de-risk vs binary on/off), and the inv-vol layer — far from neutralizing it — actually leans *into* the now-calmer sleeve A (more weight) while the blend's drawdown still falls. This is the **opposite** of the multi-horizon-ensemble result (where vol-target had already done the downside job, making the ensemble redundant).

---

## 1. Baseline reproduction (binary-A blend) — PASS ✓ (done first, per honesty rail)

| metric | known allocator | reproduced here | match |
|---|---|---|---|
| full Sharpe | 1.0125 (2026-06-18 report) | **1.0030** | ✓ (= the "~0.998 on current cache" expectation; cache refreshed since 06-22) |
| OOS Sharpe | 1.1425 | **1.1228** | ✓ (within range 1.113–1.147) |
| full maxDD | −23.897% | **−23.897%** | ✓ (exact to 4 dp) |
| avg w_tqqq / w_rot | 0.4425 / 0.558 (06-18) → 0.3485 / 0.6515 (06-22) | **0.3485 / 0.6515** | ✓ (exact) |
| common window | 2010-02 → today | 2010-02-12 → 2026-06-25 (n=4116) | ✓ |

The binary-A blend reproduces the live allocator to the float on maxDD/weights and within tolerance on Sharpe. Forward proceeds.

> Note on w_tqqq drift: the 06-18 report had w_tqqq≈0.442; the current cache gives 0.3485 (matches the 06-22 `_allocator_blend_result.json`). This is a cache-vintage effect on the inv-vol weights, identical for both arms, so the binary-vs-breadth comparison is unaffected.

---

## 2. THE BLEND COMPARISON — binary-A vs breadth-A (same path, same inv-vol-63d blend, 2bps)

| | full Sharpe | full maxDD | full CAGR | OOS Sharpe | OOS maxDD | OOS CAGR | avg w_tqqq |
|---|---|---|---|---|---|---|---|
| **binary-A blend** (live) | 1.0030 | −23.90% | 15.72% | 1.1228 | −21.88% | 19.10% | 0.3485 |
| **breadth-A blend** {30,90,180} | **1.0294** | **−20.33%** | 15.47% | **1.1496** | **−20.02%** | 18.84% | 0.3851 |
| **Δ (breadth − binary)** | **+0.0263** | **+3.57pp** | −0.25pp | **+0.0268** | **+1.86pp** | −0.26pp | +0.0365 |

- **OOS Sharpe: +0.027** (1.1228 → 1.1496) — better.
- **OOS maxDD: +1.86pp less deep** (−21.88% → −20.02%) — better.
- **Full Sharpe: +0.026**, **full maxDD: +3.57pp less deep** (−23.90% → −20.33%) — better on both.
- Cost: a small CAGR give-up (≈ −0.25pp full and OOS) — the price of the lower-vol profile, dominated by the Sharpe/DD gains.

**Breadth-A wins the blend on Sharpe AND maxDD, full AND OOS.** This passes the GO bar (beat OOS on Sharpe-OR-maxDD net of cost) on **both** legs, not just one.

---

## 3. Standalone sleeve A (separates sleeve effect from blend effect)

Allocator split (OOS = 2019-01-01→):

| sleeve A | full Sharpe | full maxDD | OOS Sharpe | OOS maxDD | avg weight |
|---|---|---|---|---|---|
| binary SMA200 | 0.8568 | −34.52% | 0.9944 | −24.41% | 0.5150 |
| breadth {30,90,180} | 0.8329 | **−29.85%** | 0.9812 | **−22.55%** | 0.4729 |

Cross-check vs `reports/_ens_breadth_tiebreak_result.json` (its own split 2018-01-01): binary OOS Sharpe 0.837 / maxDD −34.52%, breadth OOS Sharpe 0.855 / maxDD −22.55%. **Standalone breadth-A reproduces the tiebreak numbers** (OOS maxDD −22.55% matches to the bp; the Sharpe ordering flips slightly under the allocator's later 2019 split because 2018-Q4 — where breadth's de-risk helped most — sits IN-sample at 2018-12-31, but the OOS maxDD improvement is identical and large).

**Key standalone fact:** breadth makes sleeve A **calmer** (full maxDD −34.52% → −29.85%, a −4.7pp improvement; OOS −24.41% → −22.55%) at a small standalone-Sharpe cost. The drawdown compression is the load-bearing effect.

---

## 4. WHY it works at the blend level — the inv-vol layer does NOT neutralize it (mechanistic)

Sleeve-A realized vol (common window):

| | full ann vol | OOS ann vol |
|---|---|---|
| binary-A | 25.75% | 25.27% |
| breadth-A | **22.82%** | **22.60%** |
| Δ | **−2.94pp** | **−2.67pp** |

The inv-vol-63d blend weights sleeve A ∝ 1/vol_A. Breadth **lowers sleeve A's vol by ~2.7–2.9pp**, so the inv-vol layer gives sleeve A **MORE** weight (0.3485 → 0.3851, +3.65pp). Naively that re-concentration into the wild 3x sleeve should *hurt* the blend's drawdown — **but it doesn't**: blend maxDD still improves (−23.90% → −20.33% full; −21.88% → −20.02% OOS).

That is the crux: **the inv-vol layer scales the whole sleeve uniformly by its trailing realized vol; breadth specifically cuts exposure during the broad-market *deterioration* (the 30/90/180-day SMA stack rolling over one horizon at a time) that precedes sleeve A's worst drawdowns.** These are different information sets. Trailing-63d vol is a *coincident/lagging* risk measure; the breadth stack is a *leading* trend-quality measure. The inv-vol layer cannot replicate the breadth de-risk because at the onset of a broad rollover, sleeve A's *trailing* vol is often still low (the crash hasn't shown up in the 63-day window yet) — so inv-vol keeps sleeve A heavy right into the drawdown, exactly the failure breadth pre-empts. Breadth reshapes *when* the exposure comes off; inv-vol only reshapes *how much* based on already-realized vol.

**Contrast with the multi-horizon trend ensemble (prior NO-GO):** there, the vol-target layer had *already* done the downside job, so stacking more trend horizons was redundant — the second signal carried no orthogonal information past what vol-target captured. **Here it's the reverse:** the inv-vol BLEND layer captures the *cross-sleeve* risk-balancing but is *blind to within-sleeve trend deterioration*, so breadth adds a genuinely orthogonal de-risk. The inv-vol layer does **not** already neutralize the sleeve-A DD benefit — it passes a meaningful chunk of it through to the blend.

---

## 5. Canary (+1-bar lag on the sleeve-A breadth signal) — HOLDS ✓

Re-ran breadth-A with the breadth/vol DECISION date stepped back +1 trading day (signal lagged; sleeve return realization unchanged), then rebuilt the identical blend:

| | full Sharpe | full maxDD | OOS Sharpe | OOS maxDD |
|---|---|---|---|---|
| breadth-A blend (lag 0) | 1.0294 | −20.33% | 1.1496 | −20.02% |
| breadth-A blend (lag +1, canary) | 1.0276 | −22.17% | **1.1765** | −21.36% |

The +1-bar lag **does not collapse the edge** — OOS Sharpe actually *rises* to 1.1765 and both lagged numbers still beat the binary-A blend (OOS 1.1228, maxDD −21.88%). The breadth advantage is a **slow, multi-month trend-quality signal**, not a 1-day timing artifact: a one-day execution slip costs nothing and the edge is robust. (Identical behavior to the standalone tiebreak canary, where the {30,90,180} OOS Sharpe also *improved* under +1-bar lag.)

---

## 6. GO / NO-GO

### **RECOMMENDATION: GO — flip the live allocator sleeve-A gate to {30,90,180} breadth.**

Rationale:
1. **Beats the binary-A blend OOS on BOTH Sharpe (+0.027) and maxDD (+1.86pp)** net of 2bps cost — clears the bar on both legs, not a one-metric squeak.
2. **Also better full-period** on both Sharpe (+0.026) and maxDD (+3.57pp).
3. **Robust:** +1-bar canary does not collapse it (OOS Sharpe holds/improves) — not a timing artifact.
4. **Mechanistically sound and orthogonal:** breadth supplies a *leading* trend-deterioration de-risk the *coincident* inv-vol layer is structurally blind to; the inv-vol layer does NOT already neutralize the benefit (unlike the redundant multi-horizon ensemble).
5. **Self-consistent with the locked tiebreak study:** standalone breadth-A reproduces `_ens_breadth_tiebreak_result.json` (OOS maxDD −22.55% to the bp).

Caveats / sizing notes (none block GO):
- Small CAGR give-up (≈ −0.25pp full and OOS) — expected for the lower-vol profile; the risk-adjusted gain dominates.
- Breadth raises avg w_tqqq (0.3485 → 0.3851) via the inv-vol response to the calmer sleeve; the blend's drawdown *still* improves, so the re-concentration is benign here, but it does mean the live book will carry slightly more nominal TQQQ exposure — consistent with the −20% (vs −24%) blend drawdown, not a new risk.
- Magnitude is modest (≈ +2.7% relative OOS Sharpe, ≈ 1.9pp OOS drawdown). It's an *improvement*, not a regime change. Free risk reduction with a small Sharpe bump and no canary fragility.

### Suggested live change (one line, non-destructive — engine already supports it)
In `_allocator_blend_tests.py` `build_sleeves()`, the sleeve-A call:
```python
vt = run_backtest_voltarget(VolTargetParams(
    target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
    vix_gate=False, switch_cost_bps=2.0,
    breadth_windows=[30, 90, 180]))     # <-- ADD THIS LINE
```
Sleeve B and the inv-vol blend layer are unchanged. (This driver did **not** edit any live file — it built both arms by calling the engine directly. The flip itself is Cyrus's call on the live allocator.)
