"""Pins the FINDING 2 fix (2026-05-31 harness integrity audit):

Daily-bar Sharpe must annualize with sqrt(252) for EQUITIES and sqrt(365) for
CRYPTO. Prior to the fix, `1Day` used 365 unconditionally, inflating every
equity daily Sharpe by sqrt(365/252) = 1.204x (~20%).

These tests pin the `bars_per_year()` resolver and the end-to-end annualization
factor used in both the single-symbol and xsec backtest harnesses.
"""
from __future__ import annotations

import math
import unittest

from runner.backtest import bars_per_year, EQUITY_TRADING_DAYS_PER_YEAR


class TestBarsPerYearResolver(unittest.TestCase):
    def test_daily_equity_is_252(self):
        self.assertEqual(bars_per_year("1Day", is_crypto=False), 252.0)

    def test_daily_crypto_is_365(self):
        self.assertEqual(bars_per_year("1Day", is_crypto=True), 365.0)

    def test_intraday_is_clock_time_for_both_classes(self):
        # An hour is an hour regardless of market — intraday is class-independent.
        self.assertEqual(
            bars_per_year("1Hour", is_crypto=False),
            bars_per_year("1Hour", is_crypto=True),
        )
        self.assertEqual(bars_per_year("1Hour", is_crypto=False), 24 * 365)

    def test_unknown_timeframe_falls_back(self):
        self.assertEqual(bars_per_year("7Day", is_crypto=False), 24 * 365)

    def test_equity_constant_is_252(self):
        self.assertEqual(EQUITY_TRADING_DAYS_PER_YEAR, 252)

    def test_equity_daily_factor_is_not_365(self):
        # The exact regression the audit caught: 1Day equity must NOT be 365.
        self.assertNotEqual(bars_per_year("1Day", is_crypto=False), 365.0)

    def test_inflation_ratio_matches_audit(self):
        # Audit-reported inflation: sqrt(365/252) = 1.204x. Confirm the resolver
        # produces exactly that ratio between the old (crypto/365) and new
        # (equity/252) daily factors.
        crypto = bars_per_year("1Day", is_crypto=True)
        equity = bars_per_year("1Day", is_crypto=False)
        ratio = math.sqrt(crypto) / math.sqrt(equity)
        self.assertAlmostEqual(ratio, 1.204, places=3)


if __name__ == "__main__":
    unittest.main()
