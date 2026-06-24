"""tests for runner/lane_honesty.py — the shared recurring-failure-mode guards.

Anchored to the THREE lanes that established this pattern on 2026-06-23:
  - fundamentals-PIT  -> survivorship guard FAIL (long-only beats SPY but loses to EW)
  - BAB               -> survivorship guard FAIL + negative L/S spread
  - commodity-carry   -> OOS-mirage guard FAIL (neg IS Sharpe, ~0 full, gaudy OOS)

Plus clean-pass cases (a genuinely robust sleeve) and degenerate-input safety.
Pure-Python, no external deps — runnable via `python3 -m pytest` or the __main__ shim.
"""
from __future__ import annotations

import math
import random

import runner.lane_honesty as lh


# ---------------------------------------------------------------------------
# Synthetic-series builders
# ---------------------------------------------------------------------------
def _const_daily(mu: float, n: int) -> list:
    """Deterministic near-constant drift with tiny alternating wiggle (nonzero variance)."""
    out = []
    for i in range(n):
        out.append(mu + (0.0005 if i % 2 == 0 else -0.0005))
    return out


def _noisy_daily(mu: float, sigma: float, n: int, seed: int) -> list:
    rng = random.Random(seed)
    return [rng.gauss(mu, sigma) for _ in range(n)]


# ===========================================================================
# Core stats
# ===========================================================================
def test_sharpe_matches_convention():
    # constant-positive-mean series with tiny symmetric wiggle -> large positive Sharpe
    s = lh.sharpe(_const_daily(0.001, 504))
    assert s > 0
    # hand-check sign + rough magnitude against a manual computation
    rets = _const_daily(0.001, 504)
    n = len(rets); mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    expected = (mean / math.sqrt(var)) * math.sqrt(lh.TRADING_DAYS)
    assert abs(s - expected) < 1e-9


def test_sharpe_degenerate_safe():
    assert lh.sharpe([]) == 0.0
    assert lh.sharpe([0.01]) == 0.0          # n<2
    assert lh.sharpe([0.01, 0.01, 0.01]) == 0.0  # zero variance


def test_total_return_and_cagr():
    assert abs(lh.total_return([0.1, 0.1]) - 0.21) < 1e-12
    # one year of ~0 daily -> CAGR near 0; positive drift -> positive CAGR
    assert lh.cagr(_const_daily(0.0005, 252)) > 0
    assert lh.cagr([]) == 0.0


def test_slice_helpers_negative_index():
    daily = list(range(10))
    assert lh._slice_oos(daily, -3) == [7, 8, 9]
    assert lh._slice_is(daily, -3) == [0, 1, 2, 3, 4, 5, 6]
    assert lh._slice_oos(daily, None) == daily
    assert lh._slice_is(daily, None) == daily


# ===========================================================================
# Guard 1 — SURVIVORSHIP (fundamentals-PIT + BAB signature)
# ===========================================================================
def test_survivorship_fail_loses_to_ew():
    """fundamentals-PIT signature: factor underperforms a dumb EW hold of same universe OOS."""
    n = 1000; split = 600
    # EW control drifts up more than the signal in the OOS window -> survivorship beta
    signal = _const_daily(0.0004, n)
    ew = _const_daily(0.0009, n)   # dumb EW hold beats the 'factor' OOS
    v = lh.survivorship_verdict(signal, ew, split)
    assert v.passed is False
    assert v.delta_oos_total < 0
    assert "LOSES to no-signal EW" in v.reason


def test_survivorship_fail_negative_ls_spread():
    """BAB signature: beats EW on long-only, but the market-neutral L/S spread is negative OOS."""
    n = 1000; split = 600
    signal = _const_daily(0.0010, n)
    ew = _const_daily(0.0004, n)       # signal beats EW (long-only) ...
    ls = _const_daily(-0.0003, n)      # ... but L/S spread bleeds OOS -> it's beta
    v = lh.survivorship_verdict(signal, ew, split, ls_spread_daily=ls)
    assert v.passed is False
    assert v.ls_spread_oos_total is not None and v.ls_spread_oos_total < 0
    assert "L/S spread is NEGATIVE" in v.reason


def test_survivorship_pass_clean():
    """A genuinely additive sleeve: beats EW OOS and has a positive L/S spread."""
    n = 1000; split = 600
    signal = _const_daily(0.0011, n)
    ew = _const_daily(0.0004, n)
    ls = _const_daily(0.0003, n)
    v = lh.survivorship_verdict(signal, ew, split, ls_spread_daily=ls)
    assert v.passed is True
    assert v.delta_oos_total > 0
    assert v.ls_spread_oos_total > 0


# ===========================================================================
# Guard 2 — OOS-MIRAGE (commodity-carry signature)
# ===========================================================================
def test_oos_mirage_fail_regime_artifact():
    """commodity-carry signature: negative IS Sharpe, ~0 full Sharpe, gaudy OOS Sharpe.

    Build a series that LOSES money in-sample but rips in the OOS window so the OOS Sharpe
    looks great while the full-period Sharpe is ~0 — exactly the regime artifact the guard
    must reject.
    """
    split = 600; n = 1000
    # Calibrated to reproduce the REAL commodity-carry signature: full Sharpe ~0 (the
    # actual lane was -0.014), deeply negative IS, gaudy OOS. The IS bleed must be deep
    # enough that the strong OOS half does NOT pull the full-period Sharpe above the floor.
    is_part = _noisy_daily(-0.0009, 0.01, split, seed=51)      # loses money IS (neg drift)
    oos_part = _noisy_daily(0.0011, 0.01, n - split, seed=52)  # rips OOS (gaudy)
    signal = is_part + oos_part
    v = lh.oos_mirage_verdict(signal, split)
    # sanity: the constructed signature actually has neg IS + strong OOS + ~0 full
    assert v.is_sharpe < 0
    assert v.oos_sharpe > 0
    assert v.full_sharpe < lh.DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR
    assert v.passed is False
    assert "OOS-only regime artifact" in v.reason


def test_oos_mirage_pass_robust():
    """A robust sleeve: positive IS Sharpe AND healthy full Sharpe -> not a mirage."""
    split = 600; n = 1000
    signal = _noisy_daily(0.0008, 0.008, n, seed=7)  # consistent positive drift both halves
    v = lh.oos_mirage_verdict(signal, split)
    assert v.is_sharpe > 0
    assert v.full_sharpe >= lh.DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR
    assert v.passed is True


def test_oos_mirage_pass_when_full_strong_even_if_is_softish():
    """Guard only fails when BOTH full<floor AND is<0. A strong full Sharpe rescues it."""
    split = 600; n = 1000
    # mildly positive IS, strongly positive OOS -> full Sharpe well above floor
    signal = _noisy_daily(0.0003, 0.006, split, seed=3) + _noisy_daily(0.0015, 0.006, n - split, seed=4)
    v = lh.oos_mirage_verdict(signal, split)
    assert v.full_sharpe >= lh.DEFAULT_OOS_MIRAGE_FULL_SHARPE_FLOOR
    assert v.passed is True


# ===========================================================================
# Combined entry point
# ===========================================================================
def test_assert_lane_honest_runs_both_and_fails_on_either():
    n = 1000; split = 600
    # honest on survivorship, but an OOS-mirage on consistency (full Sharpe ~0)
    signal = _noisy_daily(-0.0009, 0.01, split, seed=51) + _noisy_daily(0.0011, 0.01, n - split, seed=52)
    ew = _const_daily(0.00005, n)  # signal beats this OOS (so survivorship passes)
    v = lh.assert_lane_honest(signal, split, ew_control_daily=ew)
    assert v.survivorship is not None and v.survivorship.passed is True
    assert v.oos_mirage.passed is False
    assert v.passed is False
    assert any("OOS-MIRAGE" in f for f in v.failures)


def test_assert_lane_honest_clean_pass():
    n = 1000; split = 600
    signal = _const_daily(0.0011, n)
    ew = _const_daily(0.0004, n)
    ls = _const_daily(0.0003, n)
    v = lh.assert_lane_honest(signal, split, ew_control_daily=ew, ls_spread_daily=ls)
    assert v.passed is True
    assert v.survivorship.passed is True
    assert v.oos_mirage.passed is True
    assert v.failures == []


def test_assert_lane_honest_skips_survivorship_without_ew():
    """Single-asset timing sleeve: no universe to EW-hold -> survivorship guard skipped."""
    n = 1000; split = 600
    signal = _const_daily(0.0008, n)
    v = lh.assert_lane_honest(signal, split)  # no ew_control_daily
    assert v.survivorship is None
    assert v.oos_mirage is not None
    assert v.passed is True


def test_assert_lane_honest_raise_on_fail():
    n = 1000; split = 600
    signal = _noisy_daily(-0.0009, 0.01, split, seed=51) + _noisy_daily(0.0011, 0.01, n - split, seed=52)
    raised = False
    try:
        lh.assert_lane_honest(signal, split, raise_on_fail=True)
    except AssertionError as e:
        raised = True
        assert "LANE HONESTY: FAIL" in str(e)
    assert raised


def test_verdict_summaries_render():
    n = 1000; split = 600
    signal = _const_daily(0.0011, n)
    ew = _const_daily(0.0004, n)
    ls = _const_daily(0.0003, n)
    v = lh.assert_lane_honest(signal, split, ew_control_daily=ew, ls_spread_daily=ls)
    s = v.summary()
    assert "LANE HONESTY" in s
    assert "SURVIVORSHIP" in s
    assert "OOS-MIRAGE" in s


if __name__ == "__main__":
    # Lightweight runner so the file works even without pytest installed.
    import traceback
    fns = [g for name, g in sorted(globals().items()) if name.startswith("test_") and callable(g)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"  ok   {fn.__name__}")
        except Exception:
            failed += 1; print(f"  FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
