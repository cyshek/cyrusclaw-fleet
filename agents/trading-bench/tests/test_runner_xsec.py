"""End-to-end-ish tests for runner/runner_xsec.py — the cross-sectional
(basket) live runner. Sister of tests/test_runner.py.

Same monkeypatch pattern: swap AlpacaClient + load_xsec_strategy, point
runner.db at a per-module tmp DB, run runner_xsec.run() and assert on
the rows + mock-call counts. We never hit the network.

Coverage targets (per Bar B/C/E gap-closure brief):
  - killswitch path
  - market-closed path
  - regime_gate skip path (regime classifier returns None)
  - regime_gate block path (strategy not in allow list)
  - happy path with mocked basket buys + per-leg decision/trade rows
  - risk reject on a single leg shouldn't block other legs
  - basket clamp triggered when strategy asks for >$200 total
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_TMPDIR = tempfile.mkdtemp(prefix="tess_runner_xsec_")
_TEST_DB = Path(_TMPDIR) / "t.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import db, runner_xsec  # noqa: E402


def _action(action="hold", symbol="SYM", notional_usd=0.0, reason=""):
    """Mimics the per-strategy Action dataclass. The runner reads only
    .action / .symbol / .notional_usd / .reason."""
    class _A:
        pass
    a = _A()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional_usd
    a.qty = None
    a.reason = reason
    return a


class _FakeAlpacaClient:
    """Stand-in for runner.broker_alpaca.AlpacaClient for xsec mode.

    Returns a deterministic single-bar stub for every requested symbol
    (timestamp shared across legs so clock_t alignment is trivial).
    Records every submit_market_order call for assertions."""

    SHARED_TS = "2026-05-29T20:00:00Z"

    def __init__(self):
        self.submitted_orders = []
        self.price_by_sym = {}   # default 100.0
        self.fill_status = "filled"

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        return "/" in symbol

    def latest_stock_price(self, symbol):
        return self.price_by_sym.get(symbol, 100.0)

    def latest_crypto_price(self, symbol):
        return self.price_by_sym.get(symbol, 100.0)

    def stock_bars(self, symbol, *, timeframe, limit):
        # SPY regime fetch is harmless — return a small flat series.
        price = self.price_by_sym.get(symbol, 100.0)
        return [
            {"t": "2026-05-28T20:00:00Z", "o": price, "h": price,
             "l": price, "c": price},
            {"t": self.SHARED_TS, "o": price, "h": price,
             "l": price, "c": price},
        ]

    def crypto_bars(self, symbol, *, timeframe, limit):
        return []

    def submit_market_order(self, symbol, side, *, qty=None,
                            notional_usd=None):
        order = {
            "id": f"order-{len(self.submitted_orders) + 1}",
            "status": self.fill_status,
            "filled_avg_price": self.price_by_sym.get(symbol, 100.0),
            "qty": str(qty) if qty is not None else "",
        }
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty,
                                      "notional_usd": notional_usd,
                                      "order": order})
        return order


class _RunnerXsecTestBase(unittest.TestCase):

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
                new = tuple(
                    _TEST_DB if d == orig_db_path else d
                    for d in fn.__defaults__
                )
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

        self.fake_client = _FakeAlpacaClient()
        client_class = mock.MagicMock(return_value=self.fake_client)
        client_class.is_crypto_symbol = _FakeAlpacaClient.is_crypto_symbol
        self._client_patcher = mock.patch.object(runner_xsec, "AlpacaClient",
                                                 client_class)
        self._client_patcher.start()

        self._market_patcher = mock.patch.object(
            runner_xsec, "is_us_equity_market_open", return_value=True)
        self._market_patcher.start()

        self._kill_patcher = mock.patch.object(
            runner_xsec, "killswitch_active", return_value=False)
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

    def _patch_xsec_strategy(self, decide_fn, params=None, basket=None):
        if basket is None:
            basket = ["SYM_A", "SYM_B", "SYM_C"]
        if params is None:
            params = {"basket": basket, "timeframe": "1Day",
                      "bar_limit": 10, "xsec_basket_size": len(basket)}
        else:
            params.setdefault("basket", basket)
            params.setdefault("timeframe", "1Day")
            params.setdefault("bar_limit", 10)
        patcher = mock.patch.object(runner_xsec, "load_xsec_strategy",
                                    return_value=(decide_fn, params))
        patcher.start()
        self.addCleanup(patcher.stop)
        return params

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
                "SELECT symbol, action, reason, notional_usd "
                "FROM decisions ORDER BY id ASC"
            ).fetchall()]


class TestKillswitch(_RunnerXsecTestBase):
    def test_killswitch_short_circuits(self):
        def decide(ms, ps, p):
            return {"SYM_A": _action("buy", "SYM_A", 50, "ignored")}
        self._patch_xsec_strategy(decide)
        with mock.patch.object(runner_xsec, "killswitch_active",
                               return_value=True):
            rc = runner_xsec.run("anything")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "killswitch must prevent any broker call")
        runs = self._runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["outcome"], "killswitch")


class TestMarketClosed(_RunnerXsecTestBase):
    def test_market_closed_short_circuits(self):
        def decide(ms, ps, p):
            return {"SYM_A": _action("buy", "SYM_A", 50)}
        self._patch_xsec_strategy(decide)
        with mock.patch.object(runner_xsec, "is_us_equity_market_open",
                               return_value=False):
            rc = runner_xsec.run("any")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[0]["detail"], "skip_market_closed")


class TestRegimeGate(_RunnerXsecTestBase):
    def test_regime_gate_skip_when_unknown(self):
        def decide(ms, ps, p):
            return {"SYM_A": _action("buy", "SYM_A", 50)}
        self._patch_xsec_strategy(decide, params={"regime_gate": True})

        # Patch the function directly. `runner_xsec.run` does an in-function
        # `from . import regime_classifier as _rc`, which resolves via the
        # already-imported `runner.regime_classifier` package attribute once
        # any earlier test has imported it; patching sys.modules alone does
        # NOT rebind that attribute, so we patch the function on the real
        # module object instead (works in isolation AND in full-suite order).
        import runner.regime_classifier as _real_rc
        with mock.patch.object(_real_rc, "get_today_regime",
                               return_value=None):
            rc = runner_xsec.run("xsec_x")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[0]["detail"], "skip_regime_unknown")

    def test_regime_gate_block_when_not_in_allow(self):
        def decide(ms, ps, p):
            return {"SYM_A": _action("buy", "SYM_A", 50)}
        self._patch_xsec_strategy(decide, params={"regime_gate": True})

        import runner.regime_classifier as _real_rc
        with mock.patch.object(_real_rc, "get_today_regime", return_value={
            "regime": "bear", "source": "test",
            "allow_strategies": ["someone_else"], "is_stale": False,
        }):
            rc = runner_xsec.run("xsec_x")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[0]["detail"], "skip_regime_block")


class TestHappyPath(_RunnerXsecTestBase):
    def test_basket_buys_emit_per_leg_orders_and_decisions(self):
        def decide(ms, ps, p):
            # Want to buy SYM_A and SYM_B at $40 each, hold SYM_C.
            return {
                "SYM_A": _action("buy", "SYM_A", 40, "winner #1"),
                "SYM_B": _action("buy", "SYM_B", 40, "winner #2"),
                "SYM_C": _action("hold", "SYM_C", 0, "ranked out"),
            }
        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xsec_happy")
        self.assertEqual(rc, 0)
        sides = sorted((o["symbol"], o["side"], o["notional_usd"])
                       for o in self.fake_client.submitted_orders)
        self.assertEqual(sides, [
            ("SYM_A", "buy", 40.0),
            ("SYM_B", "buy", 40.0),
        ])
        trades = self._trades()
        self.assertEqual(len(trades), 2)
        self.assertEqual({t["symbol"] for t in trades}, {"SYM_A", "SYM_B"})
        for t in trades:
            self.assertEqual(t["side"], "buy")
            self.assertEqual(t["status"], "filled")
        decisions = self._decisions()
        # Both buy decisions present + a hold for SYM_C.
        buy_decisions = [d for d in decisions if d["action"] == "buy"]
        self.assertEqual({d["symbol"] for d in buy_decisions},
                         {"SYM_A", "SYM_B"})
        hold_decisions = [d for d in decisions
                          if d["action"] == "hold" and d["symbol"] == "SYM_C"]
        self.assertEqual(len(hold_decisions), 1)
        run_detail = self._runs()[-1]["detail"]
        self.assertIn("xsec_trades=2", run_detail)
        self.assertIn("clamped=0", run_detail)

    def test_no_actions_returns_no_actions(self):
        def decide(ms, ps, p):
            return {}
        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xsec_quiet")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._trades(), [])
        self.assertEqual(self._runs()[-1]["detail"], "no_actions")


class TestRiskRejectIsolated(_RunnerXsecTestBase):
    def test_single_leg_risk_reject_does_not_block_other_legs(self):
        # Force a per-leg risk reject on SYM_A only (monkeypatch the
        # real check_trade so we don't have to set up a contrived
        # position/trade-history state that would also trip the basket
        # clamp). SYM_B's buy should still flow through to the broker.
        def decide(ms, ps, p):
            return {
                "SYM_A": _action("buy", "SYM_A", 40, "will be vetoed"),
                "SYM_B": _action("buy", "SYM_B", 40, "fine"),
            }
        self._patch_xsec_strategy(
            decide,
            params={"basket": ["SYM_A", "SYM_B"], "timeframe": "1Day",
                    "bar_limit": 10},
        )

        import runner.risk as _risk_mod
        real_check = _risk_mod.check_trade

        def selective_check(strategy, symbol, side, notional, pos_usd,
                            **kw):
            if symbol == "SYM_A":
                return _risk_mod.RiskCheck(False, "contrived per-leg veto")
            return real_check(strategy, symbol, side, notional, pos_usd,
                              **kw)

        with mock.patch.object(runner_xsec.risk, "check_trade",
                               side_effect=selective_check):
            rc = runner_xsec.run("xsec_isolate")
        self.assertEqual(rc, 0)
        # Only SYM_B was submitted.
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        self.assertEqual(self.fake_client.submitted_orders[0]["symbol"],
                         "SYM_B")
        decisions = self._decisions()
        skip_rows = [d for d in decisions
                     if d["action"] == "skip_risk" and d["symbol"] == "SYM_A"]
        self.assertEqual(len(skip_rows), 1)
        buy_rows = [d for d in decisions
                    if d["action"] == "buy" and d["symbol"] == "SYM_B"]
        self.assertEqual(len(buy_rows), 1)


class TestBasketClamp(_RunnerXsecTestBase):
    def test_oversized_basket_triggers_clamp(self):
        # Strategy asks for 4 buys * $800 = $3200 total — well over the
        # shared $1000 MAX_POSITION. Each leg is individually under
        # MAX_NOTIONAL ($1000), so per-leg risk would pass — but the
        # basket clamp should scale all four down proportionally to fit
        # $1000, and then per-leg risk passes each scaled leg. (Request
        # notionals scaled 10x with the 2026-05-31 paper cap bump.)
        def decide(ms, ps, p):
            return {
                "SYM_A": _action("buy", "SYM_A", 800, "leg1"),
                "SYM_B": _action("buy", "SYM_B", 800, "leg2"),
                "SYM_C": _action("buy", "SYM_C", 800, "leg3"),
                "SYM_D": _action("buy", "SYM_D", 800, "leg4"),
            }
        self._patch_xsec_strategy(
            decide,
            basket=["SYM_A", "SYM_B", "SYM_C", "SYM_D"],
            params={"basket": ["SYM_A", "SYM_B", "SYM_C", "SYM_D"],
                    "timeframe": "1Day", "bar_limit": 10,
                    "xsec_basket_size": 4},
        )
        rc = runner_xsec.run("xsec_clamp")
        self.assertEqual(rc, 0)
        # All 4 legs submitted (clamped, not dropped).
        self.assertEqual(len(self.fake_client.submitted_orders), 4)
        # Each submitted notional = 800 * (1000/3200) = 250.
        for o in self.fake_client.submitted_orders:
            self.assertAlmostEqual(o["notional_usd"], 250.0, places=4)
        # basket_clamp decision row should be present.
        decisions = self._decisions()
        clamp_rows = [d for d in decisions
                      if d["action"] == "basket_clamp"]
        self.assertEqual(len(clamp_rows), 1)
        run_detail = self._runs()[-1]["detail"]
        self.assertIn("clamped=1", run_detail)
        self.assertIn("xsec_trades=4", run_detail)


class TestCloseFreesCapHeadroom(_RunnerXsecTestBase):
    """When a held position is being closed AND new buys are requested,
    closes execute first so the basket clamp accounts for the freed
    headroom on the buy pass."""

    def test_close_processed_before_buy(self):
        # Seed a held position in SYM_A so the strategy can rotate out.
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("xsec_rotate", "SYM_A", "buy", 0.5, 50.0, 100.0,
                 "ord-seed", "filled", "seed",
                 None, "2026-05-01T00:00:00Z"),
            )

        def decide(ms, ps, p):
            # SYM_A currently held -> should appear in ps.
            assert "SYM_A" in ps, f"expected SYM_A in position_state, got {list(ps)}"
            return {
                "SYM_A": _action("close", "SYM_A", 0, "rotate out"),
                "SYM_B": _action("buy", "SYM_B", 50, "rotate in"),
            }
        self._patch_xsec_strategy(
            decide,
            params={"basket": ["SYM_A", "SYM_B"], "timeframe": "1Day",
                    "bar_limit": 10, "xsec_basket_size": 2},
        )
        rc = runner_xsec.run("xsec_rotate")
        self.assertEqual(rc, 0)
        # Two orders: close SYM_A (sell), then buy SYM_B.
        self.assertEqual(len(self.fake_client.submitted_orders), 2)
        self.assertEqual(self.fake_client.submitted_orders[0]["symbol"], "SYM_A")
        self.assertEqual(self.fake_client.submitted_orders[0]["side"], "sell")
        self.assertEqual(self.fake_client.submitted_orders[1]["symbol"], "SYM_B")
        self.assertEqual(self.fake_client.submitted_orders[1]["side"], "buy")


if __name__ == "__main__":
    unittest.main()
