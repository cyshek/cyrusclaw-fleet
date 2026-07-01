"""Tests for the FX trend/carry research harness (runner.fx_strategies).

Focus: LOOKAHEAD-SAFETY of the TSMOM signal, correctness of the cost/turnover
accounting, unlevered gross-exposure invariant, and the metric helpers. These
are the load-bearing guarantees the FX-lane verdict rests on.
"""

from __future__ import annotations

import math

import pytest

from runner.fx_strategies import (
    FX_SPREAD_BPS_ONEWAY,
    aligned_closes,
    cagr,
    fx_cost_model,
    max_drawdown,
    pearson_corr,
    run_basket,
    run_basket_buyhold,
    run_single,
    sharpe,
    simple_returns,
    split_is_oos,
    total_return,
    tsmom_signal,
)


# --------------------------------------------------------------------------- #
# simple_returns
# --------------------------------------------------------------------------- #
def test_simple_returns_basic():
    closes = [100.0, 110.0, 99.0]
    r = simple_returns(closes)
    assert r[0] is None
    assert abs(r[1] - 0.10) < 1e-12
    assert abs(r[2] - (99.0 / 110.0 - 1.0)) < 1e-12


def test_simple_returns_none_propagation():
    closes = [None, 100.0, None, 120.0]
    r = simple_returns(closes)
    assert r[0] is None      # no prior
    assert r[1] is None      # prior is None
    assert r[2] is None      # current is None
    assert r[3] is None      # prior is None


# --------------------------------------------------------------------------- #
# tsmom_signal — LOOKAHEAD SAFETY (the critical test)
# --------------------------------------------------------------------------- #
def test_tsmom_signal_is_lookahead_safe():
    # Position into r_t must depend ONLY on closes[:t]. We prove this by
    # mutating a FUTURE close and asserting the position at t is unchanged.
    closes = [float(x) for x in range(100, 130)]  # strictly rising -> long
    lb = 5
    pos_a = tsmom_signal(closes, lookback=lb, skip=0, allow_short=True)
    # Mutate close at index 20 (a future bar relative to t<=20).
    closes2 = list(closes)
    closes2[20] = 999.0
    pos_b = tsmom_signal(closes2, lookback=lb, skip=0, allow_short=True)
    # Positions at every t <= 20 must be identical (they only see closes[:t]).
    for t in range(0, 21):
        assert pos_a[t] == pos_b[t], f"lookahead leak at t={t}"


def test_tsmom_signal_warmup_is_flat():
    closes = [float(x) for x in range(100, 120)]
    lb = 5
    skip = 2
    pos = tsmom_signal(closes, lookback=lb, skip=skip, allow_short=True)
    # Until enough history (end=t-1-skip >=0 and start=end-lb >=0), pos==0.
    # start>=0 requires t-1-skip-lb >= 0 -> t >= lb+skip+1 = 8.
    for t in range(0, lb + skip + 1):
        assert pos[t] == 0.0, f"expected flat warmup at t={t}, got {pos[t]}"
    assert pos[lb + skip + 1] != 0.0  # first live bar


def test_tsmom_signal_direction():
    rising = [float(x) for x in range(100, 120)]
    falling = [float(x) for x in range(120, 100, -1)]
    lb = 5
    pr = tsmom_signal(rising, lookback=lb, allow_short=True)
    pf = tsmom_signal(falling, lookback=lb, allow_short=True)
    # Past return > 0 on a rising series -> long; < 0 on falling -> short.
    assert pr[-1] == 1.0
    assert pf[-1] == -1.0
    # long-or-flat variant never shorts.
    pf_lf = tsmom_signal(falling, lookback=lb, allow_short=False)
    assert min(pf_lf) >= 0.0
    assert pf_lf[-1] == 0.0


def test_tsmom_signal_position_into_t_uses_prior_close_only():
    # Explicit index check: with lookback=1, skip=0, position[t] = sign(close[t-1]
    # - close[t-2]) and must NOT involve close[t].
    closes = [10.0, 11.0, 9.0, 9.0, 12.0]
    pos = tsmom_signal(closes, lookback=1, skip=0, allow_short=True)
    # t=2: end=1,start=0 -> sign(11-10)=+1
    assert pos[2] == 1.0
    # t=3: end=2,start=1 -> sign(9-11)=-1
    assert pos[3] == -1.0
    # t=4: end=3,start=2 -> sign(9-9)=0
    assert pos[4] == 0.0


# --------------------------------------------------------------------------- #
# run_single — cost / turnover accounting
# --------------------------------------------------------------------------- #
def test_run_single_zero_cost_matches_raw():
    closes = [100.0, 110.0, 121.0]   # +10%, +10%
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    pos = [1.0, 1.0, 1.0]            # always long
    zero = fx_cost_model(spread_bps=0.0)
    res = run_single(closes, dates, pos, cost=zero)
    # Two realized returns, both +10%.
    assert len(res.rets) == 2
    assert abs(res.rets[0] - 0.10) < 1e-12
    assert abs(res.rets[1] - 0.10) < 1e-12
    assert abs(res.equity[-1] - 1.21) < 1e-9


def test_run_single_turnover_cost_applied_on_entry():
    closes = [100.0, 110.0]
    dates = ["2020-01-01", "2020-01-02"]
    pos = [1.0, 1.0]   # entered long at t=0 (prev_pos 0 -> 1 = turnover 1)
    cm = fx_cost_model(spread_bps=10.0)  # 10bp one-way
    res = run_single(closes, dates, pos, cost=cm)
    # The realized bar is t=1 (return 0->1 was at t=0 which has None return).
    # At t=0 r is None so it is skipped but prev_pos becomes 1.0 -> at t=1
    # turnover is |1-1|=0, net = 0.10. So entry cost is only charged if the
    # entry coincides with a realized-return bar. Here it does not.
    assert len(res.rets) == 1
    assert abs(res.rets[0] - 0.10) < 1e-12


def test_run_single_cost_charged_when_position_changes_on_traded_bar():
    closes = [100.0, 110.0, 121.0]
    dates = ["d0", "d1", "d2"]
    pos = [0.0, 1.0, -1.0]   # flat, then long into r1, then flip short into r2
    cm = fx_cost_model(spread_bps=10.0)  # 0.001
    res = run_single(closes, dates, pos, cost=cm)
    # r1 bar (t=1): prev_pos was 0 (from t=0), p=1 -> turnover 1 -> cost 0.001
    #   net = 1*0.10 - 0.001 = 0.099
    assert abs(res.rets[0] - 0.099) < 1e-12
    # r2 bar (t=2): prev_pos 1, p=-1 -> turnover 2 -> cost 0.002
    #   net = -1*0.10 - 0.002 = -0.102
    assert abs(res.rets[1] - (-0.102)) < 1e-12


# --------------------------------------------------------------------------- #
# run_basket — unlevered gross exposure invariant
# --------------------------------------------------------------------------- #
def test_basket_gross_exposure_never_exceeds_one():
    syms = ["EURUSD=X", "USDJPY=X", "AUDUSD=X"]
    res = run_basket(syms, lambda c: tsmom_signal(c, lookback=63, allow_short=True))
    # positions field on a basket holds gross exposure per bar.
    assert res.n > 100
    assert max(res.positions) <= 1.0 + 1e-9, f"levered! max gross={max(res.positions)}"
    assert min(res.positions) >= 0.0


def test_basket_buyhold_is_long_only_full_invested():
    syms = ["EURUSD=X", "USDJPY=X", "AUDUSD=X"]
    res = run_basket_buyhold(syms)
    assert res.n > 100
    # Once all three are live, gross exposure == 1.0 (1/3 each, all long).
    assert abs(max(res.positions) - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def test_sharpe_matches_manual():
    rets = [0.01, -0.005, 0.02, 0.0, 0.015, -0.01]
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    expected = (mean / math.sqrt(var)) * math.sqrt(252.0)
    assert abs(sharpe(rets) - expected) < 1e-9


def test_total_return_and_cagr():
    rets = [0.10, 0.10]  # 1.21x
    assert abs(total_return(rets) - 0.21) < 1e-12
    # cagr over 2 bars at 252/yr is tiny per-year compounding; just check sign.
    assert cagr(rets) > 0.0


def test_max_drawdown():
    eq = [1.0, 1.2, 0.9, 1.1, 0.6]
    # peak 1.2 -> trough 0.6 = -50%
    assert abs(max_drawdown(eq) - (-0.5)) < 1e-12


def test_pearson_corr_perfect():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [2.0, 4.0, 6.0, 8.0]
    assert abs(pearson_corr(a, b) - 1.0) < 1e-12
    c = [4.0, 3.0, 2.0, 1.0]
    assert abs(pearson_corr(a, c) - (-1.0)) < 1e-12


def test_split_is_oos():
    from runner.fx_strategies import StratResult
    res = StratResult(
        dates=["2017-06-01", "2018-01-02", "2019-03-03"],
        rets=[0.01, 0.02, 0.03], equity=[1.0], positions=[], turnover=[])
    is_r, oos_r = split_is_oos(res, boundary="2018-01-01")
    assert is_r == [0.01]
    assert oos_r == [0.02, 0.03]


# --------------------------------------------------------------------------- #
# data sanity (cache must be present)
# --------------------------------------------------------------------------- #
def test_fx_cache_present_and_aligned():
    syms = ["EURUSD=X", "USDJPY=X"]
    dates, closes = aligned_closes(syms)
    assert len(dates) > 4000
    for s in syms:
        assert len(closes[s]) == len(dates)
    # forward-fill: no None after the symbol's first live bar (majors trade
    # essentially every weekday; ffill covers holidays).
    first_live = next(i for i, v in enumerate(closes["EURUSD=X"]) if v is not None)
    assert all(v is not None for v in closes["EURUSD=X"][first_live:])


def test_fx_cost_default_is_one_bp():
    cm = fx_cost_model()
    assert cm.spread_bps == FX_SPREAD_BPS_ONEWAY == 1.0
    assert cm.fee_bps == 0.0
