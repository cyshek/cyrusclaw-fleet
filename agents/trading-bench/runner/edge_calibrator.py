"""Edge-Calibration Meta-Model.

Wraps the raw Kelly fraction with a trained logistic regression that
predicts "is this edge likely to hold OOS?" and scales Kelly down when
the model is uncertain.

Architecture
------------
1. Feature extraction from the `trades` table (per-round-trip history).
2. Logistic regression (sklearn when available, manual fallback).
3. Calibration multiplier = 2*P(win|features) - 1, clipped to [0, 1].
   → P=0.5 → multiplier=0  (fully uncertain → Kelly shrinks to 0)
   → P=0.75 → multiplier=0.5
   → P=1.0  → multiplier=1.0 (fully confident → Kelly unchanged)
4. get_calibrated_kelly_fraction: raw_fraction * multiplier.

Minimum data gate
-----------------
If total round-trips across ALL strategies < 30 → pass-through (return raw).
If training fails for any reason → pass-through + log warning.

Graceful degradation
--------------------
Every call site catches Exception broadly and falls back to raw_kelly_fraction.
The runner MUST NOT crash due to calibrator errors.
"""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Minimum data gate
# ─────────────────────────────────────────────────────────────────────────────

MIN_ROUND_TRIPS_TOTAL = 30   # across the LIVE-BOOK roster before we bother training

# ─────────────────────────────────────────────────────────────────────────────
# Universe filter — gate + train on the LIVE tournament roster only
# ─────────────────────────────────────────────────────────────────────────────
#
# WHY: the calibrator predicts "is THIS live strategy's edge likely to hold?"
# and scales its live Kelly sizing. If we count/train on non-book trips, the
# model is fit on outcomes it will never size. tournament.db historically
# accumulated test-harness + dead-crypto rows that have nothing to do with the
# live equity book; without a filter the 30-trip gate opens early on garbage
# and the eventual fit is poisoned by e.g. backstop_test's synthetic −$120
# losses and closed crypto noise. (Found 2026-06-23; fix greenlit by main.)
#
# SOURCE OF TRUTH: the universe is whatever the caller (the runner) trades.
# Callers SHOULD pass `universe=<set of live strategy names>` explicitly so this
# stays correct as the roster evolves. When no universe is supplied we fall
# back to LIVE_ROSTER below (kept in sync with the active cron_tick.sh line),
# and we ALWAYS strip EXCLUDE_STRATEGIES (known non-book noise) as a belt-and-
# suspenders guard even when an explicit universe is given.

# Live equity book — mirrors the active crontab `cron_tick.sh ...` invocation.
# Keep in sync if the roster changes (it's the default only; explicit
# `universe=` from the runner overrides this).
LIVE_ROSTER: frozenset[str] = frozenset({
    "breakout_xlk",
    "sma_crossover_qqq",
    "breakout_xlk_regime",
    "sma_crossover_qqq_regime",
    "sma_crossover_qqq_rth",
    "breakout_xlk__mut_c382b1",
    "leveraged_long_trend_paper",
    "rsi_oversold_spy",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
    "tqqq_cot_combo",
    "allocator_blend",
})

# Known non-book strategy names that must NEVER enter the gate or training set,
# regardless of universe: synthetic test harnesses + dead crypto legs. Stripped
# unconditionally (even when an explicit universe is passed) so a stray test row
# can't sneak in.
EXCLUDE_STRATEGIES: frozenset[str] = frozenset({
    "backstop_test",   # synthetic risk-backstop harness (deliberate -$120)
    "any",             # test scaffolding
    "bp2",             # test scaffolding
    "sma_crossover_btc",   # dead crypto lane (closed)
    "buy_and_hold_btc",    # dead crypto lane (closed)
    "breakout_ltc",        # dead crypto lane (closed)
    "momentum_sol",        # dead crypto lane (closed)
    "rsi_mean_revert_eth", # dead crypto lane (closed)
})


def _resolve_universe(universe: Optional[set] = None) -> Optional[frozenset]:
    """Resolve the effective allow-list of strategy names.

    - explicit `universe` (from the caller/runner) wins;
    - else fall back to LIVE_ROSTER.
    Returns None only if an explicit EMPTY set was passed *and* no fallback is
    wanted — callers pass non-empty sets in practice, so this normally returns a
    concrete allow-list. EXCLUDE_STRATEGIES is applied separately and always.
    """
    if universe is not None:
        # Respect an explicitly-provided roster (even a non-default one).
        return frozenset(universe)
    return LIVE_ROSTER


def _filter_trades(all_trades: list[dict], universe: Optional[set] = None) -> list[dict]:
    """Drop trades whose strategy is not in the live universe / is excluded.

    The single choke point so count, training, and prediction all see the same
    clean set. EXCLUDE_STRATEGIES is stripped unconditionally; the allow-list is
    applied when one is resolvable.
    """
    allow = _resolve_universe(universe)
    out = []
    for row in all_trades:
        strat = row.get("strategy", "")
        if strat in EXCLUDE_STRATEGIES:
            continue
        if allow is not None and strat not in allow:
            continue
        out.append(row)
    return out

# ─────────────────────────────────────────────────────────────────────────────
# Feature names (in order – must be consistent across extract + train + predict)
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    "n_round_trips",          # total round-trips for this strategy
    "win_rate",               # fraction of winning trips
    "avg_hold_bars",          # avg bars held (proxy for regime exposure)
    "kelly_raw",              # raw Kelly fraction at the time of trade
    "recent_vs_all_winrate",  # win_rate last 10 trips / overall win_rate
]

# ─────────────────────────────────────────────────────────────────────────────
# Internal: sklearn / manual logistic regression
# ─────────────────────────────────────────────────────────────────────────────

_SKLEARN_AVAILABLE: Optional[bool] = None


def _check_sklearn() -> bool:
    global _SKLEARN_AVAILABLE
    if _SKLEARN_AVAILABLE is None:
        try:
            import sklearn  # noqa: F401
            _SKLEARN_AVAILABLE = True
        except ImportError:
            _SKLEARN_AVAILABLE = False
    return _SKLEARN_AVAILABLE


# ─────────────────────────────────────────────────────────────────────────────
# Manual logistic regression (fallback when sklearn unavailable)
# ─────────────────────────────────────────────────────────────────────────────

import math as _math


def _sigmoid(x: float) -> float:
    # Numerically stable sigmoid.
    if x >= 0:
        z = _math.exp(-x)
        return 1.0 / (1.0 + z)
    z = _math.exp(x)
    return z / (1.0 + z)


class _ManualLogisticRegression:
    """Minimal logistic regression — gradient descent, 200 iterations, L2 reg."""

    def __init__(self, lr: float = 0.1, n_iter: int = 200, reg: float = 0.01):
        self.lr = lr
        self.n_iter = n_iter
        self.reg = reg
        self.weights_: list[float] = []
        self.bias_: float = 0.0
        self._n_features: int = 0
        self._mean: list[float] = []
        self._std: list[float] = []

    def _standardize(self, X: list[list[float]]) -> list[list[float]]:
        n_feat = len(X[0])
        means = [sum(row[j] for row in X) / len(X) for j in range(n_feat)]
        stds  = [
            _math.sqrt(sum((row[j] - means[j]) ** 2 for row in X) / max(1, len(X)))
            for j in range(n_feat)
        ]
        stds = [s if s > 1e-8 else 1.0 for s in stds]
        return [[( row[j] - means[j] ) / stds[j] for j in range(n_feat)] for row in X], means, stds

    def fit(self, X: list[list[float]], y: list[int]) -> "_ManualLogisticRegression":
        n_samples = len(X)
        n_feat = len(X[0])
        Xs, self._mean, self._std = self._standardize(X)
        self._n_features = n_feat
        w = [0.0] * n_feat
        b = 0.0
        lr, reg = self.lr, self.reg
        for _ in range(self.n_iter):
            dw = [0.0] * n_feat
            db = 0.0
            for i in range(n_samples):
                z = sum(w[j] * Xs[i][j] for j in range(n_feat)) + b
                p = _sigmoid(z)
                err = p - y[i]
                for j in range(n_feat):
                    dw[j] += err * Xs[i][j]
                db += err
            for j in range(n_feat):
                w[j] = w[j] - lr * (dw[j] / n_samples + reg * w[j])
            b = b - lr * (db / n_samples)
        self.weights_ = w
        self.bias_ = b
        return self

    def predict_proba_positive(self, x: list[float]) -> float:
        """P(class=1) for a single sample."""
        # standardize
        xs = [(x[j] - self._mean[j]) / self._std[j] for j in range(self._n_features)]
        z = sum(self.weights_[j] * xs[j] for j in range(self._n_features)) + self.bias_
        return _sigmoid(z)


# ─────────────────────────────────────────────────────────────────────────────
# Feature extraction
# ─────────────────────────────────────────────────────────────────────────────

_OPEN_STATUSES = ("submitted", "filled", "partially_filled", "accepted", "new", "pending_new")


def _fetch_all_trades(db_path: Path) -> list[dict]:
    """Return all filled/submitted trades across all strategies, ordered by id ASC."""
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT id, ts_utc, strategy, symbol, side, qty, price, notional_usd "
            f"FROM trades WHERE status IN ({placeholders}) ORDER BY id ASC",
            _OPEN_STATUSES,
        ).fetchall()
    return [dict(r) for r in rows]


def _fifo_match_strategy(rows: list[dict]) -> list[dict]:
    """FIFO-match buy/sell rows into round-trips.

    Each returned dict:
        strategy, symbol, buy_id, sell_id, buy_price, sell_price,
        qty, pnl, pnl_pct, hold_bars (None — no bar data available here)
    """
    buy_queue: list[dict] = []  # [{qty, price, notional, id, ts}]
    trips: list[dict] = []

    for row in rows:
        side = row["side"]
        try:
            q = float(row["qty"] or 0)
        except (TypeError, ValueError):
            q = 0.0
        try:
            p = float(row["price"]) if row["price"] is not None else None
        except (TypeError, ValueError):
            p = None
        try:
            n = float(row["notional_usd"] or 0)
        except (TypeError, ValueError):
            n = 0.0

        if q <= 0:
            continue

        cost_per_unit = (n / q) if q > 0 and n > 0 else (p or 0.0)

        if side == "buy":
            buy_queue.append({
                "qty": q, "cpu": cost_per_unit, "price": p, "id": row.get("id", 0)
            })

        elif side == "sell":
            remaining = q
            while remaining > 1e-10 and buy_queue:
                bq = buy_queue[0]
                matched = min(remaining, bq["qty"])
                proceeds = matched * (p or 0.0)
                cost = matched * bq["cpu"]
                pnl = proceeds - cost
                entry_price = bq["cpu"]
                pnl_pct = (pnl / cost) if cost > 1e-10 else 0.0
                trips.append({
                    "strategy": row.get("strategy", ""),
                    "symbol": row.get("symbol", ""),
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "entry_price": entry_price,
                    "exit_price": p,
                    "qty": matched,
                })
                remaining -= matched
                if matched >= bq["qty"] - 1e-10:
                    buy_queue.pop(0)
                else:
                    buy_queue[0] = {**bq, "qty": bq["qty"] - matched}

    return trips


def extract_features_for_strategy(
    strategy_name: str,
    all_trips: list[dict],
    kelly_raw: float = 0.0,
) -> Optional[list[float]]:
    """Extract a feature vector for a strategy using completed round-trips.

    Returns None if insufficient data (< 1 round-trip).
    """
    trips = [t for t in all_trips if t["strategy"] == strategy_name]
    n = len(trips)
    if n < 1:
        return None

    wins = [t for t in trips if t["pnl"] > 0]
    win_rate = len(wins) / n

    # avg_hold_bars: we don't track bars held in the trades table, so we
    # use 1.0 as a neutral placeholder when bar data is unavailable.
    avg_hold_bars = 1.0

    # recent_vs_all: last 10 trips / overall win rate
    recent = trips[-10:]
    recent_wins = sum(1 for t in recent if t["pnl"] > 0)
    recent_wr = recent_wins / len(recent) if recent else win_rate
    recent_vs_all = (recent_wr / win_rate) if win_rate > 1e-8 else 1.0
    # Cap to avoid extreme ratios from tiny samples
    recent_vs_all = min(recent_vs_all, 3.0)

    return [
        float(n),
        win_rate,
        avg_hold_bars,
        kelly_raw,
        recent_vs_all,
    ]


def extract_training_rows(
    all_trades: list[dict], universe: Optional[set] = None
) -> tuple[list[list[float]], list[int]]:
    """Build (X, y) training set from all round-trips across LIVE-BOOK strategies.

    y=1 if pnl > 0, y=0 otherwise.
    X is the feature vector at the time of each trip (using history up to that trip).
    Non-book / excluded strategies are stripped via the universe filter so the
    label set is never poisoned by synthetic-harness or dead-crypto outcomes.
    """
    all_trades = _filter_trades(all_trades, universe)
    X: list[list[float]] = []
    y_labels: list[int] = []

    # Group trades by strategy
    strategies: dict[str, list[dict]] = {}
    for row in all_trades:
        strategies.setdefault(row["strategy"], []).append(row)

    for strat_name, strat_trades in strategies.items():
        trips = _fifo_match_strategy(strat_trades)
        n_total = len(trips)
        if n_total < 2:
            continue  # need at least 2 to have a "before/after" split

        for i, trip in enumerate(trips):
            history = trips[:i]  # trips up to (not including) this one
            nh = len(history)
            if nh < 1:
                continue  # need at least 1 prior trip for features

            h_wins = [t for t in history if t["pnl"] > 0]
            win_rate = len(h_wins) / nh

            recent = history[-10:]
            rw = sum(1 for t in recent if t["pnl"] > 0)
            recent_wr = rw / len(recent) if recent else win_rate
            recent_vs_all = (recent_wr / win_rate) if win_rate > 1e-8 else 1.0
            recent_vs_all = min(recent_vs_all, 3.0)

            feat = [
                float(nh),
                win_rate,
                1.0,            # avg_hold_bars placeholder
                0.0,            # kelly_raw placeholder (not available at trip time)
                recent_vs_all,
            ]
            X.append(feat)
            y_labels.append(1 if trip["pnl"] > 0 else 0)

    return X, y_labels


# ─────────────────────────────────────────────────────────────────────────────
# Model store — in-process singleton cache
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_CACHE: dict[str, Any] = {
    "model": None,          # trained model object or None
    "n_samples": 0,
    "status": "untrained",  # "trained" | "insufficient_data" | "untrained"
    "notes": "",
    "db_path": None,        # Path the cache was trained on
}


def _calibration_multiplier(p_win: float) -> float:
    """Convert P(win) → calibration multiplier in [0, 1].

    Formula: 2*P(win) - 1, clipped to [0, 1].
    P=0.5 → 0.0 (maximum shrinkage)
    P=0.75 → 0.5 (halves Kelly)
    P=1.0 → 1.0 (no shrinkage)
    """
    raw = 2.0 * p_win - 1.0
    return max(0.0, min(1.0, raw))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def train_calibrator(db_path: str = "tournament.db", universe: Optional[set] = None) -> dict:
    """Train the meta-model on existing round-trip data.

    Args:
        db_path: tournament.db path.
        universe: optional explicit allow-list of live strategy names. When
            omitted, falls back to LIVE_ROSTER. Non-book strategies
            (EXCLUDE_STRATEGIES) are always stripped. The 30-trip gate and the
            training set therefore reflect the LIVE BOOK only.

    Returns:
        {
            "status": "trained" | "insufficient_data",
            "n_samples": int,
            "features": [...feature names...],
            "notes": str
        }
    """
    db_path = Path(db_path)
    result = {
        "status": "insufficient_data",
        "n_samples": 0,
        "features": FEATURE_NAMES,
        "notes": "",
    }

    try:
        if not db_path.exists():
            result["notes"] = f"DB not found: {db_path} — calibrator in pass-through mode"
            logger.warning(result["notes"])
            _update_cache(result, None)
            return result

        all_trades = _fetch_all_trades(db_path)
        # Restrict to the live book BEFORE counting / training so the gate and
        # the model never see test-harness or dead-crypto trips.
        all_trades = _filter_trades(all_trades, universe)

        # Count total round-trips across the LIVE-BOOK strategies
        all_trips = _fifo_match_global(all_trades)
        n_total_trips = len(all_trips)

        if n_total_trips < MIN_ROUND_TRIPS_TOTAL:
            result["notes"] = (
                f"insufficient data: {n_total_trips} round-trips total "
                f"(need {MIN_ROUND_TRIPS_TOTAL}); calibrator in pass-through mode"
            )
            logger.info(result["notes"])
            _update_cache(result, None)
            return result

        # Build training set (all_trades already universe-filtered above; pass
        # universe through so the idempotent re-filter uses the same roster)
        X, y = extract_training_rows(all_trades, universe)
        n_samples = len(X)

        if n_samples < 10:
            result["notes"] = (
                f"insufficient training rows: {n_samples} "
                f"(need ≥10 for a meaningful fit); pass-through mode"
            )
            logger.info(result["notes"])
            _update_cache(result, None)
            return result

        # Fit model
        if _check_sklearn():
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(max_iter=200, C=10.0, solver="lbfgs")
            model.fit(X, y)
            model_type = "sklearn LogisticRegression"
        else:
            model = _ManualLogisticRegression(lr=0.1, n_iter=200, reg=0.1)
            model.fit(X, y)
            model_type = "manual LogisticRegression"

        result["status"] = "trained"
        result["n_samples"] = n_samples
        result["notes"] = (
            f"trained {model_type} on {n_samples} samples "
            f"({n_total_trips} total round-trips, {len(set(t['strategy'] for t in all_trips))} strategies)"
        )
        logger.info(result["notes"])
        _update_cache(result, model, db_path=db_path)
        return result

    except Exception as exc:  # noqa: BLE001
        result["notes"] = f"training error (pass-through): {exc}"
        logger.warning(result["notes"])
        _update_cache(result, None)
        return result


def _fifo_match_global(all_trades: list[dict]) -> list[dict]:
    """FIFO match per (strategy, symbol) combination."""
    groups: dict[tuple, list] = {}
    for row in all_trades:
        key = (row["strategy"], row["symbol"])
        groups.setdefault(key, []).append(row)
    all_trips = []
    for rows in groups.values():
        all_trips.extend(_fifo_match_strategy(rows))
    return all_trips


def _update_cache(result: dict, model: Any, db_path: Optional[Path] = None) -> None:
    _MODEL_CACHE["model"] = model
    _MODEL_CACHE["n_samples"] = result.get("n_samples", 0)
    _MODEL_CACHE["status"] = result.get("status", "insufficient_data")
    _MODEL_CACHE["notes"] = result.get("notes", "")
    _MODEL_CACHE["db_path"] = db_path


def get_calibrated_kelly_fraction(
    strategy_name: str,
    raw_kelly_fraction: float,
    db_path: str = "tournament.db",
    universe: Optional[set] = None,
) -> float:
    """Return a calibrated Kelly fraction.

    If insufficient data → returns raw_kelly_fraction unchanged (pass-through).
    If model trained → returns raw_kelly_fraction * calibration_multiplier (capped 0.0–1.0).
    On any error → returns raw_kelly_fraction (graceful degradation, never crashes runner).
    """
    try:
        db_p = Path(db_path)

        # Auto-train (or check cache) — lazy, first-call training.
        if _MODEL_CACHE["model"] is None and _MODEL_CACHE["status"] == "untrained":
            train_calibrator(db_path, universe=universe)

        model = _MODEL_CACHE["model"]
        if model is None:
            # Pass-through: insufficient data or training failed
            logger.debug(
                "edge_calibrator: pass-through for %s (no model: %s)",
                strategy_name,
                _MODEL_CACHE["notes"],
            )
            return float(raw_kelly_fraction)

        # Extract features for this strategy using current DB state
        try:
            all_trades = _fetch_all_trades(db_p)
            all_trades = _filter_trades(all_trades, universe)
            all_trips = _fifo_match_global(all_trades)
            feat = extract_features_for_strategy(strategy_name, all_trips, kelly_raw=raw_kelly_fraction)
        except Exception as feat_err:  # noqa: BLE001
            logger.warning("edge_calibrator: feature extraction failed: %s", feat_err)
            return float(raw_kelly_fraction)

        if feat is None:
            # Strategy has no round-trips → can't calibrate → pass-through
            logger.debug(
                "edge_calibrator: no round-trips for %s → pass-through", strategy_name
            )
            return float(raw_kelly_fraction)

        # Predict P(win)
        if _check_sklearn():
            p_win = float(model.predict_proba([feat])[0][1])
        else:
            p_win = model.predict_proba_positive(feat)

        multiplier = _calibration_multiplier(p_win)
        calibrated = float(raw_kelly_fraction) * multiplier
        calibrated = max(0.0, min(1.0, calibrated))

        logger.info(
            "edge_calibrator [%s]: raw=%.4f p_win=%.3f multiplier=%.3f → calibrated=%.4f",
            strategy_name,
            raw_kelly_fraction,
            p_win,
            multiplier,
            calibrated,
        )
        return calibrated

    except Exception as exc:  # noqa: BLE001
        # Never crash the runner
        logger.warning("edge_calibrator: unexpected error (pass-through): %s", exc)
        return float(raw_kelly_fraction)


def calibration_report(db_path: str = "tournament.db", universe: Optional[set] = None) -> str:
    """Human-readable calibration status report (LIVE-BOOK universe)."""
    db_p = Path(db_path)

    lines = ["=== Edge Calibrator Status ==="]

    # Check db
    if not db_p.exists():
        lines.append(f"DB: NOT FOUND ({db_p})")
        lines.append("Status: pass-through (no DB)")
        return "\n".join(lines)

    lines.append(f"DB: {db_p}")

    try:
        all_trades = _fetch_all_trades(db_p)
        all_trades = _filter_trades(all_trades, universe)
        all_trips = _fifo_match_global(all_trades)
        n_total = len(all_trips)
        strategies_with_trips = sorted(set(t["strategy"] for t in all_trips))
        lines.append(f"Universe: live-book only ({len(_resolve_universe(universe))} strategies; non-book excluded)")
        lines.append(f"Total round-trips (live book): {n_total} (need {MIN_ROUND_TRIPS_TOTAL} to train)")
        lines.append(f"Strategies with ≥1 trip: {len(strategies_with_trips)}")
        if strategies_with_trips:
            for s in strategies_with_trips:
                trips = [t for t in all_trips if t["strategy"] == s]
                wins = sum(1 for t in trips if t["pnl"] > 0)
                lines.append(
                    f"  {s}: {len(trips)} trips, {wins}/{len(trips)} wins "
                    f"({100*wins/len(trips):.0f}%)"
                )
    except Exception as exc:  # noqa: BLE001
        lines.append(f"DB read error: {exc}")

    # Model status
    cache_status = _MODEL_CACHE["status"]
    if cache_status == "untrained":
        # Attempt a fresh train for the report
        result = train_calibrator(db_path, universe=universe)
        cache_status = result["status"]

    lines.append(f"\nModel status: {cache_status}")
    lines.append(f"Training notes: {_MODEL_CACHE['notes']}")
    lines.append(f"Training samples: {_MODEL_CACHE['n_samples']}")
    lines.append(f"Feature set: {FEATURE_NAMES}")
    lines.append(f"sklearn available: {_check_sklearn()}")

    if _MODEL_CACHE["model"] is not None:
        lines.append("\nCalibration formula: multiplier = 2*P(win|features) - 1, clipped [0,1]")
        lines.append("  P=0.5 → multiplier=0.0 (max shrink) | P=0.75 → 0.5 | P=1.0 → 1.0")

    return "\n".join(lines)
