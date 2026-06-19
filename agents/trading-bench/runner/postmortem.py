"""Loss-triggered postmortem diagnostics.

When a strategy hits a losing threshold in the weekly tournament, this module
produces a structured "why did this lose" note. The mutation step reads these
notes before generating variants, feeding failure analysis back into the loop.

Postmortem file: reports/postmortem/<strategy>_<YYYY-WW>.md

Loss threshold: strategy realized PnL is negative over the past N_DAYS (default 7).
A postmortem is only written if one doesn't already exist for this strategy+week
(idempotent — safe to re-run weekly cron).

Cause classification (heuristic, in priority order):
1. REGIME_MISMATCH  — strategy took many trades but hit stop / closed at loss during
                      a down-trend period (check if win_rate < 0.35 and strategy mostly
                      bought into a declining market)
2. COST_BLOWOUT     — strategy traded too frequently relative to gains (avg_trade_pnl
                      < estimated_cost_per_trade)
3. SIGNAL_DECAY     — strategy was profitable earlier in its history but declining
                      (rolling recent PnL negative while all-time PnL is positive)
4. THIN_SAMPLE      — fewer than 5 round-trips in the look-back window (not enough data)
5. UNKNOWN          — doesn't clearly fit the above

Output: a markdown note with:
- Strategy name, date range analyzed, cause classification
- Key stats: n_trades, realized_pnl, win_rate, avg_trade_pnl, turnover
- Narrative explanation (2-3 sentences) of the likely cause
- 1-2 suggested mutation directives (drawn from MUTATION_DIRECTIVES in tournament_loop.py)
  that directly address the classified cause
"""

from __future__ import annotations

import random
import sqlite3
import sys
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import db as _db  # noqa: E402 — lazy import after path fixup

# ---------------------------------------------------------------------------
# Cause constants
# ---------------------------------------------------------------------------

THIN_SAMPLE = "THIN_SAMPLE"
COST_BLOWOUT = "COST_BLOWOUT"
SIGNAL_DECAY = "SIGNAL_DECAY"
REGIME_MISMATCH = "REGIME_MISMATCH"
UNKNOWN = "UNKNOWN"

# Minimum round-trips below which we say we don't have enough data.
MIN_ROUND_TRIPS = 5

# ---------------------------------------------------------------------------
# FIFO helpers (mirrors kelly.py; inline to avoid tight coupling)
# ---------------------------------------------------------------------------

def _fifo_round_trips(rows: list) -> list[float]:
    """FIFO-match buy/sell rows into realized PnL per closing leg.

    rows: list of dict-like with keys: side, qty, price, notional_usd.
    Returns a list of floats (one per closing sell leg).
    """
    buy_queue: list[tuple[float, float]] = []  # (qty, cost_per_unit)
    pnls: list[float] = []

    for row in rows:
        if isinstance(row, dict):
            side = row["side"]
            qty_raw = row["qty"]
            price_raw = row["price"]
            notional_raw = row["notional_usd"]
        else:
            side = row[0]
            qty_raw = row[1]
            price_raw = row[2]
            notional_raw = row[3]

        try:
            q = float(qty_raw or 0)
        except (TypeError, ValueError):
            q = 0.0
        try:
            p = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            p = None
        try:
            n = float(notional_raw or 0)
        except (TypeError, ValueError):
            n = 0.0

        if q <= 0:
            continue

        cost_per_unit = (n / q) if q > 0 and n > 0 else (p or 0.0)

        if side == "buy":
            buy_queue.append((q, cost_per_unit))

        elif side == "sell":
            remaining_sell = q
            while remaining_sell > 1e-10 and buy_queue:
                buy_qty, buy_cpu = buy_queue[0]
                matched = min(remaining_sell, buy_qty)
                proceeds = matched * (p or 0.0)
                cost = matched * buy_cpu
                pnls.append(proceeds - cost)
                remaining_sell -= matched
                if matched >= buy_qty - 1e-10:
                    buy_queue.pop(0)
                else:
                    buy_queue[0] = (buy_qty - matched, buy_cpu)

    return pnls


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _open_statuses():
    return ("filled", "submitted", "partially_filled")


def _query_trades_window(strategy: str, cutoff_iso: str, db_path: Path) -> list:
    """Fetch trades for `strategy` at or after `cutoff_iso` (ISO UTC string)."""
    statuses = _open_statuses()
    placeholders = ",".join("?" * len(statuses))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT side, qty, price, notional_usd, ts_utc FROM trades "
            f"WHERE strategy = ? AND ts_utc >= ? AND status IN ({placeholders}) "
            f"ORDER BY id ASC",
            (strategy, cutoff_iso, *statuses),
        ).fetchall()
    return [dict(r) for r in rows]


def _query_all_trades(strategy: str, db_path: Path) -> list:
    """Fetch ALL historical trades for `strategy`."""
    statuses = _open_statuses()
    placeholders = ",".join("?" * len(statuses))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT side, qty, price, notional_usd, ts_utc FROM trades "
            f"WHERE strategy = ? AND status IN ({placeholders}) "
            f"ORDER BY id ASC",
            (strategy, *statuses),
        ).fetchall()
    return [dict(r) for r in rows]


def _distinct_strategies(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT DISTINCT strategy FROM trades").fetchall()
    return [r["strategy"] for r in rows]


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _compute_stats(rows: list) -> dict:
    """Compute summary stats from a set of trade rows.

    Returns:
        n_rt: number of FIFO-matched round-trips
        realized_pnl: sum of round-trip PnLs
        win_rate: fraction of round-trips that are profitable
        avg_trade_pnl: realized_pnl / n_rt  (0 if n_rt == 0)
        avg_win: mean PnL of winning trades
        avg_loss: mean PnL of losing trades (negative)
        turnover: sum of abs(notional_usd) for all rows
        n_buys: number of buy-side trades
        n_sells: number of sell-side trades
    """
    pnls = _fifo_round_trips(rows)
    n_rt = len(pnls)
    realized_pnl = sum(pnls)
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
    win_rate = len(wins) / n_rt if n_rt > 0 else 0.0
    avg_trade_pnl = realized_pnl / n_rt if n_rt > 0 else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    turnover = 0.0
    n_buys = 0
    n_sells = 0
    for row in rows:
        try:
            n = float(row.get("notional_usd") or 0)
        except (TypeError, ValueError):
            n = 0.0
        turnover += abs(n)
        side = row.get("side", "")
        if side == "buy":
            n_buys += 1
        elif side == "sell":
            n_sells += 1

    return {
        "n_rt": n_rt,
        "realized_pnl": realized_pnl,
        "win_rate": win_rate,
        "avg_trade_pnl": avg_trade_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "turnover": turnover,
        "n_buys": n_buys,
        "n_sells": n_sells,
        "n_trades": len(rows),
    }


# ---------------------------------------------------------------------------
# Cause classification
# ---------------------------------------------------------------------------

def _classify_cause(recent_stats: dict, alltime_stats: dict) -> str:
    """Determine the most likely loss cause given recent and all-time stats.

    Priority order:
    1. THIN_SAMPLE
    2. COST_BLOWOUT
    3. SIGNAL_DECAY
    4. REGIME_MISMATCH
    5. UNKNOWN
    """
    n_rt = recent_stats["n_rt"]
    realized_pnl = recent_stats["realized_pnl"]
    avg_trade_pnl = recent_stats["avg_trade_pnl"]
    win_rate = recent_stats["win_rate"]
    turnover = recent_stats["turnover"]
    n_buys = recent_stats["n_buys"]
    n_sells = recent_stats["n_sells"]

    # 1. Thin sample
    if n_rt < MIN_ROUND_TRIPS:
        return THIN_SAMPLE

    # 2. Cost blowout: small average losses + high turnover
    # avg_trade_pnl < 0 and small magnitude (cost bleed, not big directional error)
    # AND the strategy churned a lot (turnover > 200)
    if avg_trade_pnl < 0 and abs(avg_trade_pnl) < 5.0 and turnover > 200:
        return COST_BLOWOUT

    # 3. Signal decay: all-time profitable but recent losing
    alltime_pnl = alltime_stats["realized_pnl"]
    if alltime_pnl > 0 and realized_pnl < 0:
        return SIGNAL_DECAY

    # 4. Regime mismatch: low win rate + mostly bought (into a down-market)
    # win_rate < 0.35 and the strategy predominantly bought
    n_total_sides = n_buys + n_sells
    buy_fraction = n_buys / n_total_sides if n_total_sides > 0 else 0.0
    if win_rate < 0.35 and buy_fraction > 0.55:
        return REGIME_MISMATCH

    return UNKNOWN


# ---------------------------------------------------------------------------
# Directive suggestion
# ---------------------------------------------------------------------------

def _get_directives() -> list[str]:
    """Import MUTATION_DIRECTIVES from strategy_gen, falling back gracefully."""
    try:
        from .strategy_gen import MUTATION_DIRECTIVES
        return list(MUTATION_DIRECTIVES)
    except Exception:  # noqa: BLE001
        return []


def _pick_directives_for_cause(cause: str, directives: list[str], rng: random.Random) -> list[str]:
    """Return 1-2 directive suggestions that address the given cause.

    Matching strategy:
    - REGIME_MISMATCH → directives mentioning 'regime' or 'trend filter' or 'conditional'
    - COST_BLOWOUT    → directives mentioning 'cost' or 'turnover' or 'frequency' or
                        'time-of-day' or 'confirmation' or 'entry-confirm'
    - SIGNAL_DECAY    → directives mentioning 'parameter' or 'adapt' or 'lookback' or
                        'period'
    - THIN_SAMPLE / UNKNOWN → random directive
    """
    if not directives:
        return []

    keywords_map = {
        REGIME_MISMATCH: ["regime", "trend filter", "conditional"],
        COST_BLOWOUT: ["cost", "turnover", "frequency", "time-of-day", "confirmation",
                       "entry-confirm", "entry_confirm"],
        SIGNAL_DECAY: ["parameter", "adapt", "lookback", "period"],
    }

    keywords = keywords_map.get(cause)
    if keywords:
        matched = [
            d for d in directives
            if any(kw.lower() in d.lower() for kw in keywords)
        ]
        if matched:
            # Pick up to 2 distinct matches
            chosen = rng.sample(matched, min(2, len(matched)))
            return chosen

    # Fallback: random
    chosen = rng.sample(directives, min(2, len(directives)))
    return chosen


# ---------------------------------------------------------------------------
# Narrative generation
# ---------------------------------------------------------------------------

_NARRATIVES = {
    THIN_SAMPLE: (
        "This strategy had fewer than {min_rt} closed round-trips in the analysis window, "
        "which is not enough data to draw reliable conclusions. "
        "The loss may simply be statistical noise. "
        "Consider waiting for more trade history before acting on this signal."
    ),
    COST_BLOWOUT: (
        "The strategy traded frequently (${turnover:.0f} turnover) but generated only small "
        "per-trade losses (avg {avg_trade_pnl:+.2f} USD/round-trip), which is the signature "
        "of transaction-cost bleed rather than a fundamental edge problem. "
        "The strategy is likely over-trading — execution costs are eating the gross alpha. "
        "Reducing trade frequency, adding an entry-confirmation delay, or restricting to "
        "high-liquidity trading windows should help."
    ),
    SIGNAL_DECAY: (
        "This strategy was profitable over its full history (all-time PnL ${alltime_pnl:+.2f}) "
        "but has lost money in the recent {n_days}-day window (${realized_pnl:+.2f}). "
        "This is a classic signal-decay pattern: the edge that existed at inception is "
        "eroding, possibly because market conditions have shifted away from the original "
        "calibration regime. "
        "A parameter re-sweep or adaptive lookback adjustment is the recommended next step."
    ),
    REGIME_MISMATCH: (
        "Win rate was {win_rate:.0%} and {buy_frac:.0%} of trades were buys, suggesting the "
        "strategy kept buying into a declining market that its signal couldn't detect as bearish. "
        "This is regime mismatch: the strategy's entry logic is not regime-aware, so it fires "
        "in trending-down conditions where it has no edge. "
        "Adding a trend filter (e.g. only enter longs when SPY is above its 50-day SMA) is "
        "the highest-priority fix."
    ),
    UNKNOWN: (
        "The loss pattern does not clearly fit the standard failure modes (thin sample, "
        "cost blowout, signal decay, or regime mismatch). "
        "Key stats: {n_rt} round-trips, win rate {win_rate:.0%}, "
        "avg trade {avg_trade_pnl:+.2f} USD, turnover ${turnover:.0f}. "
        "Further investigation recommended; a random mutation directive is suggested below "
        "as a starting point for the next generation."
    ),
}


def _narrative(cause: str, stats: dict, alltime_stats: dict, n_days: int) -> str:
    template = _NARRATIVES.get(cause, _NARRATIVES[UNKNOWN])
    n_total_sides = stats["n_buys"] + stats["n_sells"]
    buy_frac = stats["n_buys"] / n_total_sides if n_total_sides > 0 else 0.0
    return template.format(
        min_rt=MIN_ROUND_TRIPS,
        turnover=stats["turnover"],
        avg_trade_pnl=stats["avg_trade_pnl"],
        n_days=n_days,
        alltime_pnl=alltime_stats.get("realized_pnl", 0.0),
        realized_pnl=stats["realized_pnl"],
        win_rate=stats["win_rate"],
        buy_frac=buy_frac,
        n_rt=stats["n_rt"],
    )


# ---------------------------------------------------------------------------
# Postmortem file writer
# ---------------------------------------------------------------------------

def _format_postmortem(
    strategy: str,
    date_from: str,
    date_to: str,
    cause: str,
    stats: dict,
    alltime_stats: dict,
    narrative_text: str,
    suggested_directives: list[str],
    n_days: int,
) -> str:
    lines = [
        f"# Postmortem: `{strategy}`",
        f"",
        f"**Date range:** {date_from} → {date_to} ({n_days} days)",
        f"**Cause:** `{cause}`",
        f"",
        f"## Key Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Round-trips | {stats['n_rt']} |",
        f"| Realized PnL | ${stats['realized_pnl']:+.4f} |",
        f"| Win rate | {stats['win_rate']:.1%} |",
        f"| Avg trade PnL | ${stats['avg_trade_pnl']:+.4f} |",
        f"| Avg win | ${stats['avg_win']:+.4f} |",
        f"| Avg loss | ${stats['avg_loss']:+.4f} |",
        f"| Turnover | ${stats['turnover']:.2f} |",
        f"| Trades (n) | {stats['n_trades']} |",
        f"| Buys / Sells | {stats['n_buys']} / {stats['n_sells']} |",
        f"| All-time realized PnL | ${alltime_stats['realized_pnl']:+.4f} |",
        f"",
        f"## Diagnosis",
        f"",
        narrative_text,
        f"",
        f"## Suggested Mutation Directives",
        f"",
    ]

    if suggested_directives:
        for i, d in enumerate(suggested_directives, 1):
            # Truncate to first 200 chars for readability; full text in strategy_gen.py
            truncated = d[:200].rstrip() + ("..." if len(d) > 200 else "")
            lines.append(f"**Directive {i}:** {truncated}")
            lines.append("")
    else:
        lines.append("_No directives available — check MUTATION_DIRECTIVES in strategy_gen.py._")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated by runner/postmortem.py at {datetime.now(timezone.utc).isoformat()}Z_")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_postmortem(
    strategy: str,
    *,
    n_days: int = 7,
    loss_threshold_usd: float = -1.0,
    workspace: Path = WORKSPACE,
    db_path=None,
    overwrite: bool = False,
) -> Optional[Path]:
    """Run a postmortem for `strategy` if it lost money in the past n_days.

    Returns the path to the written postmortem file, or None if:
      - strategy did not lose (PnL >= loss_threshold_usd)
      - a postmortem for this week already exists (and overwrite=False)

    The postmortem file is written to:
      workspace/reports/postmortem/<strategy>_<YYYY-WW>.md
    where YYYY-WW is the ISO year-week of today's date.
    """
    if db_path is None:
        db_path = _db.DB_PATH
    db_path = Path(db_path)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=n_days)
    cutoff_iso = cutoff.isoformat()

    # ISO week label, e.g. "2026-W24"
    iso_year, iso_week, _ = now.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"

    # Idempotency check
    postmortem_dir = workspace / "reports" / "postmortem"
    outfile = postmortem_dir / f"{strategy}_{week_label}.md"
    if outfile.exists() and not overwrite:
        return None

    # Fetch recent trades
    try:
        recent_rows = _query_trades_window(strategy, cutoff_iso, db_path)
    except Exception:  # noqa: BLE001
        return None

    # Compute recent stats
    recent_stats = _compute_stats(recent_rows)

    # Loss gate
    if recent_stats["realized_pnl"] >= loss_threshold_usd:
        return None

    # Fetch all-time trades for signal-decay check
    try:
        all_rows = _query_all_trades(strategy, db_path)
    except Exception:  # noqa: BLE001
        all_rows = []
    alltime_stats = _compute_stats(all_rows)

    # Classify cause
    cause = _classify_cause(recent_stats, alltime_stats)

    # Directives
    rng = random.Random(strategy + week_label)
    directives = _get_directives()
    suggested = _pick_directives_for_cause(cause, directives, rng)

    # Narrative
    narrative_text = _narrative(cause, recent_stats, alltime_stats, n_days)

    # Format postmortem
    content = _format_postmortem(
        strategy=strategy,
        date_from=cutoff.strftime("%Y-%m-%d"),
        date_to=now.strftime("%Y-%m-%d"),
        cause=cause,
        stats=recent_stats,
        alltime_stats=alltime_stats,
        narrative_text=narrative_text,
        suggested_directives=suggested,
        n_days=n_days,
    )

    # Write file
    postmortem_dir.mkdir(parents=True, exist_ok=True)
    outfile.write_text(content)

    return outfile


def run_postmortems_for_all(
    *,
    n_days: int = 7,
    loss_threshold_usd: float = -1.0,
    workspace: Path = WORKSPACE,
    db_path=None,
) -> list[Path]:
    """Run postmortems for all strategies that lost money in the past n_days.

    Reads strategy list from the trades table.
    Returns list of paths written.
    """
    if db_path is None:
        db_path = _db.DB_PATH
    db_path = Path(db_path)

    try:
        strategies = _distinct_strategies(db_path)
    except Exception:  # noqa: BLE001
        return []

    written = []
    for strat in strategies:
        path = run_postmortem(
            strat,
            n_days=n_days,
            loss_threshold_usd=loss_threshold_usd,
            workspace=workspace,
            db_path=db_path,
        )
        if path is not None:
            written.append(path)

    return written


# ---------------------------------------------------------------------------
# Postmortem hint for tournament_loop directive weighting
# ---------------------------------------------------------------------------

def get_postmortem_directive_hint(
    strategy: str,
    postmortem_dir: Path,
    directives: list[str],
    *,
    max_age_days: int = 14,
) -> Optional[str]:
    """Return the first 'Suggested directive' from a recent postmortem for `strategy`.

    Searches postmortem_dir for files matching <strategy>_*.md, picks the most
    recent one within max_age_days, and extracts the first suggested directive text.

    Returns the matched directive from `directives` (full text), or None.
    """
    if not postmortem_dir.exists():
        return None

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)

    # Find all postmortem files for this strategy
    candidates = sorted(postmortem_dir.glob(f"{strategy}_*.md"), reverse=True)
    if not candidates:
        return None

    # Read the most recent one
    pm_path = candidates[0]
    try:
        mtime = datetime.fromtimestamp(pm_path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            return None
        text = pm_path.read_text()
    except Exception:  # noqa: BLE001
        return None

    # Extract the hint by looking for "Directive 1: <text>" line
    for line in text.splitlines():
        if line.startswith("**Directive 1:**"):
            snippet = line.replace("**Directive 1:**", "").strip()
            # Find best matching full directive from the list
            if not directives:
                return None
            snippet_lower = snippet.lower()
            # Match by first 60 chars of directive
            for d in directives:
                if d[:60].lower() in snippet_lower or snippet_lower[:60] in d.lower():
                    return d
            # Fallback: pick the directive whose leading words are most similar
            best = max(directives, key=lambda d: sum(
                1 for w in snippet_lower.split()[:5] if w in d.lower()
            ))
            return best

    return None
