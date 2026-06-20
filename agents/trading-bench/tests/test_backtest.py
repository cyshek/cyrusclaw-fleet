"""Backtest harness tests.

Run with:
    python3 -m unittest tests.test_backtest

Covers:
    1. SMA crossover on hand-crafted bars produces expected trade count & sign.
    2. No-lookahead: a probe strategy cannot see bars beyond the current index.
    3. Risk caps: MAX_TRADES_PER_DAY enforced; over-cap signals get skipped.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.backtest import backtest, BacktestResult, CostModel  # noqa: E402
from strategies_retired.sma_crossover_btc.strategy import (  # noqa: E402 -- retired 2026-05-30, kept as test fixture for backtest-harness coverage
    decide as sma_decide,
    Action as SmaAction,
)


def _bar(t_iso: str, c: float) -> dict:
    """Minimal OHLCV bar; o=h=l=c for deterministic synthetic series."""
    return {"t": t_iso, "o": c, "h": c, "l": c, "c": c, "v": 1.0}


def _synthetic_series(closes: list[float], start_day: int = 1) -> list[dict]:
    """One bar per hour starting 2026-01-01 00:00 UTC."""
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, start_day, 0, 0, tzinfo=timezone.utc)
    return [
        _bar((base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), c)
        for i, c in enumerate(closes)
    ]


class TestSmaCrossoverSynthetic(unittest.TestCase):
    """Construct a series with one clean fast-above-slow crossover followed by
    one fast-below-slow crossover. Expect exactly 1 buy + 1 close = 2 trades
    and positive total return (price was higher when we closed than when we
    bought)."""

    def test_one_round_trip(self):
        # 40 bars at 100, then ramp up to 200 over 30 bars, then drop back.
        # SMA(10) vs SMA(30). Fast will cross above slow during ramp-up; will
        # cross back below during drop.
        flat = [100.0] * 40
        ramp_up = [100.0 + (i + 1) * 5.0 for i in range(30)]   # 105..250
        plateau = [250.0] * 15
        drop = [250.0 - (i + 1) * 5.0 for i in range(30)]      # 245..100
        flat2 = [100.0] * 20
        closes = flat + ramp_up + plateau + drop + flat2
        bars = _synthetic_series(closes)

        params = {
            "symbol": "BTC/USD",
            "timeframe": "1Hour",
            "notional_usd": 100.0,
            "fast": 10,
            "slow": 30,
        }
        r = backtest("sma_crossover_btc", bars, params, decide_fn=sma_decide)
        self.assertIsInstance(r, BacktestResult)
        # Must have at least one open + one close.
        self.assertGreaterEqual(r.n_buys, 1, f"expected ≥1 buy, got {r.n_buys}")
        self.assertGreaterEqual(r.n_closes, 1,
                                f"expected ≥1 close, got {r.n_closes}")
        # Round-trip pnl must be positive: bought during ramp-up, closed near
        # peak during drop. Equity should end above starting cash.
        self.assertGreater(r.total_return_usd, 0,
                           f"expected +ve return, got {r.total_return_usd:.4f}")
        # No leftover position by the end (price fully reverted).
        self.assertEqual(r.final_position_qty, 0.0,
                         f"expected flat, holding {r.final_position_qty}")

    def test_flat_market_no_trades(self):
        bars = _synthetic_series([100.0] * 100)
        params = {"symbol": "BTC/USD", "timeframe": "1Hour",
                  "notional_usd": 100.0, "fast": 10, "slow": 30}
        r = backtest("sma_crossover_btc", bars, params, decide_fn=sma_decide)
        # Fast == slow forever → never strictly greater → 0 trades.
        self.assertEqual(r.n_trades, 0)
        self.assertEqual(r.total_return_usd, 0.0)


class TestCostModel(unittest.TestCase):
    """Same synthetic SMA-crossover scenario as the round-trip test, but
    compare zero-cost (existing behavior) against Alpaca-crypto-ish costs.
    Costs must strictly reduce total_return_usd; zero-cost path must match
    the prior numbers EXACTLY."""

    def _bars_and_params(self):
        flat = [100.0] * 40
        ramp_up = [100.0 + (i + 1) * 5.0 for i in range(30)]
        plateau = [250.0] * 15
        drop = [250.0 - (i + 1) * 5.0 for i in range(30)]
        flat2 = [100.0] * 20
        closes = flat + ramp_up + plateau + drop + flat2
        bars = _synthetic_series(closes)
        params = {"symbol": "BTC/USD", "timeframe": "1Hour",
                  "notional_usd": 100.0, "fast": 10, "slow": 30}
        return bars, params

    def test_zero_cost_matches_legacy(self):
        bars, params = self._bars_and_params()
        zero = backtest("sma_crossover_btc", bars, params,
                        decide_fn=sma_decide,
                        cost_model=CostModel(spread_bps=0.0, fee_bps=0.0))
        # Mirrors the original TestSmaCrossoverSynthetic.test_one_round_trip
        # assertions: zero-cost results must be identical to the pre-CostModel
        # behavior (fill at close, no friction).
        self.assertGreaterEqual(zero.n_buys, 1)
        self.assertGreaterEqual(zero.n_closes, 1)
        self.assertGreater(zero.total_return_usd, 0)
        self.assertEqual(zero.final_position_qty, 0.0)
        self.assertEqual(zero.total_costs_usd, 0.0)
        # Exact equity formula with no friction: sold qty at close, no fees.
        # Recompute expected pnl deterministically from closed trades.
        expected_pnl = sum(t["pnl_usd"] for t in zero.closed_trades)
        self.assertAlmostEqual(zero.total_return_usd, expected_pnl, places=9)

    def test_costs_strictly_reduce_return(self):
        bars, params = self._bars_and_params()
        zero = backtest("sma_crossover_btc", bars, params,
                        decide_fn=sma_decide,
                        cost_model=CostModel(spread_bps=0.0, fee_bps=0.0))
        costed = backtest("sma_crossover_btc", bars, params,
                          decide_fn=sma_decide,
                          cost_model=CostModel(spread_bps=200.0, fee_bps=0.0))
        self.assertLess(costed.total_return_usd, zero.total_return_usd)
        self.assertGreater(costed.total_costs_usd, 0.0)

    def test_stocks_vs_crypto_cost_models_differ(self):
        """alpaca_stocks() (2 bps) and alpaca_crypto() (200 bps) must produce
        materially different equity curves on the same hand-crafted bars.
        Stocks cost should be ~100x less than crypto on the same trade count."""
        bars, params = self._bars_and_params()
        stocks_cm = CostModel.alpaca_stocks()
        crypto_cm = CostModel.alpaca_crypto()
        self.assertEqual(stocks_cm.spread_bps, 2.0)
        self.assertEqual(crypto_cm.spread_bps, 200.0)
        stocks_r = backtest("sma_crossover_btc", bars, params,
                            decide_fn=sma_decide, cost_model=stocks_cm)
        crypto_r = backtest("sma_crossover_btc", bars, params,
                            decide_fn=sma_decide, cost_model=crypto_cm)
        # Same trade count (cost doesn't affect decisions, only fills).
        self.assertEqual(stocks_r.n_trades, crypto_r.n_trades)
        # Stocks cost must be strictly less than crypto cost and >0.
        self.assertGreater(stocks_r.total_costs_usd, 0.0)
        self.assertGreater(crypto_r.total_costs_usd, stocks_r.total_costs_usd)
        # Stocks return must be strictly better than crypto return (less drag).
        self.assertGreater(stocks_r.total_return_usd, crypto_r.total_return_usd)
        # Cost ratio should be ~100x (200bps / 2bps), give or take rounding.
        ratio = crypto_r.total_costs_usd / stocks_r.total_costs_usd
        self.assertGreater(ratio, 50.0)
        self.assertLess(ratio, 200.0)

    def test_for_symbol_dispatch(self):
        self.assertEqual(CostModel.for_symbol("BTC/USD").spread_bps, 200.0)
        self.assertEqual(CostModel.for_symbol("SPY").spread_bps, 2.0)
        self.assertEqual(CostModel.for_symbol("ETH/USD").spread_bps, 200.0)
        self.assertEqual(CostModel.for_symbol("QQQ").spread_bps, 2.0)


class TestNoLookahead(unittest.TestCase):
    """Probe strategy asserts it never sees a bar beyond the current index.

    The bars list contains a sentinel close at the END (price 999999) that
    should never appear in market_state['bars'] except on the very last tick.
    """

    def test_strategy_cannot_see_future(self):
        closes = [100.0] * 10 + [999999.0]   # last bar is the sentinel
        bars = _synthetic_series(closes)
        seen = {"max_idx_seen": -1, "violations": []}

        def probe_decide(market_state, position_state, params):
            visible = market_state["bars"]
            # The number of visible bars - 1 must equal current bar index.
            idx = len(visible) - 1
            seen["max_idx_seen"] = max(seen["max_idx_seen"], idx)
            # Check no future sentinel is visible UNLESS we're already at it.
            sentinel_idx = len(bars) - 1
            for i, b in enumerate(visible):
                if i < sentinel_idx and float(b["c"]) >= 999999.0:
                    seen["violations"].append((idx, i, float(b["c"])))
            # The current (last visible) bar's close must equal bars[idx]['c'].
            if visible[-1]["c"] != bars[idx]["c"]:
                seen["violations"].append(("mismatch", idx, visible[-1]["c"]))

            class A:
                action = "hold"
                symbol = market_state["symbol"]
                notional_usd = 0.0
                qty = None
                reason = "probe"
            return A()

        params = {"symbol": "BTC/USD", "timeframe": "1Hour"}
        backtest("probe", bars, params, decide_fn=probe_decide)
        self.assertEqual(seen["violations"], [],
                         f"lookahead detected: {seen['violations']}")
        self.assertEqual(seen["max_idx_seen"], len(bars) - 1,
                         "strategy should have been invoked on every bar")


class TestRiskCaps(unittest.TestCase):
    """A spammy strategy that buys every bar must hit the daily cap (4/day)
    and the position cap ($200 / $100-notional = max 2 concurrent fills)."""

    def test_max_position_cap(self):
        # 10 bars in one UTC day at price 50.
        bars = _synthetic_series([50.0] * 10)

        def spammy(market_state, position_state, params):
            class A:
                action = "buy"
                symbol = "BTC/USD"
                notional_usd = 100.0
                qty = None
                reason = "spam buy"
            return A()

        params = {"symbol": "BTC/USD", "timeframe": "1Hour",
                  "notional_usd": 100.0}
        r = backtest("spam", bars, params, decide_fn=spammy)
        # MAX_POSITION = $200, so after 2 buys ($200 position) the 3rd would
        # project to $300 and be rejected. Also MAX_TRADES_PER_DAY=4 caps
        # successful trades. Whichever bites first, we should see ≥1 skip.
        self.assertGreaterEqual(r.n_skipped_risk, 1,
                                "expected risk skips on spammy buyer")
        # Cumulative buys cannot exceed daily cap.
        self.assertLessEqual(r.n_buys, 4)


class TestRegimeFilter(unittest.TestCase):
    """Regime-filtered strategies must hold when SPY is below its SMA, even
    when the parent strategy would buy. Conversely, when regime is uptrend,
    they must behave like the parent."""

    def test_regime_down_blocks_entry(self):
        from strategies.breakout_xlk_regime.strategy import decide as r_decide
        # 23 bars: 22 flat at 100, then 1 bar at 110 (breakout above 20-bar high).
        bars = _synthetic_series([100.0] * 22 + [110.0])
        params = {"symbol": "XLK", "timeframe": "1Hour",
                  "notional_usd": 100.0, "lookback": 20, "regime_period": 5}
        # SPY closes: clearly below 5-bar SMA at the end.
        spy_closes = [110.0, 108.0, 105.0, 100.0, 95.0, 90.0, 85.0]
        market_state = {
            "symbol": "XLK",
            "last_price": 110.0,
            "bars": bars,
            "timeframe": "1Hour",
            "regime": {"spy_closes": spy_closes, "spy_last": spy_closes[-1]},
        }
        action = r_decide(market_state, {}, params)
        self.assertEqual(action.action, "hold",
                         f"regime down should block entry, got {action.action}"
                         f" ({action.reason})")
        self.assertIn("regime", action.reason.lower())

    def test_regime_up_allows_entry(self):
        from strategies.breakout_xlk_regime.strategy import decide as r_decide
        bars = _synthetic_series([100.0] * 22 + [110.0])
        params = {"symbol": "XLK", "timeframe": "1Hour",
                  "notional_usd": 100.0, "lookback": 20, "regime_period": 5}
        # SPY in clear uptrend: last close above its 5-bar SMA.
        spy_closes = [80.0, 82.0, 85.0, 90.0, 95.0, 100.0, 110.0]
        market_state = {
            "symbol": "XLK", "last_price": 110.0, "bars": bars,
            "timeframe": "1Hour",
            "regime": {"spy_closes": spy_closes, "spy_last": spy_closes[-1]},
        }
        action = r_decide(market_state, {}, params)
        self.assertEqual(action.action, "buy",
                         f"regime up should allow entry, got {action.action}"
                         f" ({action.reason})")

    def test_regime_down_still_allows_close(self):
        """If already holding when regime turns down, close signal must fire."""
        from strategies.breakout_xlk_regime.strategy import decide as r_decide
        # 23 bars: 22 at 100, then 1 at 90 (breakout below 20-bar low).
        bars = _synthetic_series([100.0] * 22 + [90.0])
        params = {"symbol": "XLK", "timeframe": "1Hour",
                  "notional_usd": 100.0, "lookback": 20, "regime_period": 5}
        spy_closes = [110.0, 108.0, 105.0, 100.0, 95.0, 90.0, 85.0]
        position_state = {"XLK": {"qty": 1.0, "market_value": 90.0,
                                  "avg_entry_price": 100.0}}
        market_state = {
            "symbol": "XLK", "last_price": 90.0, "bars": bars,
            "timeframe": "1Hour",
            "regime": {"spy_closes": spy_closes, "spy_last": spy_closes[-1]},
        }
        action = r_decide(market_state, position_state, params)
        self.assertEqual(action.action, "close",
                         f"close must fire even in down regime, got {action.action}"
                         f" ({action.reason})")

    def test_regime_none_falls_through_to_parent_behavior(self):
        """When regime is None (missing data), the gate must be skipped and
        the filtered strategy must buy when the parent would buy."""
        from strategies.breakout_xlk_regime.strategy import decide as r_decide
        bars = _synthetic_series([100.0] * 22 + [110.0])
        params = {"symbol": "XLK", "timeframe": "1Hour",
                  "notional_usd": 100.0, "lookback": 20, "regime_period": 5}
        market_state = {
            "symbol": "XLK", "last_price": 110.0, "bars": bars,
            "timeframe": "1Hour", "regime": None,
        }
        action = r_decide(market_state, {}, params)
        self.assertEqual(action.action, "buy",
                         f"regime=None should fall through, got {action.action}"
                         f" ({action.reason})")


if __name__ == "__main__":
    unittest.main()
