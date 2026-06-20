"""Tests for the event-driven, shared-cash backtest harness (runner/backtest_event.py).

Run:
    python3 -m pytest tests/test_backtest_event.py -q

Coverage:
  1.  resolve_event_entries: reaction=first bar>=event, entry=reaction+1,
      weekend roll, drop too-recent events, same-bar mode for tests.
  2.  No-lookahead pin: decide_event NEVER sees a bar with t > clock_t; the
      entry bar is the LAST visible bar; the reaction bar is strictly before it.
  3.  Shared-cash accounting: a hand-computed 2-symbol fixture where portfolio
      P&L and final equity are asserted exactly.
  4.  Cash conservation: final equity == starting + realized P&L; cash floor.
  5.  Concurrency cap: cap=2 + 3 simultaneous events -> 2 enter, 1 skipped_cap.
  6.  Shared-cash exhaustion: $250 cash, $100 notional, 4 events -> 2 fund.
  7.  Exit policy: take / stop / hold-H / window-end + tie-break (stop>take).
  8.  Single position per symbol: overlapping events don't double-stack.
  9.  Determinism: identical inputs -> identical equity curve + trades.
 10.  beats-BH-SPY same path benchmark.
 11.  Cost model drags P&L; zero-cost is exact.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import List

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.backtest_event import (  # noqa: E402
    backtest_event,
    resolve_event_entries,
    EventContext,
    EventDecision,
)
from runner.backtest import CostModel  # noqa: E402


def _bar(t_iso: str, c: float, *, o=None, h=None, l=None, v: float = 1.0) -> dict:
    return {"t": t_iso, "o": o if o is not None else c,
            "h": h if h is not None else c, "l": l if l is not None else c,
            "c": c, "v": v}


def _daily(start_day: int, closes: List[float], *, month="01", year="2025") -> List[dict]:
    out = []
    for i, c in enumerate(closes):
        d = start_day + i
        out.append(_bar(f"{year}-{month}-{d:02d}T00:00:00Z", c))
    return out


ZERO_COST = CostModel(spread_bps=0.0, fee_bps=0.0)


def _always_enter(notional=100.0):
    def fn(ctx: EventContext):
        return EventDecision(True, notional_usd=notional, reason="test-enter")
    return fn


class TestResolveEntries(unittest.TestCase):
    def test_reaction_and_entry_indices(self):
        bars = _daily(1, [10, 11, 12, 13, 14])
        self.assertEqual(resolve_event_entries(bars, ["2025-01-02"]),
                         [("2025-01-02", 1, 2)])

    def test_weekend_roll(self):
        bars = [_bar("2025-01-03T00:00:00Z", 10), _bar("2025-01-06T00:00:00Z", 11),
                _bar("2025-01-07T00:00:00Z", 12)]
        self.assertEqual(resolve_event_entries(bars, ["2025-01-04"]),
                         [("2025-01-04", 1, 2)])

    def test_drop_too_recent_event(self):
        bars = _daily(1, [10, 11])
        self.assertEqual(resolve_event_entries(bars, ["2025-01-02"]), [])

    def test_drop_event_after_all_bars(self):
        bars = _daily(1, [10, 11, 12])
        self.assertEqual(resolve_event_entries(bars, ["2025-02-01"]), [])

    def test_same_bar_mode(self):
        bars = _daily(1, [10, 11, 12])
        self.assertEqual(
            resolve_event_entries(bars, ["2025-01-02"], require_gap_after_event=False),
            [("2025-01-02", 1, 1)])

    def test_sorted_and_deduped(self):
        bars = _daily(1, [10, 11, 12, 13, 14, 15])
        res = resolve_event_entries(bars, ["2025-01-04", "2025-01-02", "2025-01-02"])
        self.assertEqual([r[0] for r in res], ["2025-01-02", "2025-01-04"])
        self.assertEqual([r[2] for r in res], [2, 4])


class TestNoLookahead(unittest.TestCase):
    def test_decide_event_never_sees_future(self):
        bars = _daily(1, [10, 11, 12, 13, 14, 15, 16])
        seen = {}

        def probe(ctx: EventContext):
            last_t = ctx.bars[-1]["t"]
            self.assertTrue(all(b["t"] <= ctx.clock_t for b in ctx.bars))
            self.assertEqual(last_t, ctx.clock_t)
            self.assertLess(ctx.reaction_bar["t"], last_t)
            self.assertEqual(ctx.reaction_bar["t"], ctx.bars[-2]["t"])
            seen["ok"] = True
            return EventDecision(False)

        backtest_event("t", {"A": bars}, {"A": ["2025-01-03"]},
                       {"holding_bars": 2}, decide_event_fn=probe,
                       default_cost_model=ZERO_COST)
        self.assertTrue(seen.get("ok"))

    def test_entry_fills_after_reaction_bar(self):
        bars = _daily(1, [10, 10, 20, 21, 22])
        captured = {}

        def probe(ctx: EventContext):
            captured["fill"] = ctx.last_price
            captured["reaction_close"] = ctx.reaction_bar["c"]
            return EventDecision(True, notional_usd=100.0)

        backtest_event("t", {"A": bars}, {"A": ["2025-01-03"]},
                       {"holding_bars": 10, "stop_pct": -1, "take_pct": 99},
                       decide_event_fn=probe, default_cost_model=ZERO_COST)
        self.assertEqual(captured["reaction_close"], 20)
        self.assertEqual(captured["fill"], 21)


class TestSharedCashAccounting(unittest.TestCase):
    def test_hand_computed_two_symbol_pnl(self):
        a = _daily(1, [90, 100, 100, 105, 110])
        b = _daily(1, [60, 50, 50, 47, 45])
        params = {"holding_bars": 2, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a, "B": b},
                           {"A": ["2025-01-02"], "B": ["2025-01-02"]},
                           params, starting_cash=1000.0,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST, max_concurrent=10)
        self.assertEqual(r.n_entries, 2)
        self.assertEqual(r.n_trades, 2)
        pnls = sorted(tr.pnl_usd for tr in r.trades)
        self.assertAlmostEqual(pnls[0], -10.0, places=6)
        self.assertAlmostEqual(pnls[1], 10.0, places=6)
        self.assertAlmostEqual(r.final_equity, 1000.0, places=6)
        self.assertAlmostEqual(r.total_return_usd, 0.0, places=6)
        self.assertEqual(r.win_rate, 0.5)

    def test_cash_conservation_and_no_negative(self):
        a = _daily(1, [90, 100, 100, 105, 110, 108, 107])
        b = _daily(1, [60, 50, 50, 47, 45, 44, 43])
        params = {"holding_bars": 3, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a, "B": b},
                           {"A": ["2025-01-02"], "B": ["2025-01-02"]},
                           params, starting_cash=1000.0,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        realized = sum(tr.pnl_usd for tr in r.trades)
        self.assertAlmostEqual(r.final_equity, 1000.0 + realized, places=6)
        self.assertTrue(all(e > 700 for e in r.equity_curve))


class TestCapsAndCash(unittest.TestCase):
    def test_concurrency_cap_enforced(self):
        syms = {s: _daily(1, [90, 100, 100, 100, 100, 100]) for s in ["A", "B", "C"]}
        events = {s: ["2025-01-02"] for s in ["A", "B", "C"]}
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", syms, events, params, starting_cash=1000.0,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST, max_concurrent=2)
        self.assertEqual(r.n_entries, 2)
        self.assertEqual(r.n_skipped_cap, 1)
        self.assertLessEqual(r.max_concurrent_positions, 2)

    def test_shared_cash_exhaustion_no_negative(self):
        syms = {s: _daily(1, [90, 100, 100, 100, 100, 100]) for s in ["A", "B", "C", "D"]}
        events = {s: ["2025-01-02"] for s in ["A", "B", "C", "D"]}
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", syms, events, params, starting_cash=250.0,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST, max_concurrent=10)
        self.assertEqual(r.n_entries, 2)
        self.assertEqual(r.n_skipped_cash, 2)
        self.assertAlmostEqual(r.final_equity, 250.0, places=6)


class TestExitPolicy(unittest.TestCase):
    def test_take_profit(self):
        a = _daily(1, [90, 100, 100, 115, 120])
        params = {"holding_bars": 99, "stop_pct": -0.5, "take_pct": 0.10,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_trades, 1)
        self.assertIn("take", r.trades[0].exit_reason)
        self.assertAlmostEqual(r.trades[0].exit_price, 115.0, places=6)

    def test_stop_loss(self):
        a = _daily(1, [90, 100, 100, 90, 80])
        params = {"holding_bars": 99, "stop_pct": -0.05, "take_pct": 0.99,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertIn("stop", r.trades[0].exit_reason)
        self.assertAlmostEqual(r.trades[0].exit_price, 90.0, places=6)

    def test_hold_horizon(self):
        a = _daily(1, [90, 100, 100, 101, 102, 103, 104])
        params = {"holding_bars": 2, "stop_pct": -0.5, "take_pct": 0.99,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertIn("held", r.trades[0].exit_reason)
        self.assertEqual(r.trades[0].bars_held, 2)
        self.assertAlmostEqual(r.trades[0].exit_price, 102.0, places=6)

    def test_tie_break_stop_over_take(self):
        a = _daily(1, [90, 100, 100, 50, 50])
        params = {"holding_bars": 99, "stop_pct": -0.05, "take_pct": -0.10,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertIn("stop", r.trades[0].exit_reason)

    def test_window_end_liquidation(self):
        a = _daily(1, [90, 100, 100, 101])
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_trades, 1)
        self.assertEqual(r.trades[0].exit_reason, "window_end")


class TestOnePositionPerSymbol(unittest.TestCase):
    def test_overlapping_events_dont_stack(self):
        a = _daily(1, [90, 100, 100, 101, 102, 103, 104, 105])
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02", "2025-01-04"]},
                           params, decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_entries, 1)
        self.assertGreaterEqual(r.n_skipped_strategy, 1)


class TestDeterminism(unittest.TestCase):
    def test_identical_inputs_identical_output(self):
        a = _daily(1, [90, 100, 100, 105, 110, 108])
        b = _daily(1, [60, 50, 50, 52, 49, 51])
        params = {"holding_bars": 2, "stop_pct": -0.2, "take_pct": 0.2,
                  "notional_usd": 100.0}
        ev = {"A": ["2025-01-02"], "B": ["2025-01-02"]}
        r1 = backtest_event("t", {"A": a, "B": b}, ev, params,
                            decide_event_fn=_always_enter(100.0),
                            default_cost_model=ZERO_COST)
        r2 = backtest_event("t", {"A": a, "B": b}, ev, params,
                            decide_event_fn=_always_enter(100.0),
                            default_cost_model=ZERO_COST)
        self.assertEqual(r1.equity_curve, r2.equity_curve)
        self.assertEqual([t.pnl_usd for t in r1.trades],
                         [t.pnl_usd for t in r2.trades])


class TestBenchmark(unittest.TestCase):
    def test_bh_spy_same_path(self):
        a = _daily(1, [90, 100, 100, 105, 110, 110])
        spy_times = [bar["t"] for bar in a]
        spy_closes = [100, 100, 100, 105, 110, 110]
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST,
                           spy_closes=spy_closes, spy_times=spy_times)
        self.assertAlmostEqual(r.bh_spy_return_pct, 0.10, places=6)
        self.assertIsNotNone(r.beats_bh_spy)


class TestCostModel(unittest.TestCase):
    def test_spread_drags_pnl(self):
        a = _daily(1, [90, 100, 100, 100, 100])
        params = {"holding_bars": 2, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}
        cm = CostModel(spread_bps=2.0, fee_bps=0.0)
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=cm)
        self.assertEqual(r.n_trades, 1)
        self.assertLess(r.trades[0].pnl_usd, 0.0)
        self.assertGreater(r.total_costs_usd, 0.0)


class TestNextOpenExitFill(unittest.TestCase):
    """Pins the OPT-IN exit_fill="next_open" path (overnight MOC->MOO).

    With holding_bars=1 the hold-horizon exit fires on the bar AFTER entry, so
    filling at that bar's OPEN == selling at the next session's open. Default
    ("close") must be unchanged; "next_open" must fill at the open, not close.
    """

    def _fixture(self):
        # d03 = entry bar (fill at close=200); d04 = exit bar (open=120, close=999)
        a = [
            _bar("2025-01-01T00:00:00Z", 100, o=100),
            _bar("2025-01-02T00:00:00Z", 100, o=100),   # reaction bar
            _bar("2025-01-03T00:00:00Z", 200, o=150),   # entry: fill @ close 200
            _bar("2025-01-04T00:00:00Z", 999, o=120),   # exit: open 120 vs close 999
        ]
        return a

    def test_next_open_fills_at_open_not_close(self):
        a = self._fixture()
        params = {"holding_bars": 1, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0, "exit_fill": "next_open"}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_trades, 1)
        tr = r.trades[0]
        # entry fill = close of d03 = 200; qty = 100/200 = 0.5
        self.assertAlmostEqual(tr.entry_price, 200.0, places=6)
        self.assertAlmostEqual(tr.qty, 0.5, places=9)
        # exit fill = OPEN of d04 = 120 (NOT close 999)
        self.assertAlmostEqual(tr.exit_price, 120.0, places=6)
        # pnl = 0.5*120 - 100 = -40
        self.assertAlmostEqual(tr.pnl_usd, -40.0, places=6)

    def test_close_mode_default_unchanged(self):
        a = self._fixture()
        params = {"holding_bars": 1, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0}  # no exit_fill -> default "close"
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_trades, 1)
        tr = r.trades[0]
        # default close mode exits at close of d04 = 999
        self.assertAlmostEqual(tr.exit_price, 999.0, places=6)
        self.assertAlmostEqual(tr.pnl_usd, 0.5 * 999.0 - 100.0, places=6)

    def test_explicit_close_equals_default(self):
        a = self._fixture()
        base = {"holding_bars": 1, "stop_pct": -0.99, "take_pct": 9.9,
                "notional_usd": 100.0}
        r_default = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, dict(base),
                                   decide_event_fn=_always_enter(100.0),
                                   default_cost_model=ZERO_COST)
        r_explicit = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]},
                                    dict(base, exit_fill="close"),
                                    decide_event_fn=_always_enter(100.0),
                                    default_cost_model=ZERO_COST)
        self.assertEqual(r_default.equity_curve, r_explicit.equity_curve)
        self.assertAlmostEqual(r_default.trades[0].pnl_usd,
                               r_explicit.trades[0].pnl_usd, places=9)

    def test_bad_exit_fill_value_falls_back_to_close(self):
        a = self._fixture()
        params = {"holding_bars": 1, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0, "exit_fill": "garbage"}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertAlmostEqual(r.trades[0].exit_price, 999.0, places=6)

    def test_next_open_applies_sell_spread_to_open(self):
        a = self._fixture()
        params = {"holding_bars": 1, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0, "exit_fill": "next_open"}
        cm = CostModel(spread_bps=10.0, fee_bps=0.0)
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=cm)
        tr = r.trades[0]
        # buy fill = 200*(1+10/1e4)=200.2 ; sell fill = open 120*(1-10/1e4)=119.88
        self.assertAlmostEqual(tr.entry_price, 200.0 * (1 + 10 / 1e4), places=6)
        self.assertAlmostEqual(tr.exit_price, 120.0 * (1 - 10 / 1e4), places=6)
        self.assertGreater(r.total_costs_usd, 0.0)

    def test_window_end_still_fills_close_in_next_open_mode(self):
        # If a position never reaches its hold-horizon, window-end liquidation
        # fills at the last close (no next bar exists) even in next_open mode.
        a = [
            _bar("2025-01-01T00:00:00Z", 100, o=100),
            _bar("2025-01-02T00:00:00Z", 100, o=100),   # reaction
            _bar("2025-01-03T00:00:00Z", 200, o=150),   # entry @ close 200
        ]
        params = {"holding_bars": 99, "stop_pct": -0.99, "take_pct": 9.9,
                  "notional_usd": 100.0, "exit_fill": "next_open"}
        r = backtest_event("t", {"A": a}, {"A": ["2025-01-02"]}, params,
                           decide_event_fn=_always_enter(100.0),
                           default_cost_model=ZERO_COST)
        self.assertEqual(r.n_trades, 1)
        self.assertEqual(r.trades[0].exit_reason, "window_end")
        # window_end fills at the entry bar's close (last visible mark) = 200
        self.assertAlmostEqual(r.trades[0].exit_price, 200.0, places=6)


if __name__ == "__main__":
    unittest.main()
