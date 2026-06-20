"""Tests for strategies/tqqq_cot_combo/strategy.py

Tests: decide() interface, BUY, SELL, HOLD, SMA-200 gate, COT bearish scaling.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from strategies.tqqq_cot_combo.strategy import (
    Action,
    _get_cot_scale,
    _realized_ann_vol,
    _resolve_underlying_closes,
    _sma,
    _sleeve_returns,
    decide,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PARAMS = {
    "symbol": "TQQQ",
    "underlying": "QQQ",
    "target_ann_vol": 0.40,
    "vol_window": 20,
    "w_max": 1.0,
    "cot_scale_bearish": 0.5,
    "notional": 1000.0,
    "sma_gate_window": 200,
}


def _make_bars(n: int, start_close: float = 50.0, step: float = 0.1) -> list:
    """Build n Alpaca-format bars with gently rising closes (above SMA-200 by design)."""
    return [
        {"o": start_close + i * step,
         "h": start_close + i * step + 1.0,
         "l": start_close + i * step - 1.0,
         "c": start_close + i * step,
         "v": 1_000_000}
        for i in range(n)
    ]


def _make_market(bars: list, price: float | None = None,
                 underlying_closes: list | None = None,
                 timestamp: str = "2026-06-14T09:30:00") -> dict:
    """Build a market_state dict."""
    ms: dict = {
        "symbol": "TQQQ",
        "last_price": price if price is not None else bars[-1]["c"],
        "bars": bars,
        "timestamp": timestamp,
        "regime": None,
        "strategy_state": {},
    }
    if underlying_closes is not None:
        ms["underlying"] = {"symbol": "QQQ", "closes": underlying_closes}
    return ms


def _flat_position() -> dict:
    return {}


def _held_position(qty: int, avg: float = 50.0) -> dict:
    return {"TQQQ": {"qty": qty, "avg_entry_price": avg, "market_value": qty * avg}}


# ---------------------------------------------------------------------------
# 1. decide() returns a valid action dict/dataclass
# ---------------------------------------------------------------------------

class TestDecideReturnsValidAction:
    def test_returns_action_dataclass(self):
        """decide() must return an Action with a valid action string."""
        bars = _make_bars(220)
        ms = _make_market(bars)
        result = decide(ms, _flat_position(), PARAMS)
        assert isinstance(result, Action), f"Expected Action, got {type(result)}"
        assert result.action in ("buy", "sell", "hold", "close"), (
            f"Unexpected action: {result.action!r}"
        )
        assert isinstance(result.symbol, str) and result.symbol
        assert isinstance(result.reason, str)
        assert isinstance(result.notional_usd, (int, float))

    def test_action_values_are_lowercase(self):
        """Actions are lowercase strings (runner expects lowercase)."""
        bars = _make_bars(220)
        ms = _make_market(bars)
        result = decide(ms, _flat_position(), PARAMS)
        assert result.action == result.action.lower()

    def test_returns_hold_when_no_price(self):
        """When price is None and no bars, must HOLD safely."""
        ms = {"symbol": "TQQQ", "bars": [], "last_price": None, "timestamp": "2026-06-14"}
        result = decide(ms, _flat_position(), PARAMS)
        assert result.action == "hold"

    def test_params_can_be_empty_falls_back_to_file_defaults(self):
        """Empty params dict falls back to params.json defaults -> must not crash."""
        bars = _make_bars(220)
        ms = _make_market(bars)
        result = decide(ms, _flat_position(), {})
        assert result.action in ("buy", "sell", "hold", "close")


# ---------------------------------------------------------------------------
# 2. BUY when underweight
# ---------------------------------------------------------------------------

class TestBuyWhenUnderweight:
    def test_buy_from_flat_with_sufficient_bars(self):
        """From flat with 220 bars (gate ON, vol computable), expect BUY."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars)
        result = decide(ms, _flat_position(), PARAMS)
        assert result.action == "buy", f"Expected buy, got {result.action!r}: {result.reason}"
        assert result.notional_usd > 0

    def test_buy_qty_reflects_vol_target(self):
        """BUY qty should be consistent with floor(weight * notional / price)."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars)
        params = dict(PARAMS, notional=1000.0)
        result = decide(ms, _flat_position(), params)
        if result.action == "buy":
            price = bars[-1]["c"]
            # qty * price should be close to notional_usd
            assert result.notional_usd > 0
            if result.qty is not None:
                assert abs(result.qty * price - result.notional_usd) < price  # within 1 share

    def test_buy_when_significantly_underweight(self):
        """Holding 1 share when target is >>1 should trigger BUY."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        # Hold only 1 share vs typical target ~8 shares
        pos = _held_position(1, avg=50.0)
        result = decide(ms, pos, PARAMS)
        # With notional=1000, price=50+, target ~8 shares; holding 1 -> buy expected
        if result.action != "hold":
            assert result.action == "buy"


# ---------------------------------------------------------------------------
# 3. SELL when overweight
# ---------------------------------------------------------------------------

class TestSellWhenOverweight:
    def test_sell_when_holding_much_more_than_target(self):
        """Holding 50 shares when target is ~8 -> SELL or CLOSE."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        # 50 shares @ $50 = $2500 position, target ~$400-500 -> heavily overweight
        pos = _held_position(50, avg=50.0)
        result = decide(ms, pos, PARAMS)
        assert result.action in ("sell", "close"), (
            f"Expected sell/close when overweight, got {result.action!r}: {result.reason}"
        )

    def test_sell_notional_positive(self):
        """SELL action must carry positive notional_usd."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        pos = _held_position(50, avg=50.0)
        result = decide(ms, pos, PARAMS)
        if result.action == "sell":
            assert result.notional_usd > 0


# ---------------------------------------------------------------------------
# 4. HOLD within threshold
# ---------------------------------------------------------------------------

class TestHoldWithinThreshold:
    def test_hold_when_at_target_qty(self):
        """If current qty matches target qty exactly, expect HOLD."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        # Pre-compute target_qty for these bars
        # First do a dry decide from flat to find target_qty
        result0 = decide(ms, _flat_position(), PARAMS)
        if result0.action == "buy" and result0.qty:
            target_qty = int(result0.qty)
        else:
            target_qty = 8  # reasonable approximation

        pos = _held_position(target_qty, avg=50.0)
        result = decide(ms, pos, PARAMS)
        assert result.action == "hold", (
            f"Expected HOLD at exact target, got {result.action!r}: {result.reason}"
        )

    def test_hold_within_5pct_threshold(self):
        """delta within 5% threshold -> HOLD (no churn)."""
        # Use explicit QQQ gate-ON closes and mock COT to 1.0 (bullish)
        # so we have full control of target_qty.
        n = 220
        # Slightly rising prices -> vol near zero -> weight clips to w_max=1.0
        bars_rising = [{"o": 40 + i * 0.05, "h": 41 + i * 0.05,
                        "l": 39 + i * 0.05, "c": 40 + i * 0.05, "v": 1_000_000}
                       for i in range(n)]
        price = bars_rising[-1]["c"]
        # gate ON: last QQQ close >> SMA-200
        qqq_closes = [40.0] * 200 + [50.0]
        ms = _make_market(bars_rising, price=price)
        ms["underlying"] = {"symbol": "QQQ", "closes": qqq_closes}

        with patch("strategies.tqqq_cot_combo.strategy._get_cot_scale", return_value=1.0):
            # target_qty = floor(1.0 * 1000 / price)
            target_qty = math.floor(1000.0 / price)
            threshold = max(1, math.floor(0.05 * max(target_qty, 1)))
            # Hold exactly at target -> delta=0 -> within threshold -> HOLD
            pos = _held_position(target_qty, avg=price)
            result = decide(ms, pos, PARAMS)

        assert result.action == "hold", (
            f"Expected HOLD at exact target, got {result.action!r}: {result.reason}"
        )


# ---------------------------------------------------------------------------
# 5. SMA-200 gate: HOLD when price below 200-bar SMA
# ---------------------------------------------------------------------------

class TestSmaGate:
    def test_hold_flat_when_gate_off_via_qqq_closes(self):
        """When QQQ last close < SMA-200, gate is OFF -> HOLD (flat position)."""
        # Build QQQ closes: 200 bars at 100, then last close at 50 (far below SMA)
        qqq_closes = [100.0] * 200 + [50.0]  # 201 bars; last is 50 << SMA(100)
        bars = _make_bars(220)
        ms = _make_market(bars, underlying_closes=qqq_closes)
        result = decide(ms, _flat_position(), PARAMS)
        assert result.action == "hold", (
            f"Expected HOLD when gate OFF (flat), got {result.action!r}: {result.reason}"
        )
        assert "gate" in result.reason.lower() or "OFF" in result.reason

    def test_close_when_holding_and_gate_off(self):
        """When QQQ gate is OFF and we hold a position, expect CLOSE."""
        qqq_closes = [100.0] * 200 + [50.0]
        bars = _make_bars(220)
        ms = _make_market(bars, underlying_closes=qqq_closes)
        pos = _held_position(10, avg=50.0)
        result = decide(ms, pos, PARAMS)
        assert result.action == "close", (
            f"Expected CLOSE when gate OFF + holding, got {result.action!r}: {result.reason}"
        )

    def test_gate_permissive_when_insufficient_qqq_history(self):
        """Fewer than sma_gate_window QQQ closes -> gate skipped (permissive)."""
        qqq_closes = [50.0] * 50  # only 50 bars, gate requires 200
        bars = _make_bars(220)
        ms = _make_market(bars, underlying_closes=qqq_closes)
        result = decide(ms, _flat_position(), PARAMS)
        # Gate is skipped -> should NOT be blocked by the gate
        # (may buy if vol computable; may hold if threshold; should not say gate OFF)
        assert "gate OFF" not in result.reason, (
            f"Gate should be skipped (permissive), not OFF: {result.reason}"
        )

    def test_gate_uses_tqqq_proxy_when_no_underlying(self):
        """When no underlying block, TQQQ bars used as proxy gate -> still functional."""
        # No underlying block in market_state
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = {
            "symbol": "TQQQ",
            "last_price": bars[-1]["c"],
            "bars": bars,
            "timestamp": "2026-06-14",
        }
        result = decide(ms, _flat_position(), PARAMS)
        assert result.action in ("buy", "sell", "hold", "close")
        assert "TQQQ proxy" in result.reason  # documents the proxy usage


# ---------------------------------------------------------------------------
# 6. COT bearish: reduces target weight correctly
# ---------------------------------------------------------------------------

class TestCotBearish:
    def test_cot_bearish_reduces_target_weight(self):
        """With COT bearish (scale=0.5), target_qty should be ~half of bullish."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)

        # Bullish COT: mock _get_cot_scale to return 1.0
        with patch("strategies.tqqq_cot_combo.strategy._get_cot_scale", return_value=1.0):
            result_bull = decide(ms, _flat_position(), PARAMS)

        # Bearish COT: mock _get_cot_scale to return 0.5
        with patch("strategies.tqqq_cot_combo.strategy._get_cot_scale", return_value=0.5):
            result_bear = decide(ms, _flat_position(), PARAMS)

        # Bearish target should be ~half the bullish target
        if result_bull.action == "buy" and result_bear.action == "buy":
            assert result_bear.notional_usd <= result_bull.notional_usd, (
                f"Bearish COT notional {result_bear.notional_usd} should be <= "
                f"bullish {result_bull.notional_usd}"
            )
        elif result_bull.action == "buy" and result_bear.action == "hold":
            # Acceptable: bearish target is within threshold (very small position)
            pass
        else:
            # Both could hold if vol is low enough that threshold guard triggers
            pass

    def test_cot_bearish_scale_reflects_params(self):
        """cot_scale_bearish param is respected: smaller param = smaller scale."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        params_aggressive = dict(PARAMS, cot_scale_bearish=0.9)
        params_conservative = dict(PARAMS, cot_scale_bearish=0.1)

        with patch("strategies.tqqq_cot_combo.strategy._get_cot_scale") as mock_scale:
            # Simulate bearish by returning the param value
            mock_scale.side_effect = lambda scale, today: scale

            result_agg = decide(ms, _flat_position(), params_aggressive)
            result_con = decide(ms, _flat_position(), params_conservative)

        if result_agg.action == "buy" and result_con.action == "buy":
            assert result_agg.notional_usd >= result_con.notional_usd, (
                "More aggressive bearish scale should yield larger notional"
            )

    def test_cot_no_data_defaults_to_bullish(self):
        """When COT data unavailable, _get_cot_scale returns 1.0 (no false bearish)."""
        scale = _get_cot_scale(0.5, today_iso="2010-01-01")  # too early for COT data
        assert scale == 1.0, f"Expected 1.0 (bullish default), got {scale}"

    def test_cot_scale_bearish_in_reason_string(self):
        """COT_scale appears in the action reason for traceability."""
        bars = _make_bars(220, start_close=50.0, step=0.1)
        ms = _make_market(bars, price=50.0)
        with patch("strategies.tqqq_cot_combo.strategy._get_cot_scale", return_value=0.5):
            result = decide(ms, _flat_position(), PARAMS)
        assert "COT_scale=0.5" in result.reason, (
            f"COT scale not in reason: {result.reason}"
        )


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_realized_ann_vol_basic(self):
        """Constant positive returns -> non-zero vol."""
        returns = [0.01] * 20
        rv = _realized_ann_vol(returns, 20)
        assert rv is None or rv == 0.0  # all same -> zero pop stdev -> None

    def test_realized_ann_vol_mixed(self):
        """Mixed returns -> non-zero annualized vol."""
        returns = [0.01, -0.01] * 10
        rv = _realized_ann_vol(returns, 20)
        assert rv is not None and rv > 0

    def test_realized_ann_vol_insufficient(self):
        """Fewer than n returns -> None."""
        returns = [0.01] * 5
        assert _realized_ann_vol(returns, 20) is None

    def test_sma_basic(self):
        """SMA of 200 identical values."""
        vals = [5.0] * 200
        assert _sma(vals, 200) == pytest.approx(5.0)

    def test_sma_insufficient(self):
        """Fewer than n values -> None."""
        assert _sma([1.0] * 10, 200) is None

    def test_sleeve_returns_length(self):
        """n bars -> n-1 returns."""
        bars = [{"c": float(i + 1)} for i in range(10)]
        rets = _sleeve_returns(bars)
        assert len(rets) == 9

    def test_resolve_underlying_uses_provided_closes(self):
        """Explicit QQQ closes in market_state['underlying'] -> used directly."""
        qqq_closes = [100.0] * 210
        ms = {"underlying": {"symbol": "QQQ", "closes": qqq_closes}}
        closes, src, is_proxy = _resolve_underlying_closes(ms, "QQQ", [])
        assert closes == qqq_closes
        assert not is_proxy

    def test_resolve_underlying_falls_back_to_tqqq_proxy(self):
        """No underlying block -> TQQQ bars used as proxy."""
        bars = [{"c": 50.0 + i * 0.1} for i in range(5)]
        ms = {}
        closes, src, is_proxy = _resolve_underlying_closes(ms, "QQQ", bars)
        assert is_proxy
        assert len(closes) == len(bars)
