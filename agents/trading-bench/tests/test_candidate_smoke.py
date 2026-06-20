"""Tests for runner/candidate_smoke.py — both single-symbol and xsec paths.

Single-symbol path was previously tested only via runtime smoke (no unit
tests). Adding minimal coverage for both branches now that xsec dispatch
was added (2026-05-30).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import candidate_smoke  # noqa: E402


class _XsecModule:
    """Fake module exposing decide_xsec."""
    def __init__(self, return_value):
        self._rv = return_value
    def decide_xsec(self, ms, ps, params):  # noqa: D401
        return self._rv


class _SingleModule:
    """Fake module exposing decide."""
    def __init__(self, return_value):
        self._rv = return_value
    def decide(self, ms, ps, params):
        return self._rv


def _action(act, sym="X", notional=10.0):
    a = SimpleNamespace()
    a.action = act
    a.symbol = sym
    a.notional_usd = notional
    a.qty = None
    a.reason = "t"
    return a


class TestXsecDetection(unittest.TestCase):

    def test_module_with_decide_xsec_is_xsec(self):
        mod = _XsecModule({"A": _action("buy", "A")})
        self.assertTrue(candidate_smoke._is_xsec_candidate(mod))

    def test_module_with_decide_only_is_single(self):
        mod = _SingleModule(_action("buy"))
        self.assertFalse(candidate_smoke._is_xsec_candidate(mod))


class TestXsecSmoke(unittest.TestCase):
    """Patch load_candidate + AlpacaClient so we exercise the xsec smoke
    path without hitting Alpaca."""

    def _run(self, module, params):
        fake_client = MagicMock()
        # The xsec build_market_state calls stock_bars per symbol + SPY.
        fake_client.stock_bars.return_value = [
            {"t": "2024-01-01T00:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1}
        ]
        fake_client.crypto_bars.return_value = []
        # Patch is_crypto_symbol staticmethod via patching the class attr
        with patch.object(candidate_smoke, "load_candidate",
                          return_value=(module, params)), \
             patch.object(candidate_smoke, "AlpacaClient",
                          return_value=fake_client):
            return candidate_smoke.smoke("dummy_xsec_candidate")

    def test_xsec_basket_ok(self):
        mod = _XsecModule({"XLK": _action("buy", "XLK", 50.0)})
        rc = self._run(mod, {"basket": ["XLK", "XLF"], "timeframe": "1Day"})
        self.assertEqual(rc, 0)

    def test_xsec_empty_actions_ok(self):
        # Empty dict (= hold all) should still be OK.
        mod = _XsecModule({})
        rc = self._run(mod, {"basket": ["XLK", "XLF"], "timeframe": "1Day"})
        self.assertEqual(rc, 0)

    def test_xsec_missing_basket_fails(self):
        mod = _XsecModule({})
        rc = self._run(mod, {"timeframe": "1Day"})
        self.assertEqual(rc, 1)

    def test_xsec_bad_action_fails(self):
        mod = _XsecModule({"XLK": _action("zap", "XLK", 50.0)})
        rc = self._run(mod, {"basket": ["XLK", "XLF"], "timeframe": "1Day"})
        self.assertEqual(rc, 1)

    def test_xsec_decide_raises_fails(self):
        class _Raiser:
            def decide_xsec(self, *a, **kw):
                raise RuntimeError("boom")
        rc = self._run(_Raiser(), {"basket": ["XLK"], "timeframe": "1Day"})
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
