"""Pinning tests for runner.spy_relative — SPY-relative excess return + IR.

These lock the annualization convention, the divide-by-zero / alignment
edge handling, and one hand-computed example so a silent mis-annualization
can never sneak into candidate reports.
"""

from __future__ import annotations

import math

import pytest

from runner.backtest import bars_per_year
from runner.spy_relative import (
    align_returns_by_date,
    annualized_return,
    information_ratio,
    returns_from_closes,
    spy_relative_metrics,
)


# ---------------------------------------------------------------------------
# (a) strategy identical to SPY -> excess ~ 0, IR ~ 0 (here: IR undefined ->
#     None, because identical series have ZERO tracking error). We assert
#     both: excess return is exactly 0 and IR is None (the correct "undefined"
#     answer for zero TE), which is the risk-adjusted equivalent of "0".
# ---------------------------------------------------------------------------
def test_identical_to_spy_zero_excess_and_undefined_ir():
    strat = [0.01, -0.02, 0.005, 0.013, -0.004]
    spy = list(strat)  # identical
    m = spy_relative_metrics(strat, spy, timeframe="1Day")
    assert abs(m["excess_return_annualized"]) < 1e-12
    assert abs(m["strategy_ann_return"] - m["spy_ann_return"]) < 1e-12
    # Zero tracking error -> IR undefined, NOT a divide-by-zero blow-up.
    assert m["information_ratio"] is None


# ---------------------------------------------------------------------------
# (b) strategy = SPY + constant positive excess each period -> positive
#     excess annualized return AND a constant-excess series. Note: a CONSTANT
#     additive excess has zero tracking-error VARIANCE -> IR undefined (None).
#     So we test two things:
#       (b1) constant additive excess -> positive excess return, IR is None
#            (zero variance of excess).
#       (b2) a near-constant excess with tiny noise -> very high (finite) IR.
# ---------------------------------------------------------------------------
def test_constant_excess_positive_return_ir_undefined():
    spy = [0.01, -0.005, 0.002, 0.008, -0.003, 0.006]
    c = 0.003
    strat = [s + c for s in spy]
    m = spy_relative_metrics(strat, spy, timeframe="1Day")
    assert m["excess_return_annualized"] > 0.0
    # constant additive excess -> zero variance -> IR undefined
    assert m["information_ratio"] is None


def test_near_constant_excess_gives_very_high_ir():
    spy = [0.01, -0.005, 0.002, 0.008, -0.003, 0.006]
    # large positive mean excess, tiny noise -> huge IR
    noise = [1e-6, -1e-6, 1e-6, -1e-6, 1e-6, -1e-6]
    strat = [s + 0.01 + nz for s, nz in zip(spy, noise)]
    ir = information_ratio(strat, spy, bars_per_year("1Day", False))
    assert ir is not None
    assert ir > 1000.0  # mean >> tiny TE, annualized -> very large


# ---------------------------------------------------------------------------
# (c) zero tracking error -> IR is None (no divide-by-zero)
# ---------------------------------------------------------------------------
def test_zero_tracking_error_ir_none():
    spy = [0.02, 0.01, -0.01, 0.0]
    strat = list(spy)
    assert information_ratio(strat, spy, bars_per_year("1Day", False)) is None


# ---------------------------------------------------------------------------
# (d) length mismatch -> ValueError; empty -> ValueError
# ---------------------------------------------------------------------------
def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        information_ratio([0.01, 0.02, 0.03], [0.01, 0.02], bars_per_year("1Day", False))
    with pytest.raises(ValueError):
        spy_relative_metrics([0.01, 0.02], [0.01], timeframe="1Day")


def test_empty_series_raises():
    with pytest.raises(ValueError):
        spy_relative_metrics([], [], timeframe="1Day")
    with pytest.raises(ValueError):
        information_ratio([], [], bars_per_year("1Day", False))


def test_single_period_ir_none():
    # < 2 periods: sample stdev undefined -> IR None (not a crash)
    assert information_ratio([0.01], [0.005], bars_per_year("1Day", False)) is None


# ---------------------------------------------------------------------------
# (e) hand-computed small example: assert exact IR to several decimals.
# ---------------------------------------------------------------------------
def test_hand_computed_information_ratio_1day():
    # 4 periods. excess = strat - spy.
    strat = [0.020, 0.010, 0.030, 0.000]
    spy = [0.010, 0.015, 0.010, 0.005]
    # excess = [0.010, -0.005, 0.020, -0.005]
    excess = [0.010, -0.005, 0.020, -0.005]
    n = 4
    mean_e = sum(excess) / n  # = 0.020/4 = 0.005
    var = sum((e - mean_e) ** 2 for e in excess) / (n - 1)
    te = math.sqrt(var)
    bpy = bars_per_year("1Day", False)  # 252.0 for equities
    expected_ir = (mean_e / te) * math.sqrt(bpy)

    got = information_ratio(strat, spy, bpy)
    assert got is not None
    assert got == pytest.approx(expected_ir, rel=1e-9, abs=1e-9)

    # Pin the literal value too so a convention change is caught.
    # mean_e=0.005; var = sum([0.005^2, -0.010^2, 0.015^2, -0.010^2])/3
    #   = (0.000025 + 0.0001 + 0.000225 + 0.0001)/3 = 0.00045/3 = 0.00015
    #   te = sqrt(0.00015) = 0.0122474487...
    #   IR_per = 0.005 / 0.0122474487 = 0.40824829...
    #   annualized = 0.40824829 * sqrt(252) = 0.40824829 * 15.8745079 = 6.48068...
    assert bpy == 252.0
    assert got == pytest.approx(6.480740698, abs=1e-6)


def test_hand_computed_annualized_excess_return():
    # strat compounds [0.020,0.010,0.030,0.000]; spy [0.010,0.015,0.010,0.005]
    strat = [0.020, 0.010, 0.030, 0.000]
    spy = [0.010, 0.015, 0.010, 0.005]
    bpy = 252.0
    g_s = 1.020 * 1.010 * 1.030 * 1.000
    g_b = 1.010 * 1.015 * 1.010 * 1.005
    exp_s = g_s ** (bpy / 4) - 1.0
    exp_b = g_b ** (bpy / 4) - 1.0
    assert annualized_return(strat, bpy) == pytest.approx(exp_s, rel=1e-12)
    assert annualized_return(spy, bpy) == pytest.approx(exp_b, rel=1e-12)
    m = spy_relative_metrics(strat, spy, timeframe="1Day")
    assert m["excess_return_annualized"] == pytest.approx(exp_s - exp_b, rel=1e-12)


# ---------------------------------------------------------------------------
# Helper: returns_from_closes + align_returns_by_date
# ---------------------------------------------------------------------------
def test_returns_from_closes():
    closes = [100.0, 110.0, 99.0]
    r = returns_from_closes(closes)
    assert len(r) == 2
    assert r[0] == pytest.approx(0.10)
    assert r[1] == pytest.approx((99.0 - 110.0) / 110.0)


def test_align_returns_by_date_intersection_and_order():
    strat = {"2024-01-03": 0.02, "2024-01-01": 0.01, "2024-01-02": -0.01}
    spy = {"2024-01-02": 0.005, "2024-01-01": 0.002, "2024-01-04": 0.9}
    s, b, dates = align_returns_by_date(strat, spy)
    assert dates == ["2024-01-01", "2024-01-02"]  # sorted, common only
    assert s == [0.01, -0.01]
    assert b == [0.002, 0.005]


def test_align_no_common_dates_raises():
    with pytest.raises(ValueError):
        align_returns_by_date({"2024-01-01": 0.01}, {"2024-02-01": 0.02})


def test_annualization_uses_harness_convention_not_252_for_intraday():
    # 1Hour must NOT annualize with sqrt(252). Confirm bars_per_year differs
    # and that IR scales with it.
    bpy_day = bars_per_year("1Day", False)
    bpy_hour = bars_per_year("1Hour", False)
    assert bpy_hour != bpy_day  # would be equal only if we wrongly hardcoded
    strat = [0.02, 0.01, 0.03, 0.005]
    spy = [0.01, 0.015, 0.01, 0.004]
    ir_day = information_ratio(strat, spy, bpy_day)
    ir_hour = information_ratio(strat, spy, bpy_hour)
    # same per-period stats, different annualization factor
    assert ir_hour / ir_day == pytest.approx(math.sqrt(bpy_hour / bpy_day), rel=1e-9)
