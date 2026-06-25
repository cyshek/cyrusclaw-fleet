"""L134 regression dry-run: prove the post-fix state persistence works in a
LIVE-style fresh-position_state-every-tick simulation for BOTH affected
strategies, driving the real runner.db save/load functions against a TEMP db.

Run:  python3 _l134_dryrun.py     (exit 0 = all parts pass; exit 1 = regression)

READ-ONLY against tournament.db (uses a temp sqlite db). Imports the ACTUAL
strategy decide() functions and the ACTUAL runner persistence helpers, then
replays the live runner's per-tick contract:

  * build_position_state() returns a FRESH dict each tick (broker-truth only);
    nothing the strategy wrote last tick survives unless the runner persisted it.
  * In-position bookkeeping -> db.save_strategy_state(strategy, symbol,
    position_state[symbol]) / db.get_strategy_state (per-symbol sub-dict;
    broker-truth keys stripped).
  * Cross-flat bookkeeping -> db.save_persistent_state / db.get_persistent_state
    via market_state["strategy_state"] (persisted EVERY tick, flat or not).

Pre-fix behavior (documented in
reports/L134_POSITION_STATE_VERIFICATION_20260624.md): rsi time-stop never
fired in live; macd entry-cross was never detected in live. This test asserts
both are now fixed.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# workspace on path so `runner` and `strategies` import clean
WS = Path(__file__).resolve().parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner import db  # noqa: E402
from strategies.rsi_oversold_spy.strategy import decide as rsi_decide  # noqa: E402
from strategies.macd_momentum_iwm.strategy import decide as macd_decide  # noqa: E402

FAILURES: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILURES.append(label)


def banner(s: str) -> None:
    print("\n=== " + s + " ===")


tmp = Path(tempfile.mkdtemp()) / "l134_dryrun.db"
db.init_db(db_path=tmp)


def runner_persist_in_position(strategy: str, action_symbol: str, position_state: dict) -> None:
    """Mirror runner.py: persist position_state[action.symbol] when present."""
    if action_symbol and action_symbol in position_state:
        db.save_strategy_state(strategy, action_symbol, position_state[action_symbol], db_path=tmp)


def runner_load_in_position(strategy: str, symbol: str, position_state: dict) -> None:
    """Mirror runner.py: layer persisted per-symbol state under broker truth."""
    if symbol in position_state:
        persisted = db.get_strategy_state(strategy, symbol, db_path=tmp)
        for k, v in persisted.items():
            position_state[symbol].setdefault(k, v)


def fresh_ps(symbol: str, holding_qty: float, price: float) -> dict:
    ps: dict = {}
    if holding_qty > 0:
        ps[symbol] = {"qty": holding_qty, "market_value": holding_qty * price,
                      "avg_entry_price": price}
    return ps


# ---------------------------------------------------------------------------
# PART A — rsi_oversold_spy time-stop must FIRE in a live-style replay.
# Build a synthetic SPY bar series that goes oversold (RSI<28) to trigger
# entry, then stays in a narrow band so RSI never reaches exit_rsi(70) and the
# ONLY exit is the time-stop (time_stop_bars=20). Pre-fix the time-stop was
# dead in live; post-fix it must fire at exactly bars_held>=20.
# ---------------------------------------------------------------------------
banner("PART A: rsi_oversold_spy time-stop fires in live-style replay (per-symbol state)")
strat_r = "rsi_oversold_spy"
sym_r = "SPY"
params_r = {"symbol": sym_r, "rsi_period": 14, "oversold_threshold": 28,
            "exit_rsi": 70, "time_stop_bars": 20, "notional_usd": 159.65}

# Construct closes: a long gentle decline to force RSI below 28, then flat-ish.
closes_series = [100.0]
for _ in range(25):            # steady decline -> RSI collapses well below 28
    closes_series.append(closes_series[-1] * 0.985)
# After entry we want RSI to recover to a mid band (NOT above 70) and sit there,
# so the time-stop is the binding exit. Tiny alternating wobble around flat.
for i in range(40):
    closes_series.append(closes_series[-1] * (1.001 if i % 2 == 0 else 0.999))


def bars_from(closes_list):
    return [{"t": f"2026-01-01T{i:02d}:00:00Z", "o": c, "h": c, "l": c, "c": c,
             "v": 1000} for i, c in enumerate(closes_list)]


held_qty = 0.0
price = closes_series[0]
entry_tick = None
exit_tick = None
exit_reason = ""
for t in range(15, len(closes_series)):  # need >=15 closes for RSI(14)
    window = closes_series[: t + 1]
    price = window[-1]
    ps = fresh_ps(sym_r, held_qty, price)
    runner_load_in_position(strat_r, sym_r, ps)
    ms = {"symbol": sym_r, "bars": bars_from(window), "last_price": price}
    act = rsi_decide(ms, ps, params_r)
    runner_persist_in_position(strat_r, act.symbol, ps)
    if act.action == "buy" and held_qty == 0:
        held_qty = (params_r["notional_usd"] / price)
        entry_tick = t
    elif act.action == "close" and held_qty > 0:
        exit_tick = t
        exit_reason = act.reason
        held_qty = 0.0
        db.clear_strategy_state(strat_r, sym_r, db_path=tmp)
        break

print(f"  entry_tick={entry_tick}  exit_tick={exit_tick}  exit_reason={exit_reason!r}")
check("entry fired (RSI went oversold)", entry_tick is not None)
check("time-stop exit fired in live-style replay", exit_tick is not None and "time-stop" in exit_reason)
if entry_tick is not None and exit_tick is not None:
    bars_held_at_exit = exit_tick - entry_tick
    check(f"time-stop fired at bars_held>=20 (got {bars_held_at_exit})", bars_held_at_exit >= 20)


# ---------------------------------------------------------------------------
# PART B — macd_momentum_iwm entry-cross must be DETECTED in a live-style
# replay. The prev MACD/signal live in cross-flat strategy_state, which the
# runner persists every tick (flat or not). Pre-fix prev was lost every flat
# tick -> cross never detected -> never entered live. Post-fix: it enters.
# ---------------------------------------------------------------------------
banner("PART B: macd_momentum_iwm entry-cross detected in live-style replay (cross-flat state)")
strat_m = "macd_momentum_iwm"
sym_m = "IWM"
params_m = {"symbol": sym_m, "fast": 12, "slow": 26, "signal": 9, "notional_usd": 120.96}

# Drive off REAL IWM daily adjclose (cached, no network). Synthetic monotone
# curves put the MACD/signal crossover inside the indicator warmup where it is
# never observed; real price noise produces genuine observed crosses (142 of
# them historically). We replay the LIVE runner contract: a fresh
# position_state every tick + cross-flat strategy_state persisted every tick
# via db.save/get_persistent_state. Pre-fix the prev-cross state was dropped
# every flat tick -> the entry cross was never detected in live. We bound the
# window (last N bars) so the bar_limit-style slice resembles the live runner
# and the test stays fast.
from runner import daily_bars_cache as _dbc  # noqa: E402
_iwm = _dbc.get_daily(sym_m, use_cache=True)
_iwm_closes = [float(b["adjclose"]) for b in _iwm]
# Use a slice that we KNOW contains an observed cross (first historical observed
# bullish MACD>0 cross is ~t=244); take a generous early window.
_iwm_closes = _iwm_closes[:600]


def macd_persist_cross_flat(strategy, symbol, market_state):
    st = market_state.get("strategy_state")
    db.save_persistent_state(strategy, symbol, st if isinstance(st, dict) else {}, db_path=tmp)


held_qty_m = 0.0
entry_tick_m = None
entry_reason_m = ""
saw_prev_persisted = False
for t in range(35, len(_iwm_closes)):  # need slow+signal coverage before MACD non-None
    window = _iwm_closes[: t + 1]
    price = window[-1]
    ps = fresh_ps(sym_m, held_qty_m, price)
    # load cross-flat state (mirrors runner: get_persistent_state EVERY tick)
    cross_flat = db.get_persistent_state(strat_m, sym_m, db_path=tmp)
    ms = {"symbol": sym_m, "bars": bars_from(window), "last_price": price,
          "strategy_state": dict(cross_flat)}
    act = macd_decide(ms, ps, params_m)
    macd_persist_cross_flat(strat_m, sym_m, ms)
    # confirm prev values are actually being persisted across (flat) ticks
    reloaded = db.get_persistent_state(strat_m, sym_m, db_path=tmp)
    if "_macd_prev_macd" in reloaded:
        saw_prev_persisted = True
    if act.action == "buy" and held_qty_m == 0:
        held_qty_m = (params_m["notional_usd"] / price)
        entry_tick_m = t
        entry_reason_m = act.reason
        break

print(f"  entry_tick={entry_tick_m}  prev_persisted_across_ticks={saw_prev_persisted}")
print(f"  entry_reason={entry_reason_m!r}")
check("macd prev-cross state persisted across flat ticks", saw_prev_persisted)
check("macd entry-cross DETECTED in live-style replay (would never fire pre-fix)",
      entry_tick_m is not None)


# ---------------------------------------------------------------------------
# PART C — guardrail: the runner's per-symbol save still strips broker-truth
# keys and round-trips a custom key (unchanged contract).
# ---------------------------------------------------------------------------
banner("PART C: per-symbol save strips broker-truth, round-trips custom key")
db.save_strategy_state("guard", "SPY",
                       {"qty": 1.0, "market_value": 5.0, "avg_entry_price": 5.0,
                        "_entry_bar": 7}, db_path=tmp)
got = db.get_strategy_state("guard", "SPY", db_path=tmp)
check("custom key survives", got.get("_entry_bar") == 7)
check("broker-truth qty stripped", "qty" not in got)


banner("VERDICT")
if FAILURES:
    print(f"  REGRESSION — {len(FAILURES)} check(s) failed:")
    for f in FAILURES:
        print("    -", f)
    sys.exit(1)
print("  ALL PARTS PASS — L134 fix verified in live-style replay for both strategies.")
sys.exit(0)
