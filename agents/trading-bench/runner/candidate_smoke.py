"""Candidate-strategy smoke test (Bar A bullet #7 evaluator).

The live runner (`runner.runner`) imports from `strategies/` only. New
archetypes live in `strategies_candidates/` while under evaluation, which
made Bar A bullet #7 ("smoke test passes") structurally unverifiable
without first promoting the candidate — the chicken-and-egg main flagged
2026-05-30.

This module fixes that. Usage::

    python -m runner.candidate_smoke --candidate <name>
    # or
    ./tick.sh --candidate <name>

It loads `strategies_candidates/<name>/strategy.py` + `params.json`, fetches
real market data via the Alpaca paper client, calls the strategy's
``decide(market_state, position_state, params)`` once, prints the resulting
action, and exits. **No DB writes. No order submission. No state persistence.
No killswitch coupling.** This is a code-path smoke check only: did it
import, did decide() return a sane action dict, did no exception fire.

If a candidate needs a real position to exercise its close branch, that's
out of scope for this smoke — it's checked at promotion time by the live
runner. The purpose here is to catch import errors, schema-mismatched
params, and obviously-broken decide() output before we touch GATE.md.

Exit codes:
    0 — decide() returned a recognized action (buy/sell/close/hold).
    1 — load error, decide() raised, or action shape is invalid.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

from .broker_alpaca import AlpacaClient, AlpacaError

WORKSPACE = Path(__file__).resolve().parent.parent
CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"

VALID_ACTIONS = {"buy", "sell", "close", "hold"}


def _is_xsec_candidate(module) -> bool:
    """A candidate is xsec if its strategy module exports `decide_xsec`.
    Single-symbol candidates export `decide` instead. Mixed modules are
    treated as xsec (since the xsec entry-point is the more specialized)."""
    return hasattr(module, "decide_xsec")


def load_candidate(name: str):
    """Import strategies_candidates/<name>/strategy.py + read params.json.

    Mirrors `runner.load_strategy` but reads from the candidates tree.
    Adds WORKSPACE to sys.path so the candidate's `from strategies._lib import …`
    imports resolve the same way they would in the live runner.
    """
    strat_dir = CANDIDATES_ROOT / name
    params_path = strat_dir / "params.json"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"No candidate dir: {strat_dir}")
    if not params_path.exists():
        raise FileNotFoundError(f"No params.json: {params_path}")
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    module = importlib.import_module(f"strategies_candidates.{name}.strategy")
    params = json.loads(params_path.read_text())
    return module, params


def build_market_state(client: AlpacaClient, params: dict) -> dict:
    """Construct the same market_state shape the live runner builds.

    Differences from `runner.runner`:
    - No persistent_state lookup (always empty dict — candidate has none yet).
    - Best-effort SPY regime fetch for stocks (mirrors runner; falls back to
      None on AlpacaError).
    """
    symbol = params.get("symbol", "BTC/USD")
    is_crypto = AlpacaClient.is_crypto_symbol(symbol)
    timeframe = str(params.get("timeframe", "1Hour"))
    bar_limit = int(params.get("bar_limit", 200))

    try:
        price = (client.latest_crypto_price(symbol) if is_crypto
                 else client.latest_stock_price(symbol))
    except AlpacaError:
        price = None
    try:
        bars = (client.crypto_bars(symbol, timeframe=timeframe, limit=bar_limit)
                if is_crypto
                else client.stock_bars(symbol, timeframe=timeframe, limit=bar_limit))
    except AlpacaError:
        bars = []

    regime = None
    if not is_crypto:
        try:
            spy_bars = client.stock_bars("SPY", timeframe="1Day", limit=100)
            spy_closes = [float(b["c"]) for b in (spy_bars or [])]
            if spy_closes:
                regime = {"spy_closes": spy_closes, "spy_last": spy_closes[-1]}
        except AlpacaError:
            regime = None

    # Underlying injection (mirrors runner.run): a sleeve strategy may gate on a
    # different underlying than the symbol it trades. Keeps smoke parity with live.
    underlying_block = None
    if not is_crypto:
        underlying_sym = str(params.get("underlying", "")).upper()
        if underlying_sym and underlying_sym != symbol.upper():
            try:
                u_limit = max(int(params.get("sma_window", 200)) + 30, 260)
                u_bars = client.stock_bars(underlying_sym, timeframe="1Day", limit=u_limit)
                u_closes = [float(b["c"]) for b in (u_bars or [])]
                if u_closes:
                    underlying_block = {"symbol": underlying_sym, "closes": u_closes}
            except AlpacaError:
                underlying_block = None

    return {
        "symbol": symbol,
        "last_price": price,
        "bars": bars,
        "timeframe": timeframe,
        "regime": regime,
        "underlying": underlying_block,
        # Persistent state: empty for smoke. Strategy may mutate; we discard.
        "strategy_state": {},
    }


def smoke(name: str) -> int:
    """Run one decide() call against live market data. Returns exit code."""
    t0 = time.monotonic()
    try:
        module, params = load_candidate(name)
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: load error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

    try:
        client = AlpacaClient()
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: AlpacaClient init: {e}", file=sys.stderr)
        return 1

    # Xsec candidates take a different market_state shape (per-symbol basket)
    # so dispatch BEFORE building the single-symbol market_state, which
    # would fail on params with no `symbol` key.
    if _is_xsec_candidate(module):
        return _smoke_xsec(name, module, params, t0)

    try:
        market_state = build_market_state(client, params)
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: market_state build: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # Smoke runs with an empty position_state — the candidate's entry branch
    # (flat → buy) is what we want to exercise. The close branch is checked
    # at promotion time by the live runner.
    position_state: dict = {}

    if _is_xsec_candidate(module):
        return _smoke_xsec(name, module, params, t0)

    try:
        action = module.decide(market_state, position_state, params)
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: decide() raised: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # Shape validation: duck-type, not strict dataclass check, so the smoke
    # works regardless of whether the candidate uses a dataclass or a dict.
    act = getattr(action, "action", None)
    sym = getattr(action, "symbol", None)
    notional = getattr(action, "notional_usd", 0.0)
    reason = getattr(action, "reason", "")
    if act not in VALID_ACTIONS:
        print(f"[{name}] SMOKE FAIL: action {act!r} not in {VALID_ACTIONS}",
              file=sys.stderr)
        return 1

    bars_n = len(market_state.get("bars") or [])
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    print(f"[{name}] SMOKE OK ({elapsed_ms}ms) action={act} symbol={sym} "
          f"notional=${notional:.2f} bars={bars_n} "
          f"price={market_state.get('last_price')} reason={reason!r}")
    return 0


def build_market_state_xsec(client: AlpacaClient, basket: list, params: dict) -> dict:
    """Build the cross-sectional `market_state` shape the xsec backtester
    builds: a `symbols` dict keyed by symbol, plus optional SPY regime."""
    timeframe = str(params.get("timeframe", "1Day"))
    bar_limit = int(params.get("bar_limit", 300))
    symbols_view = {}
    clock_t = ""
    for sym in basket:
        try:
            bars = (client.crypto_bars(sym, timeframe=timeframe, limit=bar_limit)
                    if AlpacaClient.is_crypto_symbol(sym)
                    else client.stock_bars(sym, timeframe=timeframe, limit=bar_limit))
        except AlpacaError:
            bars = []
        last_price = float(bars[-1]["c"]) if bars else None
        last_t = str(bars[-1].get("t", "")) if bars else ""
        if last_t > clock_t:
            clock_t = last_t
        symbols_view[sym] = {
            "bars": bars or [],
            "last_price": last_price,
            "has_bar": bool(bars),
        }
    regime = None
    any_crypto = any(AlpacaClient.is_crypto_symbol(s) for s in basket)
    if not any_crypto:
        try:
            spy_bars = client.stock_bars("SPY", timeframe="1Day", limit=100)
            spy_closes = [float(b["c"]) for b in (spy_bars or [])]
            if spy_closes:
                regime = {"spy_closes": spy_closes, "spy_last": spy_closes[-1]}
        except AlpacaError:
            regime = None
    return {
        "timeframe": timeframe,
        "clock_t": clock_t,
        "symbols": symbols_view,
        "regime": regime,
        "strategy_state": {},
    }


def _smoke_xsec(name: str, module, params: dict, t0: float) -> int:
    """Smoke path for cross-sectional candidates (decide_xsec).

    Reads `basket` from params.json. Builds an xsec market_state
    (per-symbol bars + SPY regime), calls decide_xsec once with empty
    position_state, validates the returned dict shape (sym -> action).
    No DB writes, no order submission.
    """
    basket = list(params.get("basket") or [])
    if not basket:
        print(f"[{name}] SMOKE FAIL: xsec candidate has no `basket` in params.json",
              file=sys.stderr)
        return 1
    try:
        client = AlpacaClient()
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: AlpacaClient init: {e}", file=sys.stderr)
        return 1
    try:
        market_state = build_market_state_xsec(client, basket, params)
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: xsec market_state build: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    position_state: dict = {}
    try:
        actions = module.decide_xsec(market_state, position_state, params)
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] SMOKE FAIL: decide_xsec() raised: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    if actions is None:
        actions = {}
    if not isinstance(actions, dict):
        print(f"[{name}] SMOKE FAIL: decide_xsec returned "
              f"{type(actions).__name__}, expected dict", file=sys.stderr)
        return 1
    # Validate each action's shape.
    for sym, a in actions.items():
        act = getattr(a, "action", None)
        if act not in VALID_ACTIONS:
            print(f"[{name}] SMOKE FAIL: xsec action for {sym} is {act!r} "
                  f"(must be in {VALID_ACTIONS})", file=sys.stderr)
            return 1
    n_total_bars = sum(len(sv["bars"]) for sv in market_state["symbols"].values())
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    summary = ", ".join(
        f"{s}={getattr(a, 'action', '?')}" for s, a in actions.items()) or "hold-all"
    print(f"[{name}] SMOKE OK xsec ({elapsed_ms}ms) basket={basket} "
          f"bars_total={n_total_bars} actions={{{summary}}}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Bar A bullet #7 smoke test for "
                                             "candidates in strategies_candidates/.")
    ap.add_argument("--candidate", required=True,
                    help="candidate directory name under strategies_candidates/")
    args = ap.parse_args()
    sys.exit(smoke(args.candidate))


if __name__ == "__main__":
    main()
