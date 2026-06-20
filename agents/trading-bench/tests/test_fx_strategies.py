"""Tests for the FX strategies + cost model (strategies_candidates/fx_lane).

Locks the REAL contracts the lane depends on:
  (1) FxCostModel.cost_fraction is MONOTONIC in turnover (more |Δw| => more cost)
      and zero at zero turnover; the sensitivity grid is ordered.
  (2) NO-LEVERAGE INVARIANT: every strategy's target weights satisfy
      sum(|w|) <= 1.0 on every rebalance (the cash constraint), and the simulator
      ASSERTS it (a leveraged weight fn must blow up).
  (3) NO-LOOKAHEAD: a strategy's weight for the position held over day D is
      computed from closes <= D only — mutating a FUTURE close cannot change any
      earlier weight (the make-or-break property), demonstrated on the live
      simulator path.
  (4) NOT-ENOUGH-BARS GUARD: before a strategy has enough history to form its
      signal, it holds 0 gross (flat), never a guess.
  (5) cost-monotonicity at the BACKTEST level: higher half-spread bp => strictly
      lower net return for a turnover-positive strategy.

Network-free: a fake in-memory FX cache is injected by swapping the module memos
(mirrors test_fx_bars_cache.py and the leveraged_long_trend fake-cache tests).

Run: pytest tests/test_fx_strategies.py -q
"""
import math

import pytest

from runner import fx_bars_cache as fxc
from strategies_candidates.fx_lane import backtest_fx as bt
from strategies_candidates.fx_lane import strategies_fx as sf


# --------------------------------------------------------------------------- #
# Fake FX cache: inject several pairs of (date, close) into the module memos.
# --------------------------------------------------------------------------- #
def _install_pairs(monkeypatch, series_by_pair):
    """series_by_pair: {pair: [(date, close), ...]} ascending. Installs into the
    fxc memos and short-circuits get_daily so no disk/network is touched."""
    built = {}
    for pair, rows in series_by_pair.items():
        key = fxc._sym_key(pair)
        series = [{"date": d, "open": c, "high": c, "low": c,
                   "close": c, "adjclose": c, "volume": 0} for d, c in rows]
        monkeypatch.setitem(fxc._SERIES_MEMO, key, series)
        monkeypatch.setitem(fxc._DATES_MEMO, key, [r["date"] for r in series])
        built[key] = series

    def fake_get(sym, use_cache=True, refresh=False):
        return built[fxc._sym_key(sym)]
    monkeypatch.setattr(fxc, "get_daily", fake_get)
    return built


def _dates(n, start_day=1):
    # simple ascending business-ish dates within 2020 (month/day rollover safe)
    out = []
    y, m, d = 2020, 1, start_day
    for _ in range(n):
        out.append("%04d-%02d-%02d" % (y, m, d))
        d += 1
        if d > 28:
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
    return out


# =========================================================================== #
# (1) Cost model
# =========================================================================== #
def test_cost_zero_turnover_is_zero():
    cm = bt.FxCostModel(half_spread_bp=0.8)
    assert cm.cost_fraction(0.0) == 0.0


def test_cost_monotonic_in_turnover():
    cm = bt.FxCostModel(half_spread_bp=0.8)
    prev = -1.0
    for turn in [0.0, 0.1, 0.5, 1.0, 2.0]:
        c = cm.cost_fraction(turn)
        assert c >= prev, "cost not monotonic in turnover"
        prev = c
    # exact linearity: cost(1.0) == half_spread_bp/1e4
    assert abs(cm.cost_fraction(1.0) - 0.8 / 10_000.0) < 1e-15
    assert abs(cm.cost_fraction(2.0) - 2 * cm.cost_fraction(1.0)) < 1e-15


def test_cost_grid_is_ordered():
    grid = bt.FxCostModel.grid()
    bps = [g.half_spread_bp for g in grid]
    assert bps == sorted(bps)
    assert bps[0] == 0.5 and bps[-1] == 2.0


# =========================================================================== #
# (2) No-leverage invariant — simulator asserts gross <= 1.0
# =========================================================================== #
def test_simulator_rejects_leverage(monkeypatch):
    pairs = ["EURUSD=X", "GBPUSD=X"]
    dts = _dates(10)
    _install_pairs(monkeypatch, {p: [(d, 1.0 + 0.001 * i) for i, d in enumerate(dts)]
                                 for p in pairs})
    cal = dts
    pc = {p: bt.close_map(p) for p in pairs}
    # a weight fn that demands 1.5 gross => must trip the assert
    def levered(i, d):
        return {"EURUSD=X": 1.0, "GBPUSD=X": 0.5}
    with pytest.raises(AssertionError):
        bt.simulate_weighted(cal, pc, levered, bt.FxCostModel.baseline())


def test_strategies_never_exceed_unit_gross(monkeypatch):
    """All three strategies must keep sum(|w|) <= 1.0 on EVERY rebalance over a
    realistic multi-pair panel (the simulator would assert otherwise; we also
    check the raw weight dicts directly)."""
    pairs = list(fxc.FX_MAJORS)
    n = 400
    dts = _dates(n)
    # give each pair a distinct trend so signs differ across the basket
    import random
    rng = random.Random(7)
    series = {}
    for k, p in enumerate(pairs):
        px = 1.0 + 0.1 * k
        rows = []
        for i, d in enumerate(dts):
            px *= (1.0 + (0.0003 * (1 if k % 2 == 0 else -1)) + rng.uniform(-0.004, 0.004))
            rows.append((d, px))
        series[p] = rows
    _install_pairs(monkeypatch, series)
    cal = dts

    for strat in [sf.TrendBasket(), sf.CarryBasket(), sf.XSectionMomentum()]:
        strat.bind_calendar(cal)
        for i in range(len(cal)):
            w = strat.target_weights(i, cal[i], cal)
            gross = sum(abs(x) for x in w.values())
            assert gross <= 1.0 + 1e-9, (
                "%s exceeded unit gross at i=%d: %.6f" % (type(strat).__name__, i, gross))


# =========================================================================== #
# (3) No-lookahead — a FUTURE close cannot change an earlier weight
# =========================================================================== #
def test_strategy_signal_cannot_see_future(monkeypatch):
    """Run a strategy, capture every per-day weight dict, then mutate ONLY the
    final close of every pair to a wild value and recompute. Every weight for
    days strictly before the last must be byte-identical (the signal for day i
    uses closes <= cal[i], so a change at the last bar cannot reach back)."""
    pairs = list(fxc.FX_MAJORS)
    n = 300
    dts = _dates(n)
    base = {}
    for k, p in enumerate(pairs):
        rows = [(d, 1.0 + 0.1 * k + 0.002 * i) for i, d in enumerate(dts)]
        base[p] = rows

    def weights_for(series):
        _install_pairs(monkeypatch, series)
        cal = dts
        strat = sf.XSectionMomentum()
        strat.bind_calendar(cal)
        return [strat.target_weights(i, cal[i], cal) for i in range(len(cal))]

    w_base = weights_for(base)
    spiked = {p: list(rows) for p, rows in base.items()}
    for p in pairs:
        d_last, _ = spiked[p][-1]
        spiked[p][-1] = (d_last, 999.0)  # absurd final close
    w_spike = weights_for(spiked)

    # All weights for days < last must be identical.
    for i in range(len(w_base) - 1):
        assert w_base[i] == w_spike[i], (
            "weight at day %d changed after a FUTURE close mutation -> LOOKAHEAD" % i)


def test_trend_no_lookahead_on_simulator(monkeypatch):
    """End-to-end on the simulator: the equity curve up to the second-to-last
    day must be identical when only the FINAL bar of each pair is changed (the
    final bar only affects the LAST realized return, never an earlier weight)."""
    pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
    n = 250
    dts = _dates(n)
    base = {p: [(d, 1.0 + 0.1 * k + 0.0015 * i) for i, d in enumerate(dts)]
            for k, p in enumerate(pairs)}

    def equity_for(series):
        _install_pairs(monkeypatch, series)
        cal = dts
        pc = {p: bt.close_map(p) for p in pairs}
        strat = sf.TrendBasket(pairs=pairs)
        wf = sf.make_weight_fn(strat, cal)
        eq, _, _ = bt.simulate_weighted(cal, pc, wf, bt.FxCostModel.baseline())
        return eq

    eq_base = equity_for(base)
    spiked = {p: list(rows) for p, rows in base.items()}
    for p in pairs:
        d_last, _ = spiked[p][-1]
        spiked[p][-1] = (d_last, 5.0)
    eq_spike = equity_for(spiked)
    # equity[:-1] is decided entirely before the last bar -> identical
    for i in range(len(eq_base) - 1):
        assert abs(eq_base[i] - eq_spike[i]) < 1e-12, (
            "equity at day %d moved after a future-bar change -> LOOKAHEAD" % i)


# =========================================================================== #
# (4) Not-enough-bars guard
# =========================================================================== #
def test_trend_flat_until_warmed(monkeypatch):
    pairs = list(fxc.FX_MAJORS)
    n = 150
    dts = _dates(n)
    _install_pairs(monkeypatch, {p: [(d, 1.0 + 0.001 * i) for i, d in enumerate(dts)]
                                 for p in pairs})
    cal = dts
    strat = sf.TrendBasket(fast=20, slow=100)
    strat.bind_calendar(cal)
    # before index 99 (need 100 closes) every pair must be flat => empty book
    for i in range(0, 98):
        w = strat.target_weights(i, cal[i], cal)
        assert w == {} or all(v == 0.0 for v in w.values()), (
            "TrendBasket not flat at i=%d before warmup" % i)


def test_xsmom_flat_until_warmed(monkeypatch):
    pairs = list(fxc.FX_MAJORS)
    n = 200
    dts = _dates(n)
    _install_pairs(monkeypatch, {p: [(d, 1.0 + 0.001 * i) for i, d in enumerate(dts)]
                                 for p in pairs})
    cal = dts
    strat = sf.XSectionMomentum(lookback=120, skip=5)
    strat.bind_calendar(cal)
    # needs 120+5+1=126 closes; before that, flat.
    w = strat.target_weights(50, cal[50], cal)
    assert w == {}, "XSMom should be flat before lookback warmup"


# =========================================================================== #
# (5) Backtest-level cost monotonicity (higher bp => strictly lower net return)
# =========================================================================== #
def test_backtest_cost_monotonic(monkeypatch):
    """A turnover-positive strategy must return strictly less net as the
    half-spread rises. Build a panel that forces real rebalancing (alternating
    trends) and run XSMom at each grid cost."""
    pairs = list(fxc.FX_MAJORS)
    n = 400
    dts = _dates(n)
    import random
    rng = random.Random(3)
    series = {}
    for k, p in enumerate(pairs):
        px = 1.0 + 0.05 * k
        rows = []
        for i, d in enumerate(dts):
            # regime flips every 60 bars to force cross-sectional churn
            drift = 0.0006 if (i // 60 + k) % 2 == 0 else -0.0006
            px *= (1.0 + drift + rng.uniform(-0.003, 0.003))
            rows.append((d, px))
        series[p] = rows
    _install_pairs(monkeypatch, series)
    cal = dts
    pc = {p: bt.close_map(p) for p in pairs}

    rets = []
    for cm in bt.FxCostModel.grid():
        strat = sf.XSectionMomentum()
        wf = sf.make_weight_fn(strat, cal)
        eq, nreb, _ = bt.simulate_weighted(cal, pc, wf, cm)
        assert nreb > 0, "expected turnover for the cost test"
        rets.append(bt.stats_from_equity(eq).total_return_pct)
    assert all(rets[i] > rets[i + 1] for i in range(len(rets) - 1)), (
        "net return not strictly decreasing in cost: %s" % rets)
