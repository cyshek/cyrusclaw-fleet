"""L165 integration: bear-flatten gate fires end-to-end inside runner.run and
runner_xsec.run for opt-in strategies, and is a no-op for non-opted-in ones.

Mirrors the _FakeAlpacaClient fixture style from test_runner.py /
test_runner_xsec.py but supplies a full 260-bar SPY series so the SPY-200d
gate can actually evaluate.
"""

from __future__ import annotations

import types
import unittest
from pathlib import Path
from unittest import mock

from runner import db, runner, runner_xsec


_TEST_DB = Path(__file__).resolve().parent / "_l165_integ_test.db"


def _bear_spy(n=260):
    # Steeply descending -> last close far below SMA200.
    return [{"t": f"2020-01-{(i % 27) + 1:02d}T00:00:00Z",
             "o": 300 - i * 0.5, "h": 300 - i * 0.5,
             "l": 300 - i * 0.5, "c": 300 - i * 0.5} for i in range(n)]


def _bull_spy(n=260):
    # Steadily rising -> last close far above SMA200.
    return [{"t": f"2020-01-{(i % 27) + 1:02d}T00:00:00Z",
             "o": 100 + i * 0.5, "h": 100 + i * 0.5,
             "l": 100 + i * 0.5, "c": 100 + i * 0.5} for i in range(n)]


class _GateFakeAlpaca:
    """Fake broker whose SPY series is configurable (bull/bear) so the L165
    gate evaluates a real 200/201d SMA. The traded symbol's own bars are a
    short benign uptrend; the gated stub strategy always WANTS to buy, so any
    'no buy' outcome is attributable to the gate."""

    spy_series = _bear_spy()

    def __init__(self):
        self.submitted_orders = []
        self.price = 50.0

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        return "/" in symbol

    def latest_stock_price(self, symbol):
        return self.price

    def latest_crypto_price(self, symbol):
        return self.price

    def stock_bars(self, symbol, *, timeframe, limit):
        if symbol == "SPY":
            return list(self.spy_series)[-limit:]
        # traded symbol / basket legs: short uptrend, enough for vol etc.
        return [{"t": f"2026-01-{(i % 27) + 1:02d}T00:00:00Z",
                 "o": 40 + i, "h": 41 + i, "l": 39 + i, "c": 40 + i}
                for i in range(60)]

    def crypto_bars(self, symbol, *, timeframe, limit):
        return self.stock_bars(symbol, timeframe=timeframe, limit=limit)

    def submit_market_order(self, symbol, side, *, qty=None, notional_usd=None):
        order = {"id": f"order-{len(self.submitted_orders)+1:024d}",
                 "status": "filled", "filled_avg_price": self.price,
                 "qty": str(qty) if qty is not None else "",
                 "filled_qty": str(qty) if qty is not None else ""}
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty, "order": order})
        return order


class _Base(unittest.TestCase):
    def setUp(self):
        if _TEST_DB.exists():
            _TEST_DB.unlink()
        orig = db.DB_PATH
        self._dbp = mock.patch.object(db, "DB_PATH", _TEST_DB)
        self._dbp.start()
        self._orig_defaults = {}
        for name in dir(db):
            fn = getattr(db, name)
            if not isinstance(fn, types.FunctionType):
                continue
            if fn.__defaults__:
                new = tuple(_TEST_DB if d == orig else d for d in fn.__defaults__)
                if new != fn.__defaults__:
                    self._orig_defaults[(fn, "pos")] = fn.__defaults__
                    fn.__defaults__ = new
            if fn.__kwdefaults__:
                nkw = {k: (_TEST_DB if v == orig else v) for k, v in fn.__kwdefaults__.items()}
                if nkw != fn.__kwdefaults__:
                    self._orig_defaults[(fn, "kw")] = dict(fn.__kwdefaults__)
                    fn.__kwdefaults__ = nkw
        db.init_db(_TEST_DB)
        self.fake = _GateFakeAlpaca()

    def tearDown(self):
        for (fn, kind), defs in self._orig_defaults.items():
            if kind == "pos":
                fn.__defaults__ = defs
            else:
                fn.__kwdefaults__ = defs
        self._dbp.stop()

    def _orders(self):
        return self.fake.submitted_orders

    def _decisions(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT action, reason FROM decisions ORDER BY id ASC").fetchall()]


# ---------------------------------------------------------------------------
# runner.run (single-symbol path: tqqq_cot_combo shape)
# ---------------------------------------------------------------------------

class TestSingleSymbolGate(_Base):
    def _run_with(self, spy_series, params, decide_fn):
        self.fake.spy_series = spy_series
        cc = mock.MagicMock(return_value=self.fake)
        cc.is_crypto_symbol = _GateFakeAlpaca.is_crypto_symbol
        stub = mock.MagicMock()
        stub.decide = decide_fn
        with mock.patch.object(runner, "AlpacaClient", cc), \
             mock.patch.object(runner, "is_us_equity_market_open", return_value=True), \
             mock.patch.object(runner, "killswitch_active", return_value=False), \
             mock.patch.object(runner, "load_strategy", return_value=(stub, params)):
            return runner.run("gated")

    def test_bear_blocks_buy_when_flat(self):
        params = {"symbol": "SYM", "timeframe": "1Day", "bar_limit": 60,
                  "notional_usd": 50.0, "bear_flatten_gate": True}
        # strategy WANTS to buy; gate must suppress it and log bear_flatten_hold
        rc = self._run_with(_bear_spy(), params,
                            lambda *a, **k: _mk("buy", "SYM", 50.0))
        self.assertEqual(rc, 0)
        self.assertEqual(self._orders(), [], "bear gate must block the buy")
        actions = [d["action"] for d in self._decisions()]
        self.assertIn("bear_flatten_hold", actions)

    def test_bull_allows_strategy_buy(self):
        params = {"symbol": "SYM", "timeframe": "1Day", "bar_limit": 60,
                  "notional_usd": 50.0, "bear_flatten_gate": True}
        rc = self._run_with(_bull_spy(), params,
                            lambda *a, **k: _mk("buy", "SYM", 50.0))
        self.assertEqual(rc, 0)
        # gate defers -> strategy's buy goes through
        self.assertEqual(len(self._orders()), 1)
        self.assertEqual(self._orders()[0]["side"], "buy")

    def test_no_optin_means_no_gate(self):
        # Same bear SPY, but bear_flatten_gate absent -> strategy buy executes.
        params = {"symbol": "SYM", "timeframe": "1Day", "bar_limit": 60,
                  "notional_usd": 50.0}
        rc = self._run_with(_bear_spy(), params,
                            lambda *a, **k: _mk("buy", "SYM", 50.0))
        self.assertEqual(rc, 0)
        self.assertEqual(len(self._orders()), 1,
                         "non-opted-in strategy must be unaffected by L165")


def _mk(action, symbol, notional=0.0, qty=None, reason="stub"):
    a = types.SimpleNamespace()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional
    a.qty = qty
    a.reason = reason
    return a


# ---------------------------------------------------------------------------
# runner_xsec.run (basket path: allocator_blend shape)
# ---------------------------------------------------------------------------

class TestXsecGate(_Base):
    def _run_xsec_with(self, spy_series, params, decide_xsec_fn):
        self.fake.spy_series = spy_series
        cc = mock.MagicMock(return_value=self.fake)
        cc.is_crypto_symbol = _GateFakeAlpaca.is_crypto_symbol
        with mock.patch.object(runner_xsec, "AlpacaClient", cc), \
             mock.patch.object(runner_xsec, "is_us_equity_market_open", return_value=True), \
             mock.patch.object(runner_xsec, "killswitch_active", return_value=False), \
             mock.patch.object(runner_xsec, "load_xsec_strategy",
                               return_value=(decide_xsec_fn, params)):
            return runner_xsec.run("gated_xsec")

    def test_bear_overrides_to_close_held_legs(self):
        params = {"basket": ["AAA", "BBB"], "timeframe": "1Day",
                  "bar_limit": 60, "bear_flatten_gate": True,
                  "notional_usd": 50.0}
        # Seed a held position in AAA so the gate has something to close.
        db.log_trade(strategy="gated_xsec", symbol="AAA", side="buy",
                     qty=3.0, price=40.0, notional_usd=120.0,
                     alpaca_order_id="seedorder000000000000001",
                     status="filled")
        # decide would want to BUY BBB; gate must override to close AAA + no buy.
        def decide_xsec(ms, ps, p):
            return {"BBB": _mk("buy", "BBB", 50.0)}
        rc = self._run_xsec_with(_bear_spy(), params, decide_xsec)
        self.assertEqual(rc, 0)
        sides = [(o["symbol"], o["side"]) for o in self._orders()]
        # AAA closed (sell), no BBB buy.
        self.assertIn(("AAA", "sell"), sides)
        self.assertNotIn(("BBB", "buy"), sides)
        actions = [d["action"] for d in self._decisions()]
        self.assertIn("bear_flatten_close", actions)

    def test_bull_defers_to_decide_xsec(self):
        params = {"basket": ["AAA", "BBB"], "timeframe": "1Day",
                  "bar_limit": 60, "bear_flatten_gate": True,
                  "notional_usd": 50.0}
        called = {"n": 0}
        def decide_xsec(ms, ps, p):
            called["n"] += 1
            return {}
        rc = self._run_xsec_with(_bull_spy(), params, decide_xsec)
        self.assertEqual(rc, 0)
        self.assertEqual(called["n"], 1, "bull -> decide_xsec must be called")


if __name__ == "__main__":
    unittest.main()
