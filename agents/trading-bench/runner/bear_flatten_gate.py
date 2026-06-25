"""L165 — deterministic bear-flatten regime gate (SPY 200d SMA + hysteresis).

PAPER ONLY. Pure-price, no LLM, no external API, no DB writes. This is the
runner-level overlay specified in
reports/REGIME_DETECTION_L165_20260624T233555Z.md: when SPY closes below its
trailing 200-day SMA, FLATTEN the gated strategy (force a close / stay flat,
skip decide()); only re-enter once SPY closes back ABOVE its 201-day SMA. The
1-bar SMA-window asymmetry (200 down / 201 up) is the hysteresis buffer that
stops the gate whipsawing a position in/out on a SPY close oscillating around a
single SMA value.

Opt-in PER STRATEGY via params["bear_flatten_gate"] = true. Only
tqqq_cot_combo (primary) and allocator_blend (secondary) set it; every other
strategy is provably untouched (the runner skips this module when the flag is
absent/false).

Why a SEPARATE deterministic gate and not the Tier-2 LLM regime classifier:
the L165 backtest measured THIS rule (pure trailing SPY-SMA-200 with a 201
re-entry buffer). It must hold even when OPENAI_API_KEY is unset or the daily
classifier cron missed — there is no API dependency and no failure mode that
silently un-gates a falling market. tqqq_cot_combo already runs an internal
QQQ-SMA-200 cash gate; this SPY overlay composes belt-and-suspenders on top
(if the strategy already wants flat, the overlay agreeing is a no-op).

State (hysteresis latch) is carried in the runner's cross-flat persistent
strategy_state under the namespaced key ``_bear_flatten`` so the latch
survives every tick whether or not a position is held. The runner persists
that dict immediately after consulting the gate.

Contract: NEVER raises. On any unexpected input the gate returns
``flatten=False`` (defer to the strategy) — fail-OPEN to the strategy's own
risk management, never fail-CLOSED into an unexplained permanent flat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Namespaced sub-dict key inside strategy_state. Kept distinct from any key a
# strategy itself uses so the gate and the strategy never collide.
STATE_KEY = "_bear_flatten"

DEFAULT_SMA_WINDOW = 200       # flatten when SPY close < SMA(SPY, 200)
DEFAULT_REENTRY_WINDOW = 201   # re-enter only when SPY close >= SMA(SPY, 201)


@dataclass
class GateResult:
    """Outcome of one gate evaluation.

    flatten        : True => runner should force close-to-flat / stay flat and
                     skip decide() this tick.
    just_flipped   : True on the tick the latch CHANGES state (for logging).
    note           : human-readable one-line explanation for the decision log.
    new_state      : the updated ``_bear_flatten`` sub-dict to store back into
                     strategy_state (the runner persists it).
    active         : True iff the gate actually ran (enough bars); False means
                     it deferred (insufficient data) — distinct from flatten.
    """

    flatten: bool
    just_flipped: bool
    note: str
    new_state: Dict[str, Any] = field(default_factory=dict)
    active: bool = False


def _sma(values: List[float], n: int) -> Optional[float]:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


def _coerce_closes(spy_closes: Any) -> List[float]:
    """Best-effort: accept a list of numbers (or numeric strings). Drop
    anything non-coercible rather than raising."""
    out: List[float] = []
    if not spy_closes:
        return out
    try:
        it = list(spy_closes)
    except TypeError:
        return out
    for x in it:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            continue
    return out


def evaluate(
    spy_closes: Any,
    prev_state: Optional[Dict[str, Any]],
    *,
    sma_window: int = DEFAULT_SMA_WINDOW,
    reentry_window: int = DEFAULT_REENTRY_WINDOW,
) -> GateResult:
    """Evaluate the bear-flatten gate for one tick.

    Args:
        spy_closes: trailing SPY daily closes, oldest-first, newest LAST.
                    Needs >= reentry_window entries to fully evaluate
                    hysteresis; with >= sma_window but < reentry_window we can
                    still ENTER the bear latch (down-cross only) but cannot
                    confirm a re-entry until enough bars exist.
        prev_state: the prior ``_bear_flatten`` sub-dict (or None on first
                    run). Only the boolean ``bear_flat`` latch is read.

    Returns:
        GateResult. ``flatten`` reflects the latch AFTER applying this tick's
        SPY close. Hysteresis: once latched bear, we only clear when SPY >=
        SMA(reentry_window); a SPY close between SMA(200) and SMA(201) HOLDS
        the existing latch (the buffer).
    """
    prev_latch = False
    if isinstance(prev_state, dict):
        prev_latch = bool(prev_state.get("bear_flat", False))

    closes = _coerce_closes(spy_closes)

    # Insufficient history to even compute the down-gate -> defer entirely.
    # We do NOT invent a flat here; fail open to the strategy. Preserve the
    # prior latch so a transient short fetch doesn't silently reset state.
    if len(closes) < sma_window:
        note = (f"bear_flatten: insufficient SPY history "
                f"({len(closes)} < {sma_window}) -> defer to strategy "
                f"(latch held={prev_latch})")
        return GateResult(
            flatten=False,
            just_flipped=False,
            note=note,
            new_state={"bear_flat": prev_latch},
            active=False,
        )

    last = closes[-1]
    sma_down = _sma(closes, sma_window)            # 200d
    sma_up = _sma(closes, reentry_window)          # 201d (may be None if short)

    new_latch = prev_latch
    if not prev_latch:
        # Currently NOT flattened: enter the bear latch iff SPY < SMA200.
        if sma_down is not None and last < sma_down:
            new_latch = True
    else:
        # Currently flattened: only re-enter (clear) iff SPY >= SMA201.
        # If we don't yet have 201 bars, we CANNOT confirm re-entry, so we
        # conservatively hold the bear latch (safer than clearing blind).
        if sma_up is not None and last >= sma_up:
            new_latch = False
        # else: hold the latch (hysteresis band or insufficient up-window).

    just_flipped = (new_latch != prev_latch)

    sma_down_s = f"{sma_down:.2f}" if sma_down is not None else "n/a"
    sma_up_s = f"{sma_up:.2f}" if sma_up is not None else "n/a"
    if new_latch:
        state_word = "BEAR-FLAT" + (" (entered)" if just_flipped else " (held)")
    else:
        state_word = "RISK-ON" + (" (re-entered)" if just_flipped else "")
    note = (f"bear_flatten[SPY]: close={last:.2f} "
            f"SMA{sma_window}={sma_down_s} SMA{reentry_window}={sma_up_s} "
            f"-> {state_word}")

    return GateResult(
        flatten=new_latch,
        just_flipped=just_flipped,
        note=note,
        new_state={"bear_flat": new_latch},
        active=True,
    )


def spy_closes_from_regime(regime: Optional[dict]) -> List[float]:
    """Pull SPY closes out of the runner's injected ``regime`` block.

    Both runner.run and runner_xsec.run inject ``regime = {"spy_closes": [...],
    "spy_last": ...}``. Returns [] when absent so the gate defers."""
    if isinstance(regime, dict):
        cs = regime.get("spy_closes")
        if cs:
            return _coerce_closes(cs)
    return []
