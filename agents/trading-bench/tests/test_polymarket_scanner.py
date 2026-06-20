"""Tests for runner/polymarket_scanner.py

Covers:
  1. Volume threshold filter
  2. Days-to-close threshold filter
  3. Category / tag exclusion filter
  4. NFCI -> macro recession prior buckets
  5. Discrepancy flagging (macro: >10pp threshold)
  6. Fed rate markets flagged with CME FedWatch note
  7. scan() returns list of ScanResult with correct fields
  8. scan() handles FRED unavailability (graceful degradation)
  9. Markets with None outcomePrices handled
 10. Fee rate extraction from feeSchedule and feeType
"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# Ensure workspace root is importable
WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.polymarket_scanner import (
    MIN_DAYS_TO_CLOSE,
    MIN_VOLUME_USD,
    ScanResult,
    _classify_market_type,
    _days_to_close,
    _extract_implied_prob,
    _get_fee_rate,
    _nfci_to_recession_prior,
    _score_market,
    _should_exclude,
    scan,
)


# ---------------------------------------------------------------------------
# Helpers to build fake market dicts
# ---------------------------------------------------------------------------

def _future_date(days_ahead: int) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    return dt.strftime("%Y-%m-%d")


def _make_market(
    question: str = "Will the Fed cut rates?",
    volume_num: float = 200_000,
    days_ahead: int = 30,
    outcome_prices=None,
    fee_type: str = "politics_fees",
    tag_slugs=None,
    fee_schedule=None,
    market_id: str = "1001",
    closed: bool = False,
    active: bool = True,
) -> dict:
    """Build a minimal fake Gamma API market dict."""
    if outcome_prices is None:
        outcome_prices = ["0.60", "0.40"]
    end_iso = _future_date(days_ahead)
    tags = [{"slug": s, "label": s.title()} for s in (tag_slugs or [])]
    market = {
        "id": market_id,
        "question": question,
        "volumeNum": volume_num,
        "volume": str(volume_num),
        "endDateIso": end_iso,
        "endDate": end_iso + "T00:00:00Z",
        "outcomePrices": json.dumps(outcome_prices),
        "feeType": fee_type,
        "closed": closed,
        "active": active,
        "events": [{"tags": tags}],
    }
    if fee_schedule is not None:
        market["feeSchedule"] = fee_schedule
    return market


# ---------------------------------------------------------------------------
# Test: Volume filter
# ---------------------------------------------------------------------------

class TestVolumeFilter(unittest.TestCase):
    def test_min_volume_constant_is_100k(self):
        """MIN_VOLUME_USD should be 100,000."""
        self.assertEqual(MIN_VOLUME_USD, 100_000)

    def test_below_threshold_excluded(self):
        """Markets below MIN_VOLUME_USD should be excluded from scan."""
        self.assertLess(50_000, MIN_VOLUME_USD)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_excludes_low_volume(self, mock_nfci, mock_fetch):
        """scan() must exclude markets with volume < MIN_VOLUME_USD."""
        low_vol = _make_market(
            question="Will Congress pass a debt ceiling bill?",
            volume_num=5_000,
            days_ahead=30,
        )
        mock_fetch.return_value = [low_vol]
        results = scan()
        self.assertEqual(len(results), 0)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_includes_high_volume(self, mock_nfci, mock_fetch):
        """scan() must include markets with volume >= MIN_VOLUME_USD."""
        high_vol = _make_market(
            question="Will the government shut down?",
            volume_num=500_000,
            days_ahead=30,
        )
        mock_fetch.return_value = [high_vol]
        results = scan()
        self.assertEqual(len(results), 1)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_includes_exactly_threshold(self, mock_nfci, mock_fetch):
        """scan() must include markets with volume == MIN_VOLUME_USD."""
        exact_vol = _make_market(
            question="Will unemployment stay below 5%?",
            volume_num=100_000,
            days_ahead=30,
        )
        mock_fetch.return_value = [exact_vol]
        results = scan()
        self.assertEqual(len(results), 1)


# ---------------------------------------------------------------------------
# Test: Days-to-close filter
# ---------------------------------------------------------------------------

class TestDaysToCloseFilter(unittest.TestCase):
    def test_min_days_constant_is_14(self):
        self.assertEqual(MIN_DAYS_TO_CLOSE, 14)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_excludes_short_horizon(self, mock_nfci, mock_fetch):
        """scan() must drop markets closing in < 14 days."""
        short = _make_market(
            question="Will Fed raise rates this week?",
            volume_num=300_000,
            days_ahead=5,
        )
        mock_fetch.return_value = [short]
        results = scan()
        self.assertEqual(len(results), 0)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_includes_long_horizon(self, mock_nfci, mock_fetch):
        """scan() must include markets closing in >= 14 days."""
        long_ = _make_market(
            question="Will unemployment stay below 5%?",
            volume_num=300_000,
            days_ahead=60,
        )
        mock_fetch.return_value = [long_]
        results = scan()
        self.assertEqual(len(results), 1)

    def test_days_to_close_calculation(self):
        """_days_to_close should return days from today to the given date."""
        future = _future_date(30)
        dtc = _days_to_close(future)
        # Allow +-1 day for clock edge
        self.assertGreaterEqual(dtc, 29)
        self.assertLessEqual(dtc, 31)


# ---------------------------------------------------------------------------
# Test: Category / tag exclusion filter
# ---------------------------------------------------------------------------

class TestCategoryFilter(unittest.TestCase):
    def test_sports_tag_excluded(self):
        m = _make_market(
            question="Will Arsenal win the Premier League?",
            tag_slugs=["sports", "soccer"],
        )
        self.assertIsNotNone(_should_exclude(m, m["question"].lower()))

    def test_crypto_tag_excluded(self):
        m = _make_market(question="Will Bitcoin hit 200k?", tag_slugs=["crypto"])
        self.assertIsNotNone(_should_exclude(m, m["question"].lower()))

    def test_politics_tag_not_excluded(self):
        m = _make_market(
            question="Will the Fed cut rates by 50 bps?",
            tag_slugs=["politics"],
        )
        self.assertIsNone(_should_exclude(m, m["question"].lower()))

    def test_world_cup_keyword_excluded(self):
        m = _make_market(question="Will USA win the World Cup?")
        self.assertIsNotNone(_should_exclude(m, m["question"].lower()))

    def test_bitcoin_keyword_excluded(self):
        m = _make_market(question="Will Bitcoin hit $200k by end of year?")
        self.assertIsNotNone(_should_exclude(m, m["question"].lower()))

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_scan_excludes_sports_by_tag(self, mock_nfci, mock_fetch):
        sports = _make_market(
            question="Will LeBron James win MVP?",
            volume_num=500_000,
            days_ahead=30,
            tag_slugs=["sports", "basketball", "nba"],
        )
        mock_fetch.return_value = [sports]
        results = scan()
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# Test: NFCI -> prior buckets
# ---------------------------------------------------------------------------

class TestNFCIPriorBuckets(unittest.TestCase):
    def test_very_loose_conditions(self):
        """NFCI < -0.5 -> prior = 0.05 (very low recession risk)."""
        self.assertAlmostEqual(_nfci_to_recession_prior(-1.0), 0.05)

    def test_loose_boundary(self):
        """NFCI = -0.5 -> prior = 0.15 (at boundary, near-neutral bucket)."""
        self.assertAlmostEqual(_nfci_to_recession_prior(-0.5), 0.15)

    def test_near_neutral(self):
        """NFCI between -0.5 and 0.0 -> prior = 0.15."""
        self.assertAlmostEqual(_nfci_to_recession_prior(-0.25), 0.15)

    def test_slightly_tight(self):
        """NFCI between 0.0 and 0.5 -> prior = 0.30."""
        self.assertAlmostEqual(_nfci_to_recession_prior(0.25), 0.30)

    def test_tight_boundary(self):
        """NFCI = 0.5 -> prior = 0.50 (at or above 0.5)."""
        self.assertAlmostEqual(_nfci_to_recession_prior(0.5), 0.50)

    def test_very_tight_conditions(self):
        """NFCI > 0.5 -> prior = 0.50."""
        self.assertAlmostEqual(_nfci_to_recession_prior(1.2), 0.50)

    def test_neutral_zero(self):
        """NFCI = 0.0 -> prior = 0.30 (tight bucket starts at 0.0 inclusive)."""
        self.assertAlmostEqual(_nfci_to_recession_prior(0.0), 0.30)


# ---------------------------------------------------------------------------
# Test: Discrepancy flagging
# ---------------------------------------------------------------------------

class TestDiscrepancyFlagging(unittest.TestCase):
    def test_large_discrepancy_flagged(self):
        """Macro market with >10pp discrepancy should be flagged."""
        # implied = 0.55, nfci = -0.8 -> prior = 0.05, disc = 0.50 > 0.10
        m = _make_market(
            question="Will a recession start in 2026?",
            outcome_prices=["0.55", "0.45"],
        )
        nfci = -0.8
        prior, disc, flagged, reason = _score_market(m, nfci)
        self.assertTrue(flagged)
        self.assertIsNotNone(prior)
        self.assertGreater(disc, 0.10)

    def test_small_discrepancy_not_flagged(self):
        """Macro market with <10pp discrepancy should NOT be flagged."""
        # implied = 0.17, nfci = -0.3 -> prior = 0.15, disc = 0.02 < 0.10
        m = _make_market(
            question="Will unemployment exceed 5%?",
            outcome_prices=["0.17", "0.83"],
        )
        nfci = -0.3
        prior, disc, flagged, reason = _score_market(m, nfci)
        self.assertFalse(flagged)
        self.assertIsNotNone(prior)
        self.assertAlmostEqual(prior, 0.15)

    def test_exact_threshold_boundary(self):
        """Discrepancy exactly at 0.10 should NOT be flagged (strictly >)."""
        # implied = 0.25, nfci = -0.3 -> prior = 0.15, disc = 0.10 -> not > 0.10
        m = _make_market(
            question="Will GDP growth be negative in Q1?",
            outcome_prices=["0.25", "0.75"],
        )
        nfci = -0.3
        prior, disc, flagged, reason = _score_market(m, nfci)
        self.assertFalse(flagged)
        self.assertAlmostEqual(disc, 0.10, places=10)


# ---------------------------------------------------------------------------
# Test: Fed rate markets
# ---------------------------------------------------------------------------

class TestFedRateMarkets(unittest.TestCase):
    def test_fed_market_classified_correctly(self):
        self.assertEqual(
            _classify_market_type("will the fed cut rates by 50 bps?"), "fed_rate"
        )
        self.assertEqual(
            _classify_market_type("will fomc raise interest rates?"), "fed_rate"
        )
        self.assertEqual(
            _classify_market_type("will there be a rate hike after july meeting?"),
            "fed_rate",
        )

    def test_fed_market_flagged_with_cme_note(self):
        """Fed rate markets must be flagged with CME FedWatch message."""
        m = _make_market(
            question="Will the Fed decrease rates by 25 bps after the June 2026 meeting?",
            outcome_prices=["0.65", "0.35"],
        )
        prior, disc, flagged, reason = _score_market(m, nfci=None)
        self.assertTrue(flagged)
        self.assertIn("CME FedWatch", reason)
        self.assertIsNone(prior)

    def test_fed_market_flagged_regardless_of_nfci(self):
        """Fed rate markets are always flagged, even without NFCI."""
        m = _make_market(
            question="Will the Fed increase interest rates?",
            outcome_prices=["0.30", "0.70"],
        )
        prior, disc, flagged, reason = _score_market(m, nfci=None)
        self.assertTrue(flagged)
        self.assertIn("CME", reason)

    def test_recession_not_classified_as_fed(self):
        """Recession question should not be classified as fed_rate."""
        mtype = _classify_market_type("will a recession occur in the us by end of year?")
        self.assertEqual(mtype, "macro_stress")


# ---------------------------------------------------------------------------
# Test: scan() output format
# ---------------------------------------------------------------------------

class TestScanOutputFormat(unittest.TestCase):
    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=-0.4)
    def test_scan_returns_list_of_scan_results(self, mock_nfci, mock_fetch):
        """scan() must return List[ScanResult]."""
        mock_fetch.return_value = [
            _make_market(
                question="Will recession start in 2026?",
                volume_num=500_000,
                days_ahead=90,
            )
        ]
        results = scan()
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) >= 1)
        self.assertIsInstance(results[0], ScanResult)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=-0.4)
    def test_scan_result_has_all_required_fields(self, mock_nfci, mock_fetch):
        """Every ScanResult must have all required dataclass fields."""
        mock_fetch.return_value = [
            _make_market(
                question="Will unemployment stay below 5%?",
                volume_num=150_000,
                days_ahead=45,
            )
        ]
        results = scan()
        self.assertEqual(len(results), 1)
        r = results[0]
        required_fields = [f.name for f in fields(ScanResult)]
        for fname in required_fields:
            self.assertTrue(hasattr(r, fname), f"ScanResult missing field: {fname}")

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=-0.4)
    def test_scan_result_implied_prob_range(self, mock_nfci, mock_fetch):
        """implied_prob must be in [0, 1]."""
        mock_fetch.return_value = [
            _make_market(
                question="Will CPI exceed 3%?",
                volume_num=200_000,
                days_ahead=30,
                outcome_prices=["0.72", "0.28"],
            )
        ]
        results = scan()
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertGreaterEqual(r.implied_prob, 0.0)
        self.assertLessEqual(r.implied_prob, 1.0)
        self.assertAlmostEqual(r.implied_prob, 0.72)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=-0.4)
    def test_scan_market_id_and_question_populated(self, mock_nfci, mock_fetch):
        """ScanResult.market_id and .question must be populated."""
        mock_fetch.return_value = [
            _make_market(
                question="Will the debt ceiling be raised?",
                market_id="9999",
                volume_num=300_000,
                days_ahead=60,
            )
        ]
        results = scan()
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.market_id, "9999")
        self.assertEqual(r.question, "Will the debt ceiling be raised?")


# ---------------------------------------------------------------------------
# Test: Graceful FRED degradation
# ---------------------------------------------------------------------------

class TestFredGracefulDegradation(unittest.TestCase):
    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_fred_unavailable_no_crash(self, mock_nfci, mock_fetch):
        """When NFCI is unavailable, scan() should not crash."""
        mock_fetch.return_value = [
            _make_market(
                question="Will a recession start in 2026?",
                volume_num=200_000,
                days_ahead=45,
            )
        ]
        try:
            results = scan()
        except Exception as exc:
            self.fail(f"scan() raised unexpectedly with FRED unavailable: {exc}")
        self.assertIsInstance(results, list)

    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=None)
    def test_fred_unavailable_prior_is_none(self, mock_nfci, mock_fetch):
        """When NFCI unavailable, macro market our_prior must be None."""
        mock_fetch.return_value = [
            _make_market(
                question="Will the US enter a recession?",
                volume_num=500_000,
                days_ahead=90,
            )
        ]
        results = scan()
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIsNone(r.our_prior)
        self.assertFalse(r.flagged)


# ---------------------------------------------------------------------------
# Test: Fee rate extraction
# ---------------------------------------------------------------------------

class TestFeeRateExtraction(unittest.TestCase):
    def test_fee_schedule_rate_preferred(self):
        """feeSchedule.rate should be preferred over feeType."""
        m = _make_market(fee_type="sports_fees", fee_schedule={"rate": 0.03})
        self.assertAlmostEqual(_get_fee_rate(m), 0.03)

    def test_politics_fees_type(self):
        m = _make_market(fee_type="politics_fees")
        self.assertAlmostEqual(_get_fee_rate(m), 0.04)

    def test_general_fees_zero(self):
        m = _make_market(fee_type="general_fees")
        self.assertAlmostEqual(_get_fee_rate(m), 0.0)

    def test_sports_fees_v2(self):
        m = _make_market(fee_type="sports_fees_v2")
        self.assertAlmostEqual(_get_fee_rate(m), 0.04)

    def test_unknown_fee_type_defaults(self):
        m = _make_market(fee_type="unknown_type")
        self.assertAlmostEqual(_get_fee_rate(m), 0.04)


# ---------------------------------------------------------------------------
# Test: Implied prob extraction
# ---------------------------------------------------------------------------

class TestImpliedProbExtraction(unittest.TestCase):
    def test_normal_prices(self):
        m = _make_market(outcome_prices=["0.65", "0.35"])
        self.assertAlmostEqual(_extract_implied_prob(m), 0.65)

    def test_no_outcome_prices(self):
        m = _make_market()
        m["outcomePrices"] = None
        self.assertIsNone(_extract_implied_prob(m))

    def test_empty_prices_list(self):
        m = _make_market(outcome_prices=[])
        self.assertIsNone(_extract_implied_prob(m))

    def test_single_price(self):
        m = _make_market()
        m["outcomePrices"] = '["0.88"]'
        self.assertAlmostEqual(_extract_implied_prob(m), 0.88)


# ---------------------------------------------------------------------------
# Test: Multi-market scan with mixed types
# ---------------------------------------------------------------------------

class TestMultiMarketScan(unittest.TestCase):
    @patch("runner.polymarket_scanner.fetch_markets")
    @patch("runner.polymarket_scanner._fetch_nfci_latest", return_value=0.3)
    def test_mixed_markets_correct_flagging(self, mock_nfci, mock_fetch):
        """Fed rate markets flagged; macro stress with large discrepancy flagged; others not."""
        markets = [
            # Fed rate -> should be flagged (CME FedWatch note)
            _make_market(
                question="Will the Fed cut rates by 25 bps after July meeting?",
                market_id="101",
                volume_num=1_000_000,
                days_ahead=40,
            ),
            # Macro stress, NFCI=0.3->prior=0.30, implied=0.70 -> disc=0.40 > 0.10 -> flagged
            _make_market(
                question="Will a recession happen in 2026?",
                market_id="102",
                volume_num=300_000,
                days_ahead=60,
                outcome_prices=["0.70", "0.30"],
            ),
            # Macro stress, NFCI=0.3->prior=0.30, implied=0.32 -> disc=0.02 < 0.10 -> not flagged
            _make_market(
                question="Will the unemployment rate exceed 5%?",
                market_id="103",
                volume_num=200_000,
                days_ahead=45,
                outcome_prices=["0.32", "0.68"],
            ),
            # Sports -> excluded entirely
            _make_market(
                question="Will Real Madrid win the Champions League?",
                market_id="104",
                volume_num=500_000,
                days_ahead=30,
                tag_slugs=["sports", "soccer"],
            ),
        ]
        mock_fetch.return_value = markets
        results = scan()

        # Sports excluded -> only 3 results
        self.assertEqual(len(results), 3)
        result_ids = {r.market_id for r in results}
        self.assertNotIn("104", result_ids)  # sports excluded

        flagged = [r for r in results if r.flagged]
        self.assertEqual(len(flagged), 2)  # Fed + high-discrepancy macro

        fed_result = next(r for r in results if r.market_id == "101")
        self.assertTrue(fed_result.flagged)
        self.assertIn("CME FedWatch", fed_result.flag_reason)

        macro_high = next(r for r in results if r.market_id == "102")
        self.assertTrue(macro_high.flagged)

        macro_low = next(r for r in results if r.market_id == "103")
        self.assertFalse(macro_low.flagged)


if __name__ == "__main__":
    unittest.main()
