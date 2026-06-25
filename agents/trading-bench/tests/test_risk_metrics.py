"""Unit tests for runner.risk_metrics (Sortino + Calmar on daily-P&L series)."""

import math
from datetime import date

import pytest

from runner import risk_metrics as rm


def _series(values):
    """Build a {date: pnl} dict over consecutive days from a list of values."""
    return {date(2026, 1, 1 + i): v for i, v in enumerate(values)}


# ---- daily_values / ordering -------------------------------------------------

def test_daily_values_sorted_by_date():
    d = {date(2026, 1, 3): 3.0, date(2026, 1, 1): 1.0, date(2026, 1, 2): 2.0}
    assert rm.daily_values(d) == [1.0, 2.0, 3.0]


def test_empty_series_is_safe():
    assert rm.daily_values({}) == []
    assert rm.downside_deviation([]) is None
    assert rm.sortino([]) is None
    assert rm.calmar([]) is None
    assert rm.max_drawdown([]) == 0.0


# ---- downside deviation ------------------------------------------------------

def test_downside_deviation_basic():
    # values: +2, -3, +1, -4  -> shortfalls vs 0: 0,3,0,4 ; sq=0,9,0,16 ; mean over 4 =6.25
    vals = [2.0, -3.0, 1.0, -4.0]
    dd = rm.downside_deviation(vals, target=0.0)
    assert dd == pytest.approx(math.sqrt(6.25))  # 2.5


def test_downside_deviation_zero_when_no_losers():
    assert rm.downside_deviation([1.0, 2.0, 3.0]) == 0.0


# ---- sortino -----------------------------------------------------------------

def test_sortino_known_value_unannualized():
    # mean of [2,-3,1,-4] = -1.0 ; dd = 2.5 ; ratio = -0.4
    vals = [2.0, -3.0, 1.0, -4.0]
    s = rm.sortino(vals, annualize=False)
    assert s == pytest.approx(-0.4)


def test_sortino_annualized_scales_by_sqrt252():
    vals = [2.0, -3.0, 1.0, -4.0]
    base = rm.sortino(vals, annualize=False)
    ann = rm.sortino(vals, annualize=True)
    assert ann == pytest.approx(base * math.sqrt(252))


def test_sortino_undefined_when_no_downside():
    # all-positive -> downside dev 0 -> None, NOT +inf
    assert rm.sortino([1.0, 2.0, 3.0]) is None


def test_sortino_none_for_single_day():
    assert rm.sortino([5.0]) is None


def test_sortino_positive_when_mostly_up_with_small_dip():
    vals = [10.0, 12.0, -1.0, 11.0, 9.0]
    s = rm.sortino(vals)
    assert s is not None and s > 0


# ---- max drawdown ------------------------------------------------------------

def test_max_drawdown_simple_path():
    # cum: +10, +5(-5 day), +15, +5(-10 day) -> peak 10 then 15; worst dd = 15-5 =10
    vals = [10.0, -5.0, 10.0, -10.0]
    assert rm.max_drawdown(vals) == pytest.approx(10.0)


def test_max_drawdown_zero_for_monotone_up():
    assert rm.max_drawdown([1.0, 2.0, 3.0]) == 0.0


def test_max_drawdown_counts_initial_negative_vs_zero_peak():
    # first day negative: equity starts at 0 peak, cum=-3 -> dd=3
    vals = [-3.0, 1.0]
    assert rm.max_drawdown(vals) == pytest.approx(3.0)


# ---- calmar ------------------------------------------------------------------

def test_calmar_known_value():
    # vals mean = (10-5+10-10)/4 = 1.25 ; annual = 1.25*252 = 315 ; mdd = 10 ; calmar = 31.5
    vals = [10.0, -5.0, 10.0, -10.0]
    c = rm.calmar(vals)
    assert c == pytest.approx(31.5)


def test_calmar_undefined_when_no_drawdown():
    assert rm.calmar([1.0, 2.0, 3.0]) is None


def test_calmar_none_for_single_day():
    assert rm.calmar([5.0]) is None


# ---- bundle ------------------------------------------------------------------

def test_compute_for_series_bundle_keys_and_counts():
    out = rm.compute_for_series(_series([2.0, -3.0, 1.0, -4.0]))
    assert out["n_closed_days"] == 4
    assert out["n_down_days"] == 2
    assert out["sortino"] == pytest.approx(-0.4 * math.sqrt(252))
    # cum path: 2, -1, 0, -4 ; peak starts at 2 ; dd at -1 ->3, at 0 ->2, at -4 ->6 ; mdd=6
    assert out["max_drawdown_usd"] == pytest.approx(6.0)


def test_compute_for_series_all_positive_undefined_ratios():
    out = rm.compute_for_series(_series([1.0, 2.0, 3.0]))
    assert out["sortino"] is None
    assert out["calmar"] is None
    assert out["max_drawdown_usd"] == 0.0
    assert out["n_down_days"] == 0


def test_compute_for_series_empty():
    out = rm.compute_for_series({})
    assert out["n_closed_days"] == 0
    assert out["sortino"] is None
    assert out["calmar"] is None
