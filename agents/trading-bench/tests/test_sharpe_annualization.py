"""Pins the Sharpe annualization resolver `bars_per_year()`.

FINDING 2 (2026-05-31 harness integrity audit):
Daily-bar Sharpe must annualize with sqrt(252) for EQUITIES and sqrt(365) for
CRYPTO. Prior to the fix, `1Day` used 365 unconditionally, inflating every
equity daily Sharpe by sqrt(365/252) = 1.204x (~20%).

INTRADAY FIX (2026-06-25 intraday-readiness audit):
The ORIGINAL claim "an hour is an hour, intraday is class-independent" was
WRONG for equities. A US equity intraday bar only exists during the ~8.5h
session the data feed delivers (pre-market + RTH, ~510 min, empirically
12:00-20:30 UTC from Alpaca IEX) on ~252 days/yr -- NOT 24h x 365d. The old
class-blind resolver overstated equity intraday Sharpe by ~2.0x (1Hour: 8760
vs 2142 bars/yr). Equity intraday is now (510/tf_min)*252; crypto intraday
stays (1440/tf_min)*365 (== the legacy crypto table). See
reports/INTRADAY_READINESS_AUDIT_20260625T155500Z.md.

These tests pin the `bars_per_year()` resolver and the end-to-end annualization
factor used in both the single-symbol and xsec backtest harnesses.
"""
from __future__ import annotations

import math
import unittest

from runner.backtest import (
    bars_per_year,
    EQUITY_TRADING_DAYS_PER_YEAR,
    EQUITY_INTRADAY_MINUTES_PER_DAY,
)


class TestBarsPerYearResolver(unittest.TestCase):
    def test_daily_equity_is_252(self):
        self.assertEqual(bars_per_year("1Day", is_crypto=False), 252.0)

    def test_daily_crypto_is_365(self):
        self.assertEqual(bars_per_year("1Day", is_crypto=True), 365.0)

    def test_intraday_equity_uses_session_not_24h(self):
        # FIX 2026-06-25: equity intraday must use the ~8.5h feed session x 252,
        # NOT the crypto 24h x 365. 1Hour equity = (510/60)*252 = 2142.
        self.assertAlmostEqual(
            bars_per_year("1Hour", is_crypto=False), 2142.0, places=1)
        # 1Min equity = 510*252 = 128_520 (NOT the old 525_600).
        self.assertAlmostEqual(
            bars_per_year("1Min", is_crypto=False), 128_520.0, places=1)
        # 5Min equity = (510/5)*252 = 25_704.
        self.assertAlmostEqual(
            bars_per_year("5Min", is_crypto=False), 25_704.0, places=1)

    def test_intraday_crypto_unchanged_from_legacy(self):
        # Crypto intraday must STILL match the legacy 24h x 365 table exactly
        # (this fix is equity-only; zero behavior change for crypto).
        self.assertEqual(bars_per_year("1Hour", is_crypto=True), 24 * 365)
        self.assertEqual(bars_per_year("1Min", is_crypto=True), 60 * 24 * 365)
        self.assertEqual(bars_per_year("5Min", is_crypto=True), 12 * 24 * 365)

    def test_intraday_is_now_class_dependent(self):
        # The exact bug the intraday audit caught: equity != crypto intraday.
        self.assertNotEqual(
            bars_per_year("1Hour", is_crypto=False),
            bars_per_year("1Hour", is_crypto=True),
        )
        # And specifically equity < crypto (fewer real trading minutes).
        self.assertLess(
            bars_per_year("1Hour", is_crypto=False),
            bars_per_year("1Hour", is_crypto=True),
        )

    def test_intraday_equity_deflation_factor(self):
        # The Sharpe correction this fix applies to the live 1Hour cohort:
        # sqrt(8760 / 2142) = ~2.02x deflation of previously-reported Sharpe.
        old = 24 * 365  # the pre-fix equity 1Hour bpy
        new = bars_per_year("1Hour", is_crypto=False)
        self.assertAlmostEqual(math.sqrt(old / new), 2.022, places=2)

    def test_equity_intraday_minutes_constant(self):
        # Pin the session-length assumption so a silent change is caught.
        self.assertEqual(EQUITY_INTRADAY_MINUTES_PER_DAY, 510)

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
