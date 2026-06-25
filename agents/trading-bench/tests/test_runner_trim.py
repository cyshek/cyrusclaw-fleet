"""Pinning tests for the PARTIAL-TRIM runner primitive (runner/runner.py).

The trim primitive adds a partial-sell-while-staying-long path so a
strategy can REDUCE exposure without going flat. Until now the runner
had only BUY-notional (add) and CLOSE (liquidate full attributed qty).
A continuously-rebalanced strategy (the TQQQ vol-target sleeve, the
allocator blend) needs to trim; without it the sleeve runs hotter than
its backtest on vol-spike days (see
strategies/leveraged_long_trend_paper/RUNNER_PLUMBING_GAP.md).

THE ATTRIBUTION INVARIANT these tests lock down:
    db.strategy_position(strategy, symbol) reconstructs attributed qty by
    walking the trades table in id order: a `buy` row ADDS qty, a `sell`
    row SUBTRACTS min(sell_qty, running_qty) and scales cost basis
    proportionally, clamping oversell to flat. A partial trim therefore
    just has to write a `sell` row with the CORRECT qty and NOT clear the
    strategy bookkeeping state (it's still long). The books then stay
    synced BY CONSTRUCTION — the reconstruction already understands the
    row shape the trim emits.

These tests pin:
  (a) a partial trim decrements attributed qty correctly + stays long;
  (b) a trim cannot oversell past flat (clamped to held qty);
  (c) multi-symbol attribution stays consistent across BUY/TRIM/CLOSE for
      ONE strategy holding TWO symbols simultaneously;
  (d) existing single-symbol BUY/CLOSE behavior is UNCHANGED (regression);
  (e) trim-with-no-position fails safe to HOLD (no broker call);
  (f) a trim sweeping >= full attributed qty degrades to a CLOSE (clears
      strategy state) rather than a forbidden partial that would oversell;
  (g) a trim is de-risking: allowed even when already at MAX_POSITION
      (it strictly reduces; cannot breach the position cap);
  (h) trim qty can be expressed as a notional ($ amount) OR an explicit
      share-qty delta, and both decrement attribution correctly.

It reuses the harness shape from tests/test_runner.py (monkeypatched
load_strategy + AlpacaClient, tmp DB), but with its OWN tmp DB so the two
modules don't collide on the captured-DB_PATH default-arg trick.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Own tmp DB (separate file from test_runner.py's _TEST_DB).
_TMPDIR = tempfile.mkdtemp(prefix="tess_runner_trim_")
_TEST_DB = Path(_TMPDIR) / "t.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import db, runner  # noqa: E402


def _action(action="hold", symbol="SYM", notional_usd=0.0, reason="",
            qty=None):
    """Mimics the per-strategy Action dataclass. The runner reads
    action / symbol / notional_usd / reason, and (for trims) qty via
    getattr(..., 'qty', None). We only set qty when a test passes it so we
    also exercise the getattr-default path for legacy actions."""
    class _A:
        pass
    a = _A()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional_usd
    a.reason = reason
    if qty is not None:
        a.qty = qty
    return a


class _FakeAlpacaClient:
    """Stand-in for runner.broker_alpaca.AlpacaClient.

    submit_market_order echoes the qty back in order['qty'] (as Alpaca
    does for a qty order) so the runner's reconcile path can read a real
    filled qty. For notional orders qty is '' (empty) and the runner
    estimates qty from notional/fill_price — same as production."""

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

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        return "/" in symbol

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

    def get_order(self, order_id):
        # Reconcile lookups: echo back a terminal filled order. Find the
        # matching submitted order to return its qty/price faithfully.
        for rec in self.submitted_orders:
            if rec["order"]["id"] == order_id:
                return dict(rec["order"])
        return {"id": order_id, "status": "filled",
                "filled_avg_price": self.fill_price, "filled_qty": ""}

    def submit_market_order(self, symbol, side, *, qty=None, notional_usd=None):
        order = {
            "id": f"order-{len(self.submitted_orders) + 1}",
            "status": self.fill_status,
            "filled_avg_price": self.fill_price,
            "qty": str(qty) if qty is not None else "",
            # For a qty sell, Alpaca fills the full qty — surface it so
            # reconcile picks up a real filled_qty.
            "filled_qty": str(qty) if qty is not None else "",
        }
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty,
                                      "notional_usd": notional_usd,
                                      "order": order})
        return order


class _TrimTestBase(unittest.TestCase):
    """Common setup: fresh DB, swap AlpacaClient + load_strategy. Mirrors
    tests/test_runner.py::_RunnerTestBase but with this module's own DB."""

    def setUp(self):
        if _TEST_DB.exists():
            _TEST_DB.unlink()
        orig_db_path = db.DB_PATH
        self._db_patcher = mock.patch.object(db, "DB_PATH", _TEST_DB)
        self._db_patcher.start()
        self._orig_defaults = {}
        import types  # noqa: WPS433
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
        self._client_patcher = mock.patch.object(runner, "AlpacaClient",
                                                 client_class)
        self._client_patcher.start()

        self._market_patcher = mock.patch.object(
            runner, "is_us_equity_market_open", return_value=True)
        self._market_patcher.start()

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
        stub_module = mock.MagicMock()
        stub_module.decide = decide_fn
        if params is None:
            params = {"symbol": "SYM", "timeframe": "1Hour",
                      "bar_limit": 10, "notional_usd": 50.0}
        patcher = mock.patch.object(runner, "load_strategy",
                                    return_value=(stub_module, params))
        patcher.start()
        self.addCleanup(patcher.stop)

    # ---- DB seed + inspection helpers ----
    def _seed_buy(self, strategy, symbol, qty, price, order_id="ord-seed"):
        """Insert a filled buy row so build_position_state sees qty>0."""
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (strategy, symbol, "buy", float(qty), float(qty) * price,
                 price, order_id, "filled", "seed", None,
                 "2026-01-01T00:00:00Z"),
            )

    def _seed_state(self, strategy, symbol, key, value):
        db.save_strategy_state(strategy, symbol, {key: value})

    def _attributed_qty(self, strategy, symbol):
        return db.strategy_position(strategy, symbol)["qty"]

    def _trades(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trades ORDER BY id ASC").fetchall()]

    def _runs(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT outcome, detail FROM runs ORDER BY id ASC").fetchall()]

    def _decisions(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT action, symbol, qty, reason FROM decisions "
                "ORDER BY id ASC").fetchall()]


class TestPartialTrimDecrementsQty(_TrimTestBase):
    """(a) Hold 5 shares, trim 2 -> attributed qty becomes 3, still long,
    state preserved, exactly one sell order for 2 shares."""

    def test_trim_two_of_five(self):
        self._seed_buy("trimmer", "SYM", qty=5.0, price=100.0)
        self._seed_state("trimmer", "SYM", "running_max", 123.0)
        self.assertEqual(self._attributed_qty("trimmer", "SYM"), 5.0)

        # Trim 2 shares (notional = 2 * $100 = $200).
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 200.0, "vol up -> trim"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("trimmer")
        self.assertEqual(rc, 0)

        # Exactly one sell order, qty 2 (a QTY order, not a notional sell).
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertEqual(ord_["symbol"], "SYM")
        self.assertAlmostEqual(float(ord_["qty"]), 2.0, places=6)
        self.assertIsNone(ord_["notional_usd"],
                          "trim must submit by QTY, never a raw notional sell")

        # Attribution now 3 shares — still long.
        self.assertAlmostEqual(self._attributed_qty("trimmer", "SYM"), 3.0,
                               places=6)

        # A sell row was written with qty 2.
        trades = self._trades()
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[-1]["side"], "sell")
        self.assertAlmostEqual(trades[-1]["qty"], 2.0, places=6)

        # Strategy bookkeeping state PRESERVED (still long -> not cleared).
        st = db.get_strategy_state("trimmer", "SYM")
        self.assertEqual(st.get("running_max"), 123.0,
                         "trim must NOT clear strategy state (still long)")

    def test_trim_emits_sell_decision_with_qty(self):
        self._seed_buy("t2", "SYM", qty=4.0, price=100.0)
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 100.0, "reduce"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("t2")
        self.assertEqual(rc, 0)
        decs = [d for d in self._decisions() if d["action"] == "sell"]
        self.assertEqual(len(decs), 1)
        self.assertAlmostEqual(decs[0]["qty"], 1.0, places=6)


class TestTrimCannotOversell(_TrimTestBase):
    """(b) + (f) A trim asking for MORE than held qty is clamped: it
    degrades to a CLOSE to flat (never a short), clears strategy state."""

    def test_trim_more_than_held_degrades_to_close(self):
        self._seed_buy("over", "SYM", qty=3.0, price=100.0)
        self._seed_state("over", "SYM", "running_max", 999.0)
        # Ask to trim 10 shares ($1000 notional) but only 3 are held.
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 1000.0, "oversell?"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("over")
        self.assertEqual(rc, 0)

        # One sell order for the FULL 3 shares (clamped), not 10.
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 3.0, places=6)

        # Flat now.
        self.assertAlmostEqual(self._attributed_qty("over", "SYM"), 0.0,
                               places=6)
        # Strategy state CLEARED (we went flat -> close semantics).
        st = db.get_strategy_state("over", "SYM")
        self.assertEqual(st, {},
                         "full-sweep trim must clear state like a close")

    def test_trim_exact_full_qty_is_close(self):
        self._seed_buy("exact", "SYM", qty=2.0, price=100.0)
        # Trim exactly 2 shares worth ($200) -> close to flat.
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 200.0, "full"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("exact")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(self._attributed_qty("exact", "SYM"), 0.0,
                               places=6)
        self.assertEqual(self.fake_client.submitted_orders[0]["side"], "sell")

    def test_trim_when_flat_holds(self):
        """(e) Trim with no position -> HOLD, no broker call, fail safe."""
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 100.0, "nothing to trim"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("flat")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "trim with no position must not hit the broker")
        self.assertEqual(self._trades(), [])


class TestTrimRiskAndCaps(_TrimTestBase):
    """(g) A trim is de-risking; allowed even at/above MAX_POSITION because
    it strictly reduces. And it never submits a notional > MAX_NOTIONAL
    because it submits by clamped qty, not notional."""

    def test_trim_allowed_at_max_position(self):
        # Seed a position already at the $1000 cap (10 sh @ $100).
        self._seed_buy("atcap", "SYM", qty=10.0, price=100.0)
        self.assertAlmostEqual(self._attributed_qty("atcap", "SYM"), 10.0,
                               places=6)
        # Trim 1 share — must be ALLOWED (reducing from the cap).
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 100.0, "reduce at cap"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("atcap")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1,
                         "de-risking trim must not be blocked by position cap")
        self.assertAlmostEqual(self._attributed_qty("atcap", "SYM"), 9.0,
                               places=6)


class TestTrimByExplicitQty(_TrimTestBase):
    """(h) Trim expressed as an explicit share-qty delta (action.qty)
    instead of a notional decrements attribution the same way."""

    def test_trim_by_qty_field(self):
        self._seed_buy("byqty", "SYM", qty=6.0, price=100.0)
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 0.0, "trim 2.5 sh",
                                    qty=2.5),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("byqty")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        self.assertAlmostEqual(
            float(self.fake_client.submitted_orders[0]["qty"]), 2.5, places=6)
        self.assertAlmostEqual(self._attributed_qty("byqty", "SYM"), 3.5,
                               places=6)


class TestSellAliasRoutesToTrim(_TrimTestBase):
    """The existing 'sell' action string must route to the SAME qty-clamped
    partial path (not a raw notional sell that bypasses the attribution
    clamp). This is the safety fix: a bare 'sell' before this change would
    have gone through the notional-submit else-branch and could oversell."""

    def test_sell_action_is_qty_clamped(self):
        self._seed_buy("seller", "SYM", qty=4.0, price=100.0)
        self._patch_strategy(
            lambda *a, **k: _action("sell", "SYM", 100.0, "sell 1 sh"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("seller")
        self.assertEqual(rc, 0)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 1.0, places=6)
        self.assertIsNone(ord_["notional_usd"],
                          "'sell' must be qty-clamped, not a raw notional sell")
        self.assertAlmostEqual(self._attributed_qty("seller", "SYM"), 3.0,
                               places=6)


class TestMultiSymbolAttribution(_TrimTestBase):
    """(c) ONE strategy holding TWO symbols. BUY/TRIM/CLOSE on each must
    keep per-(strategy,symbol) attribution independent and consistent.

    The single-symbol runner ticks one symbol per run() call; the
    attribution layer (db.strategy_position) is keyed by (strategy,
    symbol), so a trim on AAA must not touch BBB and vice-versa."""

    def test_two_symbols_independent_trim_and_close(self):
        strat = "multi"
        # Seed two independent positions for the SAME strategy.
        self._seed_buy(strat, "AAA", qty=8.0, price=100.0, order_id="a-seed")
        self._seed_buy(strat, "BBB", qty=4.0, price=100.0, order_id="b-seed")
        self.assertAlmostEqual(self._attributed_qty(strat, "AAA"), 8.0,
                               places=6)
        self.assertAlmostEqual(self._attributed_qty(strat, "BBB"), 4.0,
                               places=6)

        # Tick 1: trim AAA by 3 shares ($300). BBB must be untouched.
        self._patch_strategy(
            lambda *a, **k: _action("trim", "AAA", 300.0, "trim AAA"),
            params={"symbol": "AAA", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        self.assertEqual(runner.run(strat), 0)
        self.assertAlmostEqual(self._attributed_qty(strat, "AAA"), 5.0,
                               places=6)
        self.assertAlmostEqual(self._attributed_qty(strat, "BBB"), 4.0,
                               places=6, msg="trim on AAA must not touch BBB")

        # Tick 2: close BBB. AAA must be untouched (still 5).
        self._patch_strategy(
            lambda *a, **k: _action("close", "BBB", 0.0, "close BBB"),
            params={"symbol": "BBB", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        self.assertEqual(runner.run(strat), 0)
        self.assertAlmostEqual(self._attributed_qty(strat, "BBB"), 0.0,
                               places=6)
        self.assertAlmostEqual(self._attributed_qty(strat, "AAA"), 5.0,
                               places=6, msg="close on BBB must not touch AAA")

        # Tick 3: trim AAA again by 2 shares -> 3 remain.
        self._patch_strategy(
            lambda *a, **k: _action("trim", "AAA", 200.0, "trim AAA again"),
            params={"symbol": "AAA", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        self.assertEqual(runner.run(strat), 0)
        self.assertAlmostEqual(self._attributed_qty(strat, "AAA"), 3.0,
                               places=6)
        self.assertAlmostEqual(self._attributed_qty(strat, "BBB"), 0.0,
                               places=6)


class TestRegressionBuyCloseUnchanged(_TrimTestBase):
    """(d) The pre-existing BUY-notional and CLOSE-to-flat behavior must be
    byte-for-byte unchanged by the trim addition. These mirror the BUY +
    CLOSE assertions in tests/test_runner.py to lock the contract here."""

    def test_buy_still_submits_notional(self):
        self._patch_strategy(
            lambda *a, **k: _action("buy", "SYM", 50.0, "entry"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("buyer")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "buy")
        # BUY is still a NOTIONAL order (qty None, notional 50), unchanged.
        self.assertIsNone(ord_["qty"])
        self.assertEqual(ord_["notional_usd"], 50.0)

    def test_close_still_liquidates_full_qty(self):
        self._seed_buy("closer", "SYM", qty=7.0, price=100.0)
        self._seed_state("closer", "SYM", "running_max", 55.0)
        self._patch_strategy(
            lambda *a, **k: _action("close", "SYM", 0.0, "exit"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("closer")
        self.assertEqual(rc, 0)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        # CLOSE submits by QTY = full attributed 7 shares (unchanged).
        self.assertAlmostEqual(float(ord_["qty"]), 7.0, places=6)
        self.assertAlmostEqual(self._attributed_qty("closer", "SYM"), 0.0,
                               places=6)
        # Close clears strategy state (unchanged contract).
        self.assertEqual(db.get_strategy_state("closer", "SYM"), {})

    def test_hold_still_no_trade(self):
        self._patch_strategy(
            lambda *a, **k: _action("hold", "SYM", 0.0, "no signal"),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("holder")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._trades(), [])



class TestDustQtyGuard(_TrimTestBase):
    """Pins the dust-qty guard on the trim-submit path (runner.py).

    Alpaca rejects a market sell with qty <= 1e-9 (HTTP 422 "qty must be
    > 1e-9"). A residual ~1e-9 attributed qty (seen live on
    breakout_xlk__mut_c382b1 before the dust-correction job fires) must
    never reach the broker. The invariant pinned here: a sub-threshold
    sell qty results in a no-op HOLD (no broker call, attribution + state
    unchanged), never an order submission.
    """

    def test_legit_tiny_trim_above_eps_still_submits(self):
        # held large, explicit qty = 2e-9 (> 1e-9) -> must STILL submit;
        # the dust guard must not over-fire on a legit above-threshold qty.
        self._seed_buy("tiny", "SYM", qty=5.0, price=100.0)
        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 0.0, "tiny trim", qty=2e-9),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("tiny")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1,
                         "a trim qty ABOVE 1e-9 must still reach the broker")
        self.assertAlmostEqual(
            float(self.fake_client.submitted_orders[0]["qty"]), 2e-9, places=18)

    def test_dust_sell_qty_never_reaches_broker(self):
        # A sub-threshold (== eps) sell qty must NOT be submitted. The fake
        # client raises if dust ever reaches it (mimicking the Alpaca 422),
        # so a clean rc=0 with zero submitted orders proves the guard held.
        self._seed_buy("dust", "SYM", qty=5.0, price=100.0)
        self._seed_state("dust", "SYM", "running_max", 42.0)

        orig_submit = self.fake_client.submit_market_order

        def _strict_submit(symbol, side, *, qty=None, notional_usd=None):
            dust = qty is not None and float(qty) <= 1e-9
            if dust: raise AssertionError(
                f"422-equivalent: dust qty {float(qty):.2e} reached broker")
            return orig_submit(symbol, side, qty=qty, notional_usd=notional_usd)

        self.fake_client.submit_market_order = _strict_submit

        self._patch_strategy(
            lambda *a, **k: _action("trim", "SYM", 0.0, "dust trim", qty=1e-9),
            params={"symbol": "SYM", "timeframe": "1Hour", "bar_limit": 10,
                    "notional_usd": 50.0},
        )
        rc = runner.run("dust")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "dust sell qty must never reach the broker")
        self.assertAlmostEqual(self._attributed_qty("dust", "SYM"), 5.0,
                               places=6)
        self.assertEqual(db.get_strategy_state("dust", "SYM").get("running_max"),
                         42.0, "dust no-op must not flatten/clear state")


if __name__ == "__main__":
    unittest.main()
