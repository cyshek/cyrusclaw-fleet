# Allocator Breadth Engine Port — Verification Report

**UTC:** 20260627T211538Z
**Task:** PAPER-ONLY engine change. Port the validated SMA-breadth gate into the LIVE allocator's vol-target engine (`backtest_daily_voltarget.py`) so the engine becomes *capable* of breadth, while remaining bit-identical to today on the default (`breadth_windows=None`) path.
**Verdict:** ✅ **ENGINE PORTED + VERIFIED BIT-FOR-BIT.** All 28 verification checks pass with `diff = +0.000e+00` (exact, not merely within tolerance). Non-destructive guarantee proven (None/[] paths bit-identical to baseline). Protected files unchanged. Existing pytest suite: 3 pre-existing unrelated failures, 840 pass (proven not caused by this edit).

---

## 1. What changed (single file: `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`)

Edited file md5: `e7b75d2d45f3d059743459168c6844d7`

Three additive, reversible changes — no existing line of behavior altered:

### (a) New optional dataclass field
```python
# in VolTargetParams (after w_max)
# --- breadth gate (optional, lookahead-safe; None/[] => binary SMA gate) ---
breadth_windows: Optional[List[int]] = None  # e.g. [30,90,180]; see BREADTH note
```

### (b) Two new helpers (mirror the validated `make_breadth_scaler`/`_sma` exactly)
```python
def _sma_breadth(under_closes_through_D, n):
    # trailing simple SMA = sum(closes[-n:]) / n ; None if fewer than n closes
    if n <= 0 or len(under_closes_through_D) < n:
        return None
    return sum(under_closes_through_D[-n:]) / n

def breadth_fraction(under_closes_through_D, windows):
    # g = agree / len(windows); a window 'agrees' iff SMA exists AND last > SMA
    if not under_closes_through_D:
        return 0.0
    last = under_closes_through_D[-1]
    agree = 0
    for w in windows:
        s = _sma_breadth(under_closes_through_D, w)
        if s is not None and last > s:
            agree += 1
    return agree / len(windows)
```

These are byte-for-byte the same math as `reports/_ens_breadth_tiebreak_driver.py::_sma` / `make_breadth_scaler` (the validated scaler).

### (c) Main per-day loop branch (in `run_backtest_voltarget`)
The single original line `w = target_weight(up, rv, p.target_ann_vol, p.w_max)` is now wrapped:
```python
if p.breadth_windows:
    # BREADTH path: continuous trend fraction g multiplies the vol-target weight.
    g = breadth_fraction(uc, p.breadth_windows)                       # closes <= D (lookahead-safe)
    if p.vix_gate and g > 0.0 and bd._vix_risk_off(d_prev, p.vix_ratio_thr):
        g = 0.0                                                        # VIX de-risk, unchanged convention
    vt = target_weight(True, rv, p.target_ann_vol, p.w_max)           # vol-target weight, trend factored OUT
    w = _clamp(g * vt, 0.0, p.w_max)                                  # breadth MULTIPLIES vol-target weight
else:
    # BINARY path: UNCHANGED from the pre-breadth engine (bit-identical).
    w = target_weight(up, rv, p.target_ann_vol, p.w_max)
```

**Why this is exactly the validated edge:** the validated driver `simulate()` computes `g = scaler(uc)`, then `vt = target_weight(True, rv, TARGET_VOL, W_MAX)` (trend forced True so the vol-target weight is gate-free), then `w = clamp(g * vt, 0, w_max)`. The port reproduces this expression literally. The `rvol` computation (`realized_ann_vol`, trailing 20d sleeve stdev, dates ≤ D) and the abs-change-in-weight cost model are **untouched**. When `breadth_windows` is falsy, the code path is the original line verbatim — not a reimplementation.

A pristine reversion (strip exactly these three additions) was diffed against the edited file: the diff is **only** the breadth additions, nothing else (confirmed mechanically).

---

## 2. Verification table — `reports/_allocator_breadth_engine_port_verify.py`

Convention: continuous full-span sim, slice OOS @ 2018-01-01, fp-Sharpe ddof=1 √252, `vix_gate=False`, live config (`target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0, switch_cost_bps=2.0`). Gold = `reports/_ens_breadth_tiebreak_result.json` (`base` and `triples["30-90-180"]`).

### (A) NON-DESTRUCTIVE — `breadth_windows=None` reproduces the binary baseline

| segment | metric | engine (None) | gold base | Δ |
|---|---|---|---|---|
| FULL | total_ret_% | 2002.0713 | 2002.0713 | 0.000e+00 |
| FULL | sharpe_fp | 0.853809 | 0.853809 | 0.000e+00 |
| FULL | sharpe_pop | 0.853913 | 0.853913 | 0.000e+00 |
| FULL | maxdd_% | −34.5236 | −34.5236 | 0.000e+00 |
| FULL | avg_weight | 0.514933 | 0.514933 | 0.000e+00 |
| OOS | sharpe_fp | 0.836853 | 0.836853 | 0.000e+00 |
| OOS | maxdd_% | −34.5236 | −34.5236 | 0.000e+00 |
| IS | sharpe_fp | 0.848849 | 0.848849 | 0.000e+00 |
| IS | maxdd_% | −33.1567 | −33.1567 | 0.000e+00 |

Engine's own stats (`run_backtest_voltarget(...).strategy.stats`): total 2002.0713%, pop-Sharpe 0.853913, maxDD −34.5236%, avgW 0.514933 — all exact. **`breadth_windows=[]` (empty list) is bit-identical too:** None-vs-empty `max|Δequity| = 0.0`. This is the documented base (sharpe 0.8538, maxdd −34.524%, total +2002.07%) reproduced exactly — the non-destructive guarantee holds.

### (B) CORRECT — `breadth_windows=[30,90,180]` reproduces the validated target table

| segment | metric | engine [30,90,180] | gold triple | Δ |
|---|---|---|---|---|
| FULL | total_ret_% | 1339.6395 | 1339.6395 | 0.000e+00 |
| FULL | sharpe_fp | 0.830619 | 0.830619 | 0.000e+00 |
| FULL | sharpe_pop | 0.830719 | 0.830719 | 0.000e+00 |
| FULL | maxdd_% | −29.8527 | −29.8527 | 0.000e+00 |
| FULL | avg_weight | 0.472866 | 0.472866 | 0.000e+00 |
| OOS | total_ret_% | 315.1938 | 315.1938 | 0.000e+00 |
| OOS | sharpe_fp | 0.855135 | 0.855135 | 0.000e+00 |
| OOS | maxdd_% | −22.5501 | −22.5501 | 0.000e+00 |
| OOS | avg_weight | 0.407845 | 0.407845 | 0.000e+00 |
| IS | sharpe_fp | 0.778606 | 0.778606 | 0.000e+00 |
| IS | maxdd_% | −29.8527 | −29.8527 | 0.000e+00 |

**Targets matched exactly:** FULL +1339.64% / S 0.8306 / maxdd −29.853% / avgW 0.4729 / n=4118; OOS +315.19% / S 0.8551 / maxdd −22.550% / avgW 0.4078 / n=2132; IS S 0.7786 / maxdd −29.853%.

**Result: 28/28 checks pass, 0 fail → PASS.** Every diff is `+0.000e+00` (far inside the ~1e-6 Sharpe / ~1e-9 equity tolerance — the reproduction is *exact*, because the engine path now literally is the validated driver's expression).

---

## 3. pytest — full suite (`PYTHONPATH=. python3 -m pytest -q` from workspace root)

```
3 failed, 840 passed, 3 skipped, 296 warnings in 19.51s
```

The 3 failures are **pre-existing and unrelated** to this edit:
```
FAILED tests/test_parent_pool_diversity.py::test_pool_member_is_single_name_with_decide[trend_follow_uup]
FAILED tests/test_parent_pool_diversity.py::test_pool_member_profiles_without_crash[trend_follow_uup]
FAILED tests/test_parent_pool_diversity.py::test_decorrelator_parents_are_gate_failing_but_compatible
```
- Cause: `trend_follow_uup` (a UUP dollar-trend-follower parent in the LLM-mutation pool) fails to profile — `ParentProfile(available=False, n_trades=0)`, i.e. its underlying (UUP) cache yields no trades. This is a data/strategy issue in the mutation-pool guard tests.
- That test file does **not** import or touch `backtest_daily_voltarget.py` (grep for `voltarget|breadth` → empty).
- **Proven non-causal:** swapping a pristine pre-breadth copy of the engine into place and re-running `tests/test_parent_pool_diversity.py` produced the **identical** `3 failed, 25 passed, 2 skipped`. The breadth edit changes neither the count nor the identity of failures.

The breadth change broke **zero** tests. All 840 prior passes still pass.

---

## 4. Protected-file md5s (unchanged at end of task)

| file | md5 | spec | match |
|---|---|---|---|
| runner/backtest.py | `717c36e68941b9258f86bc99950de788` | 717c36e6… | ✓ |
| runner/risk.py | `e303317e0d2ac796a1fa43e372f0a113` | e303317e… | ✓ |
| runner/runner.py | `0f763975f2d8ba535352f6a8306afb8b` | 0f763975… | ✓ |
| runner/allocator_paper_tracker.py | `0b5242474a9bad75562c94595bacbc23` | 0b524247… | ✓ |
| _allocator_blend_tests.py | `309f765dc895d621aeda6e143ab5b397` | 309f765d… | ✓ |

No protected file was touched. No order placed, no spend, no `*.db` / broker / crontab / `strategies/` / `runner/` change.

---

## 5. THE EXACT ONE-LINE CHANGE THE PARENT MUST MAKE TO GO LIVE

File: **`runner/allocator_paper_tracker.py`**, the live `VolTargetParams(...)` call site at **lines 236–238**:

**Current (today — binary SMA-200 gate):**
```python
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0))
```

**After (breadth gate live — add `breadth_windows=[30, 90, 180]`):**
```python
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0, breadth_windows=[30, 90, 180]))
```

That single added kwarg is the entire flip. It is the moment live capital behavior changes — hence left to the parent (the file is protected). Everything else (engine capability, parity, validation) is done and proven.

### Expected effect of the flip (allocator vol-target TQQQ sleeve)
A **risk-reducing refinement**, not a return-chaser:
- **OOS maxDD: −34.52% → −22.55%** (≈ 12 pp shallower — the drawdown improvement that motivated the breadth gate).
- **OOS Sharpe: 0.8369 → 0.8551** (fp; ≈ flat-to-slightly-up — actually a small *improvement* OOS).
- **OOS total return: +363.0% → +315.2%** (≈ 48 pp *less* total return — the cost of de-risking; the gate scales exposure down in choppy/declining-breadth regimes).
- FULL: total +2002% → +1340%, Sharpe 0.8538 → 0.8306, maxDD −34.52% → −29.85%, avgW 0.515 → 0.473.

Net: meaningfully lower drawdown, OOS Sharpe slightly up, at the cost of less raw return — exactly the trade the breadth gate was validated to make.

---

## 6. Deliverables produced (reports/, allowed write scope)
- `reports/ALLOCATOR_BREADTH_ENGINE_PORT_20260627T211538Z.md` — this report.
- `reports/_allocator_breadth_engine_port_verify.py` — the verification driver (runs clean: 28/28 PASS).

Engine edit confined to `strategies_candidates/leveraged_long_trend/backtest_daily_voltarget.py`. Allocator NOT wired to breadth (per task — that one-line flip is the parent's call).
