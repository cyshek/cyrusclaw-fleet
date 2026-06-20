"""Walk-forward xsec harness tests (no network — synthetic windows).

Covers:
  1. Per-window correctness: per-window metrics on a synthetic
     2-window panel match a direct call to backtest_xsec.
  2. BH-basket calc: equal-weight basket BH-return scales to bench
     equity correctly across multiple symbols.
  3. Aggregate stats: median / pct_positive / per-regime medians compute
     correctly across mixed bull/chop/bear windows.
  4. Warmup-days handling: window slice extends by warmup_days; slow-
     trigger strategy can fire inside the labeled window when warmup
     is sufficient and cannot when warmup=0.
  5. Bar A bullet #1 amended scorer: (a) pass on positive, (b) pass on
     beats-BH + ≥25% in-position, (b) capped at 1.
  6. passes_fitness_gate_xsec delegates to single-symbol gate.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.backtest import CostModel  # noqa: E402
from runner import walk_forward_xsec as wfx  # noqa: E402
from runner.walk_forward_xsec import (  # noqa: E402
    XSecWalkForwardAggregate,
    XSecWindowResult,
    ZeroTradesError,
    _bh_basket_return,
    _score_bar_a_bullet1,
    passes_fitness_gate_xsec,
    walk_forward_xsec,
    BAR_A_B_ALT_CAP,
    BAR_A_B_MIN_BARS_IN_POSITION,
)
from runner.backtest_xsec import backtest_xsec, XSecBacktestResult  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(t_iso, c):
    return {"t": t_iso, "o": c, "h": c, "l": c, "c": c, "v": 1.0}


def _daily(start_date: datetime, closes: List[float]) -> List[dict]:
    return [_bar((start_date + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), c)
            for i, c in enumerate(closes)]


class _A:
    def __init__(self, action, symbol, notional_usd=0.0, qty=None, reason=""):
        self.action = action
        self.symbol = symbol
        self.notional_usd = notional_usd
        self.qty = qty
        self.reason = reason


def _patch_bars_cache(bars_by_window_and_sym):
    """Patch bars_cache.get_bars to return the appropriate slice for the
    requested (symbol, days, end_dt). The map keys by end_dt date string."""
    def fake_get_bars(symbol, timeframe, *, days=30, end_dt=None):
        if end_dt is None:
            return []
        end_key = end_dt.strftime("%Y-%m-%d")
        # Try this exact (end_key, symbol), then fallthrough.
        slot = bars_by_window_and_sym.get((end_key, symbol))
        if slot is None:
            return []
        # Trim to last `days` bars if longer (callers ask for window+warmup).
        if days and len(slot) > days:
            return slot[-days:]
        return slot
    return patch("runner.walk_forward_xsec.bars_cache.get_bars",
                 side_effect=fake_get_bars)


# Three synthetic regimes, two symbols each.
def _build_panel():
    """Two-symbol, three-regime panel keyed by (end_date_str, symbol)."""
    # Bull: both up, A faster
    bull_end = datetime(2024, 7, 1, tzinfo=timezone.utc)
    bull_start = bull_end - timedelta(days=120)
    bull_A = _daily(bull_start, [100 + i * 0.5 for i in range(120)])  # 100 -> 159.5
    bull_B = _daily(bull_start, [100 + i * 0.2 for i in range(120)])  # 100 -> 123.8

    # Chop: flat both
    chop_end = datetime(2023, 10, 1, tzinfo=timezone.utc)
    chop_start = chop_end - timedelta(days=120)
    chop_A = _daily(chop_start, [100 + (i % 5 - 2) * 0.5 for i in range(120)])
    chop_B = _daily(chop_start, [100 + (i % 7 - 3) * 0.3 for i in range(120)])

    # Bear: both down, A worse
    bear_end = datetime(2022, 7, 1, tzinfo=timezone.utc)
    bear_start = bear_end - timedelta(days=120)
    bear_A = _daily(bear_start, [100 - i * 0.4 for i in range(120)])
    bear_B = _daily(bear_start, [100 - i * 0.2 for i in range(120)])

    return {
        ("2024-07-01", "A"): bull_A,
        ("2024-07-01", "B"): bull_B,
        ("2023-10-01", "A"): chop_A,
        ("2023-10-01", "B"): chop_B,
        ("2022-07-01", "A"): bear_A,
        ("2022-07-01", "B"): bear_B,
        # SPY for regime; backtest_xsec fetches SPY internally. Return empty
        # so we exercise the no-regime path deterministically.
        ("2024-07-01", "SPY"): [],
        ("2023-10-01", "SPY"): [],
        ("2022-07-01", "SPY"): [],
    }


# A simple cross-sec momentum: at tick 60 buy top-1 by 5-bar return.
def _simple_top1_at_tick60(min_bars=6):
    def decide(ms, ps, params):
        # Rebalance only once we have enough history.
        ranks = []
        for sym, sv in ms["symbols"].items():
            b = sv["bars"]
            if len(b) < min_bars:
                continue
            ret = (b[-1]["c"] - b[-min_bars]["c"]) / b[-min_bars]["c"]
            ranks.append((ret, sym))
        if not ranks:
            return {}
        ranks.sort(reverse=True)
        top = ranks[0][1]
        if top in ps:
            return {}  # already holding the winner
        out = {sym: _A("close", sym) for sym in ps}
        out[top] = _A("buy", top, notional_usd=80.0, reason="top1")
        return out
    return decide


# ---------------------------------------------------------------------------
# 1. Per-window correctness
# ---------------------------------------------------------------------------

class TestPerWindowMatches(unittest.TestCase):

    def test_per_window_metrics_match_direct_backtest(self):
        panel = _build_panel()
        # Use the synthetic bull-end window only
        end_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
        windows = [("synthbull", end_dt, 120, "bull")]
        decide = _simple_top1_at_tick60()
        # Direct call to backtest_xsec on the exact bars
        bars_by_sym = {"A": panel[("2024-07-01", "A")],
                       "B": panel[("2024-07-01", "B")]}
        with _patch_bars_cache(panel):
            agg = walk_forward_xsec(
                "test_xsec",
                basket=["A", "B"],
                params={"timeframe": "1Day"},
                decide_xsec_fn=decide,
                windows=windows,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(agg.n_windows_with_data, 1)
        w = agg.windows[0]
        # Direct backtest_xsec
        direct = backtest_xsec(
            "test_xsec", bars_by_sym, {"timeframe": "1Day"},
            decide_xsec_fn=decide,
            default_cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertAlmostEqual(w.backtest.total_return_pct,
                               direct.total_return_pct, places=10)
        self.assertEqual(w.backtest.n_trades, direct.n_trades)
        # In-position % should be > 0 since strategy buys A and holds.
        self.assertGreater(w.bars_in_position_pct, 0.0)


# ---------------------------------------------------------------------------
# 2. BH-basket calc
# ---------------------------------------------------------------------------

class TestBHBasketReturn(unittest.TestCase):

    def setUp(self):
        wfx._BH_BASKET_CACHE.clear()

    def test_equal_weight_basket_scales_to_bench(self):
        # 2 symbols. A: +10% over window. B: -10%. Equal-weight avg = 0%.
        # bench scale: 0 * (100/1000) = 0.
        end_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
        start = end_dt - timedelta(days=30)
        bars_A = _daily(start, [100.0, 110.0])
        bars_B = _daily(start, [100.0, 90.0])
        panel = {("2024-07-01", "A"): bars_A,
                 ("2024-07-01", "B"): bars_B}
        with _patch_bars_cache(panel):
            ret = _bh_basket_return(
                ["A", "B"], end_dt, 30, "1Day",
                notional_usd=100.0, starting_cash=1000.0,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
        # Avg leg ret = 0.0; bench-scaled = 0.0.
        self.assertAlmostEqual(ret, 0.0, places=6)

    def test_basket_positive_scales_one_tenth(self):
        # Both +10% => avg leg ret = 0.10; scaled = 0.01.
        end_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
        start = end_dt - timedelta(days=30)
        bars_A = _daily(start, [100.0, 110.0])
        bars_B = _daily(start, [100.0, 110.0])
        panel = {("2024-07-01", "A"): bars_A,
                 ("2024-07-01", "B"): bars_B}
        with _patch_bars_cache(panel):
            ret = _bh_basket_return(
                ["A", "B"], end_dt, 30, "1Day",
                notional_usd=100.0, starting_cash=1000.0,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertAlmostEqual(ret, 0.01, places=6)


# ---------------------------------------------------------------------------
# 3. Aggregate stats / per-regime medians
# ---------------------------------------------------------------------------

class TestAggregateStats(unittest.TestCase):

    def test_per_regime_median_correct(self):
        panel = _build_panel()
        windows = [
            ("bull-1", datetime(2024, 7, 1, tzinfo=timezone.utc), 120, "bull"),
            ("chop-1", datetime(2023, 10, 1, tzinfo=timezone.utc), 120, "chop"),
            ("bear-1", datetime(2022, 7, 1, tzinfo=timezone.utc), 120, "bear"),
        ]
        decide = _simple_top1_at_tick60()
        with _patch_bars_cache(panel):
            agg = walk_forward_xsec(
                "test_xsec", basket=["A", "B"],
                params={"timeframe": "1Day"},
                decide_xsec_fn=decide,
                windows=windows,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(agg.n_windows_with_data, 3)
        # Each regime had exactly 1 window, so median = that window's value.
        self.assertIsNotNone(agg.median_return_bull)
        self.assertIsNotNone(agg.median_return_chop)
        self.assertIsNotNone(agg.median_return_bear)
        # Bull window: strategy picks A (faster up) => positive.
        self.assertGreater(agg.median_return_bull, 0.0)
        # Bear window: strategy buys the "best" (A, which is worst-falling).
        # Actually momentum at tick60 will rank both negatively; top-1 picks
        # the LESS-bad (B). It still loses => bear median <= 0.
        self.assertLessEqual(agg.median_return_bear, 0.05)


# ---------------------------------------------------------------------------
# 4. Warmup-days handling
# ---------------------------------------------------------------------------

class TestWarmupDays(unittest.TestCase):

    def test_warmup_extends_fetch(self):
        """A strategy needing >120 bars of history can't fire with
        days=120 / warmup=0, but CAN with days=120 / warmup_days=200."""
        # Long bull series of 400 bars. The named window asks for 120 days.
        # Strategy fires only when bars >= 200.
        end_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
        start = end_dt - timedelta(days=400)
        bars_A = _daily(start, [100 + i * 0.1 for i in range(400)])
        bars_B = _daily(start, [100 - i * 0.1 for i in range(400)])
        panel = {
            ("2024-07-01", "A"): bars_A,
            ("2024-07-01", "B"): bars_B,
        }

        def decide_slow(ms, ps, params):
            for sym, sv in ms["symbols"].items():
                if len(sv["bars"]) < 200:
                    return {}
            # Once history threshold cleared, pick top-1 by simple last-50 ret.
            ranks = []
            for sym, sv in ms["symbols"].items():
                b = sv["bars"]
                ret = (b[-1]["c"] - b[-50]["c"]) / b[-50]["c"]
                ranks.append((ret, sym))
            ranks.sort(reverse=True)
            top = ranks[0][1]
            if top in ps:
                return {}
            return {top: _A("buy", top, notional_usd=80.0)}

        windows = [("synth", end_dt, 120, "bull")]
        with _patch_bars_cache(panel):
            # warmup=0 => trim to 120 bars, never fires. This is the
            # zero-trade case; opt into it explicitly (the guard would
            # otherwise raise ZeroTradesError, which is the point of the
            # guard — see test_zero_trades_guard below).
            agg0 = walk_forward_xsec(
                "test_xsec", basket=["A", "B"],
                params={"timeframe": "1Day"},
                decide_xsec_fn=decide_slow, windows=windows, warmup_days=0,
                allow_zero_trades=True,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
            # warmup=300 => 420 bars fetched (request) — but our slot only has
            # 400. Strategy can fire.
            agg300 = walk_forward_xsec(
                "test_xsec", basket=["A", "B"],
                params={"timeframe": "1Day"},
                decide_xsec_fn=decide_slow, windows=windows, warmup_days=300,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
        self.assertEqual(agg0.windows[0].backtest.n_trades, 0)
        self.assertGreaterEqual(agg300.windows[0].backtest.n_trades, 1)

    def test_zero_trades_guard_raises_by_default(self):
        """Finding 3a (2026-05-31): a strategy that takes 0 trades across
        EVERY data window must raise ZeroTradesError by default — that is
        the warmup-starvation reproducibility trap that produced the
        xsec_momentum_xa promotion-record correction. The guard must NOT
        fire when allow_zero_trades=True, and must NOT fire when the
        strategy trades in at least one window."""
        end_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
        start = end_dt - timedelta(days=400)
        bars_A = _daily(start, [100 + i * 0.1 for i in range(400)])
        bars_B = _daily(start, [100 - i * 0.1 for i in range(400)])
        panel = {
            ("2024-07-01", "A"): bars_A,
            ("2024-07-01", "B"): bars_B,
        }

        def decide_never(ms, ps, params):
            # Needs 200 bars; warmup=0 trims to 120 => never fires anywhere.
            for sym, sv in ms["symbols"].items():
                if len(sv["bars"]) < 200:
                    return {}
            return {}

        windows = [("synth", end_dt, 120, "bull")]
        with _patch_bars_cache(panel):
            # Default: must raise.
            with self.assertRaises(ZeroTradesError):
                walk_forward_xsec(
                    "test_xsec_zero", basket=["A", "B"],
                    params={"timeframe": "1Day"},
                    decide_xsec_fn=decide_never, windows=windows,
                    warmup_days=0,
                    cost_model=CostModel(spread_bps=0, fee_bps=0))
            # Opt-out: must NOT raise, returns a 0-trade aggregate.
            agg = walk_forward_xsec(
                "test_xsec_zero", basket=["A", "B"],
                params={"timeframe": "1Day"},
                decide_xsec_fn=decide_never, windows=windows,
                warmup_days=0, allow_zero_trades=True,
                cost_model=CostModel(spread_bps=0, fee_bps=0))
            self.assertEqual(agg.total_trades, 0)


# ---------------------------------------------------------------------------
# 5. Bar A bullet #1 amended scorer
# ---------------------------------------------------------------------------

class TestBarABullet1Scorer(unittest.TestCase):

    def _mk_window(self, label, regime, ret_pct, bh_pct, in_pos_pct):
        bt = XSecBacktestResult(strategy="x", symbols=["A"], timeframe="1Day")
        bt.total_return_pct = ret_pct / 100.0
        return XSecWindowResult(
            label=label, regime=regime, end_date="2024-01-01", days=60,
            backtest=bt, bh_basket_return_pct=bh_pct / 100.0,
            beats_bh_basket=(ret_pct > bh_pct),
            bars_in_position_pct=in_pos_pct,
        )

    def test_all_positive_passes(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=2)
        agg.windows = [self._mk_window("w1", "bull", 1.0, 0.5, 80),
                       self._mk_window("w2", "chop", 0.1, -0.2, 60)]
        agg.n_windows_with_data = 2
        _score_bar_a_bullet1(agg)
        self.assertTrue(agg.bar_a_bullet1_pass)
        self.assertEqual(agg.bar_a_b_used_count, 0)

    def test_one_bear_via_b_passes(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=2)
        agg.windows = [
            self._mk_window("w1", "bull", 1.0, 0.5, 80),
            # bear: ret -0.3% but BH-basket -1.5% => beats BH; in-pos 50%.
            self._mk_window("w2", "bear", -0.3, -1.5, 50),
        ]
        agg.n_windows_with_data = 2
        _score_bar_a_bullet1(agg)
        self.assertTrue(agg.bar_a_bullet1_pass)
        self.assertEqual(agg.bar_a_b_used_count, 1)
        # The b-window should be flagged.
        self.assertTrue(agg.windows[1].bar_a_via_b)
        self.assertFalse(agg.windows[0].bar_a_via_b)

    def test_two_b_alt_pass_blocked_by_cap(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=2)
        agg.windows = [
            # Both bears: ret negative but beats BH-basket; both want (b).
            self._mk_window("w1", "bear", -0.3, -1.5, 50),
            self._mk_window("w2", "bear", -0.4, -2.0, 50),
        ]
        agg.n_windows_with_data = 2
        _score_bar_a_bullet1(agg)
        self.assertFalse(agg.bar_a_bullet1_pass)
        self.assertEqual(agg.bar_a_b_used_count, BAR_A_B_ALT_CAP)  # =1
        self.assertTrue(agg.windows[0].bar_a_via_b)
        self.assertFalse(agg.windows[1].bar_a_via_b)  # cap blocked

    def test_b_requires_min_in_position(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=1)
        # Strategy was flat for 90% of window => (b) NOT eligible.
        agg.windows = [self._mk_window("w1", "bear", -0.3, -1.5,
                                        BAR_A_B_MIN_BARS_IN_POSITION - 5)]
        agg.n_windows_with_data = 1
        _score_bar_a_bullet1(agg)
        self.assertFalse(agg.bar_a_bullet1_pass)
        self.assertEqual(agg.bar_a_b_used_count, 0)


# ---------------------------------------------------------------------------
# 6. passes_fitness_gate_xsec delegates to single-symbol gate
# ---------------------------------------------------------------------------

class TestFitnessGateDelegation(unittest.TestCase):

    def test_passes_with_strong_metrics(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=4)
        agg.n_windows_with_data = 4
        agg.median_return_pct = 2.0
        agg.pct_positive = 0.75
        agg.pct_beat_bh_basket = 0.75
        agg.median_sharpe = 1.5
        passed, reason = passes_fitness_gate_xsec(agg)
        self.assertTrue(passed, reason)

    def test_fails_with_weak_metrics(self):
        agg = XSecWalkForwardAggregate(strategy="x", basket=["A"], n_windows=4)
        agg.n_windows_with_data = 4
        agg.median_return_pct = -0.5  # negative median
        agg.pct_positive = 0.25
        agg.pct_beat_bh_basket = 0.25
        agg.median_sharpe = 0.1
        passed, reason = passes_fitness_gate_xsec(agg)
        self.assertFalse(passed)
        self.assertIn("median", reason)


if __name__ == "__main__":
    unittest.main()
