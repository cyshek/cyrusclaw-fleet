"""Real-time safety backstops for live trading.

These are HARD safety rails that fire BEFORE the strategy's `decide()`
runs. They have one job: prevent a strategy from sitting on a runaway
position because its own exit logic failed, was buggy, or never coded.

Distinct from `runner/risk.py`:
    risk.py            : pre-trade caps (max notional, max position, daily count)
    safety_backstop.py : post-trade monitoring (close-if-loss-too-big, close-if-held-too-long)

Distinct from `walk_forward.py` gates: those are about whether to
PROMOTE a candidate. This is about protecting capital in live paper.

## Design

Pure-function check: `check(position, price, params, bars) -> BackstopAction`.
Caller (`runner/runner.py`) is responsible for actually submitting the
close order if `action == "close"`. Keeping it pure makes it trivially
testable (no DB, no broker).

## Triggers

Each trigger is opt-in via `params.json`. A strategy with no triggers
configured behaves as it does today (no backstop). Defaults are
intentionally conservative — these are last-resort rails, not
optimization parameters. If a strategy regularly trips a backstop, the
fix is the strategy logic, not the rail.

- `safety_max_loss_pct` (float, e.g. -25.0): force-close if unrealized
  PnL on the position falls below this percent. Long-only for now.
- `safety_max_holding_bars` (int): force-close if the position has been
  held for >= N bars. Bar count is approximated from `len(bars)` since
  first entry — see `_bars_since_entry()`.

## Lifecycle

Triggered BEFORE `decide()`. If a backstop fires, the strategy's tick
is short-circuited: the close order is submitted, decision/trade logged
with reason `safety_backstop:<trigger>`, and the strategy gets no second
chance for that tick. This is intentional: if the safety rail thinks
the position should be flat, the strategy doesn't get a vote.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BackstopAction:
    """Result of a backstop check.

    fire=False        -> no rail tripped; continue normally.
    fire=True         -> rail tripped; runner must submit a close order.
    reason            -> human-readable reason for logging.
    trigger           -> which trigger fired (for metrics/alerting).
    """
    fire: bool
    reason: Optional[str] = None
    trigger: Optional[str] = None


# Sentinel: a strategy with no triggers configured returns this every tick.
NO_ACTION = BackstopAction(fire=False)


def _unrealized_pct(price: float, avg_entry: float) -> Optional[float]:
    """Long-only unrealized PnL in percent. Returns None if inputs invalid."""
    try:
        price_f = float(price)
        entry_f = float(avg_entry)
    except (TypeError, ValueError):
        return None
    if entry_f <= 0 or price_f <= 0:
        return None
    return (price_f - entry_f) / entry_f * 100.0


def check(position: Optional[dict],
          price: Optional[float],
          params: dict,
          bars_since_entry: Optional[int] = None) -> BackstopAction:
    """Run all configured backstop triggers against the current position.

    Args:
        position: position_state[symbol] dict with avg_entry_price, qty,
                  market_value. None or empty -> NO_ACTION (nothing to close).
        price:    current market price. None -> NO_ACTION (can't compute PnL).
        params:   strategy params.json contents (where triggers are configured).
        bars_since_entry: optional bar count since position entry (for
                  the holding-time trigger). None -> holding-time trigger
                  is skipped even if configured.

    Returns: BackstopAction. If fire=True, caller MUST submit a close.
    """
    if not position or not isinstance(position, dict):
        return NO_ACTION
    if price is None:
        return NO_ACTION
    qty = position.get("qty")
    try:
        if qty is None or float(qty) <= 0:
            return NO_ACTION
    except (TypeError, ValueError):
        return NO_ACTION

    # --- Trigger 1: max loss percent --------------------------------------
    max_loss_pct = params.get("safety_max_loss_pct")
    if max_loss_pct is not None:
        try:
            threshold = float(max_loss_pct)
        except (TypeError, ValueError):
            threshold = None
        if threshold is not None:
            pct = _unrealized_pct(price, position.get("avg_entry_price", 0))
            if pct is not None and pct <= threshold:
                return BackstopAction(
                    fire=True,
                    trigger="max_loss_pct",
                    reason=(f"unrealized {pct:.2f}% <= safety_max_loss_pct "
                            f"{threshold:.2f}%; force close"),
                )

    # --- Trigger 2: max holding bars --------------------------------------
    max_hold = params.get("safety_max_holding_bars")
    if max_hold is not None and bars_since_entry is not None:
        try:
            hold_cap = int(max_hold)
            held = int(bars_since_entry)
        except (TypeError, ValueError):
            hold_cap = None
            held = None
        if hold_cap is not None and held is not None and held >= hold_cap:
            return BackstopAction(
                fire=True,
                trigger="max_holding_bars",
                reason=(f"held {held} bars >= safety_max_holding_bars "
                        f"{hold_cap}; force close"),
            )

    return NO_ACTION


def bars_since_entry(bars: list, entry_ts_iso: Optional[str]) -> Optional[int]:
    """Count how many bars in `bars` are >= entry_ts_iso.

    Returns None if bars is empty or entry_ts_iso is missing/malformed
    (caller treats that as 'unknown; skip holding-time trigger').
    """
    if not bars or not entry_ts_iso:
        return None
    try:
        # bars are sorted ascending by `t`; find first bar with t >= entry.
        # Linear scan — bars list is typically <= 200 entries.
        n = 0
        for b in bars:
            t = b.get("t") if isinstance(b, dict) else None
            if t and t >= entry_ts_iso:
                n += 1
        return n
    except Exception:  # noqa: BLE001
        return None
