"""Tests for the post-submit order-status reconcile (runner.py) and the
one-shot backfill helper (runner/reconcile.py).

Background: before this fix, runner.py wrote the POST /v2/orders response
status ('pending_new' / 'accepted') into trades.status and never updated it.
The reconcile step polls GET /v2/orders/{id} a few times to capture the
settled state. Tests cover:
  - terminal-on-first-poll: status flips to 'filled' immediately.
  - still-pending: graceful exit with best-known status.
  - reconcile exception: swallowed; tick still completes rc=0.
  - backfill: walks NON_TERMINAL rows and updates each one.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_TMPDIR = tempfile.mkdtemp(prefix="tess_reconcile_")
_TEST_DB = Path(_TMPDIR) / "t.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import db, runner, reconcile  # noqa: E402


def _action(action="hold", symbol="SYM", notional_usd=0.0, reason=""):
    class _A:
        pass
    a = _A()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional_usd
    a.reason = reason
    return a


class _FakeClient:
    """Captures get_order calls + serves scripted responses."""

    def __init__(self, *, submit_status="pending_new",
                 get_order_responses=None,
                 get_order_raises=False):
        self.submitted_orders = []
        self.get_order_calls = []
        self.submit_status = submit_status
        # List of dicts; one per .get_order() call, in order. Last one is
        # repeated if more calls happen.
        self.get_order_responses = get_order_responses or []
        self.get_order_raises = get_order_raises
        self.bars_data = [
            {"t": "2026-01-01T00:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100},
            {"t": "2026-01-01T01:00:00Z", "o": 100, "h": 102, "l": 100, "c": 101},
        ]
        self.price = 100.0

    @staticmethod
    def is_crypto_symbol(symbol):
        return "/" in symbol

    def latest_stock_price(self, symbol): return self.price
    def latest_crypto_price(self, symbol): return self.price

    def stock_bars(self, symbol, *, timeframe, limit):
        if symbol == "SPY":
            return [{"t": "2026-01-01T00:00:00Z", "o": 500, "h": 500, "l": 500, "c": 500}]
        return list(self.bars_data)

    def crypto_bars(self, symbol, *, timeframe, limit):
        return list(self.bars_data)

    def submit_market_order(self, symbol, side, *, qty=None, notional_usd=None):
        order_id = f"order-{len(self.submitted_orders) + 1}"
        order = {
            "id": order_id,
            "status": self.submit_status,
            "filled_avg_price": None,
            "qty": str(qty) if qty is not None else "",
        }
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty, "notional_usd": notional_usd,
                                      "order": order})
        return order

    def get_order(self, order_id):
        self.get_order_calls.append(order_id)
        if self.get_order_raises:
            from runner.broker_alpaca import AlpacaError
            raise AlpacaError("simulated network failure")
        if not self.get_order_responses:
            return {"id": order_id, "status": self.submit_status}
        # Pop until last, then sticky-repeat the last response.
        if len(self.get_order_responses) > 1:
            return self.get_order_responses.pop(0)
        return self.get_order_responses[0]


class _ReconcileBase(unittest.TestCase):
    """Same DB-patching dance as test_runner.py: rebind both __defaults__
    and __kwdefaults__ on every db helper so they all point at _TEST_DB."""

    def setUp(self):
        if _TEST_DB.exists():
            _TEST_DB.unlink()
        orig_db_path = db.DB_PATH
        self._db_patcher = mock.patch.object(db, "DB_PATH", _TEST_DB)
        self._db_patcher.start()
        self._orig_defaults = {}
        for name in dir(db):
            fn = getattr(db, name)
            if not isinstance(fn, types.FunctionType):
                continue
            if fn.__defaults__:
                new = tuple(_TEST_DB if d == orig_db_path else d
                            for d in fn.__defaults__)
                if new != fn.__defaults__:
                    self._orig_defaults[(fn, "pos")] = fn.__defaults__
                    fn.__defaults__ = new
            if fn.__kwdefaults__:
                new_kw = {k: (_TEST_DB if v == orig_db_path else v)
                          for k, v in fn.__kwdefaults__.items()}
                if new_kw != fn.__kwdefaults__:
                    self._orig_defaults[(fn, "kw")] = dict(fn.__kwdefaults__)
                    fn.__kwdefaults__ = new_kw
        db.init_db(_TEST_DB)

        # Killswitch off; market open.
        self._kill = mock.patch.object(runner, "killswitch_active",
                                       return_value=False)
        self._kill.start()
        self._mkt = mock.patch.object(runner, "is_us_equity_market_open",
                                      return_value=True)
        self._mkt.start()

    def tearDown(self):
        self._mkt.stop()
        self._kill.stop()
        self._db_patcher.stop()
        for (fn, kind), defs in self._orig_defaults.items():
            if kind == "pos":
                fn.__defaults__ = defs
            else:
                fn.__kwdefaults__ = defs

    def _install_client(self, fake):
        client_class = mock.MagicMock(return_value=fake)
        client_class.is_crypto_symbol = _FakeClient.is_crypto_symbol
        p = mock.patch.object(runner, "AlpacaClient", client_class)
        p.start()
        self.addCleanup(p.stop)

    def _install_strategy(self, decide_fn, params=None):
        stub = mock.MagicMock()
        stub.decide = decide_fn
        if params is None:
            params = {"symbol": "SYM", "timeframe": "1Hour",
                      "bar_limit": 10, "notional_usd": 50.0}
        p = mock.patch.object(runner, "load_strategy",
                              return_value=(stub, params))
        p.start()
        self.addCleanup(p.stop)

    def _trades(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trades ORDER BY id ASC").fetchall()]


class TestReconcileHappyPath(_ReconcileBase):
    """Terminal on the FIRST poll: row should reflect filled status +
    filled_avg_price + filled_qty, not the submit-time transient state."""

    def test_filled_on_first_get(self):
        fake = _FakeClient(
            submit_status="pending_new",
            get_order_responses=[{
                "id": "order-1",
                "status": "filled",
                "filled_avg_price": "101.25",
                "filled_qty": "0.4938",
            }],
        )
        self._install_client(fake)
        self._install_strategy(
            lambda *a, **k: _action("buy", "SYM", 50, "entry"))

        rc = runner.run("any")
        self.assertEqual(rc, 0)
        # Exactly one get_order call \u2014 terminal stops the loop.
        self.assertEqual(len(fake.get_order_calls), 1)
        trades = self._trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["status"], "filled")
        self.assertAlmostEqual(trades[0]["price"], 101.25)
        self.assertAlmostEqual(trades[0]["qty"], 0.4938)


class TestReconcileStillPending(_ReconcileBase):
    """Order stays in 'accepted' across all 3 polls. Reconcile should
    exit gracefully and the row should record the best-known status."""

    def test_still_pending_records_best_known(self):
        fake = _FakeClient(
            submit_status="pending_new",
            get_order_responses=[{
                "id": "order-1",
                "status": "accepted",
                "filled_avg_price": None,
                "filled_qty": "0",
            }],
        )
        self._install_client(fake)
        self._install_strategy(
            lambda *a, **k: _action("buy", "SYM", 50, "entry"))

        # Patch sleep to keep the test fast.
        with mock.patch.object(runner.time, "sleep", return_value=None):
            rc = runner.run("any")
        self.assertEqual(rc, 0)
        # We poll up to 3x while non-terminal.
        self.assertEqual(len(fake.get_order_calls), 3)
        trades = self._trades()
        self.assertEqual(trades[0]["status"], "accepted")


class TestReconcileExceptionSwallowed(_ReconcileBase):
    """If get_order itself blows up unexpectedly (not AlpacaError but a
    bare RuntimeError, say), the runner must not crash the tick. The
    trade row stays at the submit-time status; the tick completes rc=0."""

    def test_unexpected_exception_does_not_crash_tick(self):
        fake = _FakeClient(submit_status="pending_new")

        # Make get_order throw a generic RuntimeError (NOT AlpacaError, which
        # the loop already handles via `break`).
        def boom(_oid):
            raise RuntimeError("oops")
        fake.get_order = boom

        self._install_client(fake)
        self._install_strategy(
            lambda *a, **k: _action("buy", "SYM", 50, "entry"))

        rc = runner.run("any")
        self.assertEqual(rc, 0, "tick must complete even if reconcile blows up")
        trades = self._trades()
        # Row was written at submit time \u2014 status stays as submit response.
        self.assertEqual(trades[0]["status"], "pending_new")


class TestBackfillHelper(_ReconcileBase):
    """The one-shot backfill helper: walks every non-terminal row and
    updates it from Alpaca truth. Idempotent."""

    def _seed(self, status, order_id):
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("s1", "XLK", "buy", 0.5, 50.0, 100.0,
                 order_id, status, "seed", None,
                 "2026-05-26T00:00:00Z"),
            )

    def test_backfill_updates_pending_row(self):
        self._seed("pending_new", "abc-123")
        self._seed("filled", "already-done")  # terminal; must be skipped

        fake = _FakeClient(
            submit_status="filled",
            get_order_responses=[{
                "id": "abc-123",
                "status": "filled",
                "filled_avg_price": "201.50",
                "filled_qty": "0.4988",
            }],
        )
        with mock.patch.object(reconcile, "AlpacaClient",
                               return_value=fake):
            summaries = reconcile.backfill(db_path=_TEST_DB)

        # Only the non-terminal row was touched.
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["old_status"], "pending_new")
        self.assertEqual(summaries[0]["new_status"], "filled")
        self.assertEqual(fake.get_order_calls, ["abc-123"])

        trades = self._trades()
        # Find the formerly-pending row.
        updated = next(t for t in trades if t["alpaca_order_id"] == "abc-123")
        self.assertEqual(updated["status"], "filled")
        self.assertAlmostEqual(updated["price"], 201.50)
        self.assertAlmostEqual(updated["qty"], 0.4988)
        # Already-terminal row left alone.
        untouched = next(t for t in trades
                         if t["alpaca_order_id"] == "already-done")
        self.assertEqual(untouched["status"], "filled")
        self.assertAlmostEqual(untouched["price"], 100.0)

    def test_backfill_idempotent(self):
        """Second run after a successful backfill is a no-op (no more
        non-terminal rows)."""
        self._seed("pending_new", "abc")
        fake = _FakeClient(
            get_order_responses=[{
                "id": "abc", "status": "filled",
                "filled_avg_price": "100.0", "filled_qty": "0.5"}])
        with mock.patch.object(reconcile, "AlpacaClient",
                               return_value=fake):
            reconcile.backfill(db_path=_TEST_DB)
            second = reconcile.backfill(db_path=_TEST_DB)
        self.assertEqual(second, [],
                         "second backfill should find nothing to do")

    def test_backfill_swallows_per_row_alpaca_error(self):
        """A single bad row (e.g. unknown order id) shouldn't abort the
        whole backfill \u2014 it should be reported and skipped."""
        self._seed("pending_new", "missing-order")
        fake = _FakeClient(get_order_raises=True)
        with mock.patch.object(reconcile, "AlpacaClient",
                               return_value=fake):
            summaries = reconcile.backfill(db_path=_TEST_DB)
        self.assertEqual(len(summaries), 1)
        self.assertIn("error", summaries[0])
        # Row is unchanged.
        self.assertEqual(self._trades()[0]["status"], "pending_new")


class TestUpdateTradeStatusHelper(_ReconcileBase):
    """Direct unit test of db.update_trade_status \u2014 only listed fields
    are touched; None fields are left alone."""

    def test_partial_update_only_touches_listed_fields(self):
        with db.connect(_TEST_DB) as c:
            cur = c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("s", "X", "buy", 1.0, 10.0, 9.0, "oid", "pending_new",
                 "r", "raw", "2026-01-01T00:00:00Z"),
            )
            tid = cur.lastrowid
        db.update_trade_status(tid, status="filled", db_path=_TEST_DB)
        row = self._trades()[0]
        self.assertEqual(row["status"], "filled")
        self.assertEqual(row["price"], 9.0)   # untouched
        self.assertEqual(row["qty"], 1.0)     # untouched

    def test_empty_update_is_noop(self):
        with db.connect(_TEST_DB) as c:
            cur = c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("s", "X", "buy", 1.0, 10.0, 9.0, "oid", "pending_new",
                 "r", "raw", "2026-01-01T00:00:00Z"),
            )
            tid = cur.lastrowid
        db.update_trade_status(tid, db_path=_TEST_DB)  # all-None
        row = self._trades()[0]
        self.assertEqual(row["status"], "pending_new")  # unchanged


if __name__ == "__main__":
    unittest.main()
