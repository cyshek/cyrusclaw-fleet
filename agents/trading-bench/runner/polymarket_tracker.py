"""Polymarket Paper-Tracking System

Snapshots flagged markets daily and scores resolved markets against our priors.

Entry points (importable):
  snapshot_flagged_markets(db_path) -> int   # snap all flagged markets, return count
  score_resolved_markets(db_path)   -> dict  # check resolutions, score priors

The DB lives at workspace root: polymarket_track.db (default).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(WORKSPACE / "polymarket_track.db")

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Import scan at module level so tests can patch runner.polymarket_tracker.scan.
# Use a lazy shim fallback so missing scanner (unit-test isolation) doesn't crash import.
try:
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    from runner.polymarket_scanner import scan as _scanner_scan  # type: ignore
except ImportError:
    _scanner_scan = None  # type: ignore


def scan(*args, **kwargs):
    """Thin shim around polymarket_scanner.scan — exists so tests can patch this module's scan."""
    if _scanner_scan is None:
        raise ImportError("runner.polymarket_scanner not available")
    return _scanner_scan(*args, **kwargs)


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    category TEXT,
    end_date TEXT,
    snapshot_date TEXT NOT NULL,
    implied_prob REAL,
    our_prior REAL,
    discrepancy REAL,
    fee_rate REAL,
    flag_reason TEXT
);

CREATE TABLE IF NOT EXISTS market_outcomes (
    market_id TEXT PRIMARY KEY,
    question TEXT,
    resolved_date TEXT,
    outcome TEXT,
    final_implied_prob REAL,
    our_prior REAL,
    prior_correct INTEGER,
    first_snapshot_date TEXT,
    notes TEXT
);
"""


def _get_conn(db_path: str) -> sqlite3.Connection:
    """Open SQLite connection and ensure schema exists."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_get(url: str, params: Optional[dict] = None, timeout: int = 20,
              retries: int = 3) -> dict | list:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "trading-bench/1.0 (research; polymarket-tracker)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"HTTP GET failed [{url}]: {last_err}")


# ---------------------------------------------------------------------------
# Resolution detection helpers
# ---------------------------------------------------------------------------

def _detect_resolution(market: dict) -> tuple[bool, Optional[str], Optional[float]]:
    """Return (is_resolved, outcome, final_implied_prob).

    Resolution rules:
      - market["closed"] == True
      - AND one of:
        a) "resolutionPrice" key exists
        b) outcomePrices is ["1", "0"] or ["0", "1"] (or float-equivalent)

    Outcome:
      YES if float(outcomePrices[0]) >= 0.99
      NO  if float(outcomePrices[0]) <= 0.01
      None if ambiguous
    """
    if not market.get("closed", False):
        return False, None, None

    raw_prices = market.get("outcomePrices")
    outcome: Optional[str] = None
    final_prob: Optional[float] = None

    if raw_prices:
        try:
            prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            if prices:
                p0 = float(prices[0])
                final_prob = p0
                if p0 >= 0.99:
                    outcome = "YES"
                elif p0 <= 0.01:
                    outcome = "NO"
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    has_resolution_price = "resolutionPrice" in market

    if not has_resolution_price and outcome is None:
        # closed but can't determine outcome
        return True, None, final_prob

    return True, outcome, final_prob


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_prior_correct(our_prior: Optional[float], outcome: Optional[str]) -> Optional[int]:
    """Return 1 if prior direction matches outcome, 0 if not, None if indeterminate."""
    if our_prior is None or outcome is None:
        return None
    if our_prior > 0.5 and outcome == "YES":
        return 1
    if our_prior < 0.5 and outcome == "NO":
        return 1
    if our_prior == 0.5:
        return None  # no directional call
    return 0


# ---------------------------------------------------------------------------
# Public API: snapshot_flagged_markets
# ---------------------------------------------------------------------------

def snapshot_flagged_markets(db_path: str = DEFAULT_DB) -> int:
    """Pull current scan, snapshot all flagged markets to DB.

    Returns count of rows inserted (skips duplicates: same market_id + snapshot_date).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _get_conn(db_path)
    inserted = 0

    try:
        results = scan()
        flagged = [r for r in results if r.flagged]

        for r in flagged:
            # Idempotency: skip if same market_id + snapshot_date already exists
            existing = conn.execute(
                "SELECT id FROM market_snapshots WHERE market_id=? AND snapshot_date=?",
                (r.market_id, today),
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """INSERT INTO market_snapshots
                   (market_id, question, category, end_date, snapshot_date,
                    implied_prob, our_prior, discrepancy, fee_rate, flag_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.market_id,
                    r.question,
                    r.category,
                    r.end_date,
                    today,
                    r.implied_prob,
                    r.our_prior,
                    r.discrepancy,
                    r.fee_rate,
                    r.flag_reason,
                ),
            )
            inserted += 1

        conn.commit()
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------------------
# Public API: score_resolved_markets
# ---------------------------------------------------------------------------

def score_resolved_markets(db_path: str = DEFAULT_DB) -> dict:
    """Check if any tracked markets have resolved. Score our prior vs outcome.

    For each market_id in market_snapshots not yet in market_outcomes, fetch
    from Gamma API and check if resolved. Inserts into market_outcomes.

    Returns:
      {
        "newly_resolved": int,
        "total_scored": int,       # all rows in market_outcomes
        "correct": int,            # prior_correct == 1
        "incorrect": int,          # prior_correct == 0
        "no_prior": int,           # prior_correct IS NULL
        "accuracy_pct": float|str, # "N/A" if no scored rows
      }
    """
    conn = _get_conn(db_path)
    newly_resolved = 0

    try:
        # Markets we've snapped but not yet scored
        unscored = conn.execute(
            """SELECT DISTINCT s.market_id, s.question, s.our_prior, s.snapshot_date
               FROM market_snapshots s
               LEFT JOIN market_outcomes o ON s.market_id = o.market_id
               WHERE o.market_id IS NULL
               ORDER BY s.snapshot_date ASC"""
        ).fetchall()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for row in unscored:
            market_id = row["market_id"]
            question = row["question"]
            our_prior = row["our_prior"]
            first_snapshot_date = row["snapshot_date"]

            # Fetch current market state from Gamma
            try:
                market = _http_get(f"{GAMMA_BASE}/markets/{market_id}", timeout=15)
            except RuntimeError as exc:
                print(f"[polymarket_tracker] Gamma fetch failed for {market_id}: {exc}",
                      file=sys.stderr)
                continue

            if not isinstance(market, dict):
                continue

            is_resolved, outcome, final_prob = _detect_resolution(market)
            if not is_resolved:
                continue

            prior_correct = _compute_prior_correct(our_prior, outcome)
            notes = f"outcome={outcome}" + (f"; final_prob={final_prob:.3f}" if final_prob is not None else "")

            conn.execute(
                """INSERT OR REPLACE INTO market_outcomes
                   (market_id, question, resolved_date, outcome, final_implied_prob,
                    our_prior, prior_correct, first_snapshot_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    market_id,
                    question,
                    today,
                    outcome,
                    final_prob,
                    our_prior,
                    prior_correct,
                    first_snapshot_date,
                    notes,
                ),
            )
            newly_resolved += 1

        conn.commit()

        # Aggregate accuracy stats
        stats = conn.execute(
            """SELECT
                 COUNT(*) AS total_scored,
                 SUM(CASE WHEN prior_correct = 1 THEN 1 ELSE 0 END) AS correct,
                 SUM(CASE WHEN prior_correct = 0 THEN 1 ELSE 0 END) AS incorrect,
                 SUM(CASE WHEN prior_correct IS NULL THEN 1 ELSE 0 END) AS no_prior
               FROM market_outcomes"""
        ).fetchone()

        total = stats["total_scored"] or 0
        correct = stats["correct"] or 0
        incorrect = stats["incorrect"] or 0
        no_prior = stats["no_prior"] or 0

        scoreable = correct + incorrect
        accuracy_pct: float | str
        if scoreable > 0:
            accuracy_pct = round(100.0 * correct / scoreable, 1)
        else:
            accuracy_pct = "N/A"

        return {
            "newly_resolved": newly_resolved,
            "total_scored": total,
            "correct": correct,
            "incorrect": incorrect,
            "no_prior": no_prior,
            "accuracy_pct": accuracy_pct,
        }

    finally:
        conn.close()



# ---------------------------------------------------------------------------
# Paper bets table DDL
# ---------------------------------------------------------------------------

PAPER_BETS_DDL = """
CREATE TABLE IF NOT EXISTS paper_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    bet_date TEXT NOT NULL,
    side TEXT NOT NULL,
    our_prior REAL NOT NULL,
    implied_prob REAL NOT NULL,
    edge REAL NOT NULL,
    stake_usd REAL NOT NULL DEFAULT 100.0,
    kelly_fraction REAL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_date TEXT,
    outcome TEXT,
    pnl_usd REAL,
    notes TEXT
);
"""

PAPER_BETS_MIN_EDGE = 0.08
PAPER_BETS_MIN_VOLUME = 50_000
PAPER_BETS_MIN_DAYS = 3
PAPER_BETS_STAKE = 100.0


def _ensure_paper_bets_table(conn: sqlite3.Connection) -> None:
    """Ensure paper_bets table exists (run once per connection)."""
    conn.executescript(PAPER_BETS_DDL)
    conn.commit()


# ---------------------------------------------------------------------------
# Paper bets: place_paper_bets
# ---------------------------------------------------------------------------

def place_paper_bets(
    db_path: str = DEFAULT_DB,
    min_edge: float = PAPER_BETS_MIN_EDGE,
    stake: float = PAPER_BETS_STAKE,
    min_volume: float = PAPER_BETS_MIN_VOLUME,
    min_days: int = PAPER_BETS_MIN_DAYS,
) -> int:
    """Scan markets and log paper bets for edges above min_edge.

    For each market with our_prior computed AND:
      - edge > min_edge
      - days_to_close > min_days
      - volume_usd > min_volume
    Check if we already have an open bet (no duplicate bets).
    Determine side: YES if our_prior > implied_prob, NO otherwise.
    Log to paper_bets table.

    Returns count of new bets placed.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_paper_bets_table(conn)

    placed = 0
    try:
        results = scan()

        for r in results:
            # Must have a computed prior and edge
            if r.our_prior is None or r.discrepancy is None:
                continue
            # Edge filter
            edge = abs(r.our_prior - r.implied_prob)
            if edge <= min_edge:
                continue
            # Duration filter
            if r.days_to_close <= min_days:
                continue
            # Volume filter
            if r.volume_usd <= min_volume:
                continue

            # No double-bets on same market
            existing = conn.execute(
                "SELECT id FROM paper_bets WHERE market_id = ? AND status = 'open'",
                (r.market_id,),
            ).fetchone()
            if existing:
                continue

            # Determine side
            side = "YES" if r.our_prior > r.implied_prob else "NO"

            # Kelly fraction (optional sizing reference, not used for stake)
            # Kelly = edge / (1 / implied_prob - 1) = edge / (1 - implied_prob) / implied_prob
            # But since implied_prob = p_yes, and we bet YES:
            #   f = (our_prior - implied_prob) / (1 - implied_prob)  for YES bet
            #   f = (implied_prob - our_prior) / implied_prob  for NO bet (market p_yes)
            if side == "YES" and r.implied_prob < 1.0:
                kelly = (r.our_prior - r.implied_prob) / (1.0 - r.implied_prob)
            elif side == "NO" and r.implied_prob > 0.0:
                kelly = (r.implied_prob - r.our_prior) / r.implied_prob
            else:
                kelly = None

            conn.execute(
                """INSERT INTO paper_bets
                   (market_id, question, bet_date, side, our_prior, implied_prob,
                    edge, stake_usd, kelly_fraction, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
                (
                    r.market_id,
                    r.question,
                    today,
                    side,
                    r.our_prior,
                    r.implied_prob,
                    edge,
                    stake,
                    round(kelly, 4) if kelly is not None else None,
                    r.flag_reason[:200],
                ),
            )
            placed += 1

        conn.commit()
    finally:
        conn.close()

    return placed


# ---------------------------------------------------------------------------
# Paper bets: settle_paper_bets
# ---------------------------------------------------------------------------

def settle_paper_bets(db_path: str = DEFAULT_DB) -> dict:
    """Check open bets and settle any that have resolved.

    For each open bet:
      - Fetch market from Gamma API
      - If resolved: compute P&L and update status
        - Won (correct side): pnl = stake * (1 / implied_prob - 1)
        - Lost (wrong side): pnl = -stake
      - If void (market cancelled/ambiguous): status='void', pnl=0

    Returns summary dict:
      {newly_settled: int, won: int, lost: int, void: int, total_pnl: float}
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_paper_bets_table(conn)

    newly_settled = 0
    won = 0
    lost = 0
    void_count = 0
    total_pnl = 0.0

    try:
        open_bets = conn.execute(
            "SELECT * FROM paper_bets WHERE status = 'open'"
        ).fetchall()

        for bet in open_bets:
            market_id = bet["market_id"]
            side = bet["side"]
            implied_prob = bet["implied_prob"]
            stake = bet["stake_usd"]

            try:
                market = _http_get(f"{GAMMA_BASE}/markets/{market_id}", timeout=15)
            except RuntimeError as exc:
                print(f"[paper_bets] Gamma fetch failed for {market_id}: {exc}",
                      file=sys.stderr)
                continue

            if not isinstance(market, dict):
                continue

            is_resolved, outcome, final_prob = _detect_resolution(market)
            if not is_resolved:
                continue

            # Determine result
            if outcome is None:
                # Ambiguous resolution — void
                pnl = 0.0
                status = "void"
                void_count += 1
            elif (side == "YES" and outcome == "YES") or (side == "NO" and outcome == "NO"):
                # Won
                if side == "YES":
                    pnl = stake * (1.0 / implied_prob - 1.0) if implied_prob > 0 else 0.0
                else:
                    # Won NO bet: pnl = stake * (1 / (1 - implied_prob) - 1)
                    pnl = stake * (1.0 / (1.0 - implied_prob) - 1.0) if implied_prob < 1 else 0.0
                status = "won"
                won += 1
                total_pnl += pnl
            else:
                # Lost
                pnl = -stake
                status = "lost"
                lost += 1
                total_pnl += pnl

            conn.execute(
                """UPDATE paper_bets
                   SET status=?, resolved_date=?, outcome=?, pnl_usd=?
                   WHERE id=?""",
                (status, today, outcome, round(pnl, 2), bet["id"]),
            )
            newly_settled += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "newly_settled": newly_settled,
        "won": won,
        "lost": lost,
        "void": void_count,
        "total_pnl": round(total_pnl, 2),
    }

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket paper-tracker")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite DB")
    parser.add_argument("--score-only", action="store_true",
                        help="Only score resolved markets, skip snapshot")
    args = parser.parse_args()

    if not args.score_only:
        print("[polymarket_tracker] Snapshotting flagged markets...")
        snapped = snapshot_flagged_markets(db_path=args.db)
        print(f"[polymarket_tracker] Inserted {snapped} new snapshots")

    print("[polymarket_tracker] Scoring resolved markets...")
    result = score_resolved_markets(db_path=args.db)
    print(f"[polymarket_tracker] Newly resolved: {result['newly_resolved']}")
    print(f"[polymarket_tracker] Running accuracy: {result['accuracy_pct']}% "
          f"({result['correct']} correct / {result['correct'] + result['incorrect']} scoreable)")
    print(f"[polymarket_tracker] No-prior markets: {result['no_prior']}")


if __name__ == "__main__":
    main()
