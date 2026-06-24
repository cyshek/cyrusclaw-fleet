"""Unit tests for runner/position_drift.py — the position-level reconcile guard.

Focus on the two realism guards (no network, no Alpaca):
  1. SYNTHETIC EXCLUSION: test/seed strategies + fake order ids must NOT count toward
     the DB net position (they never hit the broker).
  2. ASSET-CLASS TOLERANCE / net math: buys add, sells subtract, per symbol.
"""
from __future__ import annotations

import importlib
import sqlite3

pd = importlib.import_module("runner.position_drift")


def _make_trades_db(tmp_path, rows):
    db = str(tmp_path / "drift_test.db")
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE trades (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts_utc TEXT, strategy TEXT, symbol TEXT, side TEXT,
               qty REAL, notional_usd REAL, price REAL,
               alpaca_order_id TEXT, status TEXT, reason TEXT, raw TEXT)"""
    )
    for r in rows:
        conn.execute(
            "INSERT INTO trades (strategy, symbol, side, qty, alpaca_order_id, status) "
            "VALUES (?,?,?,?,?,?)",
            (r["strategy"], r["symbol"], r["side"], r["qty"],
             r.get("oid", "11111111-2222-3333-4444-555555555555"), r.get("status", "filled")),
        )
    conn.commit()
    conn.close()
    return db


REAL_OID = "11111111-2222-3333-4444-555555555555"


def test_synthetic_strategies_excluded(tmp_path):
    db = _make_trades_db(tmp_path, [
        {"strategy": "backstop_test", "symbol": "SYM", "side": "buy", "qty": 1.0, "oid": "ord-seed"},
        {"strategy": "any", "symbol": "SYM", "side": "buy", "qty": 0.5, "oid": "order-1"},
        {"strategy": "bp2", "symbol": "SYM", "side": "buy", "qty": 1.0, "oid": "ord-seed"},
    ])
    net = pd.compute_db_net(db_path=db)
    assert "SYM" not in net  # all synthetic -> nothing real survives


def test_fake_order_id_excluded_even_for_real_strategy(tmp_path):
    # A real strategy name but a non-UUID order id is still a seed/test row.
    db = _make_trades_db(tmp_path, [
        {"strategy": "allocator_blend", "symbol": "TQQQ", "side": "buy", "qty": 2.0, "oid": "ord-seed"},
        {"strategy": "allocator_blend", "symbol": "TQQQ", "side": "buy", "qty": 3.0, "oid": REAL_OID},
    ])
    net = pd.compute_db_net(db_path=db)
    assert net["TQQQ"] == 3.0  # only the real-UUID row counts


def test_net_math_buys_minus_sells(tmp_path):
    db = _make_trades_db(tmp_path, [
        {"strategy": "breakout_xlk", "symbol": "XLK", "side": "buy", "qty": 5.0, "oid": REAL_OID},
        {"strategy": "breakout_xlk", "symbol": "XLK", "side": "sell", "qty": 2.0, "oid": REAL_OID},
    ])
    net = pd.compute_db_net(db_path=db)
    assert abs(net["XLK"] - 3.0) < 1e-12


def test_non_filled_rows_ignored(tmp_path):
    db = _make_trades_db(tmp_path, [
        {"strategy": "breakout_xlk", "symbol": "XLK", "side": "buy", "qty": 5.0, "oid": REAL_OID, "status": "filled"},
        {"strategy": "breakout_xlk", "symbol": "XLK", "side": "buy", "qty": 9.0, "oid": REAL_OID, "status": "pending_new"},
    ])
    net = pd.compute_db_net(db_path=db)
    assert net["XLK"] == 5.0  # pending row excluded


def test_asset_class_detection():
    assert pd._is_crypto("BTC/USD") is True
    assert pd._is_crypto("ETH/USD") is True
    assert pd._is_crypto("TQQQ") is False
    assert pd._is_crypto("SPY") is False


def test_synthetic_row_helper():
    assert pd._is_synthetic_row("backstop_test", REAL_OID) is True
    assert pd._is_synthetic_row("allocator_blend", "order-1") is True
    assert pd._is_synthetic_row("allocator_blend", None) is True
    assert pd._is_synthetic_row("allocator_blend", "short") is True
    assert pd._is_synthetic_row("allocator_blend", REAL_OID) is False
