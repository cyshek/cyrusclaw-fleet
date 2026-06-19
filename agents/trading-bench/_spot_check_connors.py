"""Spot-check Connors RSI(2) entries on one window.

For each candidate, replay the trading window and print every bar where
the entry condition fires (or would have fired but trend filter blocked).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import bars_cache  # noqa: E402
from strategies._lib.indicators import rsi, sma  # noqa: E402


def load_params(name):
    d = WS / "strategies_candidates" / name
    return json.loads((d / "params.json").read_text())


def spot(symbol: str, end_dt: datetime, days: int, warmup: int, label: str):
    full = days + warmup
    bars = bars_cache.get_bars(symbol, "1Day", days=full, end_dt=end_dt)
    closes_all = [float(b["c"]) for b in bars]
    # Mark the trading-window start: bars whose date >= (end_dt - days)
    trade_start = end_dt.timestamp() - days * 86400
    print(f"--- {symbol} {label}: {len(bars)} bars total, {days}d trading window")
    fires = 0
    blocked_trend = 0
    for i in range(1, len(bars)):
        slice_c = closes_all[: i + 1]
        r = rsi(slice_c, 2)
        sma200 = sma(slice_c, 200)
        sma5 = sma(slice_c, 5)
        if r is None or sma200 is None:
            continue
        c = slice_c[-1]
        t = bars[i].get("t", "")
        ts = datetime.strptime(t[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
        in_trade_window = ts >= trade_start
        if r < 10:
            if c > sma200:
                marker = "ENTRY" if in_trade_window else "warmup-only"
                print(f"  {t[:10]} c={c:.2f} RSI2={r:.1f} SMA200={sma200:.2f} SMA5={sma5:.2f} -> {marker}")
                if in_trade_window:
                    fires += 1
            else:
                if in_trade_window:
                    print(f"  {t[:10]} c={c:.2f} RSI2={r:.1f} SMA200={sma200:.2f} -> BLOCKED (close<SMA200)")
                    blocked_trend += 1
    print(f"  >>> in trading window: {fires} entries fired, {blocked_trend} blocked by trend filter")


if __name__ == "__main__":
    # SPY 2023-Q3 chop (we got 1 trade in warmup run)
    spot("SPY", datetime(2023, 10, 1, tzinfo=timezone.utc), 90, 220, "2023-Q3 chop")
    # QQQ 2024-Q2 bull (we got 1 round-trip, +0.13%)
    spot("QQQ", datetime(2024, 7, 1, tzinfo=timezone.utc), 90, 220, "2024-Q2 bull")
    # SPY 2022-H1 bear (we got 0 trades — verify trend filter blocked)
    spot("SPY", datetime(2022, 7, 1, tzinfo=timezone.utc), 90, 220, "2022-H1 bear")
