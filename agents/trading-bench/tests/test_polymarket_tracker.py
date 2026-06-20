"""Tests for runner/polymarket_tracker.py

Covers:
  1. DB schema created correctly (both tables + columns)
  2. Snapshot inserts rows for flagged markets
  3. Resolution detection logic (mock API response)
  4. Scoring logic (prior_correct calculation)
  5. Idempotency: snapshotting same market twice same day doesn't double-insert
  6. score_resolved_markets: newly resolved market recorded + accuracy computed
  7. score_resolved_markets: unresolved market not recorded
  8. _compute_prior_correct: all branches (YES/NO/None prior/0.5)
  9. score_resolved_markets: accuracy_pct is 'N/A' with no scored rows
 10. Closed market with ambiguous prices handled gracefully
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.polymarket_tracker import (
    _compute_prior_correct,
    _detect_resolution,
    _get_conn,
    score_resolved_markets,
    snapshot_flagged_markets,
)
from runner.polymarket_scanner import ScanResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_db() -> str:
    """Return path to a fresh temp DB file (caller must clean up)."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _make_scan_result(
    market_id: str = "m1",
    question: str = "Will the Fed cut rates?",
    category: str = "Economics",
    end_date: str = "2026-12-31",
    implied_prob: float = 0.70,
    our_prior: float = 0.15,
    discrepancy: float = 0.55,
    fee_rate: float = 0.04,
    flag_reason: str = "NFCI prior flagged",
    flagged: bool = True,
) -> ScanResult:
    return ScanResult(
        market_id=market_id,
        question=question,
        category=category,
        end_date=end_date,
        days_to_close=180,
        volume_usd=500_000,
        implied_prob=implied_prob,
        our_prior=our_prior,
        discrepancy=discrepancy,
        fee_rate=fee_rate,
        flagged=flagged,
        flag_reason=flag_reason,
    )


def _make_gamma_market(
    market_id: str = "m1",
    closed: bool = False,
    outcome_prices=None,
    has_resolution_price: bool = False,
) -> dict:
    """Build a fake Gamma API market response dict."""
    m = {
        "id": market_id,
        "closed": closed,
        "active": not closed,
        "question": "Test market?",
    }
    if outcome_prices is not None:
        m["outcomePrices"] = json.dumps(outcome_prices)
    if has_resolution_price:
        m["resolutionPrice"] = 1.0
    return m


# ---------------------------------------------------------------------------
# Test 1: DB schema created correctly
# ---------------------------------------------------------------------------

class TestDBSchema(unittest.TestCase):
    def test_tables_created(self):
        """Both tables must exist after _get_conn."""
        db = _tmp_db()
        conn = _get_conn(db)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        self.assertIn("market_snapshots", tables)
        self.assertIn("market_outcomes", tables)

    def test_market_snapshots_columns(self):
        """market_snapshots must have all required columns."""
        db = _tmp_db()
        conn = _get_conn(db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(market_snapshots)").fetchall()}
        conn.close()
        required = {
            "id", "market_id", "question", "category", "end_date",
            "snapshot_date", "implied_prob", "our_prior", "discrepancy",
            "fee_rate", "flag_reason",
        }
        self.assertTrue(required.issubset(cols), f"Missing columns: {required - cols}")

    def test_market_outcomes_columns(self):
        """market_outcomes must have all required columns."""
        db = _tmp_db()
        conn = _get_conn(db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(market_outcomes)").fetchall()}
        conn.close()
        required = {
            "market_id", "question", "resolved_date", "outcome",
            "final_implied_prob", "our_prior", "prior_correct",
            "first_snapshot_date", "notes",
        }
        self.assertTrue(required.issubset(cols), f"Missing columns: {required - cols}")


# ---------------------------------------------------------------------------
# Test 2: Snapshot inserts rows
# ---------------------------------------------------------------------------

class TestSnapshotInserts(unittest.TestCase):
    @patch("runner.polymarket_tracker.scan")
    def test_snapshot_inserts_flagged(self, mock_scan):
        """snapshot_flagged_markets inserts one row per flagged market."""
        mock_scan.return_value = [
            _make_scan_result(market_id="a1", flagged=True),
            _make_scan_result(market_id="a2", flagged=True),
        ]
        db = _tmp_db()
        n = snapshot_flagged_markets(db_path=db)
        self.assertEqual(n, 2)

        conn = _get_conn(db)
        rows = conn.execute("SELECT market_id FROM market_snapshots").fetchall()
        conn.close()
        ids = {r[0] for r in rows}
        self.assertIn("a1", ids)
        self.assertIn("a2", ids)

    @patch("runner.polymarket_tracker.scan")
    def test_snapshot_skips_unflagged(self, mock_scan):
        """snapshot_flagged_markets does NOT insert unflagged markets."""
        mock_scan.return_value = [
            _make_scan_result(market_id="b1", flagged=False),
            _make_scan_result(market_id="b2", flagged=True),
        ]
        db = _tmp_db()
        n = snapshot_flagged_markets(db_path=db)
        self.assertEqual(n, 1)

        conn = _get_conn(db)
        rows = conn.execute("SELECT market_id FROM market_snapshots").fetchall()
        conn.close()
        ids = {r[0] for r in rows}
        self.assertNotIn("b1", ids)
        self.assertIn("b2", ids)

    @patch("runner.polymarket_tracker.scan")
    def test_snapshot_stores_correct_values(self, mock_scan):
        """Stored row values match the ScanResult."""
        sr = _make_scan_result(
            market_id="c1",
            question="Will inflation fall below 2%?",
            our_prior=0.30,
            implied_prob=0.60,
            discrepancy=0.30,
        )
        mock_scan.return_value = [sr]
        db = _tmp_db()
        snapshot_flagged_markets(db_path=db)

        conn = _get_conn(db)
        row = conn.execute(
            "SELECT * FROM market_snapshots WHERE market_id=?", ("c1",)
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["market_id"], "c1")
        self.assertEqual(row["question"], "Will inflation fall below 2%?")
        self.assertAlmostEqual(row["our_prior"], 0.30)
        self.assertAlmostEqual(row["implied_prob"], 0.60)
        self.assertAlmostEqual(row["discrepancy"], 0.30)


# ---------------------------------------------------------------------------
# Test 3: Resolution detection logic
# ---------------------------------------------------------------------------

class TestResolutionDetection(unittest.TestCase):
    def test_not_resolved_when_open(self):
        """Open market (closed=False) is never resolved."""
        m = _make_gamma_market(closed=False, outcome_prices=["0.60", "0.40"])
        is_res, outcome, prob = _detect_resolution(m)
        self.assertFalse(is_res)
        self.assertIsNone(outcome)

    def test_resolved_yes_when_closed_price_1(self):
        """Closed market with prices=['1','0'] → YES."""
        m = _make_gamma_market(closed=True, outcome_prices=["1", "0"],
                                has_resolution_price=True)
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertEqual(outcome, "YES")
        self.assertAlmostEqual(prob, 1.0)

    def test_resolved_no_when_closed_price_0(self):
        """Closed market with prices=['0','1'] → NO."""
        m = _make_gamma_market(closed=True, outcome_prices=["0", "1"],
                                has_resolution_price=True)
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertEqual(outcome, "NO")
        self.assertAlmostEqual(prob, 0.0)

    def test_resolved_yes_near_1(self):
        """Closed market with prices=['0.9999','0.0001'] → YES (>= 0.99 threshold)."""
        m = _make_gamma_market(closed=True, outcome_prices=["0.9999", "0.0001"],
                                has_resolution_price=True)
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertEqual(outcome, "YES")

    def test_resolved_no_near_0(self):
        """Closed market with prices=['0.001','0.999'] → NO (<= 0.01 threshold)."""
        m = _make_gamma_market(closed=True, outcome_prices=["0.001", "0.999"],
                                has_resolution_price=True)
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertEqual(outcome, "NO")

    def test_closed_ambiguous_price(self):
        """Closed market with mid price → resolved=True, outcome=None."""
        m = _make_gamma_market(closed=True, outcome_prices=["0.50", "0.50"])
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertIsNone(outcome)

    def test_closed_no_outcome_prices(self):
        """Closed market with no outcomePrices → resolved=True, outcome=None."""
        m = _make_gamma_market(closed=True)
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertIsNone(outcome)


# ---------------------------------------------------------------------------
# Test 4: Scoring logic (_compute_prior_correct)
# ---------------------------------------------------------------------------

class TestScoringLogic(unittest.TestCase):
    def test_prior_above_half_outcome_yes_correct(self):
        """prior=0.7, outcome=YES → prior_correct=1."""
        self.assertEqual(_compute_prior_correct(0.7, "YES"), 1)

    def test_prior_above_half_outcome_no_incorrect(self):
        """prior=0.7, outcome=NO → prior_correct=0."""
        self.assertEqual(_compute_prior_correct(0.7, "NO"), 0)

    def test_prior_below_half_outcome_no_correct(self):
        """prior=0.2, outcome=NO → prior_correct=1."""
        self.assertEqual(_compute_prior_correct(0.2, "NO"), 1)

    def test_prior_below_half_outcome_yes_incorrect(self):
        """prior=0.2, outcome=YES → prior_correct=0."""
        self.assertEqual(_compute_prior_correct(0.2, "YES"), 0)

    def test_prior_none_returns_none(self):
        """prior=None → prior_correct=None (no directional call)."""
        self.assertIsNone(_compute_prior_correct(None, "YES"))
        self.assertIsNone(_compute_prior_correct(None, "NO"))

    def test_outcome_none_returns_none(self):
        """outcome=None → prior_correct=None."""
        self.assertIsNone(_compute_prior_correct(0.8, None))

    def test_prior_exactly_half_returns_none(self):
        """prior=0.5 → no directional call → prior_correct=None."""
        self.assertIsNone(_compute_prior_correct(0.5, "YES"))
        self.assertIsNone(_compute_prior_correct(0.5, "NO"))

    def test_both_none_returns_none(self):
        """Both prior and outcome None → None."""
        self.assertIsNone(_compute_prior_correct(None, None))


# ---------------------------------------------------------------------------
# Test 5: Idempotency (same market, same day, no double-insert)
# ---------------------------------------------------------------------------

class TestIdempotency(unittest.TestCase):
    @patch("runner.polymarket_tracker.scan")
    def test_same_market_same_day_no_double_insert(self, mock_scan):
        """Calling snapshot twice on same day for same market inserts only 1 row."""
        mock_scan.return_value = [_make_scan_result(market_id="dup1", flagged=True)]
        db = _tmp_db()

        n1 = snapshot_flagged_markets(db_path=db)
        n2 = snapshot_flagged_markets(db_path=db)

        self.assertEqual(n1, 1)
        self.assertEqual(n2, 0)  # idempotent on second call same day

        conn = _get_conn(db)
        count = conn.execute(
            "SELECT COUNT(*) FROM market_snapshots WHERE market_id=?", ("dup1",)
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    @patch("runner.polymarket_tracker.scan")
    def test_multiple_markets_idempotent(self, mock_scan):
        """Multiple markets, called twice — only first call inserts anything."""
        mock_scan.return_value = [
            _make_scan_result(market_id="e1", flagged=True),
            _make_scan_result(market_id="e2", flagged=True),
            _make_scan_result(market_id="e3", flagged=True),
        ]
        db = _tmp_db()
        n1 = snapshot_flagged_markets(db_path=db)
        n2 = snapshot_flagged_markets(db_path=db)

        self.assertEqual(n1, 3)
        self.assertEqual(n2, 0)


# ---------------------------------------------------------------------------
# Test 6: score_resolved_markets — full flow with resolved market
# ---------------------------------------------------------------------------

class TestScoreResolvedFull(unittest.TestCase):
    @patch("runner.polymarket_tracker._http_get")
    @patch("runner.polymarket_tracker.scan")
    def test_resolved_market_recorded(self, mock_scan, mock_http):
        """A resolved market (closed=True, prices=[1,0]) is recorded in outcomes."""
        mock_scan.return_value = [
            _make_scan_result(market_id="r1", our_prior=0.20, flagged=True)
        ]
        mock_http.return_value = _make_gamma_market(
            market_id="r1",
            closed=True,
            outcome_prices=["1", "0"],
            has_resolution_price=True,
        )
        db = _tmp_db()
        snapshot_flagged_markets(db_path=db)
        result = score_resolved_markets(db_path=db)

        self.assertEqual(result["newly_resolved"], 1)

        conn = _get_conn(db)
        row = conn.execute(
            "SELECT outcome, prior_correct, our_prior FROM market_outcomes WHERE market_id=?",
            ("r1",),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["outcome"], "YES")
        # our_prior=0.20 < 0.5, outcome=YES → prior_correct=0 (wrong direction)
        self.assertEqual(row["prior_correct"], 0)

    @patch("runner.polymarket_tracker._http_get")
    @patch("runner.polymarket_tracker.scan")
    def test_correct_prior_scored_accurately(self, mock_scan, mock_http):
        """Prior pointing NO, outcome=NO → prior_correct=1; accuracy=100%."""
        mock_scan.return_value = [
            _make_scan_result(market_id="r2", our_prior=0.15, flagged=True)
        ]
        mock_http.return_value = _make_gamma_market(
            market_id="r2",
            closed=True,
            outcome_prices=["0", "1"],
            has_resolution_price=True,
        )
        db = _tmp_db()
        snapshot_flagged_markets(db_path=db)
        result = score_resolved_markets(db_path=db)

        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["incorrect"], 0)
        self.assertEqual(result["accuracy_pct"], 100.0)


# ---------------------------------------------------------------------------
# Test 7: score_resolved_markets — unresolved market not recorded
# ---------------------------------------------------------------------------

class TestUnresolvedMarketNotRecorded(unittest.TestCase):
    @patch("runner.polymarket_tracker._http_get")
    @patch("runner.polymarket_tracker.scan")
    def test_open_market_not_in_outcomes(self, mock_scan, mock_http):
        """Market still open (closed=False) must not appear in market_outcomes."""
        mock_scan.return_value = [
            _make_scan_result(market_id="u1", flagged=True)
        ]
        mock_http.return_value = _make_gamma_market(
            market_id="u1",
            closed=False,
            outcome_prices=["0.60", "0.40"],
        )
        db = _tmp_db()
        snapshot_flagged_markets(db_path=db)
        result = score_resolved_markets(db_path=db)

        self.assertEqual(result["newly_resolved"], 0)

        conn = _get_conn(db)
        row = conn.execute(
            "SELECT market_id FROM market_outcomes WHERE market_id=?", ("u1",)
        ).fetchone()
        conn.close()
        self.assertIsNone(row)


# ---------------------------------------------------------------------------
# Test 8: score_resolved_markets — accuracy_pct N/A with no scored rows
# ---------------------------------------------------------------------------

class TestAccuracyNAWhenEmpty(unittest.TestCase):
    def test_accuracy_na_with_empty_db(self):
        """Fresh DB with no outcomes → accuracy_pct='N/A'."""
        db = _tmp_db()
        result = score_resolved_markets(db_path=db)
        self.assertEqual(result["accuracy_pct"], "N/A")
        self.assertEqual(result["newly_resolved"], 0)
        self.assertEqual(result["total_scored"], 0)

    @patch("runner.polymarket_tracker._http_get")
    @patch("runner.polymarket_tracker.scan")
    def test_accuracy_na_when_all_have_no_prior(self, mock_scan, mock_http):
        """Markets with our_prior=None → all no_prior → accuracy_pct='N/A'."""
        mock_scan.return_value = [
            _make_scan_result(market_id="np1", our_prior=None, flagged=True)
        ]
        # closed, but outcomePrices mid → outcome=None
        mock_http.return_value = {
            "id": "np1",
            "closed": True,
            "resolutionPrice": 1.0,
            "outcomePrices": json.dumps(["1", "0"]),
        }
        db = _tmp_db()
        snapshot_flagged_markets(db_path=db)
        result = score_resolved_markets(db_path=db)

        # prior_correct is NULL (no prior), so scoreable=0 → N/A
        self.assertEqual(result["accuracy_pct"], "N/A")


# ---------------------------------------------------------------------------
# Test 9: Closed market with ambiguous prices handled gracefully
# ---------------------------------------------------------------------------

class TestAmbiguousResolution(unittest.TestCase):
    def test_mid_price_closed_market(self):
        """Closed market with mid price → is_resolved=True, outcome=None (no crash)."""
        m = _make_gamma_market(closed=True, outcome_prices=["0.50", "0.50"])
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertIsNone(outcome)
        self.assertAlmostEqual(prob, 0.50)

    def test_malformed_prices_no_crash(self):
        """Malformed outcomePrices → no crash, outcome=None."""
        m = {
            "id": "bad",
            "closed": True,
            "outcomePrices": "not_valid_json",
        }
        is_res, outcome, prob = _detect_resolution(m)
        self.assertTrue(is_res)
        self.assertIsNone(outcome)


# ---------------------------------------------------------------------------
# Test 10: score_resolved_markets returns correct summary structure
# ---------------------------------------------------------------------------

class TestSummaryStructure(unittest.TestCase):
    def test_return_dict_has_required_keys(self):
        """score_resolved_markets must return a dict with all expected keys."""
        db = _tmp_db()
        result = score_resolved_markets(db_path=db)
        required_keys = {
            "newly_resolved", "total_scored", "correct",
            "incorrect", "no_prior", "accuracy_pct",
        }
        self.assertTrue(required_keys.issubset(result.keys()),
                        f"Missing keys: {required_keys - result.keys()}")


if __name__ == "__main__":
    unittest.main()
