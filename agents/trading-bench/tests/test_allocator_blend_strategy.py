"""Smoke + unit tests for strategies/allocator_blend/strategy.py (decide_xsec).

Two layers:
  1. DETERMINISTIC unit tests with compute_blend_state() MONKEYPATCHED to a
     fixed weight vector -> exercises the weights->orders mapping, the churn
     guard, the trim-vs-close split, and the fail-safes WITHOUT any network.
  2. A LIVE integration smoke against the real validated tracker, gated to
     skip cleanly if the engine/network is unavailable from this host.

This file does NOT touch the runner; it calls decide_xsec directly with a
hand-built market_state/position_state shaped exactly as runner_xsec emits.
"""
from __future__ import annotations

import importlib
import math

import pytest

strat = importlib.import_module("strategies.allocator_blend.strategy")


# --------------------------------------------------------------------------- #
# Helpers to build the runner-shaped inputs.
# --------------------------------------------------------------------------- #
def _market_state(prices: dict, clock_t: str = "2026-06-18T00:00:00Z",
                  strategy_state=None) -> dict:
    symbols = {}
    for sym, px in prices.items():
        symbols[sym] = {
            "bars": [{"t": clock_t, "o": px, "h": px, "l": px, "c": px, "v": 1}],
            "last_price": px,
            "has_bar": True,
        }
    return {
        "timeframe": "1Day",
        "clock_t": clock_t,
        "symbols": symbols,
        "regime": None,
        "strategy_state": strategy_state if strategy_state is not None else {},
    }


def _position_state(holdings: dict, prices: dict) -> dict:
    """holdings: {sym: qty}. Builds the {qty, market_value, avg_entry_price} view."""
    out = {}
    for sym, qty in holdings.items():
        px = prices.get(sym, 0.0)
        out[sym] = {"qty": float(qty), "market_value": float(qty) * px,
                    "avg_entry_price": px}
    return out


def _params(**over) -> dict:
    p = {
        "basket": ["TQQQ", "SPY", "QQQ", "GLD", "TLT"],
        "max_notional_usd": 100.0,
        "churn_frac": 0.05,
        "monthly_cadence": True,
    }
    p.update(over)
    return p


def _patch_weights(monkeypatch, weights):
    """Force _compute_target_weights to return a fixed vector (no network)."""
    monkeypatch.setattr(strat, "_compute_target_weights",
                        lambda params: dict(weights))


# Representative validated decomposition (from the live tracker 2026-06-18).
WEIGHTS = {"TQQQ": 0.1319, "SPY": 0.279, "QQQ": 0.279}
PRICES = {"TQQQ": 80.0, "SPY": 600.0, "QQQ": 520.0, "GLD": 250.0, "TLT": 90.0}


# --------------------------------------------------------------------------- #
# 1. Cold start: flat book -> buys each target leg at floor(tgt_notional/px).
# --------------------------------------------------------------------------- #
class TestColdStartBuys:
    def test_buys_targets_from_flat(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        ms = _market_state(PRICES)
        ps = _position_state({}, PRICES)
        acts = strat.decide_xsec(ms, ps, _params())

        # TQQQ: floor(13.19 / 80) = 0 -> tiny weight floors to flat, no order.
        assert "TQQQ" not in acts or acts["TQQQ"].action in ("hold",)
        # SPY: floor(27.9 / 600) = 0 as well at this price -> also flat.
        # Use cheaper prices to get real buys (next test); here assert no crash
        # and that no leg flips short / no close-from-flat is emitted.
        for sym, a in acts.items():
            assert a.action in ("buy", "hold")  # never trim/close from flat
            if a.action == "buy":
                assert a.qty is not None and a.qty > 0

    def test_buys_have_correct_qty_with_tradeable_prices(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        # Cheaper prices so target notionals floor to >0 shares.
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        ms = _market_state(prices)
        ps = _position_state({}, prices)
        acts = strat.decide_xsec(ms, ps, _params(max_notional_usd=1000.0))

        # tgt_notional = w * 1000; qty = floor(notional/px).
        exp = {
            "TQQQ": math.floor(0.1319 * 1000 / 8.0),   # 131.9/8 = 16
            "SPY": math.floor(0.279 * 1000 / 6.0),     # 279/6   = 46
            "QQQ": math.floor(0.279 * 1000 / 5.0),     # 279/5   = 55
        }
        for sym, q in exp.items():
            assert sym in acts, f"{sym} should be bought"
            assert acts[sym].action == "buy"
            assert acts[sym].qty == float(q), f"{sym} qty {acts[sym].qty} != {q}"
        # GLD/TLT have zero target weight -> not bought.
        assert "GLD" not in acts
        assert "TLT" not in acts


# --------------------------------------------------------------------------- #
# 2. Overweight leg -> TRIM (not close), explicit qty, stays long.
# --------------------------------------------------------------------------- #
class TestOverweightTrims:
    def test_overweight_leg_trims_with_explicit_qty(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        # SPY target qty = floor(0.279*1000/6) = 46. Hold 80 -> overweight by 34.
        ms = _market_state(prices)
        ps = _position_state({"SPY": 80}, prices)
        acts = strat.decide_xsec(ms, ps, _params(max_notional_usd=1000.0))

        assert "SPY" in acts
        a = acts["SPY"]
        assert a.action == "trim", f"expected trim, got {a.action}"
        assert a.qty == float(80 - 46)   # reduce by exactly 34 shares
        assert a.qty > 0
        # Trim keeps it long (target>0): must NOT be a close.
        assert a.action != "close"


# --------------------------------------------------------------------------- #
# 3. Target-flat leg held -> CLOSE (full exit), not trim.
# --------------------------------------------------------------------------- #
class TestTargetFlatCloses:
    def test_held_leg_with_zero_target_closes(self, monkeypatch):
        # GLD/TLT not in WEIGHTS -> target 0. Holding GLD -> close it.
        _patch_weights(monkeypatch, WEIGHTS)
        ms = _market_state(PRICES)
        ps = _position_state({"GLD": 5}, PRICES)
        acts = strat.decide_xsec(ms, ps, _params())

        assert "GLD" in acts
        assert acts["GLD"].action == "close"

    def test_unheld_zero_target_emits_nothing(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        ms = _market_state(PRICES)
        ps = _position_state({}, PRICES)
        acts = strat.decide_xsec(ms, ps, _params())
        # TLT: not held, target 0 -> no order at all.
        assert "TLT" not in acts


# --------------------------------------------------------------------------- #
# 4. Churn guard: within band -> HOLD (no thrash).
# --------------------------------------------------------------------------- #
class TestChurnGuard:
    def test_small_delta_holds(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        # QQQ target = floor(0.279*1000/5) = 55. Hold 56 -> delta -1.
        # threshold = max(1, floor(0.05*55)) = max(1,2) = 2. |−1| <= 2 -> hold.
        ms = _market_state(prices)
        ps = _position_state({"QQQ": 56}, prices)
        acts = strat.decide_xsec(ms, ps, _params(max_notional_usd=1000.0))
        assert "QQQ" in acts
        assert acts["QQQ"].action == "hold"


# --------------------------------------------------------------------------- #
# 5. Fail-safes.
# --------------------------------------------------------------------------- #
class TestFailSafes:
    def test_engine_failure_holds_whole_basket(self, monkeypatch):
        # _compute_target_weights returns None on any engine error -> {} (hold all).
        monkeypatch.setattr(strat, "_compute_target_weights", lambda params: None)
        ms = _market_state(PRICES)
        ps = _position_state({"SPY": 80, "GLD": 5}, PRICES)
        acts = strat.decide_xsec(ms, ps, _params())
        assert acts == {}, "engine failure must HOLD the whole basket (no orders)"

    def test_missing_price_holds_that_leg(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = dict(PRICES)
        ms = _market_state(prices)
        # Wipe SPY's price -> unpriceable leg.
        ms["symbols"]["SPY"]["last_price"] = None
        ms["symbols"]["SPY"]["bars"] = []
        ps = _position_state({"SPY": 80}, prices)
        acts = strat.decide_xsec(ms, ps, _params())
        assert "SPY" in acts
        assert acts["SPY"].action == "hold"
        # A held leg we can't price must NOT be closed/trimmed blindly.
        assert acts["SPY"].action not in ("close", "trim", "buy")

    def test_no_negative_or_short_qty_ever(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        ms = _market_state(prices)
        ps = _position_state({"SPY": 200, "GLD": 9}, prices)  # very overweight
        acts = strat.decide_xsec(ms, ps, _params(max_notional_usd=1000.0))
        for sym, a in acts.items():
            if a.qty is not None:
                assert a.qty > 0, f"{sym} emitted non-positive qty {a.qty}"
            # trim qty can never exceed the held qty (the runner clamps too, but
            # the strategy should already only ask for held-cur - target).
            if a.action == "trim":
                held = ps[sym]["qty"]
                assert a.qty <= held, f"{sym} trim {a.qty} exceeds held {held}"


# --------------------------------------------------------------------------- #
# 6. Monthly cadence: second call same month -> no actions.
# --------------------------------------------------------------------------- #
class TestMonthlyCadence:
    def test_same_month_second_call_holds(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        state = {}
        ms1 = _market_state(prices, clock_t="2026-06-18T00:00:00Z",
                            strategy_state=state)
        ps = _position_state({}, prices)
        acts1 = strat.decide_xsec(ms1, ps, _params(max_notional_usd=1000.0))
        assert acts1, "first call of the month should act"
        assert state.get("last_rebalance_month") == "2026-06"

        # Second call same month -> cadence gate returns {} (no churn).
        ms2 = _market_state(prices, clock_t="2026-06-25T00:00:00Z",
                            strategy_state=state)
        acts2 = strat.decide_xsec(ms2, ps, _params(max_notional_usd=1000.0))
        assert acts2 == {}, "same-month second call must HOLD all (cadence)"

    def test_cadence_off_acts_every_tick(self, monkeypatch):
        _patch_weights(monkeypatch, WEIGHTS)
        prices = {"TQQQ": 8.0, "SPY": 6.0, "QQQ": 5.0, "GLD": 25.0, "TLT": 9.0}
        state = {"last_rebalance_month": "2026-06"}
        ms = _market_state(prices, clock_t="2026-06-25T00:00:00Z",
                           strategy_state=state)
        ps = _position_state({}, prices)
        acts = strat.decide_xsec(ms, ps,
                                 _params(max_notional_usd=1000.0,
                                         monthly_cadence=False))
        assert acts, "cadence off -> should re-target even mid-month"


# --------------------------------------------------------------------------- #
# 7. LIVE integration smoke against the REAL validated tracker.
#    Gated: skips cleanly if the engine/network is unavailable.
# --------------------------------------------------------------------------- #
class TestLiveSmoke:
    def test_real_tracker_yields_sane_action_dict(self):
        try:
            from runner import allocator_paper_tracker as apt
            st = apt.compute_blend_state()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"live tracker unavailable from this host: {e!r}")

        tw = st.get("target_weights") or {}
        if not tw:
            pytest.skip("tracker returned empty target_weights")

        # Build a market_state priced at each target leg's last close, flat book.
        prices = {}
        for sym in ["TQQQ", "SPY", "QQQ", "GLD", "TLT"]:
            prices[sym] = 100.0  # placeholder; real prices not needed for sanity
        ms = _market_state(prices, clock_t=st["mark_date"] + "T00:00:00Z")
        ps = _position_state({}, prices)
        acts = strat.decide_xsec(ms, ps, _params(max_notional_usd=10000.0))

        assert isinstance(acts, dict)
        # Every emitted action is well-formed and never a short/close-from-flat.
        for sym, a in acts.items():
            assert a.action in ("buy", "trim", "hold", "close")
            assert a.symbol == sym
            if a.action == "buy":
                assert a.qty is not None and a.qty > 0
            # From a flat book we can only buy or hold (no trim/close).
            assert a.action in ("buy", "hold")
        # At least the positive-weight targets should be considered (bought or
        # held); the strategy must not silently drop them all.
        considered = set(acts.keys())
        pos_targets = {s for s, w in tw.items() if w > 0
                       and s in ("TQQQ", "SPY", "QQQ", "GLD", "TLT")}
        # With $10k notional, the sizeable targets should produce >=1 buy.
        buys = {s for s, a in acts.items() if a.action == "buy"}
        assert buys, f"expected >=1 buy for targets {pos_targets}, got {acts}"
