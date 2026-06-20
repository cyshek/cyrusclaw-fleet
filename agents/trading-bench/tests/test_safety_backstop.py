"""Safety backstop tests.

Pure-function module, so tests are tiny and direct. Covers:
    - No position / no price / qty=0 -> NO_ACTION
    - max_loss_pct: trips when unrealized <= threshold; doesn't trip otherwise
    - max_holding_bars: trips when held >= cap
    - Both triggers configured: whichever trips first wins (order doesn't matter
      for correctness, but loss-trigger evaluated first so the reason reflects it)
    - Missing/bad params silently skipped (never crash)
    - bars_since_entry helper edge cases

Run with:
    python3 -m unittest tests.test_safety_backstop
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.safety_backstop import (  # noqa: E402
    BackstopAction,
    NO_ACTION,
    check,
    bars_since_entry,
)


def _pos(qty: float = 0.5, avg_entry: float = 100.0,
         market_value: float = 50.0) -> dict:
    return {"qty": qty, "avg_entry_price": avg_entry, "market_value": market_value}


class TestCheckNoOp(unittest.TestCase):
    """Cases where no backstop should ever fire."""

    def test_no_position(self):
        self.assertEqual(check(None, 100.0, {"safety_max_loss_pct": -5.0}),
                         NO_ACTION)

    def test_empty_position(self):
        self.assertEqual(check({}, 100.0, {"safety_max_loss_pct": -5.0}),
                         NO_ACTION)

    def test_qty_zero(self):
        self.assertEqual(check(_pos(qty=0.0), 100.0,
                               {"safety_max_loss_pct": -5.0}),
                         NO_ACTION)

    def test_no_price(self):
        self.assertEqual(check(_pos(), None,
                               {"safety_max_loss_pct": -5.0}),
                         NO_ACTION)

    def test_no_triggers_configured(self):
        self.assertEqual(check(_pos(), 50.0, {}), NO_ACTION)

    def test_bad_qty_type(self):
        self.assertEqual(check({"qty": "nope", "avg_entry_price": 100.0},
                               50.0, {"safety_max_loss_pct": -5.0}),
                         NO_ACTION)


class TestMaxLossPctTrigger(unittest.TestCase):
    """`safety_max_loss_pct = -X` -> fire when (price-entry)/entry*100 <= -X."""

    def test_fires_at_threshold(self):
        # Entry 100, price 75 -> -25% exactly; threshold -25 -> fires (<=).
        a = check(_pos(avg_entry=100.0), 75.0,
                  {"safety_max_loss_pct": -25.0})
        self.assertTrue(a.fire)
        self.assertEqual(a.trigger, "max_loss_pct")
        self.assertIn("force close", a.reason)

    def test_fires_below_threshold(self):
        # Entry 100, price 50 -> -50%; threshold -25 -> well past, fires.
        a = check(_pos(avg_entry=100.0), 50.0,
                  {"safety_max_loss_pct": -25.0})
        self.assertTrue(a.fire)

    def test_does_not_fire_above_threshold(self):
        # Entry 100, price 80 -> -20%; threshold -25 -> doesn't fire.
        a = check(_pos(avg_entry=100.0), 80.0,
                  {"safety_max_loss_pct": -25.0})
        self.assertFalse(a.fire)

    def test_profitable_position_never_fires_loss_trigger(self):
        # Entry 100, price 110 -> +10%; threshold -25 -> doesn't fire.
        a = check(_pos(avg_entry=100.0), 110.0,
                  {"safety_max_loss_pct": -25.0})
        self.assertFalse(a.fire)

    def test_zero_entry_price_safe(self):
        # Defensive: bad cost_basis_usd would give avg_entry=0; must not crash
        # and must not fire (can't compute meaningful pct).
        a = check(_pos(avg_entry=0.0), 50.0,
                  {"safety_max_loss_pct": -25.0})
        self.assertFalse(a.fire)

    def test_string_threshold_coerced(self):
        # params.json may load number-strings; should still work.
        a = check(_pos(avg_entry=100.0), 50.0,
                  {"safety_max_loss_pct": "-25"})
        self.assertTrue(a.fire)

    def test_invalid_threshold_silently_skipped(self):
        a = check(_pos(avg_entry=100.0), 50.0,
                  {"safety_max_loss_pct": "not-a-number"})
        self.assertFalse(a.fire)


class TestMaxHoldingBarsTrigger(unittest.TestCase):
    """`safety_max_holding_bars = N` -> fire when bars_since_entry >= N."""

    def test_fires_at_cap(self):
        a = check(_pos(), 100.0, {"safety_max_holding_bars": 10},
                  bars_since_entry=10)
        self.assertTrue(a.fire)
        self.assertEqual(a.trigger, "max_holding_bars")

    def test_fires_above_cap(self):
        a = check(_pos(), 100.0, {"safety_max_holding_bars": 10},
                  bars_since_entry=15)
        self.assertTrue(a.fire)

    def test_does_not_fire_below_cap(self):
        a = check(_pos(), 100.0, {"safety_max_holding_bars": 10},
                  bars_since_entry=9)
        self.assertFalse(a.fire)

    def test_bars_count_none_skips_trigger(self):
        # If runner can't compute bars_since_entry (no entry timestamp,
        # empty bars), holding-time trigger is silently skipped.
        a = check(_pos(), 100.0, {"safety_max_holding_bars": 1},
                  bars_since_entry=None)
        self.assertFalse(a.fire)


class TestBothTriggers(unittest.TestCase):
    def test_loss_trigger_wins_over_holding_when_both_fire(self):
        # Both triggers would fire; current impl checks loss first so
        # that's what the operator sees in the log.
        a = check(_pos(avg_entry=100.0), 50.0,
                  {"safety_max_loss_pct": -25.0,
                   "safety_max_holding_bars": 1},
                  bars_since_entry=100)
        self.assertTrue(a.fire)
        self.assertEqual(a.trigger, "max_loss_pct")

    def test_holding_fires_when_loss_doesnt(self):
        # Position is profitable but held too long.
        a = check(_pos(avg_entry=100.0), 110.0,
                  {"safety_max_loss_pct": -25.0,
                   "safety_max_holding_bars": 5},
                  bars_since_entry=10)
        self.assertTrue(a.fire)
        self.assertEqual(a.trigger, "max_holding_bars")


class TestBarsSinceEntry(unittest.TestCase):
    def test_returns_none_on_empty_bars(self):
        self.assertIsNone(bars_since_entry([], "2026-01-01T00:00:00Z"))

    def test_returns_none_on_missing_entry_ts(self):
        bars = [{"t": "2026-01-01T00:00:00Z"}]
        self.assertIsNone(bars_since_entry(bars, None))

    def test_counts_bars_at_or_after_entry(self):
        bars = [
            {"t": "2026-01-01T00:00:00Z"},
            {"t": "2026-01-01T01:00:00Z"},
            {"t": "2026-01-01T02:00:00Z"},
            {"t": "2026-01-01T03:00:00Z"},
        ]
        # Entry at 01:00 -> 3 bars >= that (01:00, 02:00, 03:00).
        self.assertEqual(bars_since_entry(bars, "2026-01-01T01:00:00Z"), 3)

    def test_entry_after_all_bars(self):
        bars = [{"t": "2026-01-01T00:00:00Z"}]
        self.assertEqual(bars_since_entry(bars, "2026-12-31T00:00:00Z"), 0)


class TestBacktestIntegration(unittest.TestCase):

    def test_backstop_force_closes_in_backtest(self):
        from runner.backtest import backtest  # noqa: WPS433

        class _A:
            def __init__(self, action="hold", symbol="SYM",
                         notional_usd=0.0, reason=""):
                self.action = action
                self.symbol = symbol
                self.notional_usd = notional_usd
                self.reason = reason

        bought = {"done": False}

        def diamond_hands(market_state, position_state, params):
            symbol = market_state["symbol"]
            if not bought["done"] and not position_state.get(symbol):
                bought["done"] = True
                return _A("buy", symbol, notional_usd=100.0)
            return _A()

        from datetime import datetime, timezone, timedelta
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Enter near 100, crash to 50 (-50% total). Backstop at -25%.
        closes = [100.0] * 3 + [90.0, 80.0, 70.0, 60.0, 50.0, 50.0, 50.0]
        bars = [
            {"t": (base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "o": c, "h": c, "l": c, "c": c, "v": 1.0}
            for i, c in enumerate(closes)
        ]

        # Control: no backstop -> rides all the way down, never sells.
        bought["done"] = False
        no_backstop = backtest("diamond", bars=bars,
                               params={"symbol": "SYM"},
                               decide_fn=diamond_hands)
        # With backstop @ -25%: -30% (100->70) trips on bar 5.
        bought["done"] = False
        with_backstop = backtest("diamond", bars=bars,
                                 params={"symbol": "SYM",
                                         "safety_max_loss_pct": -25.0},
                                 decide_fn=diamond_hands)

        no_sells = no_backstop.n_closes
        bs_sells = with_backstop.n_closes
        self.assertEqual(no_sells, 0,
                         "control: diamond-hands strategy should never sell")
        self.assertEqual(bs_sells, 1,
                         "backstop should have force-closed exactly once")
        self.assertGreater(with_backstop.final_equity,
                           no_backstop.final_equity,
                           "backstop close should preserve more equity than "
                           "holding through the crash")


class TestPositionEntryTs(unittest.TestCase):
    """`db.position_entry_ts` powers the live runner's holding-time
    backstop. Contract: returns the ts of the buy that opened the
    currently-open position, or None if flat."""

    def setUp(self):
        import tempfile, os  # noqa: WPS433
        self.tmpdir = tempfile.mkdtemp(prefix="tess_db_")
        self.db_path = Path(self.tmpdir) / "t.db"
        from runner import db  # noqa: WPS433
        self.db = db
        db.init_db(self.db_path)

    def tearDown(self):
        import shutil  # noqa: WPS433
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _trade(self, side, qty, ts, *, status="filled", strategy="s1",
               symbol="SYM", price=100.0, notional=100.0):
        # Insert directly; log_trade fills ts_utc with now() which we can't
        # control. Need deterministic timestamps for this test.
        with self.db.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO trades(strategy, symbol, side, qty, "
                "notional_usd, price, alpaca_order_id, status, reason, "
                "raw, ts_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (strategy, symbol, side, qty, notional, price,
                 None, status, "", None, ts),
            )

    def test_flat_returns_none(self):
        self.assertIsNone(self.db.position_entry_ts("s1", "SYM",
                                                   db_path=self.db_path))

    def test_open_position_returns_opening_buy_ts(self):
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z")
        self.assertEqual(
            self.db.position_entry_ts("s1", "SYM", db_path=self.db_path),
            "2026-01-01T00:00:00Z",
        )

    def test_scale_in_does_not_reset_entry_ts(self):
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z")
        self._trade("buy", 1.0, "2026-01-01T01:00:00Z")
        # Still the original opening, not the scale-in.
        self.assertEqual(
            self.db.position_entry_ts("s1", "SYM", db_path=self.db_path),
            "2026-01-01T00:00:00Z",
        )

    def test_closed_position_returns_none(self):
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z")
        self._trade("sell", 1.0, "2026-01-01T05:00:00Z")
        self.assertIsNone(self.db.position_entry_ts("s1", "SYM",
                                                   db_path=self.db_path))

    def test_reopened_position_uses_new_entry_ts(self):
        # Cycle: buy -> sell -> buy. Second buy is the current opening.
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z")
        self._trade("sell", 1.0, "2026-01-01T05:00:00Z")
        self._trade("buy", 1.0, "2026-01-02T00:00:00Z")
        self.assertEqual(
            self.db.position_entry_ts("s1", "SYM", db_path=self.db_path),
            "2026-01-02T00:00:00Z",
        )

    def test_partial_sell_does_not_reset(self):
        # Buy 2, sell 1 -> still long 1. Entry ts unchanged.
        self._trade("buy", 2.0, "2026-01-01T00:00:00Z")
        self._trade("sell", 1.0, "2026-01-01T03:00:00Z")
        self.assertEqual(
            self.db.position_entry_ts("s1", "SYM", db_path=self.db_path),
            "2026-01-01T00:00:00Z",
        )

    def test_per_symbol_isolation(self):
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z", symbol="AAA")
        self._trade("buy", 1.0, "2026-02-01T00:00:00Z", symbol="BBB")
        self.assertEqual(
            self.db.position_entry_ts("s1", "AAA", db_path=self.db_path),
            "2026-01-01T00:00:00Z",
        )
        self.assertEqual(
            self.db.position_entry_ts("s1", "BBB", db_path=self.db_path),
            "2026-02-01T00:00:00Z",
        )

    def test_per_strategy_isolation(self):
        self._trade("buy", 1.0, "2026-01-01T00:00:00Z", strategy="s1")
        self._trade("buy", 1.0, "2026-02-01T00:00:00Z", strategy="s2")
        self.assertEqual(
            self.db.position_entry_ts("s1", "SYM", db_path=self.db_path),
            "2026-01-01T00:00:00Z",
        )
        self.assertEqual(
            self.db.position_entry_ts("s2", "SYM", db_path=self.db_path),
            "2026-02-01T00:00:00Z",
        )


if __name__ == "__main__":
    unittest.main()


    """End-to-end: backstop wired into the backtester. A strategy that
    refuses to exit a losing position MUST get force-closed when
    safety_max_loss_pct is configured."""
