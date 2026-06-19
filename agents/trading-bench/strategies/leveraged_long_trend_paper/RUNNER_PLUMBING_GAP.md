# RUNNER PLUMBING GAP — QQQ closes for the TQQQ vol-target sleeve

**Status:** BLOCKING for gate-correct live operation of `leveraged_long_trend_paper`.
The adapter is written, smoke-passes, and is SAFE today (it fails-safe to flat),
but it will **no-op every tick** until this plumbing lands, because it refuses to
evaluate the QQQ SMA-200 gate on a proxy.

## The gap
`runner/runner.py` builds `market_state` with:
- `market_state["bars"]`  = the **traded** symbol's bars only (here: **TQQQ**).
- `market_state["regime"]` = `{"spy_closes":[...100 SPY 1Day...], "spy_last":...}` — **SPY, hardcoded** (line ~208).

The sleeve's trend gate is on **QQQ** (the underlying), not TQQQ and not SPY.
Realized-vol IS on the sleeve (TQQQ) and already works from `market_state["bars"]`.
So the ONLY missing input is **QQQ daily closes**.

## What the adapter looks for (already coded — pick ONE)
`strategy.py::_resolve_underlying_closes()` accepts, in priority order:
1. `market_state["underlying"]` = `{"symbol": "QQQ", "closes": [...]}` (preferred), or `{"symbol":"QQQ","bars":[...]}`.
2. `market_state["regime"]["underlying_closes"]` (+ optional `regime["underlying_symbol"]`).

It will NOT proxy QQQ with SPY/TQQQ. Absent QQQ → `hold` (flat) / `close` (if holding).

## Minimal runner patch (option 1, recommended)
In `runner/runner.py`, right after the existing SPY-regime block (~line 214), for
stocks, if the strategy declares an `underlying` in params and it differs from the
traded symbol, fetch its daily closes and attach them:

```python
# Underlying injection: a sleeve strategy (e.g. TQQQ) may gate on a DIFFERENT
# underlying (QQQ). If params declares one, fetch its daily closes so the
# strategy can compute its gate without a proxy. Best-effort; None on failure.
underlying_sym = str(params.get("underlying", "")).upper()
if (not is_crypto) and underlying_sym and underlying_sym != symbol.upper():
    try:
        u_limit = max(int(params.get("sma_window", 200)) + 30, 260)
        u_bars = client.stock_bars(underlying_sym, timeframe="1Day", limit=u_limit)
        u_closes = [float(b["c"]) for b in (u_bars or [])]
        if u_closes:
            market_state["underlying"] = {"symbol": underlying_sym, "closes": u_closes}
    except AlpacaError:
        pass
```

(Place the assignment AFTER `market_state = {...}` is constructed, or fold the key
into the dict literal. The candidate-smoke harness `runner/candidate_smoke.py`
needs the SAME addition in `build_market_state()` for parity — currently it also
injects SPY-only.)

## Correctness notes for whoever wires this
- **adjclose vs raw close:** the backtest computes QQQ SMA + TQQQ returns from
  SPLIT/DIV-ADJUSTED closes. Alpaca `stock_bars` `c` is raw. Over a 200d SMA / 20d
  vol window with no split inside it, raw≈adjusted for the decision. If a split
  lands inside a live trailing window the raw return on the split day is corrupt.
  Prefer adjusted closes if the broker plumbing can expose them; otherwise document
  the residual risk (it is small for QQQ, which splits rarely, and for TQQQ the vol
  window is short).
- **Lookahead:** keep feeding only COMPLETED daily bars (the runner already does;
  do not pass a forming/partial bar). The adapter treats the last provided bar as
  decision-day D and applies the weight going forward — same D→D+1 convention as
  the engine.
- **VIX gate:** `params.json` sets `vix_gate=false` on purpose. The engine uses a
  VIX/VIX3M term-structure overlay, which the runner can't supply; the engine's own
  `_vix_risk_off` passes on missing data, so false == faithful graceful-degrade.
  Only flip to true once VIX term structure is also plumbed into `market_state`.

## Second (non-blocking) gap: no partial-trim primitive
The runner supports BUY notional and CLOSE-to-flat only — no partial down-trim
while staying long. The vol-target engine rebalances continuously. The adapter
quantizes honestly: full CLOSE on gate-off / weight≈0, single BUY when adding,
and HOLD (no trim) when it wants to reduce-but-not-exit. This biases the live
sleeve slightly HOTTER on vol-spike days where the engine would trim — bounded at
w_max=1.0 (never > one full $1000 position). To close this gap, add a notional
SELL/trim path the runner attributes correctly (sell `delta` notional, reconcile
attributed qty). Documented; not required for a safe first deploy.
