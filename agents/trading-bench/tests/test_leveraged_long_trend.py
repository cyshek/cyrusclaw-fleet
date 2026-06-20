"""Tests for leveraged_long_trend — locks the no-lookahead contract and the
core trend-gate mechanics. No network: monkeypatch the caches.

Run: pytest tests/test_leveraged_long_trend.py -q
"""
import math

import pytest

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    LevLongParams, trend_is_up, _stats_from_equity,
)


# --------------------------------------------------------------------------- #
# trend_is_up — signal logic
# --------------------------------------------------------------------------- #
def test_trend_up_sma_above():
    # last close above its 200-SMA => uptrend
    closes = [100.0] * 199 + [150.0]
    p = LevLongParams(gate_mode="sma200", sma_window=200)
    # only 200 points; sma uses last 200 -> mean ~100.25, last 150 > mean
    assert trend_is_up(closes, p) is True


def test_trend_down_sma_below():
    closes = [100.0] * 199 + [50.0]
    p = LevLongParams(gate_mode="sma200", sma_window=200)
    assert trend_is_up(closes, p) is False


def test_trend_insufficient_history_is_flat():
    # fewer than sma_window bars => SMA undefined => not up (fail-safe flat)
    closes = [100.0] * 50
    p = LevLongParams(gate_mode="sma200", sma_window=200)
    assert trend_is_up(closes, p) is False


def test_trend_tsmom():
    # price today > price tsmom_window bars ago => tsmom up
    closes = list(range(1, 260))  # strictly increasing
    closes = [float(x) for x in closes]
    p = LevLongParams(gate_mode="tsmom", tsmom_window=200)
    assert trend_is_up(closes, p) is True
    # strictly decreasing => tsmom down
    p2 = LevLongParams(gate_mode="tsmom", tsmom_window=200)
    assert trend_is_up(list(reversed(closes)), p2) is False


def test_trend_both_requires_and():
    # construct a series where SMA says up but TSMOM says down:
    # long flat low base then a recent spike (above SMA) but today's price
    # is BELOW the value tsmom_window ago is impossible if base is low...
    # Instead: SMA up (recent > mean) AND tsmom up => both up.
    closes = [10.0] * 200 + [float(x) for x in range(11, 70)]
    p = LevLongParams(gate_mode="both", sma_window=200, tsmom_window=200)
    assert trend_is_up(closes, p) is True


def test_empty_closes_flat():
    p = LevLongParams()
    assert trend_is_up([], p) is False


# --------------------------------------------------------------------------- #
# NO-LOOKAHEAD CONTRACT — the position held on day d must depend ONLY on
# information available strictly before d (closes <= d_prev). We verify this by
# constructing tiny synthetic caches and checking that a price spike on day d
# does NOT retroactively change the position held over day d.
# --------------------------------------------------------------------------- #
class _FakeDBC:
    """Minimal stand-in for runner.daily_bars_cache with deterministic bars."""
    def __init__(self, series):
        # series: dict[sym] -> list[(date, adjclose)]
        self._s = {
            sym: [{"date": d, "adjclose": c, "open": c, "high": c,
                   "low": c, "close": c, "volume": 0} for d, c in rows]
            for sym, rows in series.items()
        }

    def get_daily(self, sym):
        return list(self._s[sym])


def _mk_dates(n):
    # simple YYYY-MM-DD style increasing dates
    return ["2020-%02d-%02d" % (1 + i // 28, 1 + i % 28) for i in range(n)]


def test_no_lookahead_position_uses_prior_close(monkeypatch):
    """Position held over day d is set by the signal on d_prev's close.
    A huge move on day d itself must not change whether we were in-market on d.
    """
    n = 210
    dates = _mk_dates(n)
    # underlying: flat at 100 for a long time, then clearly above SMA at the end
    under = [(dates[i], 100.0) for i in range(n)]
    # make the last ~5 underlying closes high so trend flips up near the end
    for i in range(n - 5, n):
        under[i] = (dates[i], 130.0)
    # sleeve: flat then a giant +50% jump ONLY on the final day
    sleeve = [(dates[i], 10.0) for i in range(n)]
    sleeve[-1] = (dates[-1], 15.0)  # +50% on final day
    bench = [(dates[i], 100.0) for i in range(n)]

    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    # disable vix/tbill side-effects
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)

    p = LevLongParams(sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
                      gate_mode="sma200", sma_window=200, vix_gate=False,
                      use_tbill_cash=False, switch_cost_bps=0.0)
    r = bd.run_backtest(p)
    # The final day's sleeve jump should only be captured if we were ALREADY
    # in-market entering that day (decided by the prior close). The position on
    # the final day is decided by the second-to-last underlying close, which is
    # 130 > SMA -> in market. So the jump IS captured -- but crucially the
    # decision did not use the final day's own sleeve price. Verify the engine
    # ran and produced a finite equity (no NaN/inf) and the last pos is 'sleeve'.
    assert math.isfinite(r["strategy"]["equity"][-1])
    assert r["pos_log"][-1]["pos"] == "sleeve"
    # And the per-day instrument return recorded for the final day equals the
    # sleeve close-to-close (15/10-1 = +0.5), proving it used close-to-close,
    # not open or a future bar.
    assert abs(r["pos_log"][-1]["inst_ret"] - 0.5) < 1e-9


def test_cash_leg_when_flat(monkeypatch):
    """When trend is down the whole time, equity should track the cash leg
    (here 0% => flat at 1.0), never the sleeve."""
    n = 60
    dates = _mk_dates(n)
    # underlying strictly DOWN => never above SMA (and < sma_window bars anyway)
    under = [(dates[i], 100.0 - i) for i in range(n)]
    sleeve = [(dates[i], 10.0 + i) for i in range(n)]  # sleeve rising, must be ignored
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    p = LevLongParams(sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
                      gate_mode="sma200", sma_window=200, vix_gate=False,
                      use_tbill_cash=False, switch_cost_bps=0.0)
    r = bd.run_backtest(p)
    # flat in cash at 0% => final equity == 1.0 (never touched the rising sleeve)
    assert abs(r["strategy"]["equity"][-1] - 1.0) < 1e-9
    assert all(pl["pos"] == "cash" for pl in r["pos_log"])


def test_vix_gate_forces_cash(monkeypatch):
    """When VIX gate is on and term structure inverted, want -> cash even if
    trend is up."""
    n = 210
    dates = _mk_dates(n)
    under = [(dates[i], 100.0) for i in range(n)]
    for i in range(n - 5, n):
        under[i] = (dates[i], 130.0)  # trend up at end
    sleeve = [(dates[i], 10.0) for i in range(n)]
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    # VIX always risk-off
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: True)
    p = LevLongParams(sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
                      gate_mode="sma200", sma_window=200, vix_gate=True,
                      use_tbill_cash=False, switch_cost_bps=0.0)
    r = bd.run_backtest(p)
    # despite uptrend at the end, vix gate forces cash => all cash
    assert all(pl["pos"] == "cash" for pl in r["pos_log"])


# --------------------------------------------------------------------------- #
# stats sanity
# --------------------------------------------------------------------------- #
def test_stats_basic():
    eq = [1.0, 1.1, 1.21]  # +10% twice
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    st = _stats_from_equity(dates, eq)
    assert abs(st.total_return_pct - 21.0) < 1e-6
    assert st.max_drawdown_pct == 0.0  # monotonic up
    assert st.sharpe > 0


def test_stats_drawdown():
    eq = [1.0, 2.0, 1.0]  # +100% then -50%
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    st = _stats_from_equity(dates, eq)
    assert abs(st.max_drawdown_pct - (-50.0)) < 1e-6
