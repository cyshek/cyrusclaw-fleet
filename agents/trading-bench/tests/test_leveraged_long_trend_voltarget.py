"""Tests for the VOL-TARGETED leveraged_long_trend variant.

Locks: (1) the realized-vol math, (2) the stacked gate-AND-voltarget sizing rule,
(3) the NO-LOOKAHEAD contract for the vol-sizing path (a future vol spike must not
change today's weight), (4) the abs-weight-change transaction-cost model, and
(5) that target_ann_vol=None reproduces the binary behaviour (w in {0,1}).

No network: monkeypatch the caches (mirrors test_leveraged_long_trend.py).

Run: pytest tests/test_leveraged_long_trend_voltarget.py -q
"""
import math

import pytest

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend import backtest_daily_voltarget as vt
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, realized_ann_vol, target_weight, _clamp,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS


# --------------------------------------------------------------------------- #
# realized_ann_vol
# --------------------------------------------------------------------------- #
def test_realized_vol_insufficient_history_is_none():
    assert realized_ann_vol([0.01, 0.02], n=20) is None
    assert realized_ann_vol([], n=20) is None


def test_realized_vol_zero_variance_is_none():
    # constant returns => zero stdev => None (degenerate, can't size)
    assert realized_ann_vol([0.01] * 30, n=20) is None


def test_realized_vol_value_and_annualization():
    # alternating +/- r => population stdev == r, annualized *sqrt(252)
    r = 0.02
    series = [r, -r] * 20  # 40 returns, mean 0
    rv = realized_ann_vol(series, n=20)
    assert rv is not None
    assert abs(rv - r * math.sqrt(TRADING_DAYS)) < 1e-9


def test_realized_vol_uses_only_trailing_n():
    # huge early values must be ignored; only last n matter
    series = [10.0] * 5 + [0.01, -0.01] * 20
    rv_all = realized_ann_vol(series, n=20)
    rv_tail = realized_ann_vol([0.01, -0.01] * 20, n=20)
    assert abs(rv_all - rv_tail) < 1e-12


# --------------------------------------------------------------------------- #
# target_weight — the stacked sizing rule
# --------------------------------------------------------------------------- #
def test_weight_trend_down_is_zero():
    assert target_weight(False, 0.30, 0.25, 1.0) == 0.0
    # even with no target and trend down
    assert target_weight(False, None, None, 1.0) == 0.0


def test_weight_binary_path_when_target_none():
    # target None => binary: 1.0 when up (clamped to w_max), 0 when down
    assert target_weight(True, None, None, 1.0) == 1.0
    assert target_weight(True, 0.5, None, 1.0) == 1.0  # rvol ignored in binary path
    assert target_weight(True, None, None, 0.5) == 0.5  # clamped to w_max


def test_weight_inverse_vol_scaling():
    # w = target/rvol clamped [0, w_max]
    assert abs(target_weight(True, 0.40, 0.20, 1.0) - 0.5) < 1e-12   # 0.20/0.40
    assert abs(target_weight(True, 0.20, 0.20, 1.0) - 1.0) < 1e-12   # exactly 1
    # low vol would imply >1 => clamped to w_max=1.0 (no leverage-on-leverage)
    assert target_weight(True, 0.10, 0.20, 1.0) == 1.0
    # higher w_max would allow >1 but we never use it; verify clamp respects it
    assert abs(target_weight(True, 0.10, 0.20, 1.5) - 1.5) < 1e-12


def test_weight_no_vol_estimate_is_flat():
    # trend up but rvol unknown (early history) => 0.0, never guess
    assert target_weight(True, None, 0.25, 1.0) == 0.0
    assert target_weight(True, 0.0, 0.25, 1.0) == 0.0


def test_clamp():
    assert _clamp(2.0, 0.0, 1.0) == 1.0
    assert _clamp(-1.0, 0.0, 1.0) == 0.0
    assert _clamp(0.5, 0.0, 1.0) == 0.5


# --------------------------------------------------------------------------- #
# Fake cache + backtest-level tests
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


def test_binary_path_reproduces_full_invest_when_always_up(monkeypatch):
    """target_ann_vol=None and trend always up => weight 1.0 every day, equity
    tracks the sleeve exactly (no cash drag, zero cost since w never changes
    after the first day)."""
    n = 260
    dates = _mk_dates(n)
    # underlying strongly rising so it's always above its SMA once warmed up
    under = [(dates[i], 100.0 + i) for i in range(n)]
    sleeve = [(dates[i], 10.0 * (1.01 ** i)) for i in range(n)]
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    p = VolTargetParams(target_ann_vol=None, sma_window=200, vix_gate=False,
                        use_tbill_cash=False, switch_cost_bps=0.0)
    r = vt.run_backtest_voltarget(p)
    # all weights 1.0 once trend is up (after 200-bar warmup the gate is up)
    late = r["strategy"]["weights"][210:]
    assert all(abs(w - 1.0) < 1e-12 for w in late)
    assert math.isfinite(r["strategy"]["stats"]["total_return_pct"])


def test_voltarget_scales_down_in_high_vol(monkeypatch):
    """With a vol target, a high-realized-vol sleeve should be held at weight < 1
    (scaled down), unlike the binary path which would hold 1.0."""
    n = 260
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]  # always up
    # sleeve with large alternating swings => high realized vol
    sleeve = []
    px = 10.0
    for i in range(n):
        px = px * (1.05 if i % 2 == 0 else 0.96)  # ~big daily moves
        sleeve.append((dates[i], px))
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    p = VolTargetParams(target_ann_vol=0.20, vol_window=20, sma_window=200,
                        vix_gate=False, use_tbill_cash=False, switch_cost_bps=0.0)
    r = vt.run_backtest_voltarget(p)
    # once warmed up, realized vol is very high => weight clamped well below 1.0
    late_w = r["strategy"]["weights"][220:]
    assert late_w, "expected some held days"
    assert max(late_w) < 1.0
    assert r["strategy"]["stats"]["avg_weight"] < 1.0


def test_voltarget_no_lookahead_future_vol_spike(monkeypatch):
    """THE CONTRACT: a vol/price spike that happens ON or AFTER the held day must
    not change the weight decided for that day. We run the engine on a series,
    then mutate ONLY the final day's sleeve price to a wild value and confirm the
    weights for all prior held days are byte-identical."""
    n = 260
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 + i) for i in range(n)]
    sleeve = [(dates[i], 10.0 + 0.05 * i) for i in range(n)]  # mild drift
    bench = [(dates[i], 100.0) for i in range(n)]

    def run_with(sleeve_series):
        fake = _FakeDBC({"TQQQ": sleeve_series, "QQQ": under, "^GSPC": bench})
        monkeypatch.setattr(bd, "dbc", fake)
        monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
        monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
        p = VolTargetParams(target_ann_vol=0.20, vol_window=20, sma_window=200,
                            vix_gate=False, use_tbill_cash=False,
                            switch_cost_bps=0.0)
        return vt.run_backtest_voltarget(p)

    r_base = run_with(sleeve)
    spiked = list(sleeve)
    spiked[-1] = (dates[-1], 10_000.0)  # absurd spike on the FINAL day only
    r_spike = run_with(spiked)

    w_base = r_base["strategy"]["weights"]
    w_spike = r_spike["strategy"]["weights"]
    # all weights EXCEPT possibly the very last held day must be identical:
    # the last held day's weight is decided from data <= second-to-last day, so
    # it too should be identical. The spike only affects that day's REALIZED
    # return, not any weight.
    assert len(w_base) == len(w_spike)
    for i in range(len(w_base)):
        assert abs(w_base[i] - w_spike[i]) < 1e-12, (
            "weight at held-day %d changed after a FUTURE spike -> LOOKAHEAD" % i)


def test_abs_weight_change_cost_model(monkeypatch):
    """Cost is charged on |w_today - w_yesterday|. A single 0->1 entry that then
    stays at 1.0 costs the full per-side bps exactly once; staying flat costs
    nothing thereafter."""
    n = 260
    dates = _mk_dates(n)
    # flat-low underlying for a long time (trend down => w=0), then jump up so the
    # gate flips up near the end and weight goes 0 -> (something). Use target=None
    # so the flip is a clean 0 -> 1.
    under = [(dates[i], 100.0) for i in range(n)]
    for i in range(n - 3, n):
        under[i] = (dates[i], 500.0)  # sharp move up at the very end
    sleeve = [(dates[i], 10.0) for i in range(n)]  # flat sleeve => zero sleeve_ret
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    bps = 10.0
    p = VolTargetParams(target_ann_vol=None, sma_window=200, vix_gate=False,
                        use_tbill_cash=False, switch_cost_bps=bps)
    r = vt.run_backtest_voltarget(p)
    weights = r["strategy"]["weights"]
    # count weight changes
    changes = 0
    prev = 0.0
    for w in weights:
        if abs(w - prev) > 1e-9:
            changes += 1
        prev = w
    # sleeve return is 0 every day, cash 0 => the ONLY thing moving equity is cost.
    # final equity = product over changes of (1 - bps/1e4 * dw). With a single
    # 0->1 change, that's exactly (1 - bps/1e4).
    eq = r["strategy"]["equity"][-1]
    if changes == 1:
        assert abs(eq - (1.0 - bps / 10000.0)) < 1e-9
    # at minimum: equity is below 1.0 iff there was at least one rebalance
    assert (eq < 1.0) == (changes >= 1)
    assert r["strategy"]["stats"]["n_rebalances"] == changes


def test_voltarget_all_cash_when_trend_down(monkeypatch):
    """Trend down the whole time => weight 0 every day => equity flat at cash
    (0% here) regardless of a rising sleeve."""
    n = 60
    dates = _mk_dates(n)
    under = [(dates[i], 100.0 - i) for i in range(n)]  # strictly down
    sleeve = [(dates[i], 10.0 + i) for i in range(n)]  # rising, must be ignored
    bench = [(dates[i], 100.0) for i in range(n)]
    fake = _FakeDBC({"TQQQ": sleeve, "QQQ": under, "^GSPC": bench})
    monkeypatch.setattr(bd, "dbc", fake)
    monkeypatch.setattr(bd, "_vix_risk_off", lambda d, thr: False)
    monkeypatch.setattr(bd, "_tbill_daily_rate", lambda d: 0.0)
    p = VolTargetParams(target_ann_vol=0.25, vol_window=20, sma_window=200,
                        vix_gate=False, use_tbill_cash=False, switch_cost_bps=0.0)
    r = vt.run_backtest_voltarget(p)
    assert all(w == 0.0 for w in r["strategy"]["weights"])
    assert abs(r["strategy"]["equity"][-1] - 1.0) < 1e-12
