"""Tests for the lookback time-convention helper/guard (audit §2) and the
intraday-aware per-day trade cap (audit §3).

Item 2 — runner/backtest.py:
  - timeframe_to_daily_bars(timeframe, is_crypto): how many bars == 1 trading
    day. 1Day -> 1.0; equity intraday -> 510/tf_min; crypto -> 1440/tf_min;
    junk -> ValueError.
  - assert_lookback_sane(params, timeframe, is_crypto, *, lookback_keys):
    non-fatal lint that returns WARNING strings when a daily-authored bar-count
    lookback is run at a finer timeframe such that the window covers <1 session.
    [] at 1Day and for normal 1Hour daily-authored counts; warns at 1Min.

Item 3 — runner/risk.py:
  - resolve_trades_per_day(params, timeframe=None): backward-compatible when
    timeframe is omitted (None/{}/xsec UNCHANGED = 4/6/12 etc.); intraday
    default + explicit override + ceiling clamp are the new behavior.

These tests are ADDITIVE; they assert the daily/legacy book is untouched.
"""

from __future__ import annotations

import math

import pytest

from runner.backtest import (
    EQUITY_INTRADAY_MINUTES_PER_DAY,
    CRYPTO_MINUTES_PER_DAY,
    assert_lookback_sane,
    timeframe_to_daily_bars,
)
from runner.risk import (
    INTRADAY_TRADES_PER_DAY_DEFAULT,
    MAX_TRADES_PER_DAY,
    MAX_TRADES_PER_DAY_CEILING,
    resolve_trades_per_day,
)


# ---------------------------------------------------------------------------
# timeframe_to_daily_bars
# ---------------------------------------------------------------------------

def test_daily_bars_one_day_is_one_both_classes():
    assert timeframe_to_daily_bars("1Day") == 1.0
    assert timeframe_to_daily_bars("1Day", is_crypto=True) == 1.0


def test_daily_bars_equity_1hour_is_8point5():
    # 510 / 60 = 8.5
    assert timeframe_to_daily_bars("1Hour") == pytest.approx(8.5)
    assert timeframe_to_daily_bars("1Hour", is_crypto=False) == pytest.approx(
        EQUITY_INTRADAY_MINUTES_PER_DAY / 60.0)


def test_daily_bars_equity_1min_is_510():
    assert timeframe_to_daily_bars("1Min") == pytest.approx(510.0)
    assert timeframe_to_daily_bars("1Min") == pytest.approx(
        float(EQUITY_INTRADAY_MINUTES_PER_DAY))


def test_daily_bars_crypto_1hour_is_24():
    # 1440 / 60 = 24
    assert timeframe_to_daily_bars("1Hour", is_crypto=True) == pytest.approx(24.0)


def test_daily_bars_crypto_1min_is_1440():
    assert timeframe_to_daily_bars("1Min", is_crypto=True) == pytest.approx(
        float(CRYPTO_MINUTES_PER_DAY))


def test_daily_bars_crypto_gt_equity_intraday():
    # crypto 24/7 always packs more bars/day than equity's ~8.5h session
    for tf in ("1Min", "5Min", "15Min", "30Min", "1Hour"):
        assert timeframe_to_daily_bars(tf, is_crypto=True) > timeframe_to_daily_bars(
            tf, is_crypto=False)


def test_daily_bars_unknown_timeframe_raises():
    with pytest.raises(ValueError):
        timeframe_to_daily_bars("banana")
    with pytest.raises(ValueError):
        timeframe_to_daily_bars("7Min")
    with pytest.raises(ValueError):
        timeframe_to_daily_bars("")


# ---------------------------------------------------------------------------
# assert_lookback_sane
# ---------------------------------------------------------------------------

def test_lookback_sane_empty_params_no_warnings():
    assert assert_lookback_sane({}, "1Min") == []
    assert assert_lookback_sane(None, "1Min") == []


def test_lookback_sane_daily_never_warns():
    # 1Day: bar counts ARE in their authored unit -> always clean
    params = {"fast": 10, "slow": 30, "rsi_period": 14, "lookback": 20}
    assert assert_lookback_sane(params, "1Day") == []


def test_lookback_sane_normal_1hour_daily_counts_no_warning():
    # daily-authored sma_crossover_qqq counts at the LIVE 1Hour cadence are fine
    # (slow=30 -> 30/8.5 = 3.5 trading days, > 1 session)
    params = {"fast": 10, "slow": 30}
    assert assert_lookback_sane(params, "1Hour") == []


def test_lookback_sane_1min_daily_slow_warns():
    # slow=30 at 1Min = 30 bars = 30 minutes << 1 session (510 bars/day)
    params = {"fast": 10, "slow": 30}
    warns = assert_lookback_sane(params, "1Min")
    assert len(warns) == 2  # both fast=10 and slow=30 < 510
    joined = " ".join(warns)
    assert "slow" in joined and "fast" in joined
    assert "1Min" in joined


def test_lookback_sane_warning_strings_are_human_readable():
    warns = assert_lookback_sane({"slow": 30}, "1Min")
    assert len(warns) == 1
    msg = warns[0]
    # carries the key, value, timeframe, and the "trading day" framing
    assert "slow" in msg
    assert "30" in msg
    assert "1Min" in msg
    assert "trading day" in msg.lower()


def test_lookback_sane_does_not_mutate_params():
    params = {"fast": 10, "slow": 30, "symbol": "QQQ"}
    snapshot = dict(params)
    assert_lookback_sane(params, "1Min")
    assert params == snapshot


def test_lookback_sane_ignores_non_lookback_keys():
    # symbol/notional/threshold-ish keys without a lookback token are skipped
    params = {"symbol": "QQQ", "notional_usd": 100.0, "buy_threshold": 0.02}
    assert assert_lookback_sane(params, "1Min") == []


def test_lookback_sane_ignores_bool_and_non_numeric():
    params = {"slow_enabled": True, "window_label": "fast", "regime_gate": False}
    # 'slow'/'window' tokens match the KEY, but values are bool/str -> skipped
    assert assert_lookback_sane(params, "1Min") == []


def test_lookback_sane_1hour_short_exit_lookback_warns():
    # the real volume_breakout_qqq case: exit_lookback=8 at 1Hour = 0.94 days
    params = {"lookback": 20, "exit_lookback": 8}
    warns = assert_lookback_sane(params, "1Hour")
    # lookback=20 (>8.5) is fine; exit_lookback=8 (<8.5) warns
    assert len(warns) == 1
    assert "exit_lookback" in warns[0]


def test_lookback_sane_explicit_lookback_keys_override():
    # only inspect the named keys; ignore the token scan entirely
    params = {"slow": 30, "mylen": 5, "fast": 10}
    warns = assert_lookback_sane(params, "1Min", lookback_keys=["mylen"])
    assert len(warns) == 1
    assert "mylen" in warns[0]
    # slow/fast NOT inspected because lookback_keys was given
    assert "slow" not in warns[0] and "fast" not in warns[0]


def test_lookback_sane_crypto_threshold_uses_1440():
    # at 1Min crypto, 1 trading day = 1440 bars; slow=1000 still < 1440 -> warns
    assert assert_lookback_sane({"slow": 1000}, "1Min", is_crypto=True) != []
    # slow=2000 > 1440 -> no warning
    assert assert_lookback_sane({"slow": 2000}, "1Min", is_crypto=True) == []


def test_lookback_sane_unknown_timeframe_propagates_valueerror():
    with pytest.raises(ValueError):
        assert_lookback_sane({"slow": 30}, "banana")


# ---------------------------------------------------------------------------
# resolve_trades_per_day — BACKWARD COMPAT (timeframe omitted == legacy)
# ---------------------------------------------------------------------------

def test_trades_backcompat_none_and_empty_unchanged():
    assert resolve_trades_per_day(None) == 4
    assert resolve_trades_per_day({}) == 4
    assert resolve_trades_per_day(None) == MAX_TRADES_PER_DAY


def test_trades_backcompat_xsec_unchanged():
    assert resolve_trades_per_day({"xsec_basket_size": 2}) == 4
    assert resolve_trades_per_day({"xsec_basket_size": 3}) == 6
    assert resolve_trades_per_day({"xsec_basket_size": 6}) == 12
    assert resolve_trades_per_day({"xsec_basket_size": 50}) == 4  # clamped
    assert resolve_trades_per_day({"xsec_basket_size": "banana"}) == 4


def test_trades_backcompat_explicit_1day_equals_none():
    # passing timeframe="1Day" must equal the omitted-timeframe legacy path
    assert resolve_trades_per_day({}, "1Day") == 4
    assert resolve_trades_per_day(None, "1Day") == 4
    assert resolve_trades_per_day({"xsec_basket_size": 3}, "1Day") == 6


def test_trades_backcompat_none_timeframe_equals_omitted():
    assert resolve_trades_per_day({"xsec_basket_size": 6}, None) == 12


# ---------------------------------------------------------------------------
# resolve_trades_per_day — INTRADAY default (NEW)
# ---------------------------------------------------------------------------

def test_trades_intraday_default_bumps_above_legacy():
    assert resolve_trades_per_day({}, "1Min") == INTRADAY_TRADES_PER_DAY_DEFAULT
    assert resolve_trades_per_day({}, "1Hour") == INTRADAY_TRADES_PER_DAY_DEFAULT
    assert resolve_trades_per_day({}, "5Min") == INTRADAY_TRADES_PER_DAY_DEFAULT
    assert resolve_trades_per_day({}, "1Min") > MAX_TRADES_PER_DAY


def test_trades_intraday_default_never_below_basket_bump():
    # big basket at intraday -> max(intraday_default, 2*K)
    # K=12 -> 2*K=24 > 20 -> 24
    assert resolve_trades_per_day({"xsec_basket_size": 12}, "1Min") == 24
    # K=3 -> 2*K=6 < 20 -> intraday default 20 wins
    assert resolve_trades_per_day({"xsec_basket_size": 3}, "1Min") == 20


# ---------------------------------------------------------------------------
# resolve_trades_per_day — EXPLICIT override (NEW)
# ---------------------------------------------------------------------------

def test_trades_explicit_override_daily():
    assert resolve_trades_per_day({"max_trades_per_day": 8}) == 8


def test_trades_explicit_override_intraday_beats_default():
    assert resolve_trades_per_day({"max_trades_per_day": 8}, "1Min") == 8
    assert resolve_trades_per_day({"max_trades_per_day": 35}, "1Min") == 35


def test_trades_explicit_override_beats_basket_and_intraday():
    params = {"max_trades_per_day": 30, "xsec_basket_size": 12}
    assert resolve_trades_per_day(params, "1Min") == 30


def test_trades_explicit_override_clamped_to_ceiling():
    assert resolve_trades_per_day({"max_trades_per_day": 999}) == MAX_TRADES_PER_DAY_CEILING
    assert resolve_trades_per_day(
        {"max_trades_per_day": 10_000}, "1Min") == MAX_TRADES_PER_DAY_CEILING


def test_trades_explicit_override_malformed_falls_through():
    # < 1 or junk -> ignore override, fall through to the next tier
    assert resolve_trades_per_day({"max_trades_per_day": 0}, "1Min") == INTRADAY_TRADES_PER_DAY_DEFAULT
    assert resolve_trades_per_day({"max_trades_per_day": -5}) == MAX_TRADES_PER_DAY
    assert resolve_trades_per_day({"max_trades_per_day": "x"}, "1Min") == INTRADAY_TRADES_PER_DAY_DEFAULT
    assert resolve_trades_per_day({"max_trades_per_day": None}) == MAX_TRADES_PER_DAY


def test_trades_explicit_override_string_numeric_works():
    assert resolve_trades_per_day({"max_trades_per_day": "7"}) == 7


def test_trades_ceiling_is_a_hard_safety_floor():
    # no combination of intraday + basket can exceed the ceiling
    params = {"xsec_basket_size": 12}
    assert resolve_trades_per_day(params, "1Min") <= MAX_TRADES_PER_DAY_CEILING
