"""Pins the decision contract of the sma_crossover_qqq_macrogate candidate (v2
of the orthogonal-macro experiment): the existing 10/30 SMA crossover on QQQ 1h
bars, plus an ORTHOGONAL MACRO ACCELERATION ENTRY GATE.

Contract under test:
  (a) bullish SMA cross + macro risk-ON  + flat     -> BUY
  (b) bullish SMA cross + macro risk-OFF + flat     -> HOLD (entry blocked)
  (c) bearish SMA cross while holding               -> CLOSE  (REGARDLESS of macro)
  (d) missing macro warmup while holding            -> CLOSE still allowed
  (+) the close/exit branch is byte-for-byte the parent sma_crossover_qqq's, so a
      bearish cross is honored before the gate is ever consulted (never trapped).

No network: macro_cache.liq_slope_asof / curve_spread_asof are monkeypatched.

MACRO GATE RECAP (v2 = ACCELERATION, not raw level): the strategy calls
liq_slope_asof TWICE per entry decision — once for the as-of date (the "now"
slope) and once for an anchor ~accel_lookback_days earlier (the "past" slope) —
and risk_on requires (now - past) > liq_accel_min AND curve > curve_min. To make
the gate deterministic we monkeypatch liq_slope_asof with a function that returns
a HIGHER value for recent dates and a LOWER value for the ~91d-earlier anchor
(=> accel > 0 => risk-ON), or the reverse / a constant (=> accel <= 0 =>
risk-OFF). curve_spread_asof is patched to a constant.
"""
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

CAND = (Path(__file__).resolve().parent.parent / "strategies_candidates"
        / "sma_crossover_qqq_macrogate")

# The bar date the constructed market_state decides on (latest bar's date).
AS_OF = "2025-10-01"
# Anything strictly older than this is the "past" acceleration leg.
ACCEL_CUTOFF = "2025-08-15"  # ~ AS_OF - 47d; the real anchor is AS_OF - 91d


def _load():
    mod_name = "_cand_sma_crossover_qqq_macrogate_test"
    spec = importlib.util.spec_from_file_location(mod_name, CAND / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # required so @dataclass can resolve __module__
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def strat():
    return _load()


# --- Bar builders: monotone ramps drive the SMA cross deterministically. -----
# UPTREND -> SMA(fast=10) > SMA(slow=30) (bullish cross / entry candidate).
# DOWNTREND -> SMA(fast=10) < SMA(slow=30) (bearish cross / close signal).
# We construct >= slow_p+ bars so both SMAs are defined. The LAST bar carries
# AS_OF as its date so the macro lookups key off AS_OF.

def _uptrend_bars(n=40, base=100.0, date=AS_OF):
    return [{"t": f"{date}T{9 + i // 6:02d}:30:00Z", "c": base + i} for i in range(n)]


def _downtrend_bars(n=40, base=200.0, date=AS_OF):
    return [{"t": f"{date}T{9 + i // 6:02d}:30:00Z", "c": base - i} for i in range(n)]


def _ms(bars):
    # market_state the backtester passes: bars + regime (macro is NOT in here;
    # the strategy reads macro itself via macro_cache, which we monkeypatch).
    return {"bars": bars, "regime": None}


def _patch_accel(strat, monkeypatch, *, accelerating: bool, curve: float):
    """Patch macro_cache so liq accel is positive (accelerating=True => risk-ON
    eligible) or non-positive (accelerating=False), and curve is constant.

    liq_slope_asof(as_of_date, ...) returns a value that depends on whether
    as_of_date is the recent ("now") leg or the ~91d-earlier anchor leg. The
    strategy computes accel = now_slope - past_slope.
    """
    def fake_slope(as_of_date, *a, **k):
        recent = as_of_date >= ACCEL_CUTOFF
        if accelerating:
            # now (recent) HIGHER than past => accel > 0
            return 50000.0 if recent else -50000.0
        else:
            # now (recent) LOWER than past => accel < 0 (drag worsening)
            return -50000.0 if recent else 50000.0

    monkeypatch.setattr(strat.macro_cache, "liq_slope_asof", fake_slope)
    monkeypatch.setattr(strat.macro_cache, "curve_spread_asof",
                        lambda *a, **k: curve)


def _patch_missing(strat, monkeypatch):
    """Macro warmup missing => every leg None => fail-safe risk-OFF."""
    monkeypatch.setattr(strat.macro_cache, "liq_slope_asof", lambda *a, **k: None)
    monkeypatch.setattr(strat.macro_cache, "curve_spread_asof", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# (a) bullish cross + risk-ON + flat -> BUY
# ---------------------------------------------------------------------------
def test_bullish_cross_risk_on_flat_buys(strat, monkeypatch):
    _patch_accel(strat, monkeypatch, accelerating=True, curve=0.5)
    act = strat.decide(_ms(_uptrend_bars()), {}, {})
    assert act.action == "buy", act.reason
    assert act.symbol == "QQQ"
    assert act.notional_usd == 100.0


# ---------------------------------------------------------------------------
# (b) bullish cross + risk-OFF + flat -> HOLD (entry blocked)
# ---------------------------------------------------------------------------
def test_bullish_cross_risk_off_accel_flat_holds(strat, monkeypatch):
    # liquidity drag WORSENING (accel < 0) => risk-off => block the entry.
    _patch_accel(strat, monkeypatch, accelerating=False, curve=0.5)
    act = strat.decide(_ms(_uptrend_bars()), {}, {})
    assert act.action == "hold", act.reason
    assert "entry blocked" in act.reason


def test_bullish_cross_risk_off_deep_inversion_flat_holds(strat, monkeypatch):
    # liquidity accelerating but curve deeply inverted (< -0.5) => risk-off.
    _patch_accel(strat, monkeypatch, accelerating=True, curve=-0.8)
    act = strat.decide(_ms(_uptrend_bars()), {}, {})
    assert act.action == "hold", act.reason
    assert "entry blocked" in act.reason


# ---------------------------------------------------------------------------
# (c) bearish cross while holding -> CLOSE regardless of macro (never trapped)
# ---------------------------------------------------------------------------
def test_bearish_cross_while_holding_closes_even_risk_on(strat, monkeypatch):
    # Macro is fully risk-ON; close must STILL fire on the bearish cross.
    _patch_accel(strat, monkeypatch, accelerating=True, curve=0.5)
    pos = {"QQQ": {"qty": 0.25}}
    act = strat.decide(_ms(_downtrend_bars()), pos, {})
    assert act.action == "close", act.reason


def test_bearish_cross_while_holding_closes_even_risk_off(strat, monkeypatch):
    # Macro risk-OFF too — close still fires (close branch runs before any gate).
    _patch_accel(strat, monkeypatch, accelerating=False, curve=-0.8)
    pos = {"QQQ": {"qty": 0.25}}
    act = strat.decide(_ms(_downtrend_bars()), pos, {})
    assert act.action == "close", act.reason


# ---------------------------------------------------------------------------
# (d) missing macro warmup while holding -> CLOSE still allowed
# ---------------------------------------------------------------------------
def test_missing_macro_warmup_while_holding_can_close(strat, monkeypatch):
    _patch_missing(strat, monkeypatch)
    pos = {"QQQ": {"qty": 0.25}}
    # bearish cross + missing macro => close still honored (never trapped).
    act = strat.decide(_ms(_downtrend_bars()), pos, {})
    assert act.action == "close", act.reason


def test_missing_macro_warmup_flat_blocks_entry(strat, monkeypatch):
    # Fail-safe: missing macro => risk-off => a bullish cross is blocked.
    _patch_missing(strat, monkeypatch)
    act = strat.decide(_ms(_uptrend_bars()), {}, {})
    assert act.action == "hold", act.reason
    assert "entry blocked" in act.reason


# ---------------------------------------------------------------------------
# Base-behavior sanity: not enough bars -> hold; no-signal flat -> hold.
# ---------------------------------------------------------------------------
def test_not_enough_bars_holds(strat, monkeypatch):
    _patch_accel(strat, monkeypatch, accelerating=True, curve=0.5)
    act = strat.decide(_ms(_uptrend_bars(n=5)), {}, {})
    assert act.action == "hold"
    assert "not enough bars" in act.reason


def test_risk_on_while_holding_holds(strat, monkeypatch):
    # Already long, bullish cross persists, macro risk-ON => no new action.
    _patch_accel(strat, monkeypatch, accelerating=True, curve=0.5)
    pos = {"QQQ": {"qty": 0.25}}
    act = strat.decide(_ms(_uptrend_bars()), pos, {})
    assert act.action == "hold", act.reason
