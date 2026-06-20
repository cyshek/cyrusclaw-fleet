"""End-to-end-ish tests for runner/runner.py.

The runner is the highest-blast-radius file in the project — it owns the
live tick lifecycle (killswitch -> load -> position/state -> backstop ->
decide -> risk -> submit -> log). Until now its only test coverage was
`./tick.sh` smoke runs (rc==0 against live Alpaca). That misses every
branch the smoke happens not to hit.

These tests monkeypatch `load_strategy` (so we don't need a real strategy
dir) and `AlpacaClient` (so we don't hit the network) and drive `run()`
against a tmp tournament.db. Each test asserts on the rows the runner
wrote (decisions, trades, runs) plus mock-call counts on the broker.

These are integration tests, not unit tests: they exercise db.py,
risk.py, safety_backstop.py via the runner's real wiring.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Per-test-module tmp DB. runner.db.DB_PATH is captured at module-import
# time, so we can't rely on env vars (other test modules may have already
# imported runner.db). Instead we monkeypatch DB_PATH in setUp.
_TMPDIR = tempfile.mkdtemp(prefix="tess_runner_")
_TEST_DB = Path(_TMPDIR) / "t.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import db, runner  # noqa: E402


def _action(action="hold", symbol="SYM", notional_usd=0.0, reason=""):
    """Mimics the per-strategy Action dataclass. The runner only reads
    these four attrs off the returned object."""
    class _A:
        pass
    a = _A()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional_usd
    a.reason = reason
    return a


class _FakeAlpacaClient:
    """Stand-in for runner.broker_alpaca.AlpacaClient. Configured per test
    via class attributes set on instantiation."""

    def __init__(self):
        self.submitted_orders = []
        self.bars_data = [
            {"t": "2026-01-01T00:00:00Z", "o": 100, "h": 101,
             "l": 99, "c": 100},
            {"t": "2026-01-01T01:00:00Z", "o": 100, "h": 102,
             "l": 100, "c": 101},
        ]
        self.price = 100.0
        self.fill_status = "filled"
        self.fill_price = 100.0
        # filled_avg_price returned by broker (None = use last-trade price)

    # The runner calls this STATIC method on the class to detect crypto.
    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        return "/" in symbol  # SYM == stock; SYM/USD == crypto

    def latest_stock_price(self, symbol):
        return self.price

    def latest_crypto_price(self, symbol):
        return self.price

    def stock_bars(self, symbol, *, timeframe, limit):
        if symbol == "SPY":
            return [{"t": "2026-01-01T00:00:00Z", "o": 500, "h": 500,
                     "l": 500, "c": 500}]
        return list(self.bars_data)

    def crypto_bars(self, symbol, *, timeframe, limit):
        return list(self.bars_data)

    def submit_market_order(self, symbol, side, *, qty=None, notional_usd=None):
        order = {
            "id": f"order-{len(self.submitted_orders) + 1}",
            "status": self.fill_status,
            "filled_avg_price": self.fill_price,
            "qty": str(qty) if qty is not None else "",
        }
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty,
                                      "notional_usd": notional_usd,
                                      "order": order})
        return order


class _RunnerTestBase(unittest.TestCase):
    """Common setup: fresh DB, swap AlpacaClient + load_strategy."""

    def setUp(self):
        # Fresh DB per test. The db helpers capture DB_PATH as a default arg
        # AT FUNCTION DEFINITION TIME (classic Python gotcha), so we can't
        # just monkeypatch db.DB_PATH — we also have to rebind each helper's
        # __defaults__ tuple. We capture the ORIGINAL db.DB_PATH first so we
        # can find which default args to swap.
        if _TEST_DB.exists():
            _TEST_DB.unlink()
        orig_db_path = db.DB_PATH  # capture BEFORE patching
        self._db_patcher = mock.patch.object(db, "DB_PATH", _TEST_DB)
        self._db_patcher.start()
        self._orig_defaults = {}
        import types  # noqa: WPS433
        for name in dir(db):
            fn = getattr(db, name)
            if not isinstance(fn, types.FunctionType):
                continue
            # Positional defaults.
            if fn.__defaults__:
                new = tuple(
                    _TEST_DB if d == orig_db_path else d
                    for d in fn.__defaults__
                )
                if new != fn.__defaults__:
                    self._orig_defaults[(fn, "pos")] = fn.__defaults__
                    fn.__defaults__ = new
            # Keyword-only defaults (e.g. log_trade's db_path lives here).
            if fn.__kwdefaults__:
                new_kw = {k: (_TEST_DB if v == orig_db_path else v)
                          for k, v in fn.__kwdefaults__.items()}
                if new_kw != fn.__kwdefaults__:
                    self._orig_defaults[(fn, "kw")] = dict(fn.__kwdefaults__)
                    fn.__kwdefaults__ = new_kw
        db.init_db(_TEST_DB)

        # Re-stub AlpacaClient as a class so the runner's `client = AlpacaClient()`
        # call returns OUR fake. Also need is_crypto_symbol on the class.
        self.fake_client = _FakeAlpacaClient()
        client_class = mock.MagicMock(return_value=self.fake_client)
        client_class.is_crypto_symbol = _FakeAlpacaClient.is_crypto_symbol
        self._client_patcher = mock.patch.object(runner, "AlpacaClient",
                                                 client_class)
        self._client_patcher.start()

        # Default: market open (so stocks tests don't all get short-circuited).
        # Individual tests override.
        self._market_patcher = mock.patch.object(
            runner, "is_us_equity_market_open", return_value=True)
        self._market_patcher.start()

        # Killswitch off by default.
        self._kill_patcher = mock.patch.object(
            runner, "killswitch_active", return_value=False)
        self._kill_patcher.start()

    def tearDown(self):
        self._kill_patcher.stop()
        self._market_patcher.stop()
        self._client_patcher.stop()
        self._db_patcher.stop()
        for (fn, kind), defs in self._orig_defaults.items():
            if kind == "pos":
                fn.__defaults__ = defs
            else:
                fn.__kwdefaults__ = defs

    def _patch_strategy(self, decide_fn, params=None):
        """Install a stub strategy. decide_fn(market_state, position_state,
        params) -> Action."""
        stub_module = mock.MagicMock()
        stub_module.decide = decide_fn
        if params is None:
            params = {"symbol": "SYM", "timeframe": "1Hour",
                      "bar_limit": 10, "notional_usd": 50.0}
        patcher = mock.patch.object(runner, "load_strategy",
                                    return_value=(stub_module, params))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _runs(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT outcome, detail FROM runs ORDER BY id ASC").fetchall()]

    def _trades(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trades ORDER BY id ASC").fetchall()]

    def _decisions(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT action, reason FROM decisions ORDER BY id ASC"
            ).fetchall()]


class TestKillswitch(_RunnerTestBase):
    """STOP_TRADING file present -> no-op, no broker call, killswitch run row."""

    def test_killswitch_short_circuits(self):
        self._patch_strategy(lambda *a, **k: _action("buy", "SYM", 50))
        with mock.patch.object(runner, "killswitch_active", return_value=True):
            rc = runner.run("anything")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "killswitch must prevent any broker call")
        runs = self._runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["outcome"], "killswitch")


class TestMarketClosed(_RunnerTestBase):
    """Stocks + market closed -> skip_market_closed, no broker call."""

    def test_stocks_closed_short_circuits(self):
        self._patch_strategy(lambda *a, **k: _action("buy", "SYM", 50))
        with mock.patch.object(runner, "is_us_equity_market_open",
                               return_value=False):
            rc = runner.run("any_stock")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[0]["detail"], "skip_market_closed")

    def test_crypto_ignores_market_closed(self):
        """Crypto strategies tick 24/7 regardless of equity market hours."""
        self._patch_strategy(
            lambda *a, **k: _action("hold", "BTC/USD"),
            params={"symbol": "BTC/USD", "timeframe": "1Hour",
                    "bar_limit": 10, "notional_usd": 50.0},
        )
        with mock.patch.object(runner, "is_us_equity_market_open",
                               return_value=False):
            rc = runner.run("any_crypto")
        self.assertEqual(rc, 0)
        # Got past the closed gate, into decide() which returned hold.
        self.assertEqual(self._runs()[0]["detail"], "hold")


class TestBuyAndHoldAndRiskReject(_RunnerTestBase):
    def test_buy_submits_order_and_logs_trade(self):
        self._patch_strategy(
            lambda *a, **k: _action("buy", "SYM", 50, "first entry"))
        rc = runner.run("any")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "buy")
        self.assertEqual(ord_["symbol"], "SYM")
        self.assertEqual(ord_["notional_usd"], 50.0)
        trades = self._trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], "buy")
        self.assertEqual(trades[0]["symbol"], "SYM")

    def test_hold_writes_no_trade(self):
        self._patch_strategy(
            lambda *a, **k: _action("hold", "SYM", 0, "no signal"))
        rc = runner.run("any")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._trades(), [])
        self.assertEqual(self._runs()[0]["detail"], "hold")

    def test_oversized_notional_rejected_by_risk(self):
        """MAX_NOTIONAL=$100 in risk.py — a $9999 buy must be skip_risk'd
        and never submitted."""
        self._patch_strategy(
            lambda *a, **k: _action("buy", "SYM", 9999, "yolo"))
        rc = runner.run("any")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "risk reject must prevent broker submission")
        self.assertEqual(self._trades(), [])
        self.assertTrue(self._runs()[0]["detail"].startswith("risk_reject:"))


class TestCloseWhenFlat(_RunnerTestBase):
    """Close requested with zero position -> hold log, no broker call."""

    def test_close_with_no_position(self):
        self._patch_strategy(
            lambda *a, **k: _action("close", "SYM", 0, "exit signal"))
        rc = runner.run("any")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[0]["detail"], "no-pos")


class TestSafetyBackstopWiring(_RunnerTestBase):
    """The backstop wiring in runner.py — when params trip and we hold a
    position, the runner must synthesize a close, skip decide(), and
    submit the close order."""

    def test_backstop_force_close_skips_decide_and_submits(self):
        # Seed a held position via the trade log so build_position_state
        # returns qty > 0.
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("backstop_test", "SYM", "buy", 1.0, 100.0, 100.0,
                 "ord-seed", "filled", "seed",
                 None, "2026-01-01T00:00:00Z"),
            )

        # Strategy would say "hold" — but the backstop should override.
        decide_calls = []

        def decide(market_state, position_state, params):
            decide_calls.append((market_state, position_state, params))
            return _action("hold", "SYM", 0, "should not be reached")

        # Price drops to 40 (-60%) and params trip at -50%.
        self.fake_client.price = 40.0
        self.fake_client.fill_price = 40.0
        self._patch_strategy(
            decide,
            params={"symbol": "SYM", "timeframe": "1Hour",
                    "bar_limit": 10, "notional_usd": 50.0,
                    "safety_max_loss_pct": -50.0},
        )

        rc = runner.run("backstop_test")
        self.assertEqual(rc, 0)
        self.assertEqual(decide_calls, [],
                         "decide() must be skipped when backstop fires")
        self.assertEqual(len(self.fake_client.submitted_orders), 1,
                         "backstop must submit exactly one close order")
        self.assertEqual(self.fake_client.submitted_orders[0]["side"], "sell")
        trades = self._trades()
        # Two trades: the seed buy + the backstop close.
        self.assertEqual(len(trades), 2)
        backstop_trade = trades[-1]
        self.assertEqual(backstop_trade["side"], "sell")
        self.assertIn("safety_backstop:max_loss_pct",
                      backstop_trade["reason"])

    def test_backstop_no_fire_falls_through_to_decide(self):
        """Same setup but price only down 10% (above the -50% threshold)
        — decide() should be called normally."""
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("bp2", "SYM", "buy", 1.0, 100.0, 100.0,
                 "ord-seed", "filled", "seed",
                 None, "2026-01-01T00:00:00Z"),
            )
        decide_called = {"n": 0}

        def decide(market_state, position_state, params):
            decide_called["n"] += 1
            return _action("hold", "SYM", 0, "still ok")

        self.fake_client.price = 90.0  # -10%
        self._patch_strategy(
            decide,
            params={"symbol": "SYM", "timeframe": "1Hour",
                    "bar_limit": 10, "notional_usd": 50.0,
                    "safety_max_loss_pct": -50.0},
        )
        rc = runner.run("bp2")
        self.assertEqual(rc, 0)
        self.assertEqual(decide_called["n"], 1,
                         "decide() must run when backstop doesn't fire")
        # No new orders (we held).
        self.assertEqual(len(self.fake_client.submitted_orders), 0)


class TestStrategyExceptionPath(_RunnerTestBase):
    """If decide() raises, the runner logs an error and returns rc=1
    without bringing down the cron."""

    def test_decide_exception_caught(self):
        def boom(*a, **k):
            raise RuntimeError("strategy bug")
        self._patch_strategy(boom)
        rc = runner.run("any")
        self.assertEqual(rc, 1)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[-1]["outcome"], "error")


if __name__ == "__main__":
    unittest.main()
