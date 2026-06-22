"""Pinning tests for the PARTIAL-TRIM leg in runner/runner_xsec.py — the
cross-sectional (basket) live runner. Sister of tests/test_runner_trim.py
(which pins the SAME primitive in the single-symbol runner/runner.py).

WHY THIS EXISTS
---------------
Before this change the xsec runner supported only two position primitives
per (strategy, symbol) leg:
  - pass-1 CLOSE: liquidate the FULL strategy-attributed qty to flat.
  - pass-2 BUY notional / SELL notional: a `sell` leg went through the
    notional-submit branch UNCLAMPED → it could OVERSELL a leg past flat
    (into a short / eating another strategy's shares) and drift attribution
    via broker-side rounding. That was a latent bug (today xsec strategies
    emit buy/close only, so it was never live — but the allocator blend
    REQUIRES a reduce-while-long leg).

A continuously-reweighted book (the allocator blend: TQQQ + SPY/QQQ/GLD/TLT)
MUST be able to REDUCE a leg while staying long. This adds a `trim` path
(and makes the legacy `sell` SAFE) that mirrors the single-symbol design.

THE ATTRIBUTION INVARIANT these tests lock down (identical to the
single-symbol runner — that is the whole point of reusing the SAME
db.strategy_position reconstruction):
    db.strategy_position(strategy, symbol) reconstructs attributed qty by
    walking the trades table in id order, keyed by (strategy, symbol): a
    `buy` row ADDS qty, a `sell` row SUBTRACTS min(sell_qty, running_qty)
    and scales cost basis proportionally, clamping oversell to flat. A
    partial trim therefore just has to write a `sell` row with the CORRECT
    clamped qty and NOT clear the strategy bookkeeping state (still long).
    The books stay synced BY CONSTRUCTION — the reconstruction already
    understands the row shape the trim emits, and it is keyed per
    (strategy, symbol) so a trim on one leg cannot touch another.

These tests pin:
  (a) a partial trim of ONE leg decrements that leg's attributed qty +
      stays long + strategy/persistent state preserved;
  (b) a trim cannot oversell past flat (clamped → degrades to a CLOSE);
  (c) multi-leg basket: BUY two legs, TRIM one, CLOSE the other → per-leg
      attribution stays independent + correct;
  (d) existing basket BUY / full-CLOSE / HOLD behavior is UNCHANGED
      (regression pins, mirroring tests/test_runner_xsec.py);
  (e) trim-with-no-position on a leg fails safe to HOLD (no broker call);
  (f) legacy `sell` routes to the SAME qty-clamped path (the hazard fix);
  (g) trim qty can be expressed as an explicit share-qty (action.qty)
      OR a notional, and both decrement attribution correctly;
  (h) a trim is de-risking: allowed even when the leg is at MAX_NOTIONAL.

Harness: reuses the monkeypatch shape from tests/test_runner_xsec.py
(swap AlpacaClient + load_xsec_strategy, per-module tmp DB) but with its
OWN tmp DB so the modules don't collide on the captured-DB_PATH default.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# Own tmp DB (separate file from test_runner_xsec.py's DB).
_TMPDIR = tempfile.mkdtemp(prefix="tess_runner_xsec_trim_")
_TEST_DB = Path(_TMPDIR) / "t.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runner import db, runner_xsec  # noqa: E402


def _action(action="hold", symbol="SYM", notional_usd=0.0, reason="",
            qty=None):
    """Mimics the per-strategy Action dataclass. The xsec runner reads
    .action / .symbol / .notional_usd / .reason, and (for trims) .qty via
    getattr(..., 'qty', None). We only SET qty when a test passes it so we
    also exercise the getattr-default path for legacy actions that have no
    qty attribute at all."""
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
    """Stand-in for runner.broker_alpaca.AlpacaClient for xsec mode.

    submit_market_order echoes qty back in order['qty'] AND order['filled_qty']
    (as Alpaca does for a qty order) so the runner's fill recording reads a
    real filled qty for a sell. For notional orders qty/filled_qty is ''
    (empty) and the runner estimates qty from notional/fill_price — same as
    production. Records every submit for assertions."""

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
            "filled_qty": str(qty) if qty is not None else "",
        }
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty,
                                      "notional_usd": notional_usd,
                                      "order": order})
        return order


class _RunnerXsecTrimTestBase(unittest.TestCase):
    """Common setup: fresh DB, swap AlpacaClient + load_xsec_strategy,
    force market-open + killswitch-off. Mirrors
    tests/test_runner_xsec.py::_RunnerXsecTestBase but with its own DB."""

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

    # ---- DB seed + inspection helpers ----
    def _seed_buy(self, strategy, symbol, qty, price, order_id="ord-seed"):
        """Insert a filled buy row so _build_leg_position sees qty>0."""
        with db.connect(_TEST_DB) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (strategy, symbol, "buy", float(qty), float(qty) * price,
                 price, order_id, "filled", "seed", None,
                 "2026-01-01T00:00:00Z"),
            )

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
                "SELECT symbol, action, qty, reason, notional_usd "
                "FROM decisions ORDER BY id ASC").fetchall()]


class TestPartialTrimDecrementsLeg(_RunnerXsecTrimTestBase):
    """(a) A leg held at 5 shares, trim 2 -> attributed qty becomes 3 on
    that leg, still long, exactly one qty-sell of 2, NO state cleared."""

    def test_trim_two_of_five_one_leg(self):
        self._seed_buy("xtrim", "SYM_A", qty=5.0, price=100.0)
        self.assertEqual(self._attributed_qty("xtrim", "SYM_A"), 5.0)

        def decide(ms, ps, p):
            # SYM_A is held -> should be visible in position_state.
            assert "SYM_A" in ps, f"expected SYM_A held, got {list(ps)}"
            # Trim 2 shares == $200 notional. Hold the other legs.
            return {"SYM_A": _action("trim", "SYM_A", 200.0, "vol up -> trim")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xtrim")
        self.assertEqual(rc, 0)

        # Exactly one sell order, qty 2 — a QTY order, NOT a notional sell.
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertEqual(ord_["symbol"], "SYM_A")
        self.assertAlmostEqual(float(ord_["qty"]), 2.0, places=6)
        self.assertIsNone(ord_["notional_usd"],
                          "trim must submit by QTY, never a raw notional sell")

        # Attribution now 3 shares — still long.
        self.assertAlmostEqual(self._attributed_qty("xtrim", "SYM_A"), 3.0,
                               places=6)

        # A sell row was written with qty 2.
        trades = self._trades()
        sell_rows = [t for t in trades if t["side"] == "sell"]
        self.assertEqual(len(sell_rows), 1)
        self.assertAlmostEqual(sell_rows[-1]["qty"], 2.0, places=6)

        # A 'sell' decision row with the qty was logged.
        sell_decs = [d for d in self._decisions() if d["action"] == "sell"]
        self.assertEqual(len(sell_decs), 1)
        self.assertAlmostEqual(sell_decs[0]["qty"], 2.0, places=6)

    def test_trim_preserves_persistent_state(self):
        # The xsec runner persists cross-flat state under (_xsec_) and only
        # clears per-leg strategy_state on a CLOSE. A partial trim must not
        # clear either — it stays long.
        self._seed_buy("xtrim2", "SYM_A", qty=4.0, price=100.0)
        db.save_strategy_state("xtrim2", "SYM_A", {"running_max": 123.0})

        def decide(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 100.0, "reduce")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xtrim2")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(self._attributed_qty("xtrim2", "SYM_A"), 3.0,
                               places=6)
        st = db.get_strategy_state("xtrim2", "SYM_A")
        self.assertEqual(st.get("running_max"), 123.0,
                         "partial trim must NOT clear leg strategy state")


class TestTrimCannotOversellLeg(_RunnerXsecTrimTestBase):
    """(b) + full-sweep: a trim asking for MORE than the leg's held qty is
    clamped: it degrades to a CLOSE to flat (never a short), clears that
    leg's state. This is the latent-oversell bug fix."""

    def test_trim_more_than_held_degrades_to_close(self):
        self._seed_buy("xover", "SYM_A", qty=3.0, price=100.0)
        db.save_strategy_state("xover", "SYM_A", {"running_max": 999.0})

        def decide(ms, ps, p):
            # Ask to trim 10 shares ($1000) but only 3 held.
            return {"SYM_A": _action("trim", "SYM_A", 1000.0, "oversell?")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xover")
        self.assertEqual(rc, 0)

        # One sell order for the FULL 3 shares (clamped), not 10.
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 3.0, places=6)
        self.assertIsNone(ord_["notional_usd"],
                          "clamped trim->close must submit by qty")

        # Flat now.
        self.assertAlmostEqual(self._attributed_qty("xover", "SYM_A"), 0.0,
                               places=6)
        # Leg strategy state CLEARED (went flat -> close semantics).
        self.assertEqual(db.get_strategy_state("xover", "SYM_A"), {},
                         "full-sweep trim must clear leg state like a close")

    def test_trim_exact_full_qty_is_close(self):
        self._seed_buy("xexact", "SYM_A", qty=2.0, price=100.0)

        def decide(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 200.0, "full")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xexact")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(self._attributed_qty("xexact", "SYM_A"), 0.0,
                               places=6)
        self.assertEqual(self.fake_client.submitted_orders[0]["side"], "sell")
        self.assertAlmostEqual(
            float(self.fake_client.submitted_orders[0]["qty"]), 2.0, places=6)

    def test_trim_when_leg_flat_holds(self):
        """(e) Trim a leg with no position -> HOLD, no broker call."""
        def decide(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 100.0, "nothing here")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xflat")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [],
                         "trim with no position must not hit the broker")
        self.assertEqual(self._trades(), [])
        # A hold decision should be logged for the leg.
        hold_decs = [d for d in self._decisions()
                     if d["action"] == "hold" and d["symbol"] == "SYM_A"]
        self.assertGreaterEqual(len(hold_decs), 1)


class TestSellAliasIsClamped(_RunnerXsecTrimTestBase):
    """(f) The legacy `sell` action string must route to the SAME
    qty-clamped partial path — NOT the old notional-submit else-branch that
    could oversell the leg. This is the hazard fix flagged in the
    single-symbol report (xsec runner's notional-sell path was unchanged)."""

    def test_sell_action_is_qty_clamped(self):
        self._seed_buy("xsell", "SYM_A", qty=4.0, price=100.0)

        def decide(ms, ps, p):
            return {"SYM_A": _action("sell", "SYM_A", 100.0, "sell 1 sh")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xsell")
        self.assertEqual(rc, 0)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 1.0, places=6)
        self.assertIsNone(ord_["notional_usd"],
                          "'sell' leg must be qty-clamped, not a notional sell")
        self.assertAlmostEqual(self._attributed_qty("xsell", "SYM_A"), 3.0,
                               places=6)

    def test_sell_more_than_held_clamps_to_flat(self):
        # The OLD behavior would submit a $1000 notional sell on a $300
        # position -> oversell into a short. The clamp must prevent it.
        self._seed_buy("xsellover", "SYM_A", qty=3.0, price=100.0)

        def decide(ms, ps, p):
            return {"SYM_A": _action("sell", "SYM_A", 1000.0, "oversell")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xsellover")
        self.assertEqual(rc, 0)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 3.0, places=6,
                               msg="sell must clamp to held, never oversell")
        self.assertIsNone(ord_["notional_usd"])
        self.assertAlmostEqual(self._attributed_qty("xsellover", "SYM_A"), 0.0,
                               places=6)


class TestTrimByExplicitQty(_RunnerXsecTrimTestBase):
    """(g) Trim expressed as an explicit share-qty delta (action.qty)
    instead of a notional decrements attribution the same way."""

    def test_trim_by_qty_field(self):
        self._seed_buy("xbyqty", "SYM_A", qty=6.0, price=100.0)

        def decide(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 0.0, "trim 2.5 sh",
                                     qty=2.5)}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xbyqty")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1)
        self.assertAlmostEqual(
            float(self.fake_client.submitted_orders[0]["qty"]), 2.5, places=6)
        self.assertAlmostEqual(self._attributed_qty("xbyqty", "SYM_A"), 3.5,
                               places=6)


class TestTrimAtMaxNotional(_RunnerXsecTrimTestBase):
    """(h) A trim is de-risking; allowed even when the leg sits at the
    per-leg MAX_NOTIONAL cap because it strictly reduces. And it never
    submits a notional > MAX_NOTIONAL because it submits by clamped qty."""

    def test_trim_allowed_at_max_leg(self):
        # Seed a leg already at the $1000 per-leg cap (10 sh @ $100).
        self._seed_buy("xatcap", "SYM_A", qty=10.0, price=100.0)
        self.assertAlmostEqual(self._attributed_qty("xatcap", "SYM_A"), 10.0,
                               places=6)

        def decide(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 100.0, "reduce at cap")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xatcap")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.fake_client.submitted_orders), 1,
                         "de-risking trim must not be blocked by the cap")
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        self.assertAlmostEqual(float(ord_["qty"]), 1.0, places=6)
        self.assertIsNone(ord_["notional_usd"])
        self.assertAlmostEqual(self._attributed_qty("xatcap", "SYM_A"), 9.0,
                               places=6)


class TestMultiLegAttribution(_RunnerXsecTrimTestBase):
    """(c) THE CORE BASKET TEST. ONE strategy holding several legs. BUY two
    legs, TRIM one of them, CLOSE another, HOLD a fourth — across ticks —
    and assert per-(strategy,symbol) attribution stays independent and
    consistent. This is the property whose failure would make the
    tournament P&L lie: a trim on one leg must touch ONLY that leg."""

    def test_buy_two_trim_one_close_other_independent(self):
        basket = ["SYM_A", "SYM_B", "SYM_C", "SYM_D"]
        # Tick 1: open SYM_A and SYM_B (buy $400 each => 4 sh @ $100),
        # leave SYM_C / SYM_D flat.
        def decide_open(ms, ps, p):
            return {
                "SYM_A": _action("buy", "SYM_A", 400.0, "open A"),
                "SYM_B": _action("buy", "SYM_B", 400.0, "open B"),
            }
        self._patch_xsec_strategy(decide_open, basket=basket,
                                  params={"basket": basket,
                                          "timeframe": "1Day",
                                          "bar_limit": 10,
                                          "xsec_basket_size": 4})
        self.assertEqual(runner_xsec.run("xmulti"), 0)
        # Notional buys: qty estimated from notional/fill_price = 4 sh each.
        self.assertAlmostEqual(self._attributed_qty("xmulti", "SYM_A"), 4.0,
                               places=6)
        self.assertAlmostEqual(self._attributed_qty("xmulti", "SYM_B"), 4.0,
                               places=6)
        self.assertEqual(self._attributed_qty("xmulti", "SYM_C"), 0.0)
        self.assertEqual(self._attributed_qty("xmulti", "SYM_D"), 0.0)
        n_open_orders = len(self.fake_client.submitted_orders)
        self.assertEqual(n_open_orders, 2)

        # Tick 2: TRIM SYM_A by 1 share ($100), CLOSE SYM_B, HOLD SYM_C.
        # SYM_A must drop to 3, SYM_B to 0, NOTHING else perturbed.
        def decide_rebalance(ms, ps, p):
            assert "SYM_A" in ps and "SYM_B" in ps, list(ps)
            return {
                "SYM_A": _action("trim", "SYM_A", 100.0, "trim A"),
                "SYM_B": _action("close", "SYM_B", 0.0, "close B"),
                "SYM_C": _action("hold", "SYM_C", 0.0, "stay flat"),
            }
        self._patch_xsec_strategy(decide_rebalance, basket=basket,
                                  params={"basket": basket,
                                          "timeframe": "1Day",
                                          "bar_limit": 10,
                                          "xsec_basket_size": 4})
        self.assertEqual(runner_xsec.run("xmulti"), 0)

        # Per-leg attribution after the rebalance:
        self.assertAlmostEqual(self._attributed_qty("xmulti", "SYM_A"), 3.0,
                               places=6, msg="trim A: 4 -> 3, stays long")
        self.assertAlmostEqual(self._attributed_qty("xmulti", "SYM_B"), 0.0,
                               places=6, msg="close B -> flat")
        self.assertEqual(self._attributed_qty("xmulti", "SYM_C"), 0.0,
                         "hold C must remain flat")
        self.assertEqual(self._attributed_qty("xmulti", "SYM_D"), 0.0,
                         "untouched D must remain flat")

        # Exactly two NEW orders this tick: a sell-1 on SYM_A (qty order,
        # not notional) and a full-close sell-4 on SYM_B.
        new_orders = self.fake_client.submitted_orders[n_open_orders:]
        self.assertEqual(len(new_orders), 2)
        by_sym = {o["symbol"]: o for o in new_orders}
        self.assertIn("SYM_A", by_sym)
        self.assertIn("SYM_B", by_sym)
        # SYM_A: partial trim of 1 share, by QTY.
        self.assertEqual(by_sym["SYM_A"]["side"], "sell")
        self.assertAlmostEqual(float(by_sym["SYM_A"]["qty"]), 1.0, places=6)
        self.assertIsNone(by_sym["SYM_A"]["notional_usd"],
                          "trim A must be a qty order, not notional")
        # SYM_B: full close of all 4 shares.
        self.assertEqual(by_sym["SYM_B"]["side"], "sell")
        self.assertAlmostEqual(float(by_sym["SYM_B"]["qty"]), 4.0, places=6)

        # SYM_A leg state still present (it stayed long); SYM_B cleared.
        # (We never seeded explicit strategy_state here; assert via qty,
        # which already proves the per-leg reconstruction is independent.)

        # Tick 3: trim SYM_A again by 2 -> 1 remains; confirm independence
        # holds across a second trim and that B stays flat.
        def decide_trim_again(ms, ps, p):
            return {"SYM_A": _action("trim", "SYM_A", 200.0, "trim A again")}
        self._patch_xsec_strategy(decide_trim_again, basket=basket,
                                  params={"basket": basket,
                                          "timeframe": "1Day",
                                          "bar_limit": 10,
                                          "xsec_basket_size": 4})
        self.assertEqual(runner_xsec.run("xmulti"), 0)
        self.assertAlmostEqual(self._attributed_qty("xmulti", "SYM_A"), 1.0,
                               places=6)
        self.assertEqual(self._attributed_qty("xmulti", "SYM_B"), 0.0)


class TestRegressionBuyCloseHoldUnchanged(_RunnerXsecTrimTestBase):
    """(d) The pre-existing basket BUY-notional / full-CLOSE / HOLD behavior
    must be byte-for-byte unchanged by the trim addition. These mirror the
    assertions in tests/test_runner_xsec.py to lock the contract here too."""

    def test_basket_buys_still_notional_orders(self):
        def decide(ms, ps, p):
            return {
                "SYM_A": _action("buy", "SYM_A", 40.0, "winner #1"),
                "SYM_B": _action("buy", "SYM_B", 40.0, "winner #2"),
                "SYM_C": _action("hold", "SYM_C", 0.0, "ranked out"),
            }
        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xreg_buy")
        self.assertEqual(rc, 0)
        sides = sorted((o["symbol"], o["side"], o["notional_usd"])
                       for o in self.fake_client.submitted_orders)
        self.assertEqual(sides, [
            ("SYM_A", "buy", 40.0),
            ("SYM_B", "buy", 40.0),
        ])
        # Buys are NOTIONAL orders (qty None on submit), unchanged.
        for o in self.fake_client.submitted_orders:
            self.assertIsNone(o["qty"],
                              "basket buy must stay a notional order")
        run_detail = self._runs()[-1]["detail"]
        self.assertIn("xsec_trades=2", run_detail)
        self.assertIn("clamped=0", run_detail)

    def test_full_close_still_sells_full_qty_and_clears_state(self):
        self._seed_buy("xreg_close", "SYM_A", qty=7.0, price=100.0)
        db.save_strategy_state("xreg_close", "SYM_A", {"running_max": 55.0})

        def decide(ms, ps, p):
            return {"SYM_A": _action("close", "SYM_A", 0.0, "exit")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xreg_close")
        self.assertEqual(rc, 0)
        ord_ = self.fake_client.submitted_orders[0]
        self.assertEqual(ord_["side"], "sell")
        # CLOSE submits by QTY = full attributed 7 shares (unchanged).
        self.assertAlmostEqual(float(ord_["qty"]), 7.0, places=6)
        self.assertAlmostEqual(self._attributed_qty("xreg_close", "SYM_A"),
                               0.0, places=6)
        # Close clears leg strategy state (unchanged contract).
        self.assertEqual(db.get_strategy_state("xreg_close", "SYM_A"), {})

    def test_hold_still_no_trade(self):
        def decide(ms, ps, p):
            return {"SYM_A": _action("hold", "SYM_A", 0.0, "no signal")}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xreg_hold")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._trades(), [])

    def test_empty_actions_still_no_actions(self):
        def decide(ms, ps, p):
            return {}

        self._patch_xsec_strategy(decide)
        rc = runner_xsec.run("xreg_empty")
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_client.submitted_orders, [])
        self.assertEqual(self._runs()[-1]["detail"], "no_actions")


if __name__ == "__main__":
    unittest.main()