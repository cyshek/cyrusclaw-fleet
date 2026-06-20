# Multi-Symbol (Cross-Sectional) Backtest Harness

**Date:** 2026-05-30 17:36 UTC
**Author:** trading-bench subagent (harness wave)
**Scope:** New `runner/backtest_xsec.py` module unblocking 3 archetypes
(#1 cross-sec momentum, #3 low-vol anomaly, #8 sector rotation) from
`reports/ARCHETYPE_TRIAGE_20260530T170659Z.md`.

---

## 1. Design choice: (A) wrapper-of-singletons + synced bar clock

I picked **(A) wrapper-of-singletons**, but with an important refinement:
the harness drives a **synced bar clock** (union of all symbols' bar
timestamps, sorted) so the strategy sees consistent cross-sectional
state at each tick. Per-symbol position bookkeeping reuses the same
fill semantics as `backtest.py` (no-lookahead, CostModel, safety_backstop,
per-trade excursion).

### Why (A) and not (B)

1. **All three target archetypes are "compute features per symbol →
   rank → allocate" with monthly rebalance.** None require intra-bar
   synchronous coordination. Cross-sec momentum (Jegadeesh-Titman):
   12-1 month return rank, monthly rotate. Low-vol (Ang-Hodrick-Xing-
   Zhang): 1–12mo realized vol sort, monthly. Sector rotation
   (Faber/Moskowitz): 3-6mo return rank across 11 SPDR ETFs, monthly.
   The synced clock + per-symbol bar slice is sufficient.

2. **`backtest.py` is 774 LOC of battle-tested semantics** — no-lookahead
   slicing, persistent_state cross-flat protocol, safety_backstop
   pre-decide check, per-trade excursion (low/high since entry),
   regime SPY pre-fetch + walk-forward visibility, CostModel
   spread+fee accounting. Rewriting that inner loop multiplies the
   blast radius across all 116 existing tests.

3. **Live-runner mapping is clean.** `runner.py` already runs as one
   strategy per cron tick. A cross-sec strategy graduates as either
   (a) a "rotator" cron that pre-computes the basket allocation once
   per rebalance period and writes per-symbol `params.json` slots that
   sibling singleton-runners read, or (b) a new `runner_xsec.py` thin
   wrapper that calls `decide_xsec` once and dispatches N
   `submit_market_order` calls in deterministic order. Either way,
   the strategy-author API I've defined here is implementable live
   without rewriting `runner.py` itself.

4. **(B)'s only real advantage is intra-bar synchronous coordination
   between symbols** (e.g. pair-trade legs that must fire on the same
   tick). #5 pairs trading needs that — but #5 is `DEFER` in the
   triage and structurally requires shorts we don't have. When/if we
   need it, (A) and (B) can coexist; we add a `decide_xsec_tick` API
   to the same module.

### What (A)+synced-clock buys us over naive parallel singletons

Naive parallel singletons (run N independent `backtest()` then stitch
results) would break:
  - **Shared risk cap.** No way to enforce `MAX_POSITION = $100` across
    the basket — N independent runs each see $100 headroom.
  - **Cross-sectional ranking visibility.** The strategy needs to see
    *all* symbols' bars at each tick to compute relative momentum/vol.
    Independent runs can't.
  - **Atomic rebalance.** Close old leg + open new leg must use
    consistent timestamps + price state. Independent runs would
    desync.

The synced clock + single outer loop + single shared cash/cap pool
solves all three at the cost of ~600 LOC of fairly mechanical code.

---

## 2. Strategy-author API

### Function signature

```python
def decide_xsec(market_state: dict,
                position_state: dict,
                params: dict) -> dict[str, Action]:
    ...
```

### `market_state` shape

```python
{
    "timeframe": "1Day",
    "clock_t":   "2026-04-30T00:00:00Z",     # current tick (ISO 8601 UTC)
    "symbols": {
        "XLK": {
            "bars":       [...],              # oldest-first; bar.t <= clock_t
            "last_price": 234.56,             # close of most-recent visible bar
            "has_bar":    True,               # True iff a bar printed at exactly clock_t
        },
        "XLF": {...},
        ...
    },
    "regime":  {"spy_closes": [...], "spy_last": 567.8} | None,
    "strategy_state": {},                     # mutable cross-flat persistent state
}
```

### `position_state` shape

```python
{
    "XLK": {"qty": 0.42, "market_value": 98.50, "avg_entry_price": 230.10, ...extras},
    # Symbols NOT currently held are absent (not present with qty=0).
}
```

### Return shape

```python
{
    "XLK": Action(action="buy",   symbol="XLK", notional_usd=80.0, reason="top-rank"),
    "XLF": Action(action="close", symbol="XLF", reason="rotate-out"),
    # Symbols absent => implicit hold.
}
```

`Action` is the same duck-type used by single-symbol strategies
(`.action`, `.symbol`, `.notional_usd`, `.qty`, `.reason`). Strategy
authors can reuse their existing `Action` dataclass unchanged.

### Example: cross-sec momentum (illustrative; not committed)

```python
def decide_xsec(ms, ps, params):
    syms = ms["symbols"]
    lookback = params.get("lookback_bars", 252)   # ~12mo daily
    skip = params.get("skip_bars", 21)            # skip-1mo
    # Only rebalance on the first tick of each month.
    if not _is_month_start(ms["clock_t"], ms["strategy_state"]):
        return {}
    # Rank by lookback-skip return.
    ranks = []
    for sym, sv in syms.items():
        b = sv["bars"]
        if len(b) < lookback + skip:
            continue
        ret = (b[-1 - skip]["c"] - b[-1 - skip - lookback]["c"]) / b[-1 - skip - lookback]["c"]
        ranks.append((ret, sym))
    if not ranks:
        return {}
    ranks.sort(reverse=True)
    top_n = params.get("top_n", 1)
    winners = {sym for _, sym in ranks[:top_n]}
    actions = {}
    # Close losers we currently hold.
    for held in list(ps.keys()):
        if held not in winners:
            actions[held] = Action(action="close", symbol=held,
                                    reason=f"out-of-top-{top_n}")
    # Buy winners we don't currently hold. Per-leg notional = cap / top_n.
    per_leg = 100.0 / top_n   # MAX_POSITION shared across basket
    for w in winners:
        if w not in ps:
            actions[w] = Action(action="buy", symbol=w,
                                 notional_usd=per_leg, reason="top-rank")
    return actions
```

Strategy author does NOT need to think about basket cap arithmetic; if
they ask for too much, the harness scales it down proportionally (with
an `n_basket_clamps` counter incremented + skip reasons logged so the
backtest reviewer can see it happened).

---

## 3. Risk-cap enforcement story

Three layers, in order:

1. **Basket-level clamp (`_clamp_basket`)** — load-bearing new logic.
   At each tick, before any fills, compute:

       existing_pos_usd = Σ qty[s]*last_price[s] for s in books
                          where s is NOT being closed this tick
       requested        = Σ action[s].notional_usd for buy/sell actions
       cap_headroom     = max(0, MAX_POSITION - existing_pos_usd)

   If `requested > cap_headroom`, scale every buy notional by
   `cap_headroom / requested`. If `cap_headroom == 0`, zero out all
   buys (we're already at full exposure; can't add). Result: total
   strategy exposure is bounded by `MAX_POSITION` regardless of how
   greedy the strategy is. `n_basket_clamps` counter exposes this in
   the result so reviewers can see when it fires.

2. **Per-leg risk check (`_bt_check_trade`)** — unchanged from
   single-symbol path. Each clamped notional is then run through the
   same per-trade check: `notional <= MAX_NOTIONAL`, projected
   per-symbol position <= `MAX_POSITION`, and a single shared
   `trades_by_day` counter ≤ `MAX_TRADES_PER_DAY` across the basket
   (4 fills/day total, NOT per-symbol).

3. **Closes execute first** within a tick. This is deliberate: a
   rebalance that closes one name to fund another should free up cap
   headroom before the new buy is sized. Within close/buy groups,
   symbols are processed in sorted-symbol order for determinism.

### Worked example

Strategy holds $100 in XLK, current tick decides to close XLK and buy
$80 each of XLE and XLF:
- `closing_syms = {XLK}`, so `existing_pos_usd = 0` (XLK doesn't count).
- `requested = $160`, `cap_headroom = $100`, scale = `0.625`.
- Clamped: XLE → $50, XLF → $50.
- Closes-first: XLK closes (cash += $100 minus spread/fee).
- Then XLE and XLF each buy $50 (per-leg check passes).
- Total exposure end-of-tick: $100. ✅

`MAX_TRADES_PER_DAY = 4` still binds: a 5-leg rebalance on day 1 gets
exactly 4 fills; the 5th is skipped with reason logged (per-symbol
`skipped_reasons`).

---

## 4. Live-runner integration plan (when first xsec strategy graduates)

**Nothing in `runner/runner.py` changes yet.** Per task constraints, I
did not touch it. Here is the planned change when wave 3 produces a
graduating cross-sec strategy:

### Option (i) — preferred: `runner/runner_xsec.py` thin wrapper

New script that mirrors `runner.py`'s pipeline but for `decide_xsec`:

1. Killswitch check (identical).
2. Load strategy via `load_xsec_strategy()` (already implemented).
3. Read `basket` from `params.json` (or `--basket` flag).
4. Fetch bars per symbol from `AlpacaClient` (one HTTP call each, ~N
   calls — manageable for N ≤ 11 sectors).
5. Build per-symbol position state from `db.strategy_position(name, sym)`
   for each `sym in basket`.
6. Build `market_state` with `symbols` dict, `clock_t = now()`, regime
   slice (same SPY fetch as `runner.py`).
7. Safety backstop per held symbol (same as backtest).
8. Call `decide_xsec(market_state, position_state, params)`.
9. Apply the **same** `_clamp_basket` logic (need to lift it into a
   public function shared between live + backtest — trivial refactor).
10. For each action: per-leg `risk.check_trade` then
    `client.submit_market_order`. Closes first, then buys, sorted-
    symbol order.
11. Log one decision row per leg, one trade row per fill.
12. Print one consolidated receipt: `[name] REBALANCE: close XLK,
    buy XLE $50, buy XLF $50`.

This is ~200 LOC of `runner.py` parallel and doesn't touch the
single-symbol path.

### Option (ii) — defer: rotator + per-symbol params overwrite

The rotator runs at the rebalance cadence (monthly), writes the chosen
basket into each child strategy's `params.json`, and N sibling singleton
crons trade independently. Simpler infra but loses atomic-rebalance
guarantee (one symbol may execute hours before another, creating
basket-cap violations). Not recommended.

### Required `runner.py`-adjacent changes (when we ship)

- Lift `_clamp_basket` out of `backtest_xsec.py` (rename to
  `risk.clamp_basket` so live + backtest share one implementation).
- Add `db.strategy_position_multi(name, syms)` for efficient bulk
  reads (N=11 is fine even unbatched, but a single SELECT is cleaner).
- Update `tournament_loop.py` to register xsec strategies in a separate
  list (or with a `kind="xsec"` flag in params.json) so the orchestrator
  knows which dispatcher to invoke.

### What does NOT need to change

- `risk.py` caps stay the same numbers; only the basket clamp is new.
- `bars_cache.py` — already handles N symbols, just N more cache files.
- `walk_forward.py` — needs a sister `walk_forward_xsec` that calls
  `backtest_xsec` per window; same NAMED_WINDOWS + fitness gate
  semantics apply unchanged (it operates on `total_return_pct`,
  `sharpe`, etc. — all present on `XSecBacktestResult`). Out of scope
  for this PR; ~80 LOC when needed.
- `safety_backstop.py` — already pure per-symbol; reused as-is.

---

## 5. Test summary

**19 new tests in `tests/test_backtest_xsec.py`. Total suite: 135 passing
(116 original + 19 new), 0 failing.**

| # | Test class / case | Covers |
|---|---|---|
| 1 | `TestCrossSectionalRanking.test_top1_momentum_picks_strongest` | Cross-sec ranking: top-1 5-bar momentum across 3 symbols only buys the rising one; never buys flat or falling. |
| 2 | `TestSharedCapClamp.test_clamp_unit_function` | Unit: `_clamp_basket` scales 3×$80 → ~$33.33 each so total == MAX_POSITION. |
| 3 | `TestSharedCapClamp.test_clamp_passes_through_when_under_cap` | Unit: when requested ≤ headroom, clamp returns unchanged + `was_clamped=False`. |
| 4 | `TestSharedCapClamp.test_requesting_3x_80_clamped_to_100_total` | End-to-end: 3-leg rebalance basket clamp produces total deployed = $100. |
| 5 | `TestMissingBarHandling.test_symbol_with_no_bar_at_tick_is_not_fillable` | Symbol with later start date: `has_bar=False` until it prints; buys skipped with "no bar at clock_t" reason; succeeds on first print tick. |
| 6 | `TestBarClockSync.test_clock_is_union_sorted` | Unit: clock = union of all symbols' `t`, sorted ascending. |
| 7 | `TestBarClockSync.test_cursor_advances_only_on_print` | Per-symbol cursor stays put on ticks when that symbol doesn't print; `last_price` is None until first print, then sticks. |
| 8 | `TestNoLookahead.test_strategy_only_sees_bars_up_to_clock_t` | No-lookahead invariant: every bar in every symbol's slice has `t ≤ clock_t`; tick i has exactly i+1 bars per symbol. |
| 9 | `TestEquityCurveAcrossNSymbols.test_known_basket_buy_and_hold` | Equity curve: 2-symbol $50/$50 buy-and-hold of +10%/-10% nets to 0 (hand-computed). |
| 10 | `TestPerSymbolCostModel.test_per_symbol_cost_charged` | Cost model: per-symbol CostModel applied per fill; $50@100bps + $50@200bps = $1.50 total costs. |
| 11 | `TestWalkForwardIntegration.test_multiple_windows_aggregate` | Walk-forward integration: 3 synthetic windows (up-A / flat / up-B); strategy correctly picks A in window 1, nothing in window 2, B in window 3. |
| 12 | `TestDeterminism.test_same_input_same_curve` | Determinism: same bars + same params → byte-identical equity_curve and trade counts across two runs. |
| 13 | `TestAtCapAlreadyBlocksBuys.test_existing_full_position_blocks_new_buy` | Cap-headroom=0 case: existing $100 position blocks new $50 buy; `n_basket_clamps` increments; B leg shows in skipped_reasons. |
| 14 | `TestPerLegNotionalCap.test_single_leg_over_max_notional_is_clamped_to_cap` | Single $150 ask → clamped to exactly MAX_POSITION ($100), trade fills at that size. |
| 15 | `TestPerLegNotionalCap.test_two_legs_each_over_cap_clamped_to_share` | Two $200 asks → each scaled to $50; both fit per-leg cap; total = $100. |

Plus 4 fixture/helper classes split into multiple test cases.

### Smoke test (throwaway, not committed)

`/tmp/smoke_xsec.py` runs a synthetic 3-symbol (XLK rising, XLE mildly
up, XLF falling) top-1 12-bar momentum strategy with monthly-style
rebalance every 12 bars, alpaca_stocks cost model (2 bps):

```
symbols=['XLE', 'XLF', 'XLK']
ticks=50 trades=1 buys=1 closes=0
clamps=0 skipped=0
return: +1.39%  sharpe=161.88  maxDD=-0.00%
final_equity=$1013.94  total_costs=$0.0160
  XLE: buys=0 closes=0 pnl=$+0.00 final_qty=0.0000
  XLF: buys=0 closes=0 pnl=$+0.00 final_qty=0.0000
  XLK: buys=1 closes=0 pnl=$+0.00 final_qty=0.7546
```

Hand-check: ranking correctly identified XLK as strongest; bought
$80 of XLK at ~tick 12 (price ≈ $106), held through tick 49 (price
≈ $124.50). Qty = 80 / (106 * 1.0002) ≈ 0.7546. Open MV = 0.7546 *
124.5 ≈ $93.94. Cash = $1000 − $80 − $0.016 fee = $919.98. Total
equity ≈ $1013.94. Matches the printed +1.39% return.

(Sharpe is absurd because synthetic series has zero noise. Real
strategies on real bars will look nothing like this — that's the
point of `walk_forward.py`.)

---

## 6. Files added/changed

| File | Status | LOC | Notes |
|---|---|---|---|
| `runner/backtest_xsec.py` | NEW | 660 | Cross-sectional harness. Single public entry point: `backtest_xsec(strategy_name, bars_by_symbol, params, ...)`. CLI: `python3 -m runner.backtest_xsec --strategy NAME --basket SYM1,SYM2 [--days N]`. |
| `tests/test_backtest_xsec.py` | NEW | ~530 | 19 unit tests. |
| `reports/MULTI_SYMBOL_HARNESS_20260530T173605Z.md` | NEW | (this file) | Design doc. |
| `runner/backtest.py` | UNCHANGED | — | mtime confirms zero touches; 116 existing tests still green. |
| `runner/runner.py` | UNCHANGED | — | mtime confirms zero touches; live-runner integration deferred per task scope. |
| `runner/risk.py`, `runner/safety_backstop.py`, `runner/walk_forward.py` | UNCHANGED | — | Composed via import; no edits. |

---

## 7. Known limitations / TODOs

1. **No `walk_forward_xsec`.** This PR ships the harness; wiring it
   into the NAMED_WINDOWS walk-forward + fitness gate is a separate
   ~80 LOC addition to `walk_forward.py`. Trivial — the
   `XSecBacktestResult` exposes the same `total_return_pct`,
   `sharpe`, `max_drawdown_pct`, `n_trades` fields the gate reads.

2. **`_clamp_basket` lives inside `backtest_xsec.py`.** When the live
   runner ships an xsec dispatcher, lift this into `runner/risk.py`
   as `clamp_basket(...)` so live + backtest share one implementation.
   (Right now it's `_underscore-private` in the xsec module, which is
   correct — no premature API surface for code that doesn't exist yet.)

3. **Regime gate (SPY) is at the basket level, not per-symbol.** Same
   as single-symbol backtest: all symbols share one regime slice.
   This is the correct semantic for cross-sec strategies (the regime
   filter is asking "is the broad market in an up regime?", which is
   a basket-wide question), but worth flagging.

4. **`trades_by_day` is shared across the basket.** With
   `MAX_TRADES_PER_DAY = 4`, a 5-name monthly rebalance hits the cap
   on day 1 (4 fills go through, 5th is skipped). For monthly-cadence
   xsec strategies with baskets > 4 names, this WILL trip. Two ways
   to handle when it matters: (a) the strategy spreads rebalances
   over multiple days, (b) bump `MAX_TRADES_PER_DAY` for graduated
   xsec strategies via params. Defer; not blocking the 3 target
   archetypes (#8 sector rotation typically holds 1-3 sectors;
   #1/#3 with top-quintile of S&P 500 = 100 names is a different
   conversation that needs cap re-think anyway).

5. **No partial fills.** Same simplifying assumption as `backtest.py`:
   we always fill exactly `notional_usd / fill_price`. Real Alpaca
   crypto can partial-fill below minimums; live runner already handles
   this. Not a regression vs. single-symbol path.

6. **CLI loads bars via `bars_cache.get_bars`** — same caching
   behavior as `backtest.py`. N symbols = N cache files. Cold
   first run is N × single-symbol fetch latency; warm runs are
   N × disk-read. No batching, but the basket-bars Alpaca endpoint
   isn't currently used in `bars_cache.py` either, so this matches
   existing infra.

7. **No SELL action support.** Only `buy` / `close` / `hold` make
   sense for long-only cross-sec. `sell` is accepted (treated like
   buy by clamp + risk) but the 3 target archetypes don't use it.
   Not a regression; the single-symbol harness has the same
   limitation.

8. **`safety_backstop` is per-symbol** — fires independently per
   held leg. A backstop on one symbol synthesizes a close for *that
   symbol only*; other legs still get the strategy's decision.
   That's the right semantic but worth flagging.

---

## 8. Verification

```
$ python3 -m pytest tests/ -q
135 passed in 3.62s
```

(116 original + 19 new.)

Smoke test output above (`/tmp/smoke_xsec.py`) demonstrates the harness
end-to-end on a 3-symbol synthetic basket with realistic cost model.

`runner/runner.py` mtime: 1779912095 (unchanged).
`runner/backtest.py` md5: c940c9572d158aa86f1ac30b07406944 (unchanged from session start).

---

## 9. What this unblocks (and what comes next)

**Unblocked archetypes (wave 3 backtest work):**
- **#8 Sector rotation** — 11 SPDR ETFs, monthly top-1 or top-3 by
  3-6mo return. Smallest universe, simplest signal — should be the
  first archetype implemented against this harness.
- **#3 Low-vol anomaly** — sort by trailing-30d realized vol, hold
  bottom quintile of a 20-50 name universe, monthly rebalance.
- **#1 Cross-sec momentum** — 12-1 month return rank across S&P 500.
  Largest universe — `MAX_TRADES_PER_DAY` becomes relevant; will
  need either per-day stagger or a cap bump.

**Not unblocked (need more harness work):**
- #5 pairs trading: needs shorts.
- #6 PEAD: needs earnings event data (not a harness issue).
- #7 overnight drift: needs MOC/MOO execution semantics (single-symbol).

Recommend wave 3 starts with **#8 sector rotation** as the validation
case for the new harness, then #3, then #1.
