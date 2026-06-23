"""Cross-sectional backtest harness tests.

Run with:
    python3 -m pytest tests/test_backtest_xsec.py -q

Covers:
    1. Cross-sectional ranking: a top-1 momentum decide_xsec picks the
       highest-momentum symbol each tick and only buys that one.
    2. Shared-cap risk enforcement: a strategy asking for $80 in 3 names
       gets each leg proportionally clamped so total <= MAX_POSITION=$100.
    3. Missing-bar handling: a symbol with fewer bars is exposed as
       has_bar=False on ticks where it doesn't print; no fill attempted;
       eligible later when it does print.
    4. Bar-clock sync correctness: union of timestamps, sorted; per-symbol
       cursor advances only on ticks where that symbol prints.
    5. No-lookahead: a probe strategy cannot see any bar with t > clock_t.
    6. Equity-curve correctness across N symbols: known synthetic basket
       buy-and-hold matches hand-computed cash + MV.
    7. Cost model applied per-symbol-trade: total_costs_usd matches
       hand-computed spread*notional summed over fills.
    8. Walk-forward integration: run backtest_xsec across multiple
       NAMED_WINDOWS-style end-dates and assert deterministic aggregate
       per window. (Pure unit: no network — passes synthetic bars.)
    9. Determinism: same input -> identical equity_curve byte-for-byte.
   10. Basket-cap when at-cap-already: existing $100 position blocks any
       new buys even though strategy requested some.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.backtest_xsec import (  # noqa: E402
    XSecBacktestResult,
    build_clock,
    backtest_xsec,
    _clamp_basket,
    _PosBook,
)
from runner.backtest import CostModel, MAX_POSITION, MAX_NOTIONAL  # noqa: E402


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _bar(t_iso: str, c: float, *, o: float = None, h: float = None,
         l: float = None, v: float = 1.0) -> dict:
    return {
        "t": t_iso,
        "o": o if o is not None else c,
        "h": h if h is not None else c,
        "l": l if l is not None else c,
        "c": c,
        "v": v,
    }


def _hourly_bars(closes: List[float], start_day: int = 1) -> List[dict]:
    base = datetime(2026, 1, start_day, 0, 0, tzinfo=timezone.utc)
    return [
        _bar((base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), c)
        for i, c in enumerate(closes)
    ]


def _daily_bars(closes: List[float], start_day: int = 1) -> List[dict]:
    base = datetime(2026, 1, start_day, 0, 0, tzinfo=timezone.utc)
    return [
        _bar((base + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), c)
        for i, c in enumerate(closes)
    ]


class _A:
    """Lightweight Action duck-type."""
    def __init__(self, action: str, symbol: str, notional_usd: float = 0.0,
                 qty=None, reason: str = ""):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional_usd
        self.qty = qty
        self.reason = reason


# ---------------------------------------------------------------------------
# 1. Cross-sectional ranking
# ---------------------------------------------------------------------------

class TestCrossSectionalRanking(unittest.TestCase):
    """Top-1 momentum: at each tick pick the symbol with highest
    last-5-bar return; buy it if flat, hold otherwise. Close on opposite."""

    def test_top1_momentum_picks_strongest(self):
        # Three symbols, 20 hourly bars. A ramps up, B flat, C ramps down.
        bars = {
            "A/USD": _hourly_bars([100 + i * 2 for i in range(20)]),
            "B/USD": _hourly_bars([100.0] * 20),
            "C/USD": _hourly_bars([100 - i * 2 for i in range(20)]),
        }

        def decide_xsec(ms, ps, params):
            ranks = []
            for sym, sv in ms["symbols"].items():
                b = sv["bars"]
                if len(b) < 6:
                    continue
                ret = (b[-1]["c"] - b[-6]["c"]) / b[-6]["c"]
                ranks.append((ret, sym))
            if not ranks:
                return {}
            ranks.sort(reverse=True)
            top = ranks[0][1]
            out = {}
            if not ps:
                out[top] = _A("buy", top, notional_usd=50.0, reason="top1")
            return out

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Should only buy A; never B or C.
        self.assertEqual(r.per_symbol["A/USD"].n_buys, 1)
        self.assertEqual(r.per_symbol["B/USD"].n_buys, 0)
        self.assertEqual(r.per_symbol["C/USD"].n_buys, 0)
        self.assertEqual(r.n_trades, 1)


# ---------------------------------------------------------------------------
# 2. Shared-cap risk enforcement (proportional clamp)
# ---------------------------------------------------------------------------

class TestSharedCapClamp(unittest.TestCase):

    def test_requesting_3x_80_clamped_to_100_total(self):
        # 3 symbols, 1 tick each. Strategy asks $800 in each => $2400 requested
        # but MAX_POSITION = $1000. Each leg should be scaled to ~$333.33.
        # (Request notionals scaled 10x with the 2026-05-31 $100->$1000 paper
        # cap bump so the clamp still fires; ratios unchanged.)
        bars = {
            "A/USD": _hourly_bars([100.0, 100.0]),
            "B/USD": _hourly_bars([100.0, 100.0]),
            "C/USD": _hourly_bars([100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("00:00:00Z"):
                return {}  # wait one tick so we have history
            if ps:
                return {}
            return {
                "A/USD": _A("buy", "A/USD", notional_usd=800.0),
                "B/USD": _A("buy", "B/USD", notional_usd=800.0),
                "C/USD": _A("buy", "C/USD", notional_usd=800.0),
            }

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(r.n_basket_clamps, 1)
        # Each leg got 1000/2400 of $800 = ~$333.33.
        self.assertEqual(r.per_symbol["A/USD"].n_buys, 1)
        self.assertEqual(r.per_symbol["B/USD"].n_buys, 1)
        self.assertEqual(r.per_symbol["C/USD"].n_buys, 1)
        # Total deployed must be <= MAX_POSITION.
        # cost_basis is exactly notional spent (zero fees in this test).
        total = sum(ps.realized_pnl_usd for ps in r.per_symbol.values())  # 0 since no closes
        self.assertEqual(total, 0.0)
        # We deployed exactly cap_headroom = MAX_POSITION.
        # Final equity unchanged (price flat, zero costs).
        starting_equity = r.final_equity  # equity is conserved here
        self.assertGreater(starting_equity, 0.0)
        # And we should be holding ~MAX_POSITION worth across the basket.
        held = sum(ps.final_market_value for ps in r.per_symbol.values())
        self.assertAlmostEqual(held, MAX_POSITION, places=2)

    def test_clamp_unit_function(self):
        # Direct unit test of _clamp_basket.
        actions = {
            "A": _A("buy", "A", notional_usd=80.0),
            "B": _A("buy", "B", notional_usd=80.0),
            "C": _A("buy", "C", notional_usd=80.0),
        }
        books = {sym: _PosBook() for sym in ("A", "B", "C")}
        prices = {"A": 100.0, "B": 100.0, "C": 100.0}
        # Each leg requests $80; total $240. With MAX_POSITION=$1000 this is
        # UNDER cap and would not clamp -- so scale requests up to force the
        # clamp path (intent of this unit test). 3x$800 = $2400 > $1000.
        for a in actions.values():
            a.notional_usd = 800.0
        clamped, was = _clamp_basket(actions, books, prices)
        self.assertTrue(was)
        self.assertAlmostEqual(sum(clamped.values()), MAX_POSITION, places=6)
        # Equal scaling.
        self.assertAlmostEqual(clamped["A"], clamped["B"], places=6)
        self.assertAlmostEqual(clamped["B"], clamped["C"], places=6)

    def test_clamp_passes_through_when_under_cap(self):
        actions = {
            "A": _A("buy", "A", notional_usd=30.0),
            "B": _A("buy", "B", notional_usd=30.0),
        }
        books = {sym: _PosBook() for sym in ("A", "B")}
        prices = {"A": 100.0, "B": 100.0}
        clamped, was = _clamp_basket(actions, books, prices)
        self.assertFalse(was)
        self.assertEqual(clamped, {"A": 30.0, "B": 30.0})


# ---------------------------------------------------------------------------
# 3. Missing-bar handling
# ---------------------------------------------------------------------------

class TestMissingBarHandling(unittest.TestCase):

    def test_symbol_with_no_bar_at_tick_is_not_fillable(self):
        # A has bars at hours 0-9; B only has bars at hours 5-9. The clock
        # union covers 0..9. At hours 0-4, B has_bar=False (and has no
        # visible bars at all). A buy attempt for B at hour 2 must be
        # skipped with "no bar at clock_t" reason.
        bars = {
            "A/USD": _hourly_bars([100.0] * 10),
            "B/USD": _hourly_bars([100.0] * 5, start_day=1),
        }
        # Shift B's timestamps so it only covers hours 5..9 of day 1.
        base = datetime(2026, 1, 1, 5, 0, tzinfo=timezone.utc)
        bars["B/USD"] = [
            _bar((base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), 100.0)
            for i in range(5)
        ]

        calls = []

        def decide_xsec(ms, ps, params):
            calls.append({sym: sv["has_bar"] for sym, sv in ms["symbols"].items()})
            # Always try to buy B if flat.
            if not ps:
                return {"B/USD": _A("buy", "B/USD", notional_usd=50.0)}
            return {}

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # First call at hour 0: B has no bar.
        self.assertFalse(calls[0]["B/USD"])
        self.assertTrue(calls[0]["A/USD"])
        # First tick where B prints (hour 5).
        # B should have eventually bought (clock tick == 5).
        self.assertEqual(r.per_symbol["B/USD"].n_buys, 1)
        # Pre-print attempts should be in skipped_reasons.
        skipped_for_b = r.per_symbol["B/USD"].skipped_reasons
        self.assertTrue(any("no bar at clock_t" in s for s in skipped_for_b),
                        f"expected skip-noise; got {skipped_for_b}")


# ---------------------------------------------------------------------------
# 4. Bar-clock sync correctness
# ---------------------------------------------------------------------------

class TestBarClockSync(unittest.TestCase):

    def test_clock_is_union_sorted(self):
        b_a = [_bar("2026-01-01T00:00:00Z", 1),
               _bar("2026-01-01T02:00:00Z", 2)]
        b_b = [_bar("2026-01-01T01:00:00Z", 1),
               _bar("2026-01-01T02:00:00Z", 1)]
        clock = build_clock({"A": b_a, "B": b_b})
        self.assertEqual(clock, [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T02:00:00Z",
        ])

    def test_cursor_advances_only_on_print(self):
        # A prints at h=0,1,2,3. B prints only at h=2.
        bars_a = _hourly_bars([10.0, 20.0, 30.0, 40.0])
        bars_b = [_bar("2026-01-01T02:00:00Z", 99.0)]
        seen_b_lastprice = []

        def decide_xsec(ms, ps, params):
            seen_b_lastprice.append(ms["symbols"]["B"]["last_price"])
            return {}

        backtest_xsec("xsec_test", {"A": bars_a, "B": bars_b},
                      {"timeframe": "1Hour"},
                      decide_xsec_fn=decide_xsec,
                      default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # 4 ticks. B's last_price is None until tick 2, then 99 from tick 2 on.
        self.assertEqual(seen_b_lastprice, [None, None, 99.0, 99.0])


# ---------------------------------------------------------------------------
# 5. No-lookahead invariant
# ---------------------------------------------------------------------------

class TestNoLookahead(unittest.TestCase):

    def test_strategy_only_sees_bars_up_to_clock_t(self):
        # 5 bars, ascending close.
        bars_a = _hourly_bars([1.0, 2.0, 3.0, 4.0, 5.0])
        bars_b = _hourly_bars([10.0, 20.0, 30.0, 40.0, 50.0])
        max_seen_per_tick = []

        def decide_xsec(ms, ps, params):
            t = ms["clock_t"]
            for sym, sv in ms["symbols"].items():
                for b in sv["bars"]:
                    # Hard invariant: no bar's timestamp may exceed clock_t.
                    if b["t"] > t:
                        raise AssertionError(
                            f"LOOKAHEAD VIOLATION: {sym} bar t={b['t']} > clock_t={t}")
            max_seen_per_tick.append({
                sym: len(sv["bars"]) for sym, sv in ms["symbols"].items()
            })
            return {}

        backtest_xsec("xsec_test", {"A": bars_a, "B": bars_b},
                      {"timeframe": "1Hour"},
                      decide_xsec_fn=decide_xsec,
                      default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Tick i sees exactly i+1 bars per symbol.
        self.assertEqual([m["A"] for m in max_seen_per_tick], [1, 2, 3, 4, 5])
        self.assertEqual([m["B"] for m in max_seen_per_tick], [1, 2, 3, 4, 5])


# ---------------------------------------------------------------------------
# 6. Equity curve correctness across N symbols
# ---------------------------------------------------------------------------

class TestEquityCurveAcrossNSymbols(unittest.TestCase):

    def test_known_basket_buy_and_hold(self):
        # 2 symbols, 3 bars each. Buy $50 of each on tick 1; hold; mark to market.
        bars = {
            "A/USD": _hourly_bars([100.0, 100.0, 110.0]),  # +10%
            "B/USD": _hourly_bars([100.0, 100.0, 90.0]),   # -10%
        }

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z") and not ps:
                return {
                    "A/USD": _A("buy", "A/USD", notional_usd=50.0),
                    "B/USD": _A("buy", "B/USD", notional_usd=50.0),
                }
            return {}

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # After tick 0: nothing bought, equity = 1000.
        # After tick 1: bought 0.5 A @ 100 + 0.5 B @ 100, cash 900, MV 100 -> 1000.
        # After tick 2: A at 110, B at 90 -> MV = 0.5*110 + 0.5*90 = 100.
        self.assertEqual(len(r.equity_curve), 3)
        self.assertAlmostEqual(r.equity_curve[0], 1000.0, places=2)
        self.assertAlmostEqual(r.equity_curve[1], 1000.0, places=2)
        self.assertAlmostEqual(r.equity_curve[2], 1000.0, places=2)
        self.assertAlmostEqual(r.final_equity, 1000.0, places=2)


# ---------------------------------------------------------------------------
# 7. Cost model applied per-symbol-trade
# ---------------------------------------------------------------------------

class TestPerSymbolCostModel(unittest.TestCase):

    def test_per_symbol_cost_charged(self):
        # Same setup as #6 but with 100 bps spread on A, 200 bps on B.
        # Buy $50 of each → spread cost: A: 0.50, B: 1.00, total $1.50.
        bars = {
            "A/USD": _hourly_bars([100.0, 100.0]),
            "B/USD": _hourly_bars([100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z") and not ps:
                return {
                    "A/USD": _A("buy", "A/USD", notional_usd=50.0),
                    "B/USD": _A("buy", "B/USD", notional_usd=50.0),
                }
            return {}

        cm_map = {
            "A/USD": CostModel(spread_bps=100.0, fee_bps=0.0),
            "B/USD": CostModel(spread_bps=200.0, fee_bps=0.0),
        }
        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          cost_model_by_symbol=cm_map)
        self.assertAlmostEqual(r.per_symbol["A/USD"].total_costs_usd, 0.50, places=4)
        self.assertAlmostEqual(r.per_symbol["B/USD"].total_costs_usd, 1.00, places=4)
        self.assertAlmostEqual(r.total_costs_usd, 1.50, places=4)


# ---------------------------------------------------------------------------
# 8. Walk-forward style integration: run across multiple windows
# ---------------------------------------------------------------------------

class TestWalkForwardIntegration(unittest.TestCase):
    """Show backtest_xsec composes with multiple end-dt windows: we hand
    it 3 distinct synthetic windows and assert aggregates match per
    window. Uses synthetic bars only — no network."""

    def test_multiple_windows_aggregate(self):
        # 3 windows, each a tiny synthetic basket. Strategy: always buy
        # the strongest of 2 symbols on the second tick of each window.
        def make_window(closes_a, closes_b):
            return {
                "A/USD": _hourly_bars(closes_a),
                "B/USD": _hourly_bars(closes_b),
            }

        windows = [
            ("up_a",   make_window([100, 102, 104, 106], [100, 99, 98, 97])),
            ("flat",   make_window([100, 100, 100, 100], [100, 100, 100, 100])),
            ("up_b",   make_window([100, 99, 98, 97],   [100, 102, 104, 106])),
        ]

        def decide_xsec(ms, ps, params):
            if ps:
                return {}
            ranks = []
            for sym, sv in ms["symbols"].items():
                b = sv["bars"]
                if len(b) < 2:
                    continue
                ret = (b[-1]["c"] - b[0]["c"]) / b[0]["c"]
                ranks.append((ret, sym))
            if not ranks:
                return {}
            ranks.sort(reverse=True)
            best_ret, best_sym = ranks[0]
            if best_ret <= 0:
                return {}
            return {best_sym: _A("buy", best_sym, notional_usd=50.0)}

        results = []
        for label, bars in windows:
            r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                              decide_xsec_fn=decide_xsec,
                              default_cost_model=CostModel(spread_bps=0, fee_bps=0))
            results.append((label, r))

        # up_a: bought A, A rose → positive return.
        self.assertEqual(results[0][1].per_symbol["A/USD"].n_buys, 1)
        self.assertEqual(results[0][1].per_symbol["B/USD"].n_buys, 0)
        self.assertGreater(results[0][1].total_return_pct, 0.0)
        # flat: no positive momentum -> no trades.
        self.assertEqual(results[1][1].n_trades, 0)
        self.assertAlmostEqual(results[1][1].total_return_pct, 0.0, places=6)
        # up_b: bought B.
        self.assertEqual(results[2][1].per_symbol["A/USD"].n_buys, 0)
        self.assertEqual(results[2][1].per_symbol["B/USD"].n_buys, 1)
        self.assertGreater(results[2][1].total_return_pct, 0.0)


# ---------------------------------------------------------------------------
# 9. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):
    def test_same_input_same_curve(self):
        bars = {
            "A/USD": _hourly_bars([100 + (i % 5) for i in range(50)]),
            "B/USD": _hourly_bars([100 + ((i + 2) % 7) for i in range(50)]),
            "C/USD": _hourly_bars([100 + ((i + 4) % 3) for i in range(50)]),
        }

        def decide_xsec(ms, ps, params):
            if len(ps) >= 2:
                return {}
            out = {}
            for sym in ms["symbols"]:
                if sym in ps:
                    continue
                if ms["symbols"][sym]["has_bar"]:
                    out[sym] = _A("buy", sym, notional_usd=20.0)
                    break
            return out

        r1 = backtest_xsec("d", bars, {"timeframe": "1Hour"},
                           decide_xsec_fn=decide_xsec,
                           default_cost_model=CostModel(spread_bps=10, fee_bps=0))
        r2 = backtest_xsec("d", bars, {"timeframe": "1Hour"},
                           decide_xsec_fn=decide_xsec,
                           default_cost_model=CostModel(spread_bps=10, fee_bps=0))
        self.assertEqual(r1.equity_curve, r2.equity_curve)
        self.assertEqual(r1.n_trades, r2.n_trades)


# ---------------------------------------------------------------------------
# 10. Basket cap when at-cap-already blocks new buys
# ---------------------------------------------------------------------------

class TestAtCapAlreadyBlocksBuys(unittest.TestCase):

    def test_existing_full_position_blocks_new_buy(self):
        # Buy $1000 of A on tick 1 (eats full cap). On tick 2 strategy
        # tries to buy $500 of B → must be clamped to $0. (Scaled 10x with
        # the 2026-05-31 $100->$1000 paper cap bump.)
        bars = {
            "A/USD": _hourly_bars([100.0, 100.0, 100.0]),
            "B/USD": _hourly_bars([100.0, 100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            t = ms["clock_t"]
            if t.endswith("01:00:00Z"):
                return {"A/USD": _A("buy", "A/USD", notional_usd=1000.0)}
            if t.endswith("02:00:00Z"):
                # A is already at cap; ask for B too.
                return {"B/USD": _A("buy", "B/USD", notional_usd=500.0)}
            return {}

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(r.per_symbol["A/USD"].n_buys, 1)
        self.assertEqual(r.per_symbol["B/USD"].n_buys, 0)
        # Should be flagged as a clamp on tick 2.
        self.assertEqual(r.n_basket_clamps, 1)
        # And the B leg should appear in skipped_reasons.
        self.assertTrue(any("basket clamp" in s
                             for s in r.per_symbol["B/USD"].skipped_reasons))


# ---------------------------------------------------------------------------
# 11. Per-leg notional cap still enforced (each leg <= MAX_NOTIONAL)
# ---------------------------------------------------------------------------

class TestPerLegNotionalCap(unittest.TestCase):
    def test_single_leg_over_max_notional_is_clamped_to_cap(self):
        # A single $1500 buy is over both MAX_NOTIONAL and MAX_POSITION ($1000
        # each). The basket clamp scales it down to exactly cap_headroom =
        # MAX_POSITION = $1000, which equals MAX_NOTIONAL so the downstream
        # per-leg risk check passes. Net effect: strategy gets exactly $1000
        # of exposure, never more. This is the intended semantic — the
        # harness's job is to keep TOTAL exposure within cap, not to
        # punish strategies that overshoot. (Request scaled 10x with the
        # 2026-05-31 paper cap bump.)
        bars = {"A/USD": _hourly_bars([100.0, 100.0])}

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z"):
                return {"A/USD": _A("buy", "A/USD", notional_usd=1500.0)}
            return {}

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Clamped, but trade went through at exactly MAX_POSITION.
        self.assertEqual(r.n_basket_clamps, 1)
        self.assertEqual(r.per_symbol["A/USD"].n_buys, 1)
        self.assertAlmostEqual(r.per_symbol["A/USD"].final_market_value,
                                MAX_POSITION, places=2)

    def test_two_legs_each_over_cap_clamped_to_share(self):
        # Two symbols each asking $2000. Total $4000. Cap headroom $1000.
        # Each leg should be scaled to $500, both fit per-leg cap, both fill.
        # (Requests scaled 10x with the 2026-05-31 $100->$1000 paper bump.)
        bars = {
            "A/USD": _hourly_bars([100.0, 100.0]),
            "B/USD": _hourly_bars([100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z"):
                return {
                    "A/USD": _A("buy", "A/USD", notional_usd=2000.0),
                    "B/USD": _A("buy", "B/USD", notional_usd=2000.0),
                }
            return {}

        r = backtest_xsec("xsec_test", bars, {"timeframe": "1Hour"},
                          decide_xsec_fn=decide_xsec,
                          default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(r.n_basket_clamps, 1)
        self.assertEqual(r.per_symbol["A/USD"].n_buys, 1)
        self.assertEqual(r.per_symbol["B/USD"].n_buys, 1)
        held = sum(ps.final_market_value for ps in r.per_symbol.values())
        self.assertAlmostEqual(held, MAX_POSITION, places=2)


# ---------------------------------------------------------------------------
# 11. Basket-aware per-day trade cap (added 2026-05-30 with risk.py change).
#     A 6-leg basket trying to open all 6 names on day 1 must NOT be
#     truncated at trade #4 by the legacy single-symbol MAX_TRADES_PER_DAY.
#     Strategy declares `xsec_basket_size: 6`; harness resolves cap to 12.
# ---------------------------------------------------------------------------

class TestBasketTradeCap(unittest.TestCase):

    def _six_symbol_bars(self):
        return {
            "S1/USD": _hourly_bars([100.0] * 4),
            "S2/USD": _hourly_bars([100.0] * 4),
            "S3/USD": _hourly_bars([100.0] * 4),
            "S4/USD": _hourly_bars([100.0] * 4),
            "S5/USD": _hourly_bars([100.0] * 4),
            "S6/USD": _hourly_bars([100.0] * 4),
        }

    def _open_all_six_decide(self, ms, ps, params):
        # On second tick (so we have one bar of history), open ALL six legs
        # at $15 each ($90 total => fits MAX_POSITION=$100 without clamp).
        if ms["clock_t"].endswith("00:00:00Z"):
            return {}
        if ps:
            return {}
        return {
            sym: _A("buy", sym, notional_usd=15.0)
            for sym in ["S1/USD", "S2/USD", "S3/USD", "S4/USD", "S5/USD", "S6/USD"]
        }

    def test_without_xsec_basket_size_truncates_at_legacy_cap_of_4(self):
        bars = self._six_symbol_bars()
        # No xsec_basket_size declared => legacy MAX_TRADES_PER_DAY=4.
        # Strategy asks for 6 buys, only 4 should fill, 2 skipped on risk.
        r = backtest_xsec(
            "xsec_test", bars, {"timeframe": "1Hour"},
            decide_xsec_fn=self._open_all_six_decide,
            default_cost_model=CostModel(spread_bps=0, fee_bps=0),
        )
        total_buys = sum(ps.n_buys for ps in r.per_symbol.values())
        total_skipped = sum(ps.n_skipped_risk for ps in r.per_symbol.values())
        # Exactly 4 fills, exactly 2 risk-skips (the 5th and 6th).
        self.assertEqual(total_buys, 4)
        self.assertGreaterEqual(total_skipped, 2)
        # The skipped legs were rejected for the day-cap reason.
        all_reasons = []
        for ps in r.per_symbol.values():
            all_reasons.extend(ps.skipped_reasons)
        cap_reasons = [r for r in all_reasons if "cap 4" in r]
        self.assertEqual(len(cap_reasons), 2,
                         msg=f"Expected 2 'cap 4' skips, got {len(cap_reasons)} "
                             f"out of all reasons: {all_reasons}")

    def test_with_xsec_basket_size_6_allows_all_6_legs_in_one_day(self):
        bars = self._six_symbol_bars()
        # Declare basket size => cap resolves to 2*6=12. All 6 buys fill.
        r = backtest_xsec(
            "xsec_test", bars,
            {"timeframe": "1Hour", "xsec_basket_size": 6},
            decide_xsec_fn=self._open_all_six_decide,
            default_cost_model=CostModel(spread_bps=0, fee_bps=0),
        )
        total_buys = sum(ps.n_buys for ps in r.per_symbol.values())
        total_skipped_risk = sum(ps.n_skipped_risk for ps in r.per_symbol.values())
        self.assertEqual(total_buys, 6,
                         msg=f"With xsec_basket_size=6 expected 6 fills, "
                             f"got {total_buys}")
        # No day-cap skips at all under K=6 (we only opened 6 of 12 budget).
        cap_reasons = []
        for ps in r.per_symbol.values():
            cap_reasons.extend(
                r for r in ps.skipped_reasons if "cap" in r and "already" in r
            )
        self.assertEqual(
            len(cap_reasons), 0,
            msg=f"Did not expect any day-cap skips under K=6, got: {cap_reasons}",
        )
        # Sanity: total_skipped_risk may be > 0 if the bar harness rejected
        # for *other* reasons (notional/position), but should be 0 here.
        self.assertEqual(total_skipped_risk, 0,
                         msg=f"Unexpected risk skips: {[ps.skipped_reasons for ps in r.per_symbol.values()]}")


# ---------------------------------------------------------------------------
# 11. Deployed-capital (instrument-level) drawdown — GATE Bar A #5(b)
#     binding fix (RULING 2, 2026-05-31).
#
#     The wipeout this clause must catch: a single $100 leg crashes -50%.
#     Against the $1000 portfolio NAV (~$900 idle cash), that crash dilutes
#     to ~-5% in `max_drawdown_pct` — invisible to a 30% NAV-based ceiling.
#     `worst_instrument_dd_pct` reports the un-diluted -50%, so the gate
#     (passes_bar_a_5b) TRIPS as it should.
# ---------------------------------------------------------------------------

class TestDeployedCapitalDrawdown(unittest.TestCase):

    def _crash_basket(self):
        # CRASH/USD: buy at 100, rides down to 50 by window end (-50% leg DD).
        # STABLE/USD: flat at 100 the whole window (no DD).
        return {
            "CRASH/USD": _hourly_bars([100.0, 100.0, 75.0, 50.0]),
            "STABLE/USD": _hourly_bars([100.0, 100.0, 100.0, 100.0]),
        }

    def _buy_crash_decide(self):
        # On tick 1, deploy $100 into the crashing leg only (the rest of the
        # $1000 book stays in cash — exactly the ~90%-cash dilution case).
        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z") and not ps:
                return {"CRASH/USD": _A("buy", "CRASH/USD", notional_usd=100.0)}
            return {}
        return decide_xsec

    def test_open_position_crash_shows_instrument_dd_not_diluted(self):
        """A -50% leg held into window-end: portfolio NAV DD is ~-5%
        (diluted), but worst_instrument_dd_pct is -50%."""
        r = backtest_xsec(
            "xsec_crash", self._crash_basket(), {"timeframe": "1Hour"},
            decide_xsec_fn=self._buy_crash_decide(),
            default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Portfolio NAV: $1000 book, $100 deployed, leg -> $50 => NAV ~ $950.
        # Portfolio-NAV drawdown is therefore only ~-5%.
        self.assertLess(abs(r.max_drawdown_pct), 0.10,
                        msg=f"portfolio NAV DD should be diluted (~-5%), "
                            f"got {r.max_drawdown_pct*100:.2f}%")
        # Deployed-capital DD is the real -50% (open position at window-end).
        self.assertAlmostEqual(r.worst_instrument_dd_pct, -0.50, places=2,
                               msg=f"instrument DD should be -50%, got "
                                   f"{r.worst_instrument_dd_pct*100:.2f}%")

    def test_closed_crash_trade_records_instrument_dd(self):
        """Same crash, but the leg is closed before window-end — the -50%
        DD-from-entry must still be captured via closed_trades."""
        bars = {
            "CRASH/USD": _hourly_bars([100.0, 100.0, 50.0, 60.0]),
            "STABLE/USD": _hourly_bars([100.0, 100.0, 100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            t = ms["clock_t"]
            if t.endswith("01:00:00Z") and not ps:
                return {"CRASH/USD": _A("buy", "CRASH/USD", notional_usd=100.0)}
            if t.endswith("03:00:00Z") and ps:
                return {"CRASH/USD": _A("close", "CRASH/USD")}
            return {}

        r = backtest_xsec(
            "xsec_crash_closed", bars, {"timeframe": "1Hour"},
            decide_xsec_fn=decide_xsec,
            default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Entry 100, intra-trade low 50 => -50% DD-from-entry on the closed trade.
        self.assertAlmostEqual(r.worst_instrument_dd_pct, -0.50, places=2,
                               msg=f"closed-trade instrument DD should be -50%, "
                                   f"got {r.worst_instrument_dd_pct*100:.2f}%")

    def test_minus_50_instrument_crash_TRIPS_bar_a_5b(self):
        """THE RULING 2 FIXTURE: a -50% instrument crash must now FAIL
        GATE Bar A #5(b), even though the diluted portfolio NAV DD is tiny.
        Builds an XSecWalkForwardAggregate directly from a crash window so
        we exercise passes_bar_a_5b without needing network/NAMED_WINDOWS."""
        from runner.walk_forward_xsec import (
            XSecWalkForwardAggregate, XSecWindowResult, passes_bar_a_5b,
            BAR_A_5B_MAX_INSTRUMENT_DD_PCT,
        )
        r = backtest_xsec(
            "xsec_crash", self._crash_basket(), {"timeframe": "1Hour"},
            decide_xsec_fn=self._buy_crash_decide(),
            default_cost_model=CostModel(spread_bps=0, fee_bps=0))

        # Hand-assemble the aggregate the way walk_forward_xsec would.
        agg = XSecWalkForwardAggregate(strategy="xsec_crash",
                                       basket=["CRASH/USD", "STABLE/USD"])
        agg.windows = [XSecWindowResult(
            label="crash_window", regime="bear", end_date="2026-01-01",
            days=1, backtest=r, bh_basket_return_pct=0.0,
            beats_bh_basket=False, bars_in_position_pct=75.0)]
        agg.worst_instrument_dd_pct = (
            min(w.backtest.worst_instrument_dd_pct for w in agg.windows) * 100.0)

        # Sanity: the diluted NAV DD would NOT trip a 30% ceiling.
        self.assertLess(abs(r.max_drawdown_pct) * 100.0,
                        BAR_A_5B_MAX_INSTRUMENT_DD_PCT,
                        msg="diluted NAV DD should be under the 30% ceiling "
                            "(that's the bug RULING 2 fixes)")

        # The deployed-capital gate must FAIL on the -50% instrument crash.
        ok, reason = passes_bar_a_5b(agg)
        self.assertFalse(ok,
                         msg=f"-50% instrument crash MUST trip #5(b); "
                             f"got pass with reason: {reason}")
        self.assertIn("FAIL", reason)
        self.assertAlmostEqual(agg.worst_instrument_dd_pct, -50.0, places=1)

    def test_well_behaved_strategy_passes_bar_a_5b(self):
        """Negative control: a leg with a shallow -8% DD passes #5(b)."""
        from runner.walk_forward_xsec import (
            XSecWalkForwardAggregate, XSecWindowResult, passes_bar_a_5b)
        bars = {
            "MILD/USD": _hourly_bars([100.0, 100.0, 92.0, 105.0]),  # -8% trough
            "STABLE/USD": _hourly_bars([100.0, 100.0, 100.0, 100.0]),
        }

        def decide_xsec(ms, ps, params):
            if ms["clock_t"].endswith("01:00:00Z") and not ps:
                return {"MILD/USD": _A("buy", "MILD/USD", notional_usd=100.0)}
            return {}

        r = backtest_xsec(
            "xsec_mild", bars, {"timeframe": "1Hour"},
            decide_xsec_fn=decide_xsec,
            default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        agg = XSecWalkForwardAggregate(strategy="xsec_mild",
                                       basket=["MILD/USD", "STABLE/USD"])
        agg.windows = [XSecWindowResult(
            label="mild", regime="chop", end_date="2026-01-01", days=1,
            backtest=r, bh_basket_return_pct=0.0, beats_bh_basket=True,
            bars_in_position_pct=75.0)]
        agg.worst_instrument_dd_pct = (
            min(w.backtest.worst_instrument_dd_pct for w in agg.windows) * 100.0)
        ok, reason = passes_bar_a_5b(agg)
        self.assertTrue(ok, msg=f"-8% DD should pass #5(b); reason: {reason}")
        self.assertIn("PASS", reason)


# ---------------------------------------------------------------------------
# 11. Loader candidate-path support (load_xsec_strategy candidate=...)
#     Pins: live path unchanged; candidate=True reads strategies_candidates/;
#     error messages name the right tree; decide_xsec export check still fires.
#     Hermetic: writes throwaway strategy packages under temp roots that are
#     monkeypatched into the module, then cleans them up. No real candidate
#     dir is depended on, and nothing is left on disk.
# ---------------------------------------------------------------------------
class TestLoadXsecStrategyCandidatePath(unittest.TestCase):
    def setUp(self):
        import tempfile
        import importlib
        import runner.backtest_xsec as bx
        self.bx = bx
        # Two temp roots standing in for strategies/ and strategies_candidates/.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.live_root = root / "strategies"
        self.cand_root = root / "strategies_candidates"
        self.live_root.mkdir()
        self.cand_root.mkdir()
        (self.live_root / "__init__.py").write_text("")
        (self.cand_root / "__init__.py").write_text("")
        # CRITICAL for suite-order independence: earlier tests import the REAL
        # `strategies` / `strategies_candidates` packages, which get cached in
        # sys.modules with their real __path__. importlib.import_module() then
        # resolves OUR throwaway submodules against that real path and misses
        # them. So evict the parent packages (saving them), put the temp root
        # FIRST on sys.path, and restore the real packages in cleanup. This
        # makes the test hermetic whether it runs alone or mid-suite.
        self._saved_mods = {}
        for key in list(sys.modules):
            if key == "strategies" or key.startswith("strategies.") \
               or key == "strategies_candidates" \
               or key.startswith("strategies_candidates."):
                self._saved_mods[key] = sys.modules.pop(key)
        sys.path.insert(0, str(root))
        self.addCleanup(self._restore_path_and_mods, str(root))
        # Point the module's roots at our temp trees.
        self._orig_live = bx.STRATEGIES_ROOT
        self._orig_cand = bx.CANDIDATES_ROOT
        bx.STRATEGIES_ROOT = self.live_root
        bx.CANDIDATES_ROOT = self.cand_root
        def _restore_roots():
            bx.STRATEGIES_ROOT = self._orig_live
            bx.CANDIDATES_ROOT = self._orig_cand
        self.addCleanup(_restore_roots)
        self._importlib = importlib

    def _restore_path_and_mods(self, root_str: str):
        if root_str in sys.path:
            sys.path.remove(root_str)
        # Drop any temp submodules we imported, then restore the real packages.
        for key in list(sys.modules):
            if key == "strategies" or key.startswith("strategies.") \
               or key == "strategies_candidates" \
               or key.startswith("strategies_candidates."):
                sys.modules.pop(key, None)
        sys.modules.update(self._saved_mods)

    def _write_strategy(self, root: Path, name: str, *, with_decide=True):
        d = root / name
        d.mkdir()
        (d / "__init__.py").write_text("")
        body = (
            "def decide_xsec(market_state, position_state, params):\n"
            "    return {}\n"
        ) if with_decide else (
            "def decide(market_state, position_state, params):\n"
            "    return None\n"
        )
        (d / "strategy.py").write_text(body)
        (d / "params.json").write_text('{"basket": ["AAA", "BBB"], "k": 1}')

    def test_live_path_unchanged(self):
        self._write_strategy(self.live_root, "xs_live")
        fn, params = self.bx.load_xsec_strategy("xs_live")
        self.assertTrue(callable(fn))
        self.assertEqual(params["basket"], ["AAA", "BBB"])
        self.assertEqual(fn({}, {}, {}), {})

    def test_candidate_path_loads_from_candidates_tree(self):
        # Same name in BOTH trees, different params, to prove which tree won.
        self._write_strategy(self.live_root, "xs_dup")
        d = self.cand_root / "xs_dup"
        d.mkdir()
        (d / "__init__.py").write_text("")
        (d / "strategy.py").write_text(
            "def decide_xsec(m, p, params):\n    return {'CAND': 1}\n")
        (d / "params.json").write_text('{"basket": ["ZZZ"], "k": 9}')
        fn, params = self.bx.load_xsec_strategy("xs_dup", candidate=True)
        self.assertEqual(params["basket"], ["ZZZ"])  # candidate tree, not live
        self.assertEqual(params["k"], 9)
        self.assertEqual(fn(None, None, None), {"CAND": 1})

    def test_candidate_missing_dir_message(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            self.bx.load_xsec_strategy("does_not_exist", candidate=True)
        self.assertIn("candidate dir", str(ctx.exception))
        self.assertIn("strategies_candidates", str(ctx.exception))

    def test_live_missing_dir_message_unchanged(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            self.bx.load_xsec_strategy("does_not_exist")
        self.assertIn("strategy dir", str(ctx.exception))

    def test_candidate_without_decide_xsec_raises(self):
        self._write_strategy(self.cand_root, "xs_nodecide", with_decide=False)
        with self.assertRaises(AttributeError) as ctx:
            self.bx.load_xsec_strategy("xs_nodecide", candidate=True)
        self.assertIn("decide_xsec", str(ctx.exception))
        self.assertIn("strategies_candidates", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
