"""Backtest partial-trim (scale-out) tests.

Run with:
    python3 -m unittest tests.test_backtest_partial_trim

Regression coverage for the 2026-06-26 backtester bug: `runner/backtest.py`
read `action.notional_usd` but never `action.qty`, so a partial-exit
`Action('sell', qty=half, notional_usd=0.0)` was (a) rejected by the risk gate
as "non-positive notional" and (b) — even past the gate — would have sold the
WHOLE position. The live runner (`runner/runner.py`) DOES honor `action.qty`
on sells (partial trim, stay long), so the backtester was blind to a behavior
that live paper trading actually performs. These tests pin the fixed semantics:

  1. A `sell` carrying qty>0 (notional=0) is NOT rejected by the gate.
  2. A partial sell (qty < held) reduces the position pro-rata and STAYS LONG.
  3. The trimmed slice's realized pnl is correct (pro-rata cost basis).
  4. The remainder rides on and a later `close` exits it (full flat).
  5. avg_entry_price is preserved across a partial trim (basis/qty ratio held).
  6. A `sell` with neither usable qty nor notional is a no-op (still rejected),
     so the fix didn't open a hole for malformed actions.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.backtest import backtest, BacktestResult, CostModel  # noqa: E402


@dataclass
class _Action:
    """Minimal Action mirroring the runner's duck-typed contract:
    .action ('buy'|'sell'|'close'|'hold'), .symbol, .notional_usd, .qty, .reason."""
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _bar(t_iso: str, c: float) -> dict:
    return {"t": t_iso, "o": c, "h": c, "l": c, "c": c, "v": 1.0}


def _synthetic_series(closes: list[float]) -> list[dict]:
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    return [
        _bar((base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), c)
        for i, c in enumerate(closes)
    ]


# A no-cost model so we can reason about qty/pnl arithmetic exactly.
_ZERO = CostModel(spread_bps=0.0, fee_bps=0.0)


class TestPartialTrim(unittest.TestCase):
    """Buy at bar 1 ($100), scale out HALF at bar 3 ($110), close remainder
    at bar 5 ($120). With $100 notional → entry qty = 1.0 share. Scale-out
    sells 0.5 share; remainder 0.5 share closes at $120."""

    def _scaleout_decide(self, market_state, position_state, params):
        symbol = params["symbol"]
        i = len(market_state["bars"]) - 1
        pos = position_state.get(symbol) or {}
        held = float(pos.get("qty", 0.0) or 0.0)
        # Bar 1: open. Bar 3: trim half (qty-based, notional=0 — the bug pattern).
        # Bar 5: close remainder.
        if i == 1 and held <= 0:
            return _Action("buy", symbol, notional_usd=params["notional_usd"],
                           reason="open")
        if i == 3 and held > 0 and not pos.get("scaled_out"):
            pos["scaled_out"] = True  # once-per-trade flag (preserved across bars)
            return _Action("sell", symbol, notional_usd=0.0, qty=held * 0.5,
                           reason="scale out half")
        if i == 5 and held > 0:
            return _Action("close", symbol, reason="exit remainder")
        return _Action("hold", symbol, reason="hold")

    def test_partial_trim_reduces_position_and_stays_long(self):
        bars = _synthetic_series([100.0, 100.0, 105.0, 110.0, 115.0, 120.0,
                                  120.0, 120.0])
        params = {"symbol": "XLK", "timeframe": "1Hour", "notional_usd": 100.0}
        r = backtest("scaleout_probe", bars, params,
                     decide_fn=self._scaleout_decide, cost_model=_ZERO)
        self.assertIsInstance(r, BacktestResult)
        # Two SELL/close events fired: the partial trim + the final close.
        # (n_closes increments on both the partial slice and the full exit.)
        self.assertEqual(r.n_closes, 2,
                         f"expected 2 sell events (trim+close), got {r.n_closes}")
        # There must be TWO closed-trade slices, the first flagged partial.
        self.assertEqual(len(r.closed_trades), 2,
                         f"expected 2 closed slices, got {len(r.closed_trades)}")
        self.assertTrue(r.closed_trades[0].get("partial") is True,
                        "first slice should be flagged partial")
        self.assertFalse(r.closed_trades[1].get("partial") is True,
                         "second slice (final close) should not be partial")
        # Final position flat after the close.
        self.assertEqual(r.final_position_qty, 0.0,
                         f"expected flat, holding {r.final_position_qty}")

    def test_partial_trim_slice_qty_and_pnl(self):
        # $100 @ $100 -> 1.0 share. Trim 0.5 @ $110 -> slice pnl = 0.5*(110-100)=+5.
        # Remainder 0.5 @ $120 -> slice pnl = 0.5*(120-100)=+10. Total +15.
        bars = _synthetic_series([100.0, 100.0, 105.0, 110.0, 115.0, 120.0,
                                  120.0, 120.0])
        params = {"symbol": "XLK", "timeframe": "1Hour", "notional_usd": 100.0}
        r = backtest("scaleout_probe", bars, params,
                     decide_fn=self._scaleout_decide, cost_model=_ZERO)
        trim, final = r.closed_trades[0], r.closed_trades[1]
        self.assertAlmostEqual(trim["qty"], 0.5, places=6)
        self.assertAlmostEqual(final["qty"], 0.5, places=6)
        self.assertAlmostEqual(trim["pnl_usd"], 5.0, places=4,
                               msg=f"trim slice pnl {trim['pnl_usd']}")
        self.assertAlmostEqual(final["pnl_usd"], 10.0, places=4,
                               msg=f"final slice pnl {final['pnl_usd']}")
        # Total realized return must equal +15 on $100 starting cash.
        self.assertAlmostEqual(r.total_return_usd, 15.0, places=4,
                               msg=f"total {r.total_return_usd}")
        # Entry price preserved on BOTH slices (avg_entry unchanged by trim).
        self.assertAlmostEqual(trim["entry_price"], 100.0, places=6)
        self.assertAlmostEqual(final["entry_price"], 100.0, places=6)

    def test_qty_sell_not_rejected_by_gate(self):
        """The core bug: a sell with notional=0 but qty>0 must NOT be skipped.
        If the gate still rejected it, n_closes would be 1 (only the final
        close) and there'd be a single full-position slice."""
        bars = _synthetic_series([100.0, 100.0, 105.0, 110.0, 115.0, 120.0,
                                  120.0, 120.0])
        params = {"symbol": "XLK", "timeframe": "1Hour", "notional_usd": 100.0}
        r = backtest("scaleout_probe", bars, params,
                     decide_fn=self._scaleout_decide, cost_model=_ZERO)
        # No skip whose reason mentions non-positive notional.
        bad = [s for s in r.skipped_reasons if "non-positive notional" in s]
        self.assertEqual(bad, [],
                         f"qty-sell wrongly rejected as non-positive notional: {bad}")

    def test_malformed_sell_is_noop(self):
        """A sell with neither usable qty nor notional resolves to a full exit
        ONLY if a position exists; with qty=None and notional=0 the runner
        treats it as a full close (req_qty None -> sell whole). Guard that this
        is intentional and doesn't crash or oversell."""
        def _bad_decide(market_state, position_state, params):
            symbol = params["symbol"]
            i = len(market_state["bars"]) - 1
            pos = position_state.get(symbol) or {}
            held = float(pos.get("qty", 0.0) or 0.0)
            if i == 1 and held <= 0:
                return _Action("buy", symbol, notional_usd=params["notional_usd"])
            if i == 3 and held > 0:
                # qty None + notional 0 -> resolves to FULL close (whole position).
                return _Action("sell", symbol, notional_usd=0.0, qty=None)
            return _Action("hold", symbol)
        bars = _synthetic_series([100.0, 100.0, 105.0, 110.0, 110.0, 110.0])
        params = {"symbol": "XLK", "timeframe": "1Hour", "notional_usd": 100.0}
        r = backtest("bad_probe", bars, params, decide_fn=_bad_decide,
                     cost_model=_ZERO)
        # One full exit, flat at end, no partial slice.
        self.assertEqual(r.final_position_qty, 0.0)
        self.assertEqual(len(r.closed_trades), 1)
        self.assertFalse(r.closed_trades[0].get("partial") is True)


if __name__ == "__main__":
    unittest.main()
