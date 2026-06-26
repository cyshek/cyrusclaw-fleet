# INTRADAY / MINUTE-BAR READINESS AUDIT — trading-bench harness
**Generated:** 2026-06-25T15:55:00Z · **Scope:** read-only gap analysis (no runner/strategy code modified) · **Auditor:** subagent (opus)

---

## (a) VERDICT

> ## ⚠️ **NOT-READY — 3 must-fix items** (1 of them is a silent Sharpe-inflation bug that ALSO corrupts the *current* default-timeframe `1Hour` results, not just future minute work).

The harness *plumbing* is timeframe-parameterized and will mechanically *run* at 1Min/5Min/etc. — but it will produce **wrong, optimistically-biased numbers** at every intraday timeframe because of a class-blind annualization constant, and the strategy library carries a lookback-semantics foot-gun. None of these are blockers to *building* an intraday strategy; they are blockers to *trusting its backtest*. Data feasibility is **GREEN** (better than assumed — see section (e)).

---

## (b) FINDINGS TABLE

| # | Item | Status | Evidence (FILE:LINE) | Impact |
|---|------|--------|----------------------|--------|
| 1 | Annualization (bars/year) class-blind for intraday | ❌ **MUST-FIX** | `runner/backtest.py:124-150` | **Sharpe overstated 2.31× at EVERY intraday TF** (incl. current default 1Hour). Uses 24h×365d; equities are ~6.5h×252d. |
| 2 | Multi-year intraday data availability (free) | ✅ FINE | live probe (Alpaca IEX) | 1Min→~2yr (212k bars), 5Min/1Hour→4yr+. Multi-year intraday IS feasible free. NOT a blocker. |
| 3 | Cost model frequency | ✅ FINE | `runner/backtest.py:497,522`; no per-bar cost | Charged **per-trade only** (buy/sell/close). No per-bar/financing/borrow. Correct at any frequency. (One caveat on bps realism — see detail.) |
| 4 | Warmup / lookback-in-bars translation | ❌ **MUST-FIX** | `strategies/_lib/indicators.py:16`, all `params.json`; no scaler anywhere in `runner/` | A daily-intent `slow:30` SMA becomes a **30-MINUTE** SMA at 1Min. Zero guard. Strategies are written assuming the bar = the daily intent. |
| 5 | Sharpe denominator consumes the bad bpy | ❌ confirmed (propagation of #1) | `runner/backtest.py:587-588` | Headline Sharpe = `(mean/std)*sqrt(bars_per_year(...))` → finding #1 flows straight into the leaderboard number. |
| 6 | Other hard-coded 252/365/"1Day" landmines | ✅ mostly FINE | `fp_sharpe.py:104`, `backtest_xsec.py:827`, `backtest_event.py:690`, `spy_relative.py:156`, `vix_overlay_backtest.py:59` | All route through the SAME `bars_per_year()` → all inherit #1 for intraday, but none add a *new* independent bug. `risk_metrics.py`/`allocator`/`finra` √252 are on **daily-P&L series** → correctly daily, unaffected. |
| 7 | Risk rails "per day" at intraday | ⚠️ REVIEW | `runner/risk.py:51` (`MAX_TRADES_PER_DAY=4`), `backtest.py:254` (`_bar_utc_day`) | Cap is enforced correctly per **UTC** day, but `cap=4/day` is a daily-decision assumption that will throttle/distort any intraday strategy that wants >4 entries/exits in a session. Bounding works; the *number* is wrong for intraday. |

Legend: ✅ fine · ⚠️ review/known-limitation · ❌ must-fix before trusting intraday results.

---

## (c) PER-ITEM DETAIL (with code quotes)

### 1 ❌ Annualization is class-blind for intraday — THE BIG ONE

`runner/backtest.py:124-150`. The `BARS_PER_YEAR` map hard-codes **24 hours/day × 365 days/year** for every intraday timeframe, and the `bars_per_year()` accessor only branches on market class for the `1Day` case:

```python
# runner/backtest.py:124
BARS_PER_YEAR = {
    "1Min": 60 * 24 * 365,     # = 525,600
    "5Min": 12 * 24 * 365,     # = 105,120
    "15Min": 4 * 24 * 365,
    "30Min": 2 * 24 * 365,
    "1Hour": 24 * 365,         # = 8,760
    ...
    "1Day": 365,
}
EQUITY_TRADING_DAYS_PER_YEAR = 252        # line 138

def bars_per_year(timeframe: str, is_crypto: bool) -> float:   # line 141
    if timeframe == "1Day":
        return 365.0 if is_crypto else float(EQUITY_TRADING_DAYS_PER_YEAR)
    return float(BARS_PER_YEAR.get(timeframe, 24 * 365))       # line 150  ← is_crypto IGNORED for ALL intraday
```

**The exact code path the task asked me to trace:** for any intraday `timeframe`, the `if timeframe == "1Day"` branch is skipped and execution falls through to line 150, which indexes `BARS_PER_YEAR` **with no reference to `is_crypto`**. There is **NO equity-vs-crypto branch for intraday anywhere** — `is_crypto=False` gets the identical 24×365-derived count as crypto. The in-code comment (lines 143-146) explicitly *defends* this: *"Intraday timeframes are wall-clock based and identical for both classes."* That reasoning is **wrong for equities**: a US equity 1Min bar only exists during the ~6.5h regular session on ~252 days/yr, not 24/7×365.

**Magnitude (computed + empirically grounded):** Equities trade ~390 min/day × 252 sessions ≈ **98,280** 1-min bars/yr. The harness assumes **525,600**. Ratio = 5.348 → Sharpe is multiplied by `sqrt(5.348)` =

> **Sharpe OVERSTATED by 2.31× at *every* intraday timeframe** (1Min, 5Min, 15Min, 30Min, **and 1Hour**).

The ratio is identical across timeframes because the error is purely `(1440 min/day ÷ ~390 min/day) × (365 ÷ 252) = 3.69 × 1.448 = 5.35` regardless of bar size. (Live-confirmed bar density below pins the ~390 figure: Alpaca returned 392-404 1Min bars/day and 7-9 1Hour buckets/day for SPY.)

**This is not hypothetical / future-only.** The current default timeframe across the live strategy slate is `1Hour` (every `params.json` checked: `sma_crossover_qqq`, `buy_and_hold_spy`, `rsi_mean_revert_iwm`, `…_rth`). So **existing 1Hour backtests already carry the 2.31× inflation** — the leaderboard Sharpe for the equities tournament is overstated by that factor today.

**Suggested fix (do NOT apply here — punch-list item):** make `bars_per_year` class-aware for intraday, e.g. equity intraday bpy = `(390 / interval_minutes) * 252` (or `6.5*60/…`), crypto intraday stays `(1440/interval_minutes) * 365`. The `TF_MINUTES` map already exists in `bars_cache.py:28` to source `interval_minutes`.

---

### 5 ❌ The per-tick Sharpe denominator consumes the same bad bpy (direct propagation of #1)

The task referenced a `_stats_from_equity` at ~line 178 — **that function does not exist**; stats are computed **inline** inside `backtest()`. The actual headline-Sharpe site is `runner/backtest.py:582-589`:

```python
mean = sum(returns) / len(returns)
var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
std = math.sqrt(var)
if std > 0:
    bpy = bars_per_year(timeframe, is_crypto)      # line 587  ← the poisoned constant
    sharpe = (mean / std) * math.sqrt(bpy)          # line 588
```

`returns` are **per-bar equity returns**; multiplying per-bar stdev by `sqrt(bpy)` is the standard annualization. Because `bpy` is wrong by 5.35× for intraday equities, the reported `result.sharpe` is wrong by `sqrt(5.35)=2.31×`. Confirmed: **finding #1 propagates directly into the single headline number** the bench ranks on. Same structure in the other two engines:
- `runner/backtest_xsec.py:820-828` — `bpy = bars_per_year(timeframe, xsec_is_crypto)` then `sharpe = (mean/std)*sqrt(bpy)`.
- `runner/backtest_event.py:690` — `bpy = bars_per_year(timeframe, is_crypto)` → `sharpe_from_returns(rets, bpy)`.

---

### 2 ✅ Data fetch depth / availability — FEASIBLE (better than assumed)

`runner/bars_cache.py:get_bars` (line 112) → `_fetch_range` (line 64). For sub-hour equity timeframes it builds:

```python
# runner/bars_cache.py:88
url = (f"{client.cfg.data_base}/v2/stocks/{quote(sym)}/bars"
       f"?timeframe={timeframe}&limit=10000&feed=iex"
       f"&start={start_iso}&end={end_iso}&sort=asc&adjustment=raw")
```

Source = **Alpaca v2 stocks bars, `feed=iex` (free tier; SIP is paid)**, fully paginated via `next_page_token` (no client-side range cap — it pulls the entire `[start,end]` window). **Yahoo is NOT used for intraday** — `daily_bars_cache.py` is `interval=1d` only (`daily_bars_cache.py:79`), so the famous Yahoo 1m→7d / 5m→60d caps are **irrelevant** to this harness.

**Live-probed from THIS VM (2026-06-25, SPY, end=2026-06-20):**

| TF | days requested | bars returned | earliest bar | per-day density |
|----|----|----|----|----|
| 1Min | 800 | 212,635 | 2024-04-11 | ~392-404/day |
| 5Min | 1500 | 85,564 | 2022-05-12 | ~78/day |
| 1Hour | 1500 | 8,477 | 2022-05-12 | ~7-9/day |

→ **1Min reaches back ~2.2 years; 5Min & 1Hour reach the full 4-year window requested.** Multi-year intraday backtesting is **possible for free today**. Caveats: (i) free feed is **IEX-only** (a fraction of consolidated volume — fills/liquidity at minute scale will be optimistic vs SIP/NBBO); (ii) bars are `adjustment=raw` (fine intraday within a split-free window, but a multi-year intraday backtest spanning a split will see a price discontinuity — relevant for split-happy names, not for SPY/QQQ-class); (iii) data is ~RTH + thin pre-market (12:00-20:20Z observed), so there is *some* extended-hours contamination in the bar stream.

---

### 3 ✅ Cost model is per-TRADE, not per-bar — safe at minute frequency

`CostModel` (`runner/backtest.py:189`) applies a one-way `spread_bps` via fill-price skew + a per-side `fee_bps`. Costs accrue **only inside the buy/sell/close branches** (`backtest.py:497` on buy, `:522` on close; mirrored at `backtest_event.py:479/631`, `backtest_xsec.py:668/756`). Grep for `financing|borrow|carry|per_bar|holding_cost|funding` in the three engines → **empty**. So holding a position for 1 bar vs 1000 bars costs the same — **no cost explosion at 1Min**. ✅

**Caveat (not a bug, but document for intraday):** `CostModel.alpaca_stocks()` (`backtest.py:217`) hard-codes **2 bps one-way** ("SPY/QQQ-class"). That is a *daily-liquidity* spread assumption. At 1Min, effective spread + impact for anything outside mega-cap ETFs is materially wider, and the IEX-only feed understates true touch. The model won't break, but **2 bps will flatter minute-frequency strategies** — tune per-symbol before trusting high-turnover intraday Sharpe.

---

### 4 ❌ Lookback windows are raw bar counts with NO timeframe translation — the foot-gun

Every strategy expresses lookbacks as **integer bar counts** in `params.json` and feeds them straight to the indicator lib, which slices the last N **bars** with no notion of wall-clock:

```python
# strategies/_lib/indicators.py:16
def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period      # last `period` BARS, full stop
```
```json
// strategies/sma_crossover_qqq/params.json   (timeframe "1Hour")
{ "fast": 10, "slow": 30, "bar_limit": 120 }
```

A grep across `runner/` and `strategies/_lib/` for any `timeframe→lookback` / `bars_per_day` / `minutes_to_bars` scaler returns **nothing** (the only "scale" hits are vol-targeting in `tsmom_blend_paper_tracker.py`, unrelated). Consequence: run `sma_crossover_qqq` unchanged at `1Min` and `slow:30` is a **30-MINUTE** SMA, not the ~30-day-equivalent the author intended. `rsi_period:14` → 14 minutes. **There is no guard, no warning, no auto-rescale.** `strategy_gen.py:634` even instructs the generator *"bar_limit >= 2x your longest lookback"* — reinforcing that the entire library treats "lookback" as bars and silently inherits whatever `timeframe` says.

Related warmup gap: `bar_limit` is only a *fetch-size* hint (`runner.py:197`, `candidate_smoke.py:88`); `walk_forward.py:289` has `min_bars=10` which is a "did we get data" floor, **not** a lookback-semantics guard. A 200-bar SMA at 1Min needs only ~0.5 trading days of history to "warm up," so warmup-sufficiency checks that were sane for daily bars become meaningless. **Document, don't fix** (per task) — but any intraday strategy must define lookbacks in the intended units and/or the harness needs a `lookback_bars = lookback_minutes / interval_minutes` convention before reuse.

---

### 6 ✅ Other 252/365/"1Day" sites — all either route through `bars_per_year` or are legitimately daily

Full grep of `runner/*.py` for `252`, `365`, `1Day`, `bars_per_year` callsites:
- **Route through the shared (buggy-for-intraday) `bars_per_year`** → inherit #1, add nothing new: `fp_sharpe.py:104`, `backtest_xsec.py:827`, `backtest_event.py:690`, `spy_relative.py:156`, `vix_overlay_backtest.py:59`. Fixing `bars_per_year` once fixes all of these.
- **Legitimately daily (√252 on a realized DAILY-P&L series, intraday-irrelevant)** → ✅ correct as-is: `risk_metrics.py:30` (Sortino/Calmar on daily P&L), `allocator_paper_tracker.py:81/386`, `tsmom_blend_paper_tracker.py:107`, `lane_honesty.py:56`, `finra_shortvol_backtest.py:38`, `sweep.py:282` (CAGR years = days/252). These operate on per-day aggregates, so 252 is right regardless of the underlying bar timeframe — **do not "fix" these.**
- `regime_classifier.py:209` (`max(closes[-252:])` = 52-wk high) and `vix_regime.py:41` (252d percentile window) are daily-series lookbacks — fine in their daily context; would be a *separate* lookback-in-bars issue (#4-class) only if ever fed intraday bars.

---

### 7 ⚠️ Risk rails: "per day" is enforced correctly but the *cap value* is a daily-decision assumption

`runner/risk.py:51` `MAX_TRADES_PER_DAY = 4`. Enforcement keys on the bar's **UTC calendar day**:

```python
# runner/backtest.py:254
def _bar_utc_day(bar: dict) -> str:
    t = bar.get("t") or ""
    return t[:10] if isinstance(t, str) and len(t) >= 10 else ""
```
…and `trades_by_day[day]` is checked in all three engines (`backtest.py`, `backtest_xsec.py:623/637`, event). So the mechanism **does** work at intraday: it correctly counts trades within a UTC day even when there are hundreds of bars/day. **No correctness bug** in the counter. **But:** `4 trades/UTC day` encodes "this is a once-or-twice-a-day-decision book." An intraday strategy that legitimately enters/exits several times per session will be **silently throttled** (every trade past #4 logs `skip_risk` and is dropped, biasing the backtest toward the early-session trades). The basket override (`resolve_trades_per_day`, `risk.py:71`, `max(4, 2*K)`) only helps *cross-sectional* baskets, not a high-frequency single-name. Also note `_bar_utc_day` buckets on **UTC**, not ET — an intraday equity session (09:30-16:00 ET) sits within one UTC day so this is fine *today*, but any logic that should reset on the **trading** day rather than the UTC day is a latent mismatch worth noting. **Decision needed** (not a code bug): pick an intraday-appropriate per-session cap before running minute strategies.

---

## (d) MUST-FIX PUNCH-LIST (priority order, before first intraday strategy)

1. **[CRITICAL] Fix `bars_per_year()` for intraday equities** (`runner/backtest.py:141-150`). Add a class-aware intraday branch: equity intraday bpy = `(390 / TF_MINUTES[tf]) * 252` (crypto keeps `(1440/TF_MINUTES[tf]) * 365`). This single change corrects the 2.31× Sharpe inflation across **all** engines (`backtest`, `backtest_xsec`, `backtest_event`, `fp_sharpe`, `spy_relative`, `vix_overlay`) at once. **Bonus: it also de-inflates the *current* 1Hour leaderboard** — re-run/re-rank existing 1Hour results after the fix, because today's rankings are overstated by 2.31×. Add a unit test pinning `bars_per_year("1Min", is_crypto=False) ≈ 98_280`.
2. **[HIGH] Establish a lookback-in-time convention + guard** (`strategies/_lib` + new strategies). Either express lookbacks as minutes and convert `lookback_bars = minutes / TF_MINUTES[tf]`, or add an assertion/warning when a strategy's bar-count lookback × `interval_minutes` is wildly shorter than a daily-equivalent. At minimum, **never reuse a daily-authored strategy at 1Min without rescaling its windows** — the SMA/RSI periods are bars, not days.
3. **[MEDIUM] Re-scope the per-day risk cap for intraday** (`runner/risk.py:51`). Decide an intraday-appropriate `MAX_TRADES_PER_DAY` (or per-session cap) so a legitimate multi-entry intraday strategy isn't silently truncated after 4 trades. Consider bucketing on the **ET trading day** rather than UTC if any future symbol/session crosses a UTC midnight.

(Non-blocking follow-ups: tune `CostModel.alpaca_stocks` spread per-symbol for minute realism; account for IEX-only feed + `adjustment=raw` split discontinuities when a multi-year intraday window spans a split.)

---

## (e) DATA FEASIBILITY VERDICT

> **GREEN — multi-year intraday bars ARE obtainable for free from the current source (Alpaca IEX), no new paid data required to start.**

Live-verified from this datacenter VM today: **1Min ≈ 2.2 years** (212k SPY bars back to 2024-04), **5Min & 1Hour ≈ 4+ years** (back to 2022-05). The harness already paginates the full window (`bars_cache._fetch_range`, no range cap) and caches to disk. This is **more** intraday depth than the task's prior assumption ("Alpaca free minute history famously limited"). Real constraints to design around, none of which are hard blockers:
- **IEX-only feed** (free) ≠ consolidated SIP/NBBO → minute-scale fills/liquidity are optimistic; treat intraday Sharpe as an upper bound until validated on better data or with wider cost assumptions.
- **1Min depth (~2yr) is shallower than 5Min/1Hour (~4yr)** — if a strategy needs a long intraday sample, 5Min is the sweet spot for both depth and bar count.
- **`adjustment=raw`** intraday bars carry split discontinuities across multi-year windows (irrelevant for non-splitting ETFs like SPY/QQQ; matters for split-happy single names).

**Bottom line:** data is not the blocker. The blocker is the **annualization bug (must-fix #1)** plus the **lookback-semantics foot-gun (must-fix #2)**. Fix those two and the harness is trustworthy for intraday; #3 (risk cap) is a quick config decision.

---

*Report is analysis-only. No `runner/` or `strategies/` code was modified. Temporary probe scripts were created and deleted.*
