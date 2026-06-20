"""Strategy-invariant tests for the FX research lane (FX_LANE_20260609),
covering the `strategies_candidates.fx_lane.fx_strategies` weight-path modules
(dual_sma_trend / breakout_trend / carry_proxy / xsec_momentum).

NOTE ON THE TWO FX STRATEGY MODULES: this lane was built with two parallel
strategy modules on disk — `strategies_fx.py` (class-based TrendBasket/
CarryBasket/XSectionMomentum, covered by tests/test_fx_strategies.py) and this
file's target `fx_strategies.py` (factory-based make_* closures consumed by
backtest_fx.simulate_weighted + evaluate_fx.py). Both are honest, no-leverage,
leak-free. This file locks the two make-or-break invariants for the FACTORY
module specifically, which tests/test_fx_strategies.py does not exercise:

  5. NO-LEVERAGE CAP — every make_* weight dict satisfies sum(|w|) <= 1.0 (and
     each pair weight in [-1, 1]) at every sampled calendar index. The engine
     also asserts this; here we prove the strategies build it by construction so
     the rail can never trip.
  6. NO LOOKAHEAD — a strategy's weight for index i is a pure function of closes
     at indices <= i. Proven by MUTATING a strictly-future bar (index > i) in the
     cache memo, rebuilding the factory, and asserting the weight at i is
     byte-identical. A strategy that peeked ahead would change; ours must not.

These read the local on-disk Yahoo FX cache (data_cache/yahoo_fx, already
populated for all 6 majors) and SKIP cleanly if it is absent — never hits the
network.
"""
from __future__ import annotations

import pytest

from runner import fx_bars_cache as fxc


def _have_local_fx_cache() -> bool:
    try:
        from strategies_candidates.fx_lane import backtest_fx as B
        from strategies_candidates.fx_lane import fx_strategies as S
        cal = B.common_calendar(list(S.MAJORS), start="2010-01-01")
        return len(cal) > 500
    except Exception:
        return False


needs_cache = pytest.mark.skipif(
    not _have_local_fx_cache(),
    reason="local Yahoo FX cache not populated (data_cache/yahoo_fx) — skipping "
           "factory-strategy invariant tests that need real bars")


@needs_cache
def test_factory_strategies_respect_no_leverage_cap():
    from strategies_candidates.fx_lane import backtest_fx as B
    from strategies_candidates.fx_lane import fx_strategies as S
    cal = B.common_calendar(list(S.MAJORS), start="2008-01-01")
    assert len(cal) > 1000
    idxs = list(range(0, len(cal), 50))  # sample across the full window
    for name, factory in S.STRATEGIES.items():
        fn = factory(cal)
        for i in idxs:
            w = fn(i, cal[i])
            gross = sum(abs(x) for x in w.values())
            assert gross <= 1.0 + 1e-9, f"{name} levered at i={i}: gross={gross:.5f}"
            for p, x in w.items():
                assert -1.0 - 1e-9 <= x <= 1.0 + 1e-9, f"{name} pair {p} weight {x}"


@needs_cache
def test_factory_strategies_have_no_lookahead():
    """Mutate a FUTURE bar (calendar index > i) and assert the weight at i is
    byte-identical for every factory strategy. A future bar must not change
    today's position."""
    from strategies_candidates.fx_lane import backtest_fx as B
    from strategies_candidates.fx_lane import fx_strategies as S

    cal = B.common_calendar(list(S.MAJORS), start="2010-01-01")
    i = 800                       # "today" index whose weight must be stable
    future = i + 60               # strictly-future bar
    assert future < len(cal) - 1

    pair = "EURUSD=X"
    key = fxc._sym_key(pair)
    fxc.get_daily(pair)           # ensure loaded into memo
    orig_series = fxc._SERIES_MEMO[key]
    orig_dates = fxc._DATES_MEMO[key]

    future_date = cal[future]
    pos = orig_dates.index(future_date)

    baseline = {name: factory(cal)(i, cal[i])
                for name, factory in S.STRATEGIES.items()}

    doctored = [dict(b) for b in orig_series]
    doctored[pos]["close"] = doctored[pos]["close"] * 10.0
    doctored[pos]["adjclose"] = doctored[pos]["close"]
    try:
        fxc._SERIES_MEMO[key] = doctored
        for name, factory in S.STRATEGIES.items():
            w_doctored = factory(cal)(i, cal[i])
            assert w_doctored == baseline[name], (
                f"{name} LEAKED: mutating a future bar (index {future} > {i}) "
                f"changed today's weight.\n base={baseline[name]}\n doct={w_doctored}")
    finally:
        fxc._SERIES_MEMO[key] = orig_series
        fxc._DATES_MEMO[key] = orig_dates


@needs_cache
def test_carry_proxy_is_static_and_excludes_zero_diff_pair():
    """The carry proxy is a STATIC book (1 rebalance over the window) and must
    EXCLUDE USDCAD (USD and CAD share the same stylized-yield rank -> 0 carry
    signal). Locks the documented behaviour so a future edit can't silently turn
    it into a momentum strategy."""
    from strategies_candidates.fx_lane import backtest_fx as B
    from strategies_candidates.fx_lane import fx_strategies as S
    cal = B.common_calendar(list(S.MAJORS), start="2010-01-01")
    fn = S.make_carry(cal)
    w = fn(1000, cal[1000])
    assert "USDCAD=X" not in w, "carry proxy must exclude the zero-rate-diff pair"
    # long the high-yielders / short funders (signs from the static ranking)
    assert w.get("AUDUSD=X", 0) > 0   # long AUD (high yield)
    assert w.get("USDJPY=X", 0) > 0   # long USD vs funding JPY
    assert w.get("EURUSD=X", 0) < 0   # short EUR / long USD
    # static: weights identical across two distant in-window dates (book doesn't
    # change once all pairs are live)
    w2 = fn(1500, cal[1500])
    assert w == w2, "carry proxy book should be static once all pairs are live"
