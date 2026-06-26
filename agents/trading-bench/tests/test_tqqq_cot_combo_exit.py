"""Characterization / pinning tests for tqqq_cot_combo EXIT logic.

CONTEXT (2026-06-25): an intraday audit flagged this strategy's exit logic as
"possibly broken" because the live book showed 10 buys / 0 sells and a small
unrealized drawdown. A READ-ONLY forensic audit
(reports/TQQQ_COT_COMBO_EXIT_AUDIT_20260625.md) concluded the exit logic is
WORKING AS DESIGNED: tqqq_cot_combo is an SMA-200-gated vol-target ACCUMULATOR
(it rebalances toward a target weight), not a discrete entry/exit signal
trader. The "no sells" was simply the SMA-200 risk-gate being ON the entire
window (QQQ was ~+12.65% above its 200d SMA), so no exit *should* have fired.

Rather than "fix" a non-bug, these tests PIN the three real exit paths so a
future refactor cannot silently break them (which is the failure mode the
audit was actually worried about). All three are exercised against the LIVE
strategy code with the LIVE params, exactly as the runner calls decide().

Exit paths (from strategy.py / the audit's §1 table):
  A. SMA-200 gate OFF  -> Action("close")  (full de-risk to cash)
  B. Vol-target overweight (target_qty < holdings - threshold) -> Action("sell")
  C. target_qty collapses to 0 while holding -> Action("close")

Plus the correct NON-exit (gate ON, converged) -> Action("hold").

These are pure-Python (no network, no DB); they call decide() directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from strategies.tqqq_cot_combo.strategy import decide  # noqa: E402

PARAMS_PATH = WORKSPACE / "strategies" / "tqqq_cot_combo" / "params.json"


def _live_params() -> dict:
    return json.loads(PARAMS_PATH.read_text())


def _bars_from_closes(closes):
    """Build Alpaca-style OHLCV bar dicts from a close series (newest last)."""
    return [
        {"t": i, "o": c, "h": c * 1.01, "l": c * 0.99, "c": c, "v": 1_000_000}
        for i, c in enumerate(closes)
    ]


# A long, gently-oscillating TQQQ series: >=200 bars for SMA + >=20 for vol,
# with enough wiggle that realized vol is well-defined and non-degenerate.
def _tqqq_bars(n=240, base=75.0, wiggle=0.5):
    closes = [base + (i % 5) * wiggle for i in range(n)]
    return _bars_from_closes(closes)


def _held(qty=12.0, avg=78.69):
    return {"TQQQ": {"qty": qty, "avg_entry_price": avg, "market_value": qty * avg}}


# ---------------------------------------------------------------------------
# PATH A — SMA-200 gate OFF -> full CLOSE
# ---------------------------------------------------------------------------
def test_exit_path_a_gate_off_closes_full_position():
    """When the QQQ underlying closes BELOW its 200d SMA, a held position is
    fully de-risked to cash via Action('close')."""
    params = _live_params()
    # QQQ history high then crashes below its own SMA-200 on the last bars.
    qqq_closes = [700.0] * 201 + [600.0] * 25
    ms = {
        "symbol": "TQQQ",
        "last_price": 75.0,
        "bars": _tqqq_bars(),
        "underlying": {"symbol": "QQQ", "closes": qqq_closes},
        "timestamp": "2026-06-25",
    }
    act = decide(ms, _held(), params)
    assert act.action == "close", f"expected close, got {act.action}: {act.reason}"
    assert "gate OFF" in act.reason


def test_exit_path_a_gate_off_when_flat_stays_hold():
    """Gate OFF while already flat must NOT emit a spurious sell/close."""
    params = _live_params()
    qqq_closes = [700.0] * 201 + [600.0] * 25
    ms = {
        "symbol": "TQQQ",
        "last_price": 75.0,
        "bars": _tqqq_bars(),
        "underlying": {"symbol": "QQQ", "closes": qqq_closes},
        "timestamp": "2026-06-25",
    }
    act = decide(ms, {"TQQQ": {"qty": 0.0}}, params)
    assert act.action == "hold", f"expected hold, got {act.action}: {act.reason}"


# ---------------------------------------------------------------------------
# PATH B — vol-target overweight -> partial SELL (trim)
# ---------------------------------------------------------------------------
def test_exit_path_b_overweight_trims_via_sell():
    """Gate ON but holdings exceed the vol-target by more than the churn
    threshold -> Action('sell') trims the excess. (This is the path that fires
    imminently now that notional was cut $1000 -> $160.)"""
    params = _live_params()
    # Gate firmly ON: QQQ well above its SMA-200.
    qqq_closes = [600.0] * 201 + [710.0] * 25
    # Very low realized vol -> raw weight pegs at w_max=1.0 -> target ~ notional/price.
    # With live notional $160 and price ~75, target ~ 2 sh << 12 held -> SELL.
    low_vol_closes = [75.0 + (0.02 if i % 2 else -0.02) for i in range(240)]
    ms = {
        "symbol": "TQQQ",
        "last_price": 75.0,
        "bars": _bars_from_closes(low_vol_closes),
        "underlying": {"symbol": "QQQ", "closes": qqq_closes},
        "timestamp": "2026-06-25",
    }
    act = decide(ms, _held(qty=12.0), params)
    assert act.action == "sell", f"expected sell, got {act.action}: {act.reason}"
    assert act.qty is not None and act.qty > 0


# ---------------------------------------------------------------------------
# PATH C — target_qty collapses to 0 -> full CLOSE
# ---------------------------------------------------------------------------
def test_exit_path_c_target_zero_closes():
    """If the target notional rounds the target_qty to 0 while a position is
    held (gate ON), the strategy closes to flat."""
    params = _live_params()
    params["notional"] = 0.01  # forces floor(weight*notional/price) == 0
    qqq_closes = [600.0] * 201 + [710.0] * 25
    ms = {
        "symbol": "TQQQ",
        "last_price": 75.0,
        "bars": _tqqq_bars(),
        "underlying": {"symbol": "QQQ", "closes": qqq_closes},
        "timestamp": "2026-06-25",
    }
    act = decide(ms, _held(), params)
    assert act.action == "close", f"expected close, got {act.action}: {act.reason}"
    assert "target_qty=0" in act.reason


# ---------------------------------------------------------------------------
# NON-exit — gate ON + converged -> HOLD (this is the live state being audited)
# ---------------------------------------------------------------------------
def test_no_exit_when_gate_on_and_converged():
    """The audited live condition: gate ON, position already at target within
    the churn threshold -> HOLD (correctly NOT a buy or sell). This pins that
    'no sell' is the CORRECT behavior in a risk-ON regime, not a broken exit."""
    params = _live_params()
    qqq_closes = [600.0] * 201 + [710.0] * 25
    ms = {
        "symbol": "TQQQ",
        "last_price": 75.0,
        "bars": _tqqq_bars(),
        "underlying": {"symbol": "QQQ", "closes": qqq_closes},
        "timestamp": "2026-06-25",
    }
    # Hold a qty near the target so |delta| <= threshold -> hold.
    # target ~ floor(1.0 * 160 / 75) ~ 2 sh; hold 2 sh -> hold.
    act = decide(ms, _held(qty=2.0), params)
    assert act.action == "hold", f"expected hold, got {act.action}: {act.reason}"
