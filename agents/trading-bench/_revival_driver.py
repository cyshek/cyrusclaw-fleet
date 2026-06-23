"""Driver: broad-universe ($1000, 16-instrument) cross-asset 12-1 momentum vs SPX.

Honest OOS: train <=2017-12-31, test 2018+. Net 2bps/side both legs.
Full-period CONTINUOUS-SPAN Sharpe headlined (sharpe_from_returns over the
single equity curve's per-tick returns). Also reports the per-instrument
SELECTION-FREQUENCY table (the saturation test).

Reuses runner.backtest_xsec (engine) + the candidate decide_xsec. Imports
runner modules read-only. Builds NOTHING under strategies/.
"""
from __future__ import annotations
import sys, json, importlib, math
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import daily_bars_cache as dbc
from runner.backtest import CostModel, bars_per_year
from runner.backtest_xsec import backtest_xsec
from runner.fp_sharpe import equity_curve_returns, sharpe_from_returns

CAND = "xsec_momentum_revival_b16"
cand_dir = WORKSPACE / "strategies_candidates" / CAND
mod = importlib.import_module(f"strategies_candidates.{CAND}.strategy")
params_base = json.loads((cand_dir / "params.json").read_text())
BASKET = list(params_base["basket"])
TF = params_base["timeframe"]
LOOKBACK = int(params_base["lookback_bars"])
SKIP = int(params_base["skip_bars"])
BPY = bars_per_year(TF, False)  # 252

COMMON_START = "2007-01-01"   # after SLV 2006-04 inception; gives 12-1 warmup room
TRAIN_END = "2017-12-31"
TEST_START = "2018-01-01"

# ---- Load bars: daily_bars_cache {date,adjclose,...} -> backtest_xsec {t,c} ----
def load_bars(sym):
    d = dbc.get_daily(sym)
    out = []
    for r in d:
        ac = r.get("adjclose")
        if ac is None:
            continue
        out.append({"t": f'{r["date"]}T00:00:00Z', "c": float(ac),
                    "o": float(r.get("open") or ac), "h": float(r.get("high") or ac),
                    "l": float(r.get("low") or ac), "v": float(r.get("volume") or 0)})
    return out

ALL = {s: load_bars(s) for s in BASKET}
for s in BASKET:
    assert ALL[s], f"no bars for {s}"

# Window slicer: keep bars with date in [start_lo, end_hi]. For the signal
# warmup we INCLUDE pre-start history so the first tradeable month already has
# 252+21 bars. The backtest equity curve is what we measure; trades only fire
# from the first month-change tick that has enough history.
def slice_bars(bars, lo, hi):
    return [b for b in bars if lo <= b["t"][:10] <= hi]

# For a given measurement window [wstart, wend], we load bars from
# (wstart - ~14 months of warmup) so 12-1 is computable at wstart.
def warmup_start(wstart_iso, extra_days=420):
    d = datetime.strptime(wstart_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (d.replace(year=d.year-2)).strftime("%Y-%m-%d")  # 2yr warmup, generous

CM = CostModel.alpaca_stocks()  # 2 bps spread, 0 fee -> 2bps/side
print("CostModel:", CM)

# ---- SPX (SPY) buy&hold on the SAME measurement path, 2bps/side ----
def spx_buyhold_metrics(wstart, wend):
    """SPY adjclose buy at first bar in window (2bps), mark-to-market daily,
    continuous-span Sharpe on the daily equity curve. Sell-cost applied to the
    terminal value for raw-return parity."""
    spy = slice_bars(ALL["SPY"], wstart, wend)
    if len(spy) < 2:
        return None
    buy_px = CM.buy_fill_price(spy[0]["c"])
    eq = []
    for b in spy:
        # mark to market at adjclose (no exit cost intramark)
        eq.append(b["c"] / buy_px)  # normalized to 1.0 at entry pre-cost
    # raw cumulative return net of entry+exit cost:
    sell_px = CM.sell_fill_price(spy[-1]["c"])
    raw_ret = (sell_px - buy_px) / buy_px
    rets = equity_curve_returns(eq)
    sharpe = sharpe_from_returns(rets, BPY)
    # CAGR + maxDD on the eq curve
    yrs = (datetime.strptime(spy[-1]["t"][:10], "%Y-%m-%d") - datetime.strptime(spy[0]["t"][:10], "%Y-%m-%d")).days / 365.25
    cagr = (eq[-1]) ** (1/yrs) - 1 if yrs > 0 and eq[-1] > 0 else float("nan")
    peak = -1e9; mdd = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v/peak - 1)
    return {"raw_ret_pct": raw_ret*100, "sharpe": sharpe, "cagr_pct": cagr*100,
            "maxdd_pct": mdd*100, "n_bars": len(spy),
            "span": [spy[0]["t"][:10], spy[-1]["t"][:10]]}

# ---- Strategy metrics for a given K + measurement window ----
def strat_metrics(top_k, wstart, wend):
    params = dict(params_base)
    params["top_k"] = top_k
    params["xsec_basket_size"] = top_k
    # load bars with warmup, then the engine's clock naturally spans them; we
    # measure return over the curve but want it aligned to [wstart, wend]. The
    # cleanest honest approach: feed bars from warmup_start..wend, then slice
    # the equity curve to the sub-span >= wstart. backtest_xsec returns one
    # equity point per clock tick (union of all symbols' bar dates), so we can
    # map ticks->dates and slice.
    ws = warmup_start(wstart)
    bbs = {s: slice_bars(ALL[s], ws, wend) for s in BASKET}
    bbs = {s: b for s, b in bbs.items() if len(b) > (LOOKBACK + SKIP + 5)}
    bt = backtest_xsec(CAND, bbs, params, decide_xsec_fn=mod.decide_xsec,
                       default_cost_model=CM, starting_cash=1000.0)
    # Build the clock (union of dates) to align equity_curve to dates.
    all_t = sorted({b["t"] for b in (bi for bs in bbs.values() for bi in bs)})
    # backtest_xsec builds its own clock identically (build_clock = sorted union)
    ec = bt.equity_curve
    # equity_curve length should equal len(clock). Align:
    if len(ec) != len(all_t):
        # be defensive: truncate to min
        n = min(len(ec), len(all_t))
        ec = ec[:n]; all_t = all_t[:n]
    # slice to measurement window [wstart, wend]
    idx = [i for i, t in enumerate(all_t) if wstart <= t[:10] <= wend]
    if not idx:
        return None
    i0, i1 = idx[0], idx[-1]
    ec_win = ec[i0:i1+1]
    if len(ec_win) < 2 or ec_win[0] <= 0:
        return None
    # normalize so window starts at 1.0
    base = ec_win[0]
    ec_norm = [v/base for v in ec_win]
    rets = equity_curve_returns(ec_norm)
    sharpe = sharpe_from_returns(rets, BPY)
    raw_ret = ec_norm[-1] - 1.0
    yrs = (datetime.strptime(all_t[i1][:10], "%Y-%m-%d") - datetime.strptime(all_t[i0][:10], "%Y-%m-%d")).days / 365.25
    cagr = (ec_norm[-1]) ** (1/yrs) - 1 if yrs > 0 and ec_norm[-1] > 0 else float("nan")
    peak = -1e9; mdd = 0.0
    for v in ec_norm:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v/peak - 1)
    return {"raw_ret_pct": raw_ret*100, "sharpe": sharpe, "cagr_pct": cagr*100,
            "maxdd_pct": mdd*100, "n_trades": bt.n_trades, "n_buys": bt.n_buys,
            "n_closes": bt.n_closes, "n_clamps": bt.n_basket_clamps,
            "span": [all_t[i0][:10], all_t[i1][:10]], "n_ticks_win": len(ec_win)}

# ---- Selection-frequency: replicate monthly winners over [wstart,wend] ----
def selection_frequency(top_k, wstart, wend):
    """At each calendar-month boundary in [wstart,wend], compute the 12-1 rank
    on bars visible up to that month-end and record the top-K winners. Pure
    signal replay (lookahead-safe: uses only bars dated <= month-end, with the
    skip-month gap baked into _rank_12_1). Returns {sym: n_months_held}, n_months."""
    ws = warmup_start(wstart)
    bbs = {s: slice_bars(ALL[s], ws, wend) for s in BASKET}
    # union of month-end trading dates within window
    months = {}
    for s, bs in bbs.items():
        for b in bs:
            mk = b["t"][:7]
            if b["t"][:10] >= wstart:
                months.setdefault(mk, set())
    counts = {s: 0 for s in BASKET}
    n_months = 0
    # For each month, find the last bar date <= that month's last day across union
    union_dates = sorted({b["t"] for bs in bbs.values() for b in bs})
    # group union dates by month, take the last date of each month >= wstart
    by_month = {}
    for t in union_dates:
        by_month.setdefault(t[:7], []).append(t)
    for mk in sorted(by_month):
        last_t = by_month[mk][-1]
        if last_t[:10] < wstart:
            continue
        # bars visible up to last_t per symbol
        vis = {}
        for s, bs in bbs.items():
            v = [b for b in bs if b["t"] <= last_t]
            if len(v) >= (LOOKBACK + SKIP + 1):
                vis[s] = v
        ranks = mod._rank_12_1(vis, LOOKBACK, SKIP)
        if not ranks:
            continue
        winners = [sym for _, sym in ranks[:top_k]]
        for w in winners:
            counts[w] += 1
        n_months += 1
    return counts, n_months

# ====================== RUN ======================
RESULTS = {"common_start": COMMON_START, "train_end": TRAIN_END, "test_start": TEST_START}

windows = {
    "FULL": (COMMON_START, "2026-06-30"),
    "TRAIN(<=2017)": (COMMON_START, TRAIN_END),
    "TEST(2018+)": (TEST_START, "2026-06-30"),
}
RESULTS["spx"] = {wn: spx_buyhold_metrics(*wr) for wn, wr in windows.items()}
RESULTS["strat"] = {}
for K in (3, 4, 5):
    RESULTS["strat"][K] = {wn: strat_metrics(K, *wr) for wn, wr in windows.items()}

RESULTS["selection"] = {}
for K in (3, 4, 5):
    for wn, wr in windows.items():
        c, n = selection_frequency(K, *wr)
        RESULTS["selection"][f"K{K}_{wn}"] = {"counts": c, "n_months": n}

print(json.dumps(RESULTS, indent=2, default=str))
Path("_revival_results.json").write_text(json.dumps(RESULTS, indent=2, default=str))
print("\nWROTE _revival_results.json")
