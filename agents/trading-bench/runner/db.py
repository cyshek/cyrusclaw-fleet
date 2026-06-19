"""SQLite schema + helpers for the tournament database.

Tables
------
trades:    every executed paper trade (one row per fill / per intended action).
decisions: every strategy decision, including HOLDs and risk-rejections.
runs:      one row per runner invocation (useful for debugging cron gaps).
"""

from __future__ import annotations

import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(os.environ.get(
    "TOURNAMENT_DB",
    Path(__file__).resolve().parent.parent / "tournament.db",
))


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    strategy        TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    side            TEXT    NOT NULL CHECK (side IN ('buy','sell')),
    qty             REAL    NOT NULL,
    notional_usd    REAL,
    price           REAL,
    alpaca_order_id TEXT,
    status          TEXT    NOT NULL,  -- 'submitted','filled','rejected','error'
    reason          TEXT,               -- strategy's one-liner rationale
    raw             TEXT                -- json blob of alpaca response, optional
);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_ts ON trades(strategy, ts_utc);

CREATE TABLE IF NOT EXISTS decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc       TEXT    NOT NULL,
    strategy     TEXT    NOT NULL,
    symbol       TEXT,
    action       TEXT    NOT NULL,   -- 'buy','sell','hold','skip_risk','skip_killswitch','error'
    qty          REAL,
    notional_usd REAL,
    reason       TEXT,
    detail       TEXT                 -- optional json blob
);
CREATE INDEX IF NOT EXISTS idx_decisions_strategy_ts ON decisions(strategy, ts_utc);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc       TEXT    NOT NULL,
    strategy     TEXT    NOT NULL,
    outcome      TEXT    NOT NULL,   -- 'ok','killswitch','error'
    duration_ms  INTEGER,
    detail       TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_strategy_ts ON runs(strategy, ts_utc);

-- Per-(strategy, symbol) bookkeeping state for stateful exit logic
-- (trailing stops, partial exits, time-stops, etc.). The live runner
-- loads this into position_state[symbol] before calling decide() and
-- saves any mutations back after decide() returns. Cleared when a
-- position transitions to flat. Mirrors the backtester's hoisted
-- position_state dict.
CREATE TABLE IF NOT EXISTS strategy_state (
    strategy     TEXT    NOT NULL,
    symbol       TEXT    NOT NULL,
    state_json   TEXT    NOT NULL,    -- JSON object: extra keys for position_state[symbol]
    updated_utc  TEXT    NOT NULL,
    PRIMARY KEY (strategy, symbol)
);

-- Per-(strategy, symbol) PERSISTENT bookkeeping state that SURVIVES the
-- position going flat. For directives that need to remember things
-- between trades: post-loss cooldowns, pending-entry confirmations,
-- per-symbol fatigue counters, equity-curve awareness, etc.
--
-- Surfaced to strategies as `market_state["strategy_state"]` (a single
-- dict, freely mutable). Persisted automatically after every decide()
-- call in both the live runner and the backtester. NEVER auto-cleared
-- on close/flat — only cleared by explicit operator action or by the
-- strategy assigning {} into market_state["strategy_state"].
--
-- Why a separate table from `strategy_state`: clear lifecycle separation.
-- A future code reader (LLM or human) should be able to reason about
-- "what state does this strategy hold while flat?" without grepping for
-- close-fill branches. One table per lifecycle.
CREATE TABLE IF NOT EXISTS strategy_persistent_state (
    strategy     TEXT    NOT NULL,
    symbol       TEXT    NOT NULL,
    state_json   TEXT    NOT NULL,    -- JSON object
    updated_utc  TEXT    NOT NULL,
    PRIMARY KEY (strategy, symbol)
);

-- ---------------------------------------------------------------
-- Tier 2: LLM-decision audit trail (Bar C.3) + regime classifier
-- canonical-per-day verdict.
--
-- Two tables, intentionally:
--   llm_decisions    : generic per-LLM-call audit log. Every LLM call
--                      (regime classifier, future position sizer, etc.)
--                      writes one row here with the raw request/response.
--                      Replay-safety surface area (Bar C.3 spec literal).
--   regime_decisions : denormalized, one-canonical-row-per-trading-day
--                      verdict consumed by the runner gate. May come from
--                      the LLM (source='llm', with a foreign-key-ish ref
--                      to llm_decisions.id via llm_decision_id) or from
--                      the deterministic code fallback (source='fallback').
--
-- Why split: llm_decisions is append-only and grows with EVERY call (incl.
-- retries, calibration runs, future strategies). regime_decisions is
-- one-row-per-day and is what the runner queries on every tick. Querying
-- a tiny table for the hot path keeps the runner cheap, while the audit
-- log can grow unbounded.
CREATE TABLE IF NOT EXISTS llm_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT    NOT NULL,
    strategy        TEXT    NOT NULL,   -- 'regime_classifier_v1', etc.
    purpose         TEXT    NOT NULL,   -- 'regime_classification', etc.
    model           TEXT    NOT NULL,   -- 'gpt-4o-mini', etc.
    model_version   TEXT,                -- provider-reported (system_fingerprint, etc.)
    temperature     REAL    NOT NULL,
    seed            INTEGER,
    prompt_hash     TEXT    NOT NULL,   -- SHA-256 of frozen prompt+schema
    prompt_version  TEXT    NOT NULL,   -- e.g. 'regime_classifier_v1'
    inputs_json     TEXT    NOT NULL,   -- the features bundle / user msg payload
    response_raw    TEXT,                -- raw model output, pre-parse (NULL on API failure)
    response_parsed TEXT,                -- normalized JSON; NULL if invalid/failed
    cost_usd        REAL,                -- token-based estimate
    latency_ms      INTEGER,
    ok              INTEGER NOT NULL DEFAULT 0,  -- 1 = parsed & validated
    error           TEXT                 -- failure reason (api_error/timeout/parse_fail/schema_fail/missing_key)
);
CREATE INDEX IF NOT EXISTS idx_llm_decisions_strategy_ts ON llm_decisions(strategy, ts_utc);

CREATE TABLE IF NOT EXISTS regime_decisions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_ts       TEXT    NOT NULL,   -- ISO8601 UTC when row was written
    trading_date      TEXT    NOT NULL,   -- YYYY-MM-DD the decision is FOR
    source            TEXT    NOT NULL,   -- 'llm' | 'fallback'
    regime            TEXT    NOT NULL,   -- 'RISK_ON' | 'RISK_OFF' | 'CHOP'
    confidence        REAL,
    rationale         TEXT,
    allow_strategies  TEXT    NOT NULL,   -- JSON array of strategy names
    llm_decision_id   INTEGER,             -- FK-ish into llm_decisions(id); NULL if source='fallback'
    fallback_reason   TEXT                  -- populated when source='fallback'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_regime_decisions_tradingdate
    ON regime_decisions(trading_date);
"""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as c:
        c.executescript(SCHEMA)


def log_run(strategy: str, outcome: str, duration_ms: int,
            detail: Optional[str] = None, db_path: Path = DB_PATH) -> int:
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT INTO runs (ts_utc, strategy, outcome, duration_ms, detail) VALUES (?,?,?,?,?)",
            (now_utc_iso(), strategy, outcome, duration_ms, detail),
        )
        return cur.lastrowid


def log_decision(strategy: str, action: str, *,
                 symbol: Optional[str] = None,
                 qty: Optional[float] = None,
                 notional_usd: Optional[float] = None,
                 reason: Optional[str] = None,
                 detail: Optional[str] = None,
                 db_path: Path = DB_PATH) -> int:
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT INTO decisions (ts_utc, strategy, symbol, action, qty, notional_usd, reason, detail) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (now_utc_iso(), strategy, symbol, action, qty, notional_usd, reason, detail),
        )
        return cur.lastrowid


def log_trade(strategy: str, symbol: str, side: str, qty: float, *,
              notional_usd: Optional[float] = None,
              price: Optional[float] = None,
              alpaca_order_id: Optional[str] = None,
              status: str = "submitted",
              reason: Optional[str] = None,
              raw: Optional[str] = None,
              db_path: Path = DB_PATH) -> int:
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT INTO trades (ts_utc, strategy, symbol, side, qty, notional_usd, price, "
            "alpaca_order_id, status, reason, raw) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (now_utc_iso(), strategy, symbol, side, qty, notional_usd, price,
             alpaca_order_id, status, reason, raw),
        )
        return cur.lastrowid


_OPEN_STATUSES = ("submitted", "filled", "partially_filled", "accepted", "new", "pending_new")

# Terminal Alpaca order statuses. When the reconcile step sees one of these,
# stop polling — the order is settled. ("filled" and "partially_filled" are
# the only ones we ever expect to see as a success outcome; the rest are
# failure modes we still want recorded faithfully.)
TERMINAL_ORDER_STATUSES = (
    "filled",
    "partially_filled",
    "canceled",
    "cancelled",  # alpaca sometimes uses both spellings; play safe
    "expired",
    "rejected",
    "done_for_day",
    "replaced",
    "stopped",
    "suspended",
)


def update_trade_status(trade_id: int, *,
                        status: Optional[str] = None,
                        price: Optional[float] = None,
                        qty: Optional[float] = None,
                        raw: Optional[str] = None,
                        db_path: Path = DB_PATH) -> None:
    """Update an existing trade row with reconciled order state.

    Used by the post-submit reconcile step in the runner, and by the
    one-shot backfill script. Only non-None fields are touched, so the
    same call site can update just `status`, or status+price+qty when a
    fill is observed. Idempotent — safe to call repeatedly on the same
    row (the backfill relies on this).
    """
    sets: list[str] = []
    args: list = []
    if status is not None:
        sets.append("status = ?")
        args.append(status)
    if price is not None:
        sets.append("price = ?")
        args.append(price)
    if qty is not None:
        sets.append("qty = ?")
        args.append(qty)
    if raw is not None:
        sets.append("raw = ?")
        args.append(raw)
    if not sets:
        return
    args.append(trade_id)
    with connect(db_path) as c:
        c.execute(
            f"UPDATE trades SET {', '.join(sets)} WHERE id = ?",
            tuple(args),
        )


def trades_today(strategy: str, db_path: Path = DB_PATH) -> int:
    """Count of submitted/filled trades for `strategy` since UTC midnight."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    with connect(db_path) as c:
        row = c.execute(
            f"SELECT COUNT(*) AS n FROM trades WHERE strategy=? AND ts_utc LIKE ? "
            f"AND status IN ({placeholders})",
            (strategy, f"{today_prefix}%", *_OPEN_STATUSES),
        ).fetchone()
        return int(row["n"])


def strategy_position(strategy: str, symbol: str,
                      db_path: Path = DB_PATH) -> dict:
    """Reconstruct strategy-attributed position from the trade log.

    Returns dict with qty (signed; >0 long), cost_basis_usd, last_price (last fill).
    """
    with connect(db_path) as c:
        placeholders = ",".join("?" * len(_OPEN_STATUSES))
        rows = c.execute(
            f"SELECT side, qty, price, notional_usd FROM trades "
            f"WHERE strategy=? AND symbol=? AND status IN ({placeholders}) "
            f"ORDER BY id ASC",
            (strategy, symbol, *_OPEN_STATUSES),
        ).fetchall()
    qty = 0.0
    cost = 0.0
    last_price = None
    for r in rows:
        q = float(r["qty"] or 0)
        p = float(r["price"]) if r["price"] is not None else None
        n = float(r["notional_usd"] or 0)
        if p:
            last_price = p
        if r["side"] == "buy":
            qty += q
            cost += n if n > 0 else (q * (p or 0))
        elif r["side"] == "sell":
            # Close logic: scale cost basis proportionally; if we sell more than we hold, clamp.
            if qty > 0:
                sell_qty = min(q, qty)
                cost *= max(0.0, (qty - sell_qty) / qty)
                qty -= sell_qty
    return {"qty": qty, "cost_basis_usd": cost, "last_price": last_price}


def position_entry_ts(strategy: str, symbol: str,
                      db_path: Path = DB_PATH) -> Optional[str]:
    """ISO timestamp of the buy that opened the CURRENTLY-OPEN position.

    Walks the trades log in order; tracks every 0 -> >0 qty transition and
    remembers the ts_utc of that opening buy. Scale-in buys while qty>0
    do NOT reset the entry timestamp (we still want "when did this
    position start"). A close back to qty<=0 clears it.

    Returns the entry ts of the still-open position, or None if the
    strategy is currently flat / has no trades.

    Used by `runner/safety_backstop.py` to compute bars_since_entry for
    the holding-time trigger.
    """
    with connect(db_path) as c:
        placeholders = ",".join("?" * len(_OPEN_STATUSES))
        rows = c.execute(
            f"SELECT ts_utc, side, qty FROM trades "
            f"WHERE strategy=? AND symbol=? AND status IN ({placeholders}) "
            f"ORDER BY id ASC",
            (strategy, symbol, *_OPEN_STATUSES),
        ).fetchall()
    qty = 0.0
    entry_ts: Optional[str] = None
    for r in rows:
        try:
            q = float(r["qty"] or 0)
        except (TypeError, ValueError):
            q = 0.0
        if r["side"] == "buy":
            # 0 -> >0 transition: this is a new opening.
            if qty <= 0 and q > 0:
                entry_ts = r["ts_utc"]
            qty += q
        elif r["side"] == "sell":
            if qty > 0:
                qty -= min(q, qty)
                if qty <= 0:
                    # Position closed; entry stamp no longer applies.
                    entry_ts = None
    return entry_ts if qty > 0 else None


def strategy_pnl(strategy: str, *,
                 mark_prices: Optional[dict] = None,
                 db_path: Path = DB_PATH) -> dict:
    """Realized + unrealized PnL for a strategy across all symbols.

    Walks the trade log in time order: each closing sell realizes proportional
    cost basis; remaining open qty is marked-to-market against `mark_prices`
    (dict of {symbol: price}). If a mark is missing, that symbol's open position
    is marked at its last-fill price (so unrealized=0 for that leg).

    Returns:
        {
          'realized_usd': float,
          'unrealized_usd': float,
          'total_pnl_usd': float,
          'gross_buys_usd': float,
          'gross_sells_usd': float,
          'n_trades': int,
          'n_round_trips': int,    # # of closing legs
          'positions': {symbol: {qty, cost_basis_usd, last_price}},
        }
    """
    mark_prices = mark_prices or {}
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT ts_utc, symbol, side, qty, price, notional_usd FROM trades "
            "WHERE strategy=? AND status IN ('submitted','filled') "
            "ORDER BY id ASC",
            (strategy,),
        ).fetchall()

    positions: dict[str, dict] = {}
    realized = 0.0
    gross_buys = 0.0
    gross_sells = 0.0
    n_round_trips = 0

    for r in rows:
        sym = r["symbol"]
        q = float(r["qty"] or 0)
        p = float(r["price"]) if r["price"] is not None else None
        n = float(r["notional_usd"] or 0)
        notional = n if n > 0 else (q * (p or 0))
        pos = positions.setdefault(sym, {"qty": 0.0, "cost_basis_usd": 0.0, "last_price": None})
        if p:
            pos["last_price"] = p
        if r["side"] == "buy":
            gross_buys += notional
            pos["qty"] += q
            pos["cost_basis_usd"] += notional
        elif r["side"] == "sell":
            gross_sells += notional
            if pos["qty"] > 0:
                sell_qty = min(q, pos["qty"])
                # proportional cost basis released
                cost_released = pos["cost_basis_usd"] * (sell_qty / pos["qty"]) if pos["qty"] > 0 else 0.0
                proceeds = sell_qty * (p or 0)
                realized += proceeds - cost_released
                pos["cost_basis_usd"] -= cost_released
                pos["qty"] -= sell_qty
                n_round_trips += 1

    unrealized = 0.0
    for sym, pos in positions.items():
        if pos["qty"] <= 0:
            continue
        mark = mark_prices.get(sym) or pos["last_price"] or 0.0
        mv = pos["qty"] * float(mark)
        unrealized += mv - pos["cost_basis_usd"]

    return {
        "realized_usd": round(realized, 4),
        "unrealized_usd": round(unrealized, 4),
        "total_pnl_usd": round(realized + unrealized, 4),
        "gross_buys_usd": round(gross_buys, 4),
        "gross_sells_usd": round(gross_sells, 4),
        "n_trades": len(rows),
        "n_round_trips": n_round_trips,
        "positions": positions,
    }


# Keys that are broker-truth (refreshed every tick from Alpaca / trade log)
# and must NOT be stored in strategy_state. Custom keys a strategy writes
# to position_state[symbol] (running_max, scaled_out, entry_bar_index, etc.)
# are persisted.
_BROKER_TRUTH_KEYS = {"qty", "market_value", "avg_entry_price"}


def get_strategy_state(strategy: str, symbol: str,
                      db_path: Path = DB_PATH) -> dict:
    """Load strategy bookkeeping state for (strategy, symbol). Returns {} if
    no row exists or the JSON is malformed (treated as fresh state)."""
    with connect(db_path) as c:
        row = c.execute(
            "SELECT state_json FROM strategy_state WHERE strategy = ? AND symbol = ?",
            (strategy, symbol),
        ).fetchone()
    if not row:
        return {}
    try:
        state = json.loads(row["state_json"])
        return state if isinstance(state, dict) else {}
    except (ValueError, TypeError):
        return {}


def save_strategy_state(strategy: str, symbol: str, state: dict,
                       db_path: Path = DB_PATH) -> None:
    """Persist strategy bookkeeping state. Strips broker-truth keys before
    saving so we only persist custom strategy keys."""
    if not isinstance(state, dict):
        return
    persisted = {k: v for k, v in state.items() if k not in _BROKER_TRUTH_KEYS}
    if not persisted:
        clear_strategy_state(strategy, symbol, db_path=db_path)
        return
    payload = json.dumps(persisted, default=str)
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO strategy_state (strategy, symbol, state_json, updated_utc) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(strategy, symbol) DO UPDATE SET "
            "  state_json = excluded.state_json, updated_utc = excluded.updated_utc",
            (strategy, symbol, payload, now_utc_iso()),
        )


def clear_strategy_state(strategy: str, symbol: str,
                        db_path: Path = DB_PATH) -> None:
    """Drop strategy state for (strategy, symbol). Called on flat transition."""
    with connect(db_path) as c:
        c.execute(
            "DELETE FROM strategy_state WHERE strategy = ? AND symbol = ?",
            (strategy, symbol),
        )


# ---------------------------------------------------------------------------
# Cross-flat persistent state
# ---------------------------------------------------------------------------
# Lifecycle is intentionally DIFFERENT from strategy_state:
#   strategy_state           : in-position bookkeeping; cleared on close.
#   strategy_persistent_state: between-trades memory; survives close.
#
# Surfaced to strategies via market_state["strategy_state"]. Persisted
# wholesale after every decide() call. Strategies can clear by assigning
# {} into that key (the save helper will then DELETE the row).


def get_persistent_state(strategy: str, symbol: str,
                         db_path: Path = DB_PATH) -> dict:
    """Load cross-flat persistent state for (strategy, symbol). Returns {}
    if no row exists or the JSON is malformed (treated as fresh state)."""
    with connect(db_path) as c:
        row = c.execute(
            "SELECT state_json FROM strategy_persistent_state "
            "WHERE strategy = ? AND symbol = ?",
            (strategy, symbol),
        ).fetchone()
    if not row:
        return {}
    try:
        state = json.loads(row["state_json"])
        return state if isinstance(state, dict) else {}
    except (ValueError, TypeError):
        return {}


def save_persistent_state(strategy: str, symbol: str, state: dict,
                          db_path: Path = DB_PATH) -> None:
    """Persist cross-flat state. Unlike `save_strategy_state`, no key
    stripping — the strategy owns the full dict. An empty dict triggers
    a DELETE so we don't accumulate stale empty rows."""
    if not isinstance(state, dict):
        return
    if not state:
        clear_persistent_state(strategy, symbol, db_path=db_path)
        return
    payload = json.dumps(state, default=str)
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO strategy_persistent_state "
            "(strategy, symbol, state_json, updated_utc) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(strategy, symbol) DO UPDATE SET "
            "  state_json = excluded.state_json, updated_utc = excluded.updated_utc",
            (strategy, symbol, payload, now_utc_iso()),
        )


def clear_persistent_state(strategy: str, symbol: str,
                           db_path: Path = DB_PATH) -> None:
    """Drop persistent state for (strategy, symbol). NEVER called from
    the live runner's normal flow — only by explicit operator action or
    by save_persistent_state when handed {}."""
    with connect(db_path) as c:
        c.execute(
            "DELETE FROM strategy_persistent_state WHERE strategy = ? AND symbol = ?",
            (strategy, symbol),
        )


# ---------------------------------------------------------------------------
# Tier 2 helpers: llm_decisions + regime_decisions
# ---------------------------------------------------------------------------

def log_llm_decision(*,
                     strategy: str,
                     purpose: str,
                     model: str,
                     temperature: float,
                     prompt_hash: str,
                     prompt_version: str,
                     inputs_json: str,
                     model_version: Optional[str] = None,
                     seed: Optional[int] = None,
                     response_raw: Optional[str] = None,
                     response_parsed: Optional[str] = None,
                     cost_usd: Optional[float] = None,
                     latency_ms: Optional[int] = None,
                     ok: bool = False,
                     error: Optional[str] = None,
                     db_path: Path = DB_PATH) -> int:
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT INTO llm_decisions (ts_utc, strategy, purpose, model, model_version, "
            "temperature, seed, prompt_hash, prompt_version, inputs_json, response_raw, "
            "response_parsed, cost_usd, latency_ms, ok, error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now_utc_iso(), strategy, purpose, model, model_version,
             float(temperature), seed, prompt_hash, prompt_version, inputs_json,
             response_raw, response_parsed, cost_usd, latency_ms,
             1 if ok else 0, error),
        )
        return cur.lastrowid


def save_regime_decision(*,
                         trading_date: str,
                         source: str,
                         regime: str,
                         allow_strategies: list,
                         confidence: Optional[float] = None,
                         rationale: Optional[str] = None,
                         llm_decision_id: Optional[int] = None,
                         fallback_reason: Optional[str] = None,
                         db_path: Path = DB_PATH) -> int:
    """UPSERT a regime decision for `trading_date`. Last writer wins per
    design §8 ("two cron runs same day")."""
    if source not in ("llm", "fallback"):
        raise ValueError(f"source must be 'llm' or 'fallback', got {source!r}")
    if regime not in ("RISK_ON", "RISK_OFF", "CHOP"):
        raise ValueError(f"invalid regime: {regime!r}")
    allow_json = json.dumps(sorted(set(allow_strategies)))
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO regime_decisions (decision_ts, trading_date, source, regime, "
            "confidence, rationale, allow_strategies, llm_decision_id, fallback_reason) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(trading_date) DO UPDATE SET "
            "  decision_ts=excluded.decision_ts, source=excluded.source, regime=excluded.regime, "
            "  confidence=excluded.confidence, rationale=excluded.rationale, "
            "  allow_strategies=excluded.allow_strategies, llm_decision_id=excluded.llm_decision_id, "
            "  fallback_reason=excluded.fallback_reason",
            (now_utc_iso(), trading_date, source, regime, confidence,
             rationale, allow_json, llm_decision_id, fallback_reason),
        )
        row = c.execute(
            "SELECT id FROM regime_decisions WHERE trading_date=?",
            (trading_date,),
        ).fetchone()
        return int(row["id"])


def get_regime_decision_for_date(trading_date: str,
                                 db_path: Path = DB_PATH) -> Optional[dict]:
    """Return the canonical regime decision row for `trading_date` (YYYY-MM-DD),
    or None if no decision exists yet.

    allow_strategies is JSON-decoded back into a list[str]."""
    with connect(db_path) as c:
        row = c.execute(
            "SELECT * FROM regime_decisions WHERE trading_date=?",
            (trading_date,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["allow_strategies"] = json.loads(d.get("allow_strategies") or "[]")
    except (ValueError, TypeError):
        d["allow_strategies"] = []
    return d


def latest_regime_decision(db_path: Path = DB_PATH) -> Optional[dict]:
    """Return the most recent regime_decisions row (by trading_date), or None.
    Used by the runner gate to find a possibly-stale decision before the
    TTL check kicks in."""
    with connect(db_path) as c:
        row = c.execute(
            "SELECT * FROM regime_decisions ORDER BY trading_date DESC LIMIT 1",
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["allow_strategies"] = json.loads(d.get("allow_strategies") or "[]")
    except (ValueError, TypeError):
        d["allow_strategies"] = []
    return d


def known_strategies(db_path: Path = DB_PATH) -> list[str]:
    """Distinct strategies that have ever taken any decision or trade."""
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT DISTINCT strategy FROM decisions UNION SELECT DISTINCT strategy FROM trades"
        ).fetchall()
    return sorted(r["strategy"] for r in rows)


def leaderboard(mark_prices: Optional[dict] = None,
                db_path: Path = DB_PATH) -> list[dict]:
    """Per-strategy PnL summary, sorted by total_pnl_usd desc.

    Caveat: tiny samples. PnL is not Sharpe; do not declare winners until
    n_round_trips >= 30 (Session 2 won't reach that — this is for ranking, not
    judging).
    """
    out = []
    for s in known_strategies(db_path):
        row = strategy_pnl(s, mark_prices=mark_prices, db_path=db_path)
        row["strategy"] = s
        out.append(row)
    out.sort(key=lambda r: r["total_pnl_usd"], reverse=True)
    return out


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
