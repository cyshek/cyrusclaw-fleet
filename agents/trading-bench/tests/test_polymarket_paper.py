"""Tests for the Polymarket paper-betting layer."""
from __future__ import annotations
import json, sqlite3, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.polymarket_tracker import (_ensure_paper_bets_table, place_paper_bets, settle_paper_bets)


def _sr(**kw):
    d = dict(market_id="m1", question="Will X?", category="Politics",
             end_date="2026-12-31", days_to_close=30, volume_usd=100_000,
             implied_prob=0.30, our_prior=0.60, discrepancy=0.30,
             fee_rate=0.0, flagged=True, flag_reason="edge")
    d.update(kw)
    return SimpleNamespace(**d)


def _gamma(resolved, outcome="Yes"):
    """Fake gamma API response matching _detect_resolution expectations.

    _detect_resolution requires market["closed"]==True (not "resolved").
    outcomePrices must be a JSON-encoded string list.
    """
    if resolved:
        prices = '["1", "0"]' if outcome == "Yes" else '["0", "1"]'
        data = {
            "closed": True,
            "resolutionTime": "2026-07-01T00:00:00Z",
            "outcomePrices": prices,
            "resolutionPrice": 1 if outcome == "Yes" else 0,
        }
    else:
        data = {"closed": False}
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=resp)


def _seed(db_path, market_id="m1", side="YES", implied_prob=0.30, stake=100.0, status="open"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_paper_bets_table(conn)
    conn.execute(
        "INSERT INTO paper_bets (market_id, question, bet_date, side, our_prior,"
        " implied_prob, edge, stake_usd, status) VALUES (?,?,'2026-06-16',?,0.60,?,0.30,?,?)",
        (market_id, f"Will {market_id}?", side, implied_prob, stake, status),
    )
    conn.commit()
    conn.close()


class TestPaperBetsTable(unittest.TestCase):
    def test_created(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = sqlite3.connect(f.name)
            _ensure_paper_bets_table(conn)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
        self.assertIn("paper_bets", tables)

    def test_columns(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = sqlite3.connect(f.name)
            _ensure_paper_bets_table(conn)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(paper_bets)").fetchall()}
            conn.close()
        for c in ("market_id", "question", "bet_date", "side", "our_prior",
                  "implied_prob", "edge", "stake_usd", "status", "pnl_usd"):
            self.assertIn(c, cols, f"Missing: {c}")

    def test_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = sqlite3.connect(f.name)
            _ensure_paper_bets_table(conn)
            _ensure_paper_bets_table(conn)
            conn.close()


class TestPlacePaperBets(unittest.TestCase):
    def _place(self, results, min_edge=0.08):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        with patch("runner.polymarket_tracker.scan", return_value=results):
            count = place_paper_bets(min_edge=min_edge, stake=100.0, db_path=db_path)
        return count, db_path

    def test_places_valid_bet(self):
        count, db_path = self._place([_sr()])
        self.assertEqual(count, 1)
        conn = sqlite3.connect(db_path)
        side, stake, status = conn.execute("SELECT side, stake_usd, status FROM paper_bets").fetchone()
        conn.close()
        self.assertEqual(side, "YES")
        self.assertAlmostEqual(stake, 100.0)
        self.assertEqual(status, "open")

    def test_no_duplicate_open_bet(self):
        r = _sr(market_id="dup1")
        count1, db_path = self._place([r])
        with patch("runner.polymarket_tracker.scan", return_value=[r]):
            count2 = place_paper_bets(min_edge=0.08, stake=100.0, db_path=db_path)
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 0)

    def test_skips_below_min_edge(self):
        count, _ = self._place([_sr(our_prior=0.35, implied_prob=0.30, discrepancy=0.05)], min_edge=0.08)
        self.assertEqual(count, 0)

    def test_skips_low_volume(self):
        count, _ = self._place([_sr(volume_usd=10_000)])
        self.assertEqual(count, 0)

    def test_skips_expiring_soon(self):
        count, _ = self._place([_sr(days_to_close=2)])
        self.assertEqual(count, 0)

    def test_skips_no_prior(self):
        count, _ = self._place([_sr(our_prior=None, discrepancy=None)])
        self.assertEqual(count, 0)

    def test_side_no_when_prior_below_implied(self):
        _, db_path = self._place([_sr(our_prior=0.20, implied_prob=0.60, discrepancy=0.40)])
        conn = sqlite3.connect(db_path)
        side = conn.execute("SELECT side FROM paper_bets").fetchone()[0]
        conn.close()
        self.assertEqual(side, "NO")


class TestSettlePaperBets(unittest.TestCase):
    def test_won_pnl(self):
        implied, stake = 0.25, 100.0
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        _seed(db_path, market_id="w1", side="YES", implied_prob=implied, stake=stake)
        with patch("runner.polymarket_tracker.urllib.request.urlopen", _gamma(True, "Yes")):
            settle_paper_bets(db_path=db_path)
        conn = sqlite3.connect(db_path)
        status, pnl = conn.execute("SELECT status, pnl_usd FROM paper_bets WHERE market_id='w1'").fetchone()
        conn.close()
        self.assertEqual(status, "won")
        self.assertAlmostEqual(pnl, stake * (1.0 / implied - 1.0), places=2)

    def test_lost_pnl(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        _seed(db_path, market_id="l1", side="YES", implied_prob=0.30, stake=100.0)
        with patch("runner.polymarket_tracker.urllib.request.urlopen", _gamma(True, "No")):
            settle_paper_bets(db_path=db_path)
        conn = sqlite3.connect(db_path)
        status, pnl = conn.execute("SELECT status, pnl_usd FROM paper_bets WHERE market_id='l1'").fetchone()
        conn.close()
        self.assertEqual(status, "lost")
        self.assertAlmostEqual(pnl, -100.0, places=2)

    def test_unresolved_stays_open(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        _seed(db_path, market_id="o1")
        with patch("runner.polymarket_tracker.urllib.request.urlopen", _gamma(False)):
            settle_paper_bets(db_path=db_path)
        conn = sqlite3.connect(db_path)
        status = conn.execute("SELECT status FROM paper_bets WHERE market_id='o1'").fetchone()[0]
        conn.close()
        self.assertEqual(status, "open")

    def test_already_settled_skipped(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        _seed(db_path, market_id="d1", status="won")
        mock_url = _gamma(True, "Yes")
        with patch("runner.polymarket_tracker.urllib.request.urlopen", mock_url):
            settle_paper_bets(db_path=db_path)
        mock_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
