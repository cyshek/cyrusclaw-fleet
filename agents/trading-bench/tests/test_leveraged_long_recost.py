"""Tests for the REALISTIC re-costing layer of the vol-targeted leveraged-long engine.

Locks the cost model's REAL contract (not just "it runs"):
  1. Zero rebalances => the per-rebalance turnover cost adds NOTHING (only the
     holding/ER drag and gross returns remain).
  2. Higher per-rebalance bps STRICTLY reduces net return whenever there is any
     turnover (monotonic in turnover cost).
  3. Higher expense ratio STRICTLY reduces net return whenever any sleeve weight
     is held (monotonic in ER), and ER=0 with held weight leaves return above an
     ER>0 run.
  4. gross_factors round-trips the engine equity to ~machine precision, and the
     "optimistic" level (2bps, ER 0) reproduces the engine's own equity exactly.
  5. The holding drag is charged ONLY on the sleeve-invested portion w (cash-parked
     capital pays no fund fee): an all-cash (w=0) book pays zero ER drag even at a
     high ER, while a fully-invested (w=1) book pays the full ER.
  6. n_rebalances counts weight changes (matches the engine convention).

No network: monkeypatch the caches (mirrors test_leveraged_long_trend_voltarget.py).

Run: pytest tests/test_leveraged_long_recost.py -q
"""
import math

import pytest

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend import backtest_daily_voltarget as vt
from strategies_candidates.leveraged_long_trend import recost_voltarget as rc
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import VolTargetParams
from strategies_candidates.leveraged_long_trend.recost_voltarget import (
    CostModel, gross_factors, rebuild_equity, recost_run, _n_rebalances,
    ENGINE_BASELINE_BPS,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS


# --------------------------------------------------------------------------- #
# CostModel arithmetic
# --------------------------------------------------------------------------- #
def test_cost_model_per_rebal_is_sum_of_components():
    cm = CostModel("x", half_spread_bps=3.0, slippage_bps=2.0, commission_bps=0.0,
                   expense_ratio_ann=0.0095)
    assert cm.per_rebal_bps == 5.0
    d = cm.to_dict()
    assert d["per_rebal_bps_total"] == 5.0
    assert abs(d["expense_ratio_ann_pct"] - 0.95) < 1e-9


def test_named_levels_optimistic_is_engine_anchor():
    # the optimistic level must be the 2bps / ER-0 audit anchor.
    opt = next(c for c in rc.COST_LEVELS if c.name == "optimistic")
    assert abs(opt.per_rebal_bps - ENGINE_BASELINE_BPS) < 1e-12
    assert opt.expense_ratio_ann == 0.0
    # realistic & pessimistic must be strictly harsher on BOTH dials.
    real = next(c for c in rc.COST_LEVELS if c.name == "realistic")
    pess = next(c for c in rc.COST_LEVELS if c.name == "pessimistic")
    assert real.per_rebal_bps > opt.per_rebal_bps
    assert pess.per_rebal_bps > real.per_rebal_bps
    assert real.expense_ratio_ann > 0.0
    assert pess.expense_ratio_ann >= real.expense_ratio_ann


# --------------------------------------------------------------------------- #
# gross_factors / rebuild_equity unit contracts (synthetic, no engine)
# --------------------------------------------------------------------------- #
def test_gross_factors_roundtrip_reconstructs_engine_equity():
    # Build a synthetic engine equity exactly as the engine would, then confirm
    # gross_factors -> rebuild at the SAME (2bps, ER0) reproduces it.
    weights = [0.0, 0.5, 0.5, 1.0, 0.3, 0.0, 0.0, 0.8]
    blended = [0.01, -0.02, 0.005, 0.03, -0.01, 0.0, 0.002, 0.04]
    bps = ENGINE_BASELINE_BPS
    eq = [1.0]
    prev = 0.0
    for i, w in enumerate(weights):
        cost = (bps / 1e4) * abs(w - prev)
        eq.append(eq[-1] * (1.0 + blended[i]) * (1.0 - cost))
        prev = w
    g = gross_factors(eq, weights)
    # recovered gross factor must equal (1 + blended)
    for i in range(len(weights)):
        assert abs(g[i] - (1.0 + blended[i])) < 1e-12
    # rebuild at optimistic (2bps, ER0) must reproduce eq
    anchor = CostModel("a", half_spread_bps=2.0, slippage_bps=0.0,
                       commission_bps=0.0, expense_ratio_ann=0.0)
    reb = rebuild_equity(g, weights, anchor)
    for i in range(len(eq)):
        assert abs(reb[i] - eq[i]) < 1e-12


def test_zero_rebalance_adds_zero_turnover_cost():
    # Constant weight after entry => only ONE weight change at i=0 (0 -> w).
    # Compare a model with high per_rebal but ER=0 against gross: the ONLY
    # difference must be the single entry charge, nothing per-day after.
    w = 0.7
    weights = [w] * 50  # but w_{-1}=0 so there's a single 0->0.7 entry at i=0
    g = [1.0] * 50      # flat gross => isolate cost
    cm = CostModel("hi", half_spread_bps=50.0, slippage_bps=50.0,
                   commission_bps=0.0, expense_ratio_ann=0.0)
    eq = rebuild_equity(g, weights, cm)
    entry_cost = (cm.per_rebal_bps / 1e4) * w
    # equity drops once by the entry charge, then is flat (no ER, flat gross).
    assert abs(eq[1] - (1.0 - entry_cost)) < 1e-12
    for k in range(2, len(eq)):
        assert abs(eq[k] - eq[1]) < 1e-12  # no further turnover cost
    # And if weight NEVER changes from 0, zero turnover cost at all.
    eq0 = rebuild_equity([1.0] * 50, [0.0] * 50, cm)
    assert all(abs(v - 1.0) < 1e-15 for v in eq0)


def test_higher_per_rebal_bps_strictly_reduces_net_when_turnover():
    # alternating weights => lots of turnover; flat gross isolates cost effect.
    weights = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    g = [1.0] * len(weights)
    lo = CostModel("lo", half_spread_bps=1.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=0.0)
    hi = CostModel("hi", half_spread_bps=10.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=0.0)
    eq_lo = rebuild_equity(g, weights, lo)[-1]
    eq_hi = rebuild_equity(g, weights, hi)[-1]
    assert eq_hi < eq_lo  # strictly more cost => strictly less net


def test_monotonic_in_per_rebal_across_a_grid():
    weights = [0.0, 0.6, 0.2, 0.9, 0.1, 0.7]
    g = [1.0] * len(weights)
    finals = []
    for bps in (0.0, 2.0, 5.0, 12.0, 30.0):
        cm = CostModel("c", half_spread_bps=bps, slippage_bps=0.0,
                       commission_bps=0.0, expense_ratio_ann=0.0)
        finals.append(rebuild_equity(g, weights, cm)[-1])
    # strictly decreasing as bps increases
    for a, b in zip(finals, finals[1:]):
        assert b < a


def test_higher_expense_ratio_strictly_reduces_net_when_held():
    # constant full weight, flat gross => only ER drag bites; higher ER => lower.
    weights = [1.0] * 252  # one year fully invested
    g = [1.0] * 252
    base = CostModel("er0", half_spread_bps=0.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=0.0)
    er1 = CostModel("er1", half_spread_bps=0.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=0.0095)
    er2 = CostModel("er2", half_spread_bps=0.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=0.02)
    e0 = rebuild_equity(g, weights, base)[-1]
    e1 = rebuild_equity(g, weights, er1)[-1]
    e2 = rebuild_equity(g, weights, er2)[-1]
    assert e0 == 1.0          # no ER, flat gross, single entry has zero cost here? w_{-1}=0 -> entry but per_rebal=0
    assert e1 < e0
    assert e2 < e1
    # ~0.95%/yr over a year of full investment should cost ~0.95% (geometric ~0.945%)
    assert abs((1.0 - e1) - 0.0095) < 5e-4


def test_expense_ratio_charged_only_on_invested_portion():
    # all-cash book (w=0 every day) pays NO ER drag even at a huge ER.
    weights = [0.0] * 100
    g = [1.0] * 100
    big_er = CostModel("bigER", half_spread_bps=0.0, slippage_bps=0.0,
                       commission_bps=0.0, expense_ratio_ann=0.50)
    eq_cash = rebuild_equity(g, weights, big_er)
    assert all(abs(v - 1.0) < 1e-15 for v in eq_cash)
    # a half-invested book pays exactly half the daily ER drag of a full book.
    er = 0.12
    cm = CostModel("c", half_spread_bps=0.0, slippage_bps=0.0, commission_bps=0.0, expense_ratio_ann=er)
    eq_full = rebuild_equity([1.0] * 2, [1.0, 1.0], cm)
    eq_half = rebuild_equity([1.0] * 2, [0.5, 0.5], cm)
    # day-1 drag: full = er/252, half = 0.5*er/252
    full_drag = 1.0 - eq_full[1]
    half_drag = 1.0 - eq_half[1]
    assert abs(half_drag - 0.5 * full_drag) < 1e-12


def test_n_rebalances_counts_weight_changes():
    assert _n_rebalances([0.0, 0.0, 0.0]) == 0
    assert _n_rebalances([1.0, 1.0, 1.0]) == 1          # 0->1 once
    assert _n_rebalances([0.0, 1.0, 0.0, 1.0]) == 3     # 0->1, 1->0, 0->1
    assert _n_rebalances([0.5, 0.5, 0.6, 0.6]) == 2     # 0->0.5, 0.5->0.6


# --------------------------------------------------------------------------- #
# End-to-end through the engine (fake cache), the way the report runs it.
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


def _fake_engine_result(monkeypatch, target=0.25):
    n = 260
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]  # always up after warmup
    # mild-vol sleeve so weights land strictly between 0 and 1 (real turnover).
    sleeve = []
    px = 10.0
    for i in range(n):
        px = px * (1.012 if i % 2 == 0 else 0.995)
        sleeve.append((dates[i], px))
    bench = [(dates[i], 100.0 + 0.3 * i) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    p = VolTargetParams(target_ann_vol=target, vol_window=20, sma_window=200,
                        vix_gate=False, use_tbill_cash=False, switch_cost_bps=2.0)
    return vt.run_backtest_voltarget(p)


def test_optimistic_recost_reproduces_engine_total_return(monkeypatch):
    r = _fake_engine_result(monkeypatch)
    engine_tot = r["strategy"]["stats"]["total_return_pct"]
    opt = next(c for c in rc.COST_LEVELS if c.name == "optimistic")
    out = recost_run(r, opt)
    # optimistic (2bps, ER0) == engine's own flat-2bps cost => same total return.
    assert abs(out["full"]["totalRet_pct"] - round(engine_tot, 1)) < 0.15


def test_realistic_and_pessimistic_reduce_return_vs_optimistic(monkeypatch):
    r = _fake_engine_result(monkeypatch)
    levels = {cm.name: recost_run(r, cm)["stats"]["total_return_pct"] for cm in rc.COST_LEVELS}
    # strictly: optimistic >= er_only >= realistic >= pessimistic (more cost, less return),
    # with at least one strict drop (there IS turnover + held weight here).
    assert levels["optimistic"] >= levels["er_only"] >= levels["realistic"] >= levels["pessimistic"]
    assert levels["optimistic"] > levels["pessimistic"]


def test_recost_run_emits_oos_fields(monkeypatch):
    r = _fake_engine_result(monkeypatch)
    out = recost_run(r, rc.COST_LEVELS[0])
    for k in ("cost_level", "cost_model", "stats", "full",
              "is_net_ret_pct", "oos_net_ret_pct", "oos_net_maxdd_pct"):
        assert k in out
    assert math.isfinite(out["oos_net_ret_pct"])
