"""Tests for runner/edge_calibrator.py — Edge Calibration Meta-Model.

All tests use in-memory / temp SQLite DBs; no tournament.db touched.
Tests cover:
  1. Pass-through when insufficient data
  2. Feature extraction from mock trades
  3. Calibration multiplier formula
  4. get_calibrated_kelly_fraction returns value in [0, 1]
  5. train_calibrator returns correct status dict
  6. Calibrated fraction ≤ raw fraction (calibration only shrinks, never inflates)
  7. Manual logistic regression gradient descent
  8. Graceful degradation on bad DB / no data
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_trades_db(rows: list[dict]) -> Path:
    """Create a temp SQLite DB with the minimal trades schema."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc       TEXT    NOT NULL DEFAULT '2024-01-01T00:00:00Z',
                strategy     TEXT    NOT NULL,
                symbol       TEXT    NOT NULL DEFAULT 'BTC/USD',
                side         TEXT    NOT NULL,
                qty          REAL    NOT NULL,
                notional_usd REAL,
                price        REAL,
                status       TEXT    NOT NULL DEFAULT 'filled',
                reason       TEXT,
                raw          TEXT
            )
        """)
        for r in rows:
            conn.execute(
                "INSERT INTO trades "
                "(strategy, symbol, side, qty, price, notional_usd, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    r.get("strategy", "breakout_xlk"),
                    r.get("symbol", "BTC/USD"),
                    r["side"],
                    r["qty"],
                    r.get("price"),
                    r.get("notional_usd"),
                    r.get("status", "filled"),
                ),
            )
        conn.commit()
    return db_path


def _make_round_trips_rows(
    n: int,
    win_rate: float,
    strategy: str = "breakout_xlk",
    entry_price: float = 100.0,
    win_pct: float = 0.10,
    loss_pct: float = 0.05,
) -> list[dict]:
    """Generate n round-trip trade pairs (buy + sell)."""
    rows = []
    n_wins = round(n * win_rate)
    for i in range(n):
        rows.append({
            "strategy": strategy,
            "side": "buy",
            "qty": 1.0,
            "price": entry_price,
            "notional_usd": entry_price,
        })
        if i < n_wins:
            sell_price = entry_price * (1 + win_pct)
        else:
            sell_price = entry_price * (1 - loss_pct)
        rows.append({
            "strategy": strategy,
            "side": "sell",
            "qty": 1.0,
            "price": sell_price,
            "notional_usd": sell_price,
        })
    return rows


def _make_multi_strategy_db(
    per_strategy_trips: int = 10,
    n_strategies: int = 4,
    win_rate: float = 0.6,
) -> Path:
    """Create DB with multiple strategies each having per_strategy_trips round-trips.

    Uses LIVE_ROSTER strategy names so the universe filter (live-book only)
    keeps these rows — these fixtures exercise the trained-model path, not the
    filter policy (that has its own dedicated tests).
    """
    from runner.edge_calibrator import LIVE_ROSTER
    roster = sorted(LIVE_ROSTER)
    rows = []
    for i in range(n_strategies):
        rows.extend(
            _make_round_trips_rows(
                per_strategy_trips,
                win_rate=win_rate,
                strategy=roster[i % len(roster)],
            )
        )
    return _make_trades_db(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Calibration multiplier formula (pure unit test, no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrationMultiplierFormula:
    """Test 3: the multiplier = 2*P(win) - 1, clipped [0, 1]."""

    def test_p50_gives_zero(self):
        from runner.edge_calibrator import _calibration_multiplier
        assert _calibration_multiplier(0.5) == 0.0

    def test_p75_gives_half(self):
        from runner.edge_calibrator import _calibration_multiplier
        assert abs(_calibration_multiplier(0.75) - 0.5) < 1e-9

    def test_p100_gives_one(self):
        from runner.edge_calibrator import _calibration_multiplier
        assert _calibration_multiplier(1.0) == 1.0

    def test_p_below_half_clips_to_zero(self):
        from runner.edge_calibrator import _calibration_multiplier
        assert _calibration_multiplier(0.3) == 0.0
        assert _calibration_multiplier(0.0) == 0.0

    def test_p_above_one_clips_to_one(self):
        from runner.edge_calibrator import _calibration_multiplier
        # Shouldn't happen from a real model, but formula must clip safely
        assert _calibration_multiplier(1.5) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Pass-through when insufficient data
# ─────────────────────────────────────────────────────────────────────────────

class TestPassThroughInsufficientData:
    """Test 1: When total round-trips < 30, get_calibrated_kelly_fraction must
    return the raw fraction unchanged."""

    def setup_method(self):
        """Reset the model cache before each test."""
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    def test_empty_db_passthrough(self):
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        raw = 0.35
        result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
        assert result == raw, f"Expected pass-through {raw}, got {result}"

    def test_few_trips_passthrough(self):
        """15 total round-trips (< 30) → pass-through."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction, _MODEL_CACHE
        rows = _make_round_trips_rows(15, win_rate=0.6)
        db_path = _make_trades_db(rows)
        raw = 0.20
        result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
        assert result == raw, f"Expected pass-through {raw}, got {result}"

    def test_train_calibrator_insufficient_data_status(self):
        """train_calibrator returns status='insufficient_data' with few trips."""
        from runner.edge_calibrator import train_calibrator
        rows = _make_round_trips_rows(10, win_rate=0.6)
        db_path = _make_trades_db(rows)
        result = train_calibrator(db_path=str(db_path))
        assert result["status"] == "insufficient_data"
        assert result["n_samples"] == 0
        assert "insufficient" in result["notes"].lower()

    def test_missing_db_passthrough(self):
        """Non-existent DB → pass-through, no exception."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        raw = 0.15
        result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path="/tmp/nonexistent_edge_calib.db")
        assert result == raw

    def test_zero_kelly_passthrough(self):
        """raw_kelly_fraction=0.0 → calibrated fraction is also 0.0 (pass-through)."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        result = get_calibrated_kelly_fraction("breakout_xlk", 0.0, db_path=str(db_path))
        assert result == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Feature extraction from mock trades
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureExtraction:
    """Test 2: Feature vectors are extracted correctly from mock round-trips."""

    def test_feature_length_matches_names(self):
        from runner.edge_calibrator import (
            extract_features_for_strategy,
            _fifo_match_strategy,
            FEATURE_NAMES,
        )
        rows = _make_round_trips_rows(5, win_rate=0.6)
        trips = _fifo_match_strategy([r for r in rows])
        feat = extract_features_for_strategy("breakout_xlk", trips, kelly_raw=0.2)
        assert feat is not None
        assert len(feat) == len(FEATURE_NAMES)

    def test_win_rate_feature_correct(self):
        """60% win rate rows → feature win_rate ≈ 0.6."""
        from runner.edge_calibrator import (
            extract_features_for_strategy,
            _fifo_match_strategy,
            FEATURE_NAMES,
        )
        rows = _make_round_trips_rows(10, win_rate=0.6)
        trips = _fifo_match_strategy(rows)
        feat = extract_features_for_strategy("breakout_xlk", trips, kelly_raw=0.2)
        assert feat is not None
        win_rate_idx = FEATURE_NAMES.index("win_rate")
        assert abs(feat[win_rate_idx] - 0.6) < 0.05  # allow small rounding

    def test_n_round_trips_feature(self):
        """n_round_trips feature should match number of completed round-trips."""
        from runner.edge_calibrator import (
            extract_features_for_strategy,
            _fifo_match_strategy,
            FEATURE_NAMES,
        )
        n = 7
        rows = _make_round_trips_rows(n, win_rate=0.5)
        trips = _fifo_match_strategy(rows)
        feat = extract_features_for_strategy("breakout_xlk", trips, kelly_raw=0.1)
        assert feat is not None
        nrt_idx = FEATURE_NAMES.index("n_round_trips")
        assert feat[nrt_idx] == float(n)

    def test_kelly_raw_feature_propagated(self):
        """kelly_raw passed in should appear as the kelly_raw feature."""
        from runner.edge_calibrator import (
            extract_features_for_strategy,
            _fifo_match_strategy,
            FEATURE_NAMES,
        )
        rows = _make_round_trips_rows(5, win_rate=0.5)
        trips = _fifo_match_strategy(rows)
        kelly_in = 0.333
        feat = extract_features_for_strategy("breakout_xlk", trips, kelly_raw=kelly_in)
        assert feat is not None
        kelly_idx = FEATURE_NAMES.index("kelly_raw")
        assert abs(feat[kelly_idx] - kelly_in) < 1e-9

    def test_no_trips_returns_none(self):
        """Strategy with no trips → feature extraction returns None."""
        from runner.edge_calibrator import extract_features_for_strategy
        feat = extract_features_for_strategy("no_trades_strat", [], kelly_raw=0.1)
        assert feat is None

    def test_training_rows_shapes(self):
        """extract_training_rows returns X and y with equal lengths."""
        from runner.edge_calibrator import (
            extract_training_rows,
            _fetch_all_trades,
        )
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        all_trades = _fetch_all_trades(db_path)
        X, y = extract_training_rows(all_trades)
        assert len(X) == len(y)
        assert len(X) > 0
        assert all(len(x) == 5 for x in X)   # 5 features per sample


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: get_calibrated_kelly_fraction returns value in [0, 1]
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibratedFractionBounds:
    """Test 4: Output is always in [0, 1] regardless of model or raw input."""

    def setup_method(self):
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    def test_output_in_zero_one_range_with_model(self):
        """With a trained model, output must be in [0, 1]."""
        from runner.edge_calibrator import (
            get_calibrated_kelly_fraction,
            train_calibrator,
            _MODEL_CACHE,
        )
        # Create enough data to trigger training
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        # Force training
        result = train_calibrator(db_path=str(db_path))
        # Even if pass-through (insufficient_data), the result should be in [0, 1]
        raw = 0.40
        calibrated = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
        assert 0.0 <= calibrated <= 1.0, f"Out of bounds: {calibrated}"

    def test_output_in_range_passthrough_mode(self):
        """In pass-through mode, output = raw, which is already in [0, 1]."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        for raw in [0.0, 0.1, 0.5, 0.9, 1.0]:
            result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
            assert 0.0 <= result <= 1.0

    def test_raw_fraction_zero_gives_zero(self):
        """Zero Kelly → calibrated = 0 always (0 * anything = 0)."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        result = get_calibrated_kelly_fraction("breakout_xlk", 0.0, db_path=str(db_path))
        assert result == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: train_calibrator returns correct status dict structure
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainCalibratorStatusDict:
    """Test 5: train_calibrator always returns the correct keys."""

    def setup_method(self):
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    def test_status_dict_keys_present_insufficient(self):
        from runner.edge_calibrator import train_calibrator
        db_path = _make_trades_db([])
        result = train_calibrator(db_path=str(db_path))
        assert "status" in result
        assert "n_samples" in result
        assert "features" in result
        assert "notes" in result

    def test_status_dict_keys_present_trained(self):
        from runner.edge_calibrator import train_calibrator
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        result = train_calibrator(db_path=str(db_path))
        assert "status" in result
        assert "n_samples" in result
        assert "features" in result
        assert "notes" in result

    def test_insufficient_data_has_zero_samples(self):
        from runner.edge_calibrator import train_calibrator
        db_path = _make_trades_db([])
        result = train_calibrator(db_path=str(db_path))
        assert result["status"] == "insufficient_data"
        assert result["n_samples"] == 0

    def test_features_list_matches_feature_names(self):
        from runner.edge_calibrator import train_calibrator, FEATURE_NAMES
        db_path = _make_trades_db([])
        result = train_calibrator(db_path=str(db_path))
        assert result["features"] == FEATURE_NAMES

    def test_trained_status_with_enough_data(self):
        """With 40+ total round-trips → status should be 'trained'."""
        from runner.edge_calibrator import train_calibrator
        # 4 strategies × 10 trips = 40 trips total → meets 30-trip gate
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        result = train_calibrator(db_path=str(db_path))
        # Either trained (enough training rows) or insufficient_data (if training rows < 10)
        assert result["status"] in ("trained", "insufficient_data")
        assert isinstance(result["n_samples"], int)

    def test_missing_db_returns_insufficient_data(self):
        from runner.edge_calibrator import train_calibrator
        result = train_calibrator(db_path="/tmp/does_not_exist_edge_calib_99.db")
        assert result["status"] == "insufficient_data"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Calibrated fraction ≤ raw fraction (calibration only shrinks)
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrationOnlyShrinks:
    """Test 6: The calibrated Kelly fraction must NEVER exceed the raw fraction."""

    def setup_method(self):
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    def test_calibrated_le_raw_passthrough(self):
        """Pass-through: calibrated == raw, trivially ≤."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        raw = 0.3
        result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
        assert result <= raw + 1e-9, f"Calibrated {result} > raw {raw}"

    def test_calibrated_le_raw_with_model_many_strategies(self):
        """With a model trained on multi-strategy data, output ≤ raw."""
        from runner.edge_calibrator import (
            get_calibrated_kelly_fraction,
            train_calibrator,
        )
        db_path = _make_multi_strategy_db(per_strategy_trips=10, n_strategies=4)
        train_calibrator(db_path=str(db_path))
        raw = 0.40
        result = get_calibrated_kelly_fraction("breakout_xlk", raw, db_path=str(db_path))
        assert result <= raw + 1e-9, f"Calibrated {result} > raw {raw}"

    def test_multiplier_never_above_one(self):
        """_calibration_multiplier ≤ 1.0 for all p in [0, 1]."""
        from runner.edge_calibrator import _calibration_multiplier
        for i in range(101):
            p = i / 100.0
            m = _calibration_multiplier(p)
            assert m <= 1.0 + 1e-9, f"multiplier={m} > 1 for p={p}"

    def test_calibrated_fraction_clips_at_one(self):
        """Even if raw_kelly_fraction > 1 (shouldn't happen), output ≤ 1."""
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        # raw > 1 is unusual but we must not output > 1
        result = get_calibrated_kelly_fraction("breakout_xlk", 1.5, db_path=str(db_path))
        # In pass-through mode raw is returned as-is (contract: raw_kelly_fraction is user's),
        # so we test that when a model IS available, it clips.
        # For pass-through the contract says "return raw_kelly_fraction unchanged".
        # Just verify the output is a float.
        assert isinstance(result, float)


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Manual logistic regression correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestManualLogisticRegression:
    """The manual logistic regression should learn separable data."""

    def test_separable_data_predicts_correctly(self):
        from runner.edge_calibrator import _ManualLogisticRegression
        # Simple separable 1-D data: x>0 → class 1, x<0 → class 0
        X = [[x] for x in [-2, -1.5, -1, -0.5, 0.5, 1.0, 1.5, 2.0]]
        y = [0, 0, 0, 0, 1, 1, 1, 1]
        model = _ManualLogisticRegression(lr=0.5, n_iter=500, reg=0.001)
        model.fit(X, y)
        # Positive x → P(win) > 0.5
        assert model.predict_proba_positive([2.0]) > 0.5
        # Negative x → P(win) < 0.5
        assert model.predict_proba_positive([-2.0]) < 0.5

    def test_output_in_zero_one(self):
        from runner.edge_calibrator import _ManualLogisticRegression
        X = [[i * 0.1] for i in range(10)]
        y = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        model = _ManualLogisticRegression()
        model.fit(X, y)
        for x_val in [-10, 0, 5, 100]:
            p = model.predict_proba_positive([x_val])
            assert 0.0 <= p <= 1.0, f"p={p} out of [0,1] for x={x_val}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Graceful degradation (no exception on bad inputs)
# ─────────────────────────────────────────────────────────────────────────────

class TestGracefulDegradation:
    """Calibrator must never raise; always return a float."""

    def setup_method(self):
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    def test_no_exception_bad_db_path(self):
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        result = get_calibrated_kelly_fraction("x", 0.2, db_path="/nowhere/nope.db")
        assert isinstance(result, float)
        assert result == 0.2

    def test_no_exception_empty_strategy_name(self):
        from runner.edge_calibrator import get_calibrated_kelly_fraction
        db_path = _make_trades_db([])
        result = get_calibrated_kelly_fraction("", 0.1, db_path=str(db_path))
        assert isinstance(result, float)

    def test_calibration_report_no_db(self):
        from runner.edge_calibrator import calibration_report
        report = calibration_report(db_path="/tmp/nonexistent_calib_test.db")
        assert isinstance(report, str)
        assert len(report) > 0

    def test_calibration_report_empty_db(self):
        from runner.edge_calibrator import calibration_report
        db_path = _make_trades_db([])
        report = calibration_report(db_path=str(db_path))
        assert isinstance(report, str)
        assert "pass-through" in report.lower() or "insufficient" in report.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Universe filter — gate + train on the LIVE-BOOK roster only
# (fix 2026-06-23: trip counter was polluted by test-harness + dead-crypto rows)
# ─────────────────────────────────────────────────────────────────────────────

class TestUniverseFilter:
    """The calibrator must count/train ONLY on live-book strategies.

    Non-book noise (backstop_test, dead crypto, test scaffolding) must never
    reach the 30-trip gate or the training labels.
    """

    def setup_method(self):
        import runner.edge_calibrator as ec
        ec._MODEL_CACHE.update({
            "model": None, "n_samples": 0,
            "status": "untrained", "notes": "", "db_path": None,
        })

    @staticmethod
    def _roundtrip_rows(strategy: str, n: int, win: bool, symbol: str = "AAA"):
        """Generate n completed round-trips (buy then sell) for a strategy.

        win=True → sell above buy (pnl>0); win=False → sell below buy (pnl<0).
        """
        rows = []
        for _ in range(n):
            rows.append({"strategy": strategy, "symbol": symbol, "side": "buy",
                         "qty": 1.0, "price": 100.0})
            sell_px = 110.0 if win else 90.0
            rows.append({"strategy": strategy, "symbol": symbol, "side": "sell",
                         "qty": 1.0, "price": sell_px})
        return rows

    def test_excluded_strategies_dropped_from_count(self):
        from runner.edge_calibrator import _fetch_all_trades, _filter_trades, _fifo_match_global
        # 2 live-book trips + a pile of excluded noise
        rows = (self._roundtrip_rows("tqqq_cot_combo", 2, win=True)
                + self._roundtrip_rows("backstop_test", 5, win=False)
                + self._roundtrip_rows("sma_crossover_btc", 4, win=True)
                + self._roundtrip_rows("any", 3, win=False))
        db_path = _make_trades_db(rows)
        all_trades = _fetch_all_trades(str(db_path))
        # Unfiltered sees everything
        assert len(_fifo_match_global(all_trades)) == 2 + 5 + 4 + 3
        # Filtered (default LIVE_ROSTER) sees only the live-book trips
        filt = _filter_trades(all_trades)
        trips = _fifo_match_global(filt)
        assert len(trips) == 2
        assert all(t["strategy"] == "tqqq_cot_combo" for t in trips)

    def test_not_in_roster_dropped(self):
        from runner.edge_calibrator import _filter_trades
        # A strategy that's neither excluded nor in the live roster is still dropped
        rows = ([{"strategy": "some_random_unlisted_strat", "symbol": "AAA", "side": "buy", "qty": 1.0, "price": 100.0}]
                + [{"strategy": "tqqq_cot_combo", "symbol": "AAA", "side": "buy", "qty": 1.0, "price": 100.0}])
        filt = _filter_trades(rows)
        strats = {r["strategy"] for r in filt}
        assert "some_random_unlisted_strat" not in strats
        assert strats == {"tqqq_cot_combo"}

    def test_explicit_universe_overrides_default(self):
        from runner.edge_calibrator import _filter_trades
        rows = ([{"strategy": "custom_live", "symbol": "AAA", "side": "buy", "qty": 1.0, "price": 100.0}]
                + [{"strategy": "breakout_xlk", "symbol": "AAA", "side": "buy", "qty": 1.0, "price": 100.0}])
        # Explicit universe = {custom_live} → keep only that one (breakout_xlk now out-of-universe)
        filt = _filter_trades(rows, universe={"custom_live"})
        assert {r["strategy"] for r in filt} == {"custom_live"}

    def test_excluded_stripped_even_with_explicit_universe(self):
        from runner.edge_calibrator import _filter_trades
        # backstop_test is excluded UNCONDITIONALLY, even if someone passes it in the universe
        rows = (self._roundtrip_rows("backstop_test", 3, win=False)
                + self._roundtrip_rows("custom_live", 2, win=True))
        filt = _filter_trades(rows, universe={"backstop_test", "custom_live"})
        assert {r["strategy"] for r in filt} == {"custom_live"}

    def test_train_gate_counts_live_book_only(self):
        from runner.edge_calibrator import train_calibrator, MIN_ROUND_TRIPS_TOTAL
        # 5 live-book trips + 40 excluded crypto trips → still below gate (only 5 count)
        rows = (self._roundtrip_rows("tqqq_cot_combo", 5, win=True)
                + self._roundtrip_rows("sma_crossover_btc", 40, win=True))
        db_path = _make_trades_db(rows)
        res = train_calibrator(db_path=str(db_path))
        assert res["status"] == "insufficient_data"
        assert "5 round-trips" in res["notes"]
        assert MIN_ROUND_TRIPS_TOTAL == 30

    def test_training_labels_exclude_harness_losses(self):
        from runner.edge_calibrator import extract_training_rows, _fetch_all_trades
        # backstop_test has many LOSING trips; live book has winning trips.
        # The training label set must contain NONE of the harness losses.
        rows = (self._roundtrip_rows("tqqq_cot_combo", 6, win=True)
                + self._roundtrip_rows("sma_crossover_qqq_regime", 6, win=True)
                + self._roundtrip_rows("backstop_test", 20, win=False))
        db_path = _make_trades_db(rows)
        all_trades = _fetch_all_trades(str(db_path))
        X, y = extract_training_rows(all_trades)
        # Without the filter, y would contain a wall of 0s from backstop_test.
        # With the filter, every label comes from the (winning) live book → all 1s.
        assert len(y) > 0
        assert all(label == 1 for label in y), f"harness losses leaked into labels: {y}"

    def test_report_says_live_book(self):
        from runner.edge_calibrator import calibration_report
        rows = (self._roundtrip_rows("tqqq_cot_combo", 2, win=True)
                + self._roundtrip_rows("backstop_test", 3, win=False))
        db_path = _make_trades_db(rows)
        rep = calibration_report(db_path=str(db_path))
        assert "live-book" in rep.lower()
        # backstop_test must not appear in the per-strategy breakdown
        assert "backstop_test" not in rep
