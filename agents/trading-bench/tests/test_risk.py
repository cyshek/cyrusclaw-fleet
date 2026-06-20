"""Tests for runner/risk.py.

Two concerns:
  1. Legacy single-symbol per-day cap behavior (regression).
  2. Basket-aware cap resolution via `resolve_trades_per_day(params)`
     (added 2026-05-30 for xsec basket strategies).

`check_trade` reads `db.trades_today` for live counts; tests monkeypatch
that to control n_today without standing up a real DB.
"""

from __future__ import annotations

import pytest

from runner import risk as risk_mod
from runner.risk import (
    MAX_NOTIONAL,
    MAX_POSITION,
    MAX_TRADES_PER_DAY,
    MAX_XSEC_BASKET_SIZE,
    RiskCheck,
    check_trade,
    resolve_trades_per_day,
)


# ---------------------------------------------------------------------------
# resolve_trades_per_day
# ---------------------------------------------------------------------------

def test_resolve_none_params_returns_legacy_cap():
    assert resolve_trades_per_day(None) == MAX_TRADES_PER_DAY


def test_resolve_empty_params_returns_legacy_cap():
    assert resolve_trades_per_day({}) == MAX_TRADES_PER_DAY


def test_resolve_no_xsec_key_returns_legacy_cap():
    assert resolve_trades_per_day({"symbol": "SPY"}) == MAX_TRADES_PER_DAY


def test_resolve_k_equals_2_returns_max_of_legacy_and_4():
    # max(4, 2*2) = 4. K=2 baskets behave identically to single-symbol.
    assert resolve_trades_per_day({"xsec_basket_size": 2}) == MAX_TRADES_PER_DAY


def test_resolve_k_equals_3_returns_6():
    assert resolve_trades_per_day({"xsec_basket_size": 3}) == 6


def test_resolve_k_equals_6_returns_12():
    # The motivating case: 6-leg cross-asset basket (SPY/EFA/TLT/VNQ/DBC/GLD).
    assert resolve_trades_per_day({"xsec_basket_size": 6}) == 12


def test_resolve_k_at_ceiling_works():
    assert resolve_trades_per_day(
        {"xsec_basket_size": MAX_XSEC_BASKET_SIZE}
    ) == 2 * MAX_XSEC_BASKET_SIZE


def test_resolve_k_over_ceiling_falls_back_to_legacy():
    # Safety floor against typo'd params authorizing 1000 trades/day.
    assert resolve_trades_per_day(
        {"xsec_basket_size": MAX_XSEC_BASKET_SIZE + 1}
    ) == MAX_TRADES_PER_DAY


def test_resolve_k_zero_falls_back_to_legacy():
    assert resolve_trades_per_day({"xsec_basket_size": 0}) == MAX_TRADES_PER_DAY


def test_resolve_k_negative_falls_back_to_legacy():
    assert resolve_trades_per_day({"xsec_basket_size": -5}) == MAX_TRADES_PER_DAY


def test_resolve_k_string_numeric_works():
    # JSON parsing or hand-edited params may yield strings.
    assert resolve_trades_per_day({"xsec_basket_size": "3"}) == 6


def test_resolve_k_garbage_falls_back_to_legacy():
    assert resolve_trades_per_day({"xsec_basket_size": "banana"}) == MAX_TRADES_PER_DAY
    assert resolve_trades_per_day({"xsec_basket_size": None}) == MAX_TRADES_PER_DAY
    assert resolve_trades_per_day({"xsec_basket_size": [1, 2]}) == MAX_TRADES_PER_DAY


# ---------------------------------------------------------------------------
# check_trade — basket-aware cap propagation
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_trades_today(monkeypatch):
    """Yield a setter that overrides db.trades_today."""
    state = {"n": 0}

    def setter(n: int) -> None:
        state["n"] = n

    monkeypatch.setattr(
        risk_mod.db,
        "trades_today",
        lambda strategy: state["n"],
    )
    return setter


def test_check_trade_default_cap_rejects_at_legacy_floor(fake_trades_today):
    fake_trades_today(MAX_TRADES_PER_DAY)
    rc = check_trade("s", "SPY", "buy", 50.0, 0.0)
    assert not rc.ok
    assert "cap 4" in rc.reason


def test_check_trade_default_cap_allows_under_floor(fake_trades_today):
    fake_trades_today(MAX_TRADES_PER_DAY - 1)
    rc = check_trade("s", "SPY", "buy", 50.0, 0.0)
    assert rc.ok


def test_check_trade_basket_cap_allows_above_legacy_floor(fake_trades_today):
    # K=6 -> cap 12. Trade #5 should pass.
    fake_trades_today(4)
    rc = check_trade("s", "TLT", "buy", 16.0, 0.0,
                     max_trades_per_day=resolve_trades_per_day({"xsec_basket_size": 6}))
    assert rc.ok


def test_check_trade_basket_cap_rejects_at_resolved_ceiling(fake_trades_today):
    fake_trades_today(12)
    rc = check_trade("s", "TLT", "buy", 16.0, 0.0,
                     max_trades_per_day=resolve_trades_per_day({"xsec_basket_size": 6}))
    assert not rc.ok
    assert "cap 12" in rc.reason


def test_check_trade_basket_cap_close_path_uses_resolved_cap(fake_trades_today):
    # Closes still daily-capped. With K=6 (cap 12), close #11 ok, #12 blocked.
    cap = resolve_trades_per_day({"xsec_basket_size": 6})
    fake_trades_today(11)
    rc = check_trade("s", "TLT", "close", 0.0, 16.0, max_trades_per_day=cap)
    assert rc.ok
    fake_trades_today(12)
    rc = check_trade("s", "TLT", "close", 0.0, 16.0, max_trades_per_day=cap)
    assert not rc.ok


# ---------------------------------------------------------------------------
# Regression: notional/position caps unaffected by trades-per-day change
# ---------------------------------------------------------------------------

def test_check_trade_notional_cap_still_enforced(fake_trades_today):
    fake_trades_today(0)
    rc = check_trade("s", "SPY", "buy", MAX_NOTIONAL + 1.0, 0.0,
                     max_trades_per_day=12)
    assert not rc.ok
    assert "notional" in rc.reason


def test_check_trade_position_cap_still_enforced(fake_trades_today):
    fake_trades_today(0)
    rc = check_trade("s", "SPY", "buy", 50.0, MAX_POSITION,
                     max_trades_per_day=12)
    assert not rc.ok
    assert "position" in rc.reason


def test_check_trade_non_positive_notional_rejected(fake_trades_today):
    fake_trades_today(0)
    rc = check_trade("s", "SPY", "buy", 0.0, 0.0, max_trades_per_day=12)
    assert not rc.ok
    assert "non-positive" in rc.reason
