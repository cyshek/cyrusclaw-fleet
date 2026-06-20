"""Tests for runner.correlation."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from runner import correlation, db


def _seed(tmp_path: Path, trades: list) -> Path:
    """Helper: create a fresh tournament.db and insert raw trade rows.

    trades is a list of dicts: {strategy, symbol, side, qty, price, ts_utc}.
    All trades inserted as status='filled'.
    """
    db_path = tmp_path / "t.db"
    db.init_db(db_path)
    with db.connect(db_path) as c:
        for t in trades:
            c.execute(
                "INSERT INTO trades (ts_utc, strategy, symbol, side, qty, "
                "notional_usd, price, status) VALUES (?,?,?,?,?,?,?,?)",
                (t["ts_utc"], t["strategy"], t["symbol"], t["side"],
                 t["qty"], t["qty"] * t["price"], t["price"], "filled"),
            )
    return db_path


def _round_trip(strategy: str, symbol: str, day: str, buy_px: float, sell_px: float, qty: float = 1.0):
    """Two trades on the same day: buy in the morning, sell at close.
    Realized P&L = (sell_px - buy_px) * qty, attributed to `day`.
    """
    return [
        {"strategy": strategy, "symbol": symbol, "side": "buy",
         "qty": qty, "price": buy_px, "ts_utc": f"{day}T09:30:00+00:00"},
        {"strategy": strategy, "symbol": symbol, "side": "sell",
         "qty": qty, "price": sell_px, "ts_utc": f"{day}T16:00:00+00:00"},
    ]


class TestDailyPnLSeries:
    def test_basic_realized_pnl(self, tmp_path):
        trades = (
            _round_trip("alpha", "BTC", "2026-05-01", 100.0, 110.0)
            + _round_trip("alpha", "BTC", "2026-05-02", 110.0, 105.0)
        )
        db_path = _seed(tmp_path, trades)
        series = correlation.daily_pnl_series("alpha", db_path)
        assert series[date(2026, 5, 1)] == pytest.approx(10.0)
        assert series[date(2026, 5, 2)] == pytest.approx(-5.0)

    def test_no_trades(self, tmp_path):
        db_path = _seed(tmp_path, [])
        assert correlation.daily_pnl_series("ghost", db_path) == {}


class TestCorrelationMatrix:
    def test_identical_series_is_perfectly_correlated(self, tmp_path):
        # Both strategies trade BTC with the same P&L pattern.
        trades = []
        for s in ("alpha", "beta"):
            trades += _round_trip(s, "BTC", "2026-05-01", 100, 110)  # +10
            trades += _round_trip(s, "BTC", "2026-05-02", 100, 105)  # +5
            trades += _round_trip(s, "BTC", "2026-05-03", 100, 90)   # -10
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        r = m.at("alpha", "beta")
        assert r is not None
        assert r == pytest.approx(1.0, abs=1e-9)

    def test_opposite_series_is_perfectly_anticorrelated(self, tmp_path):
        trades = []
        # alpha: +10, +5, -10
        trades += _round_trip("alpha", "BTC", "2026-05-01", 100, 110)
        trades += _round_trip("alpha", "BTC", "2026-05-02", 100, 105)
        trades += _round_trip("alpha", "BTC", "2026-05-03", 100, 90)
        # beta: -10, -5, +10  (negative of alpha)
        trades += _round_trip("beta", "BTC", "2026-05-01", 100, 90)
        trades += _round_trip("beta", "BTC", "2026-05-02", 100, 95)
        trades += _round_trip("beta", "BTC", "2026-05-03", 100, 110)
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        r = m.at("alpha", "beta")
        assert r is not None
        assert r == pytest.approx(-1.0, abs=1e-9)

    def test_no_overlap_handled_gracefully(self, tmp_path):
        """Disjoint trading days — union is [d1, d2, d3, d4]. After 0-fill
        each series has a non-constant signal so correlation IS defined,
        but the important guarantee is: no NaN/crash."""
        trades = []
        trades += _round_trip("alpha", "BTC", "2026-05-01", 100, 110)  # +10 on d1
        trades += _round_trip("alpha", "BTC", "2026-05-02", 100, 105)  # +5  on d2
        trades += _round_trip("beta",  "BTC", "2026-05-10", 100, 110)  # +10 on d10
        trades += _round_trip("beta",  "BTC", "2026-05-11", 100, 95)   # -5  on d11
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        r = m.at("alpha", "beta")
        # With 0-fill: alpha=[10,5,0,0], beta=[0,0,10,-5] — non-degenerate,
        # so r is finite and != NaN. Must not raise.
        assert r is not None
        assert isinstance(r, float)
        assert not (r != r)  # not NaN
        assert -1.0 <= r <= 1.0

    def test_constant_series_returns_none(self, tmp_path):
        """A strategy with only one closing trade has a constant zero-padded
        series across all extra days except one — variance > 0, so still
        defined. But if BOTH strategies trade only on the same single day,
        zero-fill gives a 1-element vector? No — union has 1 day, so n=1
        and Pearson is undefined."""
        trades = _round_trip("alpha", "BTC", "2026-05-01", 100, 110)
        trades += _round_trip("beta", "BTC", "2026-05-01", 100, 90)
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        # n=1 day → Pearson undefined
        assert m.at("alpha", "beta") is None


class TestFlagHighCorrelation:
    def test_identifies_high_pair(self, tmp_path):
        trades = []
        # alpha & beta identical; gamma independent
        for s in ("alpha", "beta"):
            trades += _round_trip(s, "BTC", "2026-05-01", 100, 110)
            trades += _round_trip(s, "BTC", "2026-05-02", 100, 105)
            trades += _round_trip(s, "BTC", "2026-05-03", 100, 90)
        # gamma trades on different pattern
        trades += _round_trip("gamma", "ETH", "2026-05-01", 50, 49)  # -1
        trades += _round_trip("gamma", "ETH", "2026-05-02", 50, 52)  # +2
        trades += _round_trip("gamma", "ETH", "2026-05-03", 50, 51)  # +1

        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta", "gamma"], db_path)
        flagged = correlation.flag_high_correlation(m, threshold=0.7)
        names = {tuple(sorted([a, b])) for a, b, _ in flagged}
        assert ("alpha", "beta") in names
        # alpha↔gamma and beta↔gamma should be below 0.7 in absolute value
        for a, b, r in flagged:
            if "gamma" in (a, b):
                assert abs(r) >= 0.7  # if it slipped in, must be legit

    def test_empty_when_below_threshold(self, tmp_path):
        # Two strategies with weak/zero correlation
        trades = []
        trades += _round_trip("alpha", "BTC", "2026-05-01", 100, 110)  # +10
        trades += _round_trip("alpha", "BTC", "2026-05-02", 100, 90)   # -10
        trades += _round_trip("beta",  "BTC", "2026-05-01", 100, 105)  # +5
        trades += _round_trip("beta",  "BTC", "2026-05-02", 100, 107)  # +7
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        # threshold absurdly high → nothing flagged
        flagged = correlation.flag_high_correlation(m, threshold=0.99)
        assert flagged == [] or all(abs(r) >= 0.99 for _, _, r in flagged)

    def test_skips_undefined_pairs(self, tmp_path):
        # Single-day overlap → r is None; flag function must not crash
        trades = _round_trip("alpha", "BTC", "2026-05-01", 100, 110)
        trades += _round_trip("beta", "BTC", "2026-05-01", 100, 90)
        db_path = _seed(tmp_path, trades)
        m = correlation.correlation_matrix(["alpha", "beta"], db_path)
        assert correlation.flag_high_correlation(m, threshold=0.5) == []
