"""Pins the core decision contract of the macro_regime_long candidate:
close-logic-first (never trapped long when the macro regime turns risk-off) and
fail-safe-flat on missing macro warmup. Does NOT hit the network — macro_cache
is monkeypatched so the test is fast + deterministic.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

CAND = Path(__file__).resolve().parent.parent / "strategies_candidates" / "macro_regime_long"


def _load():
    mod_name = "_cand_macro_regime_long_test"
    spec = importlib.util.spec_from_file_location(mod_name, CAND / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # required so @dataclass can resolve __module__
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def strat():
    return _load()


def _ms(date="2024-05-01"):
    # market_state the backtester would pass: latest bar carries the date.
    return {"bars": [{"t": f"{date}T15:00:00Z", "c": 400.0}], "regime": None}


def _patch_macro(strat, monkeypatch, liq, curve):
    monkeypatch.setattr(strat.macro_cache, "liq_slope_asof", lambda *a, **k: liq)
    monkeypatch.setattr(strat.macro_cache, "curve_spread_asof", lambda *a, **k: curve)


def test_risk_on_flat_enters_long(strat, monkeypatch):
    _patch_macro(strat, monkeypatch, liq=100000.0, curve=0.5)  # both gates pass
    act = strat.decide(_ms(), {}, {})
    assert act.action == "buy", act.reason


def test_risk_off_while_holding_closes(strat, monkeypatch):
    # liquidity contracting (QT) => risk-off; we are long => MUST close, not hold.
    _patch_macro(strat, monkeypatch, liq=-250000.0, curve=0.5)
    pos = {"QQQ": {"qty": 0.25}}
    act = strat.decide(_ms(), pos, {})
    assert act.action == "close", act.reason


def test_risk_on_while_holding_holds(strat, monkeypatch):
    _patch_macro(strat, monkeypatch, liq=100000.0, curve=0.5)
    pos = {"QQQ": {"qty": 0.25}}
    act = strat.decide(_ms(), pos, {})
    assert act.action == "hold", act.reason


def test_deep_inversion_blocks_entry(strat, monkeypatch):
    # liquidity fine but curve deeply inverted (< -0.5) => risk-off => stay flat.
    _patch_macro(strat, monkeypatch, liq=100000.0, curve=-0.8)
    act = strat.decide(_ms(), {}, {})
    assert act.action == "hold", act.reason


def test_missing_warmup_is_failsafe_flat_and_can_close(strat, monkeypatch):
    # macro None => risk-off by construction. Flat stays flat...
    _patch_macro(strat, monkeypatch, liq=None, curve=None)
    assert strat.decide(_ms(), {}, {}).action == "hold"
    # ...but if somehow long, fail-safe must still CLOSE (never trapped).
    pos = {"QQQ": {"qty": 0.25}}
    assert strat.decide(_ms(), pos, {}).action == "close"
