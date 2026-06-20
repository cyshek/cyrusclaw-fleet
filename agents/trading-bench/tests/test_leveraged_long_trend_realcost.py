"""Tests for the REALISTIC-COST leveraged_long_trend engine
(backtest_daily_voltarget_realcost).

Locks the four contracts the parent task requires:
  (1) NO-LOOKAHEAD still holds on the realcost path: a FUTURE sleeve-price spike
      cannot change any prior held-day weight (mirrors the voltarget contract test,
      now with ER+spread costs active).
  (2) ER-DRAG MATH is correct: the daily expense charge is exactly
      (annual_ER / 252) * w_today on the sleeve-exposed fraction, and the (1-w)
      cash sleeve pays ZERO ER. Verified against a hand-computed closed form.
  (3) COST IS MONOTONIC in both bps and ER: raising per-side spread_bps (ER fixed)
      can only lower net total return; raising ER (bps fixed) can only lower it.
  (4) ZERO-COST REDUCTION: ER=0 and spread_bps_per_side=2 reduces EXACTLY (to FP
      tolerance) to the prior voltarget engine with switch_cost_bps=2 — proving the
      realcost daily loop is identical save for the two injected cost terms.

No network: monkeypatch the caches (mirrors test_leveraged_long_trend_voltarget.py).

Run: pytest tests/test_leveraged_long_trend_realcost.py -q
"""
import math

import pytest

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend import backtest_daily_voltarget as vt
from strategies_candidates.leveraged_long_trend import backtest_daily_voltarget_realcost as rc
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget_realcost import (
    RealCostParams, DEFAULT_EXPENSE_RATIO, DEFAULT_SPREAD_BPS,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS


# --------------------------------------------------------------------------- #
# Param resolution
# --------------------------------------------------------------------------- #
def test_resolved_er_uses_default_then_override():
    p = RealCostParams(sleeve="TQQQ")
    assert p.resolved_er() == DEFAULT_EXPENSE_RATIO["TQQQ"]
    p2 = RealCostParams(sleeve="TQQQ", expense_ratio_annual=0.0123)
    assert p2.resolved_er() == 0.0123
    # explicit 0.0 must be honored (NOT treated as "unset" -> default)
    p3 = RealCostParams(sleeve="UPRO", expense_ratio_annual=0.0)
    assert p3.resolved_er() == 0.0


def test_resolved_spread_uses_default_then_override():
    p = RealCostParams(sleeve="UPRO")
    assert p.resolved_spread_bps() == DEFAULT_SPREAD_BPS["UPRO"]
    p2 = RealCostParams(sleeve="UPRO", spread_bps_per_side=7.0)
    assert p2.resolved_spread_bps() == 7.0
    p3 = RealCostParams(sleeve="SPXL", spread_bps_per_side=0.0)
    assert p3.resolved_spread_bps() == 0.0


# --------------------------------------------------------------------------- #
# Fake cache (mirrors the voltarget test harness)
# --------------------------------------------------------------------------- #
class _FakeDBC:
    def __init__(self, series):
        self._s = {
            sym: [{"date": d, "adjclose": c, "open": c, "high": c,
                   "low": c, "close": c, "volume": 0} for d, c in rows]
            for sym, rows in series.items()
        }

    def get_daily(self, sym):
        return list(self._s[sym])


def _mk_dates(n):
    return ["2020-%02d-%02d" % (1 + i // 28, 1 + i % 28) for i in range(n)]


def _patch(monkeypatch, fake):
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)


# --------------------------------------------------------------------------- #
# (4) ZERO-COST REDUCTION to the prior engine
# --------------------------------------------------------------------------- #
def test_zero_er_spread2_reduces_to_voltarget(monkeypatch):
    """ER=0 and spread_bps_per_side=2 must reproduce the voltarget engine
    (switch_cost_bps=2) to FP tolerance, on a non-trivial vol-target series."""
    n = 300
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]  # always up after warmup
    px = 10.0
    sleeve = []
    for i in range(n):
        px = px * (1.03 if i % 3 else 0.98)
        sleeve.append((dates[i], px))
    bench = [(dates[i], 100.0 + 0.3 * i) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    _patch(monkeypatch, fake)

    pv = vt.VolTargetParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                            sma_window=200, vix_gate=False, use_tbill_cash=False,
                            switch_cost_bps=2.0)
    pr = RealCostParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                        sma_window=200, vix_gate=False, use_tbill_cash=False,
                        expense_ratio_annual=0.0, spread_bps_per_side=2.0)
    rv = vt.run_backtest_voltarget(pv)
    rr = rc.run_backtest_realcost(pr)
    ev, er = rv["strategy"]["equity"], rr["strategy"]["equity"]
    assert len(ev) == len(er)
    for a, b in zip(ev, er):
        assert abs(a - b) < 1e-12
    assert abs(rv["strategy"]["stats"]["total_return_pct"]
               - rr["strategy"]["stats"]["total_return_pct"]) < 1e-9
    # weights identical too (same sizing path)
    assert rv["strategy"]["weights"] == rr["strategy"]["weights"]


# --------------------------------------------------------------------------- #
# (2) ER-DRAG MATH — closed-form check
# --------------------------------------------------------------------------- #
def test_er_drag_math_closed_form_binary(monkeypatch):
    """Binary path (target=None), trend ALWAYS up so w=1 every held day, FLAT
    sleeve (zero sleeve return), zero cash, zero spread. Then the ONLY thing
    moving equity is the ER charge at w=1: each held day multiplies equity by
    (1 - ER/252). Over H held days, final equity = (1 - ER/252)**H exactly."""
    n = 260
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]   # always rising -> gate up
    sleeve = [(dates[i], 10.0) for i in range(n)]        # FLAT -> sleeve_ret = 0
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    _patch(monkeypatch, fake)

    ER = 0.0084
    p = RealCostParams(target_ann_vol=None, sma_window=200, vix_gate=False,
                       use_tbill_cash=False, expense_ratio_annual=ER,
                       spread_bps_per_side=0.0)
    r = rc.run_backtest_realcost(p)
    weights = r["strategy"]["weights"]
    # held days = those with w == 1.0 (after the 200-bar SMA warmup the gate is up)
    held = sum(1 for w in weights if w == 1.0)
    assert held > 0
    # since sleeve_ret=0, cash=0, spread=0, the per-day factor on held days is
    # exactly (1 - ER/252) and on flat (w=0) days it's 1.0.
    expected = (1.0 - ER / TRADING_DAYS) ** held
    got = r["strategy"]["equity"][-1]
    assert abs(got - expected) < 1e-12, (got, expected, held)


def test_er_charged_only_on_sleeve_fraction(monkeypatch):
    """ER must scale with the held WEIGHT: at a partial weight w<1 the daily ER
    charge is (ER/252)*w, NOT the full (ER/252). Verify the cumulative ER drag
    recorded equals sum over days of (ER/252)*w_today, and that the (1-w) cash
    portion contributes no ER."""
    n = 300
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]
    px = 10.0
    sleeve = []
    for i in range(n):
        px = px * (1.04 if i % 2 == 0 else 0.97)   # high vol -> partial weights
        sleeve.append((dates[i], px))
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    _patch(monkeypatch, fake)

    ER = 0.0090
    p = RealCostParams(target_ann_vol=0.20, vol_window=20, w_max=1.0,
                       sma_window=200, vix_gate=False, use_tbill_cash=False,
                       expense_ratio_annual=ER, spread_bps_per_side=0.0)
    r = rc.run_backtest_realcost(p)
    weights = r["strategy"]["weights"]
    # some held weights must be strictly between 0 and 1 (the partial-exposure case)
    assert any(0.0 < w < 1.0 for w in weights)
    expected_er_drag = sum((ER / TRADING_DAYS) * w for w in weights)
    got_er_drag = r["strategy"]["stats"]["cum_er_cost_drag_frac"]
    assert abs(got_er_drag - expected_er_drag) < 1e-12
    # per-day pos_log er_cost must equal (ER/252)*weight for that day
    for pl, w in zip(r["pos_log"], weights):
        assert abs(pl["er_cost"] - (ER / TRADING_DAYS) * w) < 1e-15


def test_er_zero_means_no_er_drag(monkeypatch):
    n = 120
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]
    sleeve = [(dates[i], 10.0 + 0.1 * i) for i in range(n)]
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    _patch(monkeypatch, fake)
    p = RealCostParams(target_ann_vol=None, sma_window=50, vix_gate=False,
                       use_tbill_cash=False, expense_ratio_annual=0.0,
                       spread_bps_per_side=0.0)
    r = rc.run_backtest_realcost(p)
    assert r["strategy"]["stats"]["cum_er_cost_drag_frac"] == 0.0


# --------------------------------------------------------------------------- #
# (3) MONOTONICITY in bps and ER
# --------------------------------------------------------------------------- #
def _build_voltarget_world():
    n = 320
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]
    px = 10.0
    sleeve = []
    for i in range(n):
        px = px * (1.03 if i % 3 else 0.97)
        sleeve.append((dates[i], px))
    bench = [(dates[i], 100.0 + 0.2 * i) for i in range(n)]
    return {"TQQQ": sleeve, "QQQ": under, "^GSPC": bench}


def test_net_return_monotonic_decreasing_in_spread(monkeypatch):
    fake = _FakeDBC(_build_voltarget_world())
    _patch(monkeypatch, fake)
    prev = None
    for bps in [0.0, 2.0, 5.0, 10.0, 20.0, 40.0]:
        p = RealCostParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                           sma_window=200, vix_gate=False, use_tbill_cash=False,
                           expense_ratio_annual=0.0090, spread_bps_per_side=bps)
        tot = rc.run_backtest_realcost(p)["strategy"]["stats"]["total_return_pct"]
        if prev is not None:
            assert tot <= prev + 1e-9, ("spread %g raised return" % bps)
        prev = tot


def test_net_return_monotonic_decreasing_in_er(monkeypatch):
    fake = _FakeDBC(_build_voltarget_world())
    _patch(monkeypatch, fake)
    prev = None
    for er in [0.0, 0.0030, 0.0060, 0.0090, 0.0150]:
        p = RealCostParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                           sma_window=200, vix_gate=False, use_tbill_cash=False,
                           expense_ratio_annual=er, spread_bps_per_side=2.0)
        tot = rc.run_backtest_realcost(p)["strategy"]["stats"]["total_return_pct"]
        if prev is not None:
            assert tot <= prev + 1e-9, ("ER %g raised return" % er)
        prev = tot


# --------------------------------------------------------------------------- #
# (1) NO-LOOKAHEAD on the realcost path
# --------------------------------------------------------------------------- #
def test_realcost_no_lookahead_future_vol_spike(monkeypatch):
    """A sleeve-price spike on the FINAL day only must not change ANY prior
    held-day weight, even with ER + spread costs active. Weights must be
    byte-identical between the base and spiked runs."""
    n = 300
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]
    sleeve = [(dates[i], 10.0 + 0.05 * i) for i in range(n)]
    bench = [(dates[i], 100.0) for i in range(n)]

    def run_with(sleeve_series):
        fake = _FakeDBC({"TQQQ": sleeve_series, "QQQ": under, "^GSPC": bench})
        _patch(monkeypatch, fake)
        p = RealCostParams(target_ann_vol=0.20, vol_window=20, w_max=1.0,
                           sma_window=200, vix_gate=False, use_tbill_cash=False,
                           expense_ratio_annual=0.0090, spread_bps_per_side=4.0)
        return rc.run_backtest_realcost(p)

    r_base = run_with(sleeve)
    spiked = list(sleeve)
    spiked[-1] = (dates[-1], 10_000.0)
    r_spike = run_with(spiked)

    w_base = r_base["strategy"]["weights"]
    w_spike = r_spike["strategy"]["weights"]
    assert len(w_base) == len(w_spike)
    for i in range(len(w_base)):
        assert abs(w_base[i] - w_spike[i]) < 1e-12, (
            "weight at held-day %d changed after a FUTURE spike -> LOOKAHEAD" % i)
    # the per-day ER/trade costs for all days EXCEPT the last must also match
    # (they depend only on weights, which are unchanged); the last day's costs
    # also depend only on its weight, which is decided from data <= prior day.
    for i in range(len(r_base["pos_log"])):
        assert abs(r_base["pos_log"][i]["er_cost"]
                   - r_spike["pos_log"][i]["er_cost"]) < 1e-15
        assert abs(r_base["pos_log"][i]["trade_cost"]
                   - r_spike["pos_log"][i]["trade_cost"]) < 1e-15


def test_costs_strictly_reduce_equity_vs_costless(monkeypatch):
    """Sanity: with real ER+spread, net equity is strictly below the costless
    (ER=0, spread=0) run whenever the book is ever in-market."""
    fake = _FakeDBC(_build_voltarget_world())
    _patch(monkeypatch, fake)
    base = RealCostParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                          sma_window=200, vix_gate=False, use_tbill_cash=False,
                          expense_ratio_annual=0.0, spread_bps_per_side=0.0)
    costed = RealCostParams(target_ann_vol=0.25, vol_window=20, w_max=1.0,
                            sma_window=200, vix_gate=False, use_tbill_cash=False,
                            expense_ratio_annual=0.0090, spread_bps_per_side=4.0)
    eb = rc.run_backtest_realcost(base)["strategy"]["equity"][-1]
    ec = rc.run_backtest_realcost(costed)["strategy"]["equity"][-1]
    assert ec < eb
