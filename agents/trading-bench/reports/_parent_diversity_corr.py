"""Measure P&L correlation of candidate diversifying parents vs the existing
GATE_PASSING_PARENTS pool, using the SAME structural-backtest methodology as
the 2026-06-22 interstrategy-correlation audit:

  - each strategy's actual decide() logic run via runner.backtest.backtest()
  - fed DAILY adjclose bars (Yahoo v8 cache, split/div-adjusted) shaped into
    the engine's {t,o,h,l,c,v} contract, timeframe='1Day'
  - ZERO cost model (correlation reflects signal shape, not friction)
  - equity curve -> per-bar (daily) returns indexed by bar date
  - Pearson correlation over the union of common trading days (missing -> 0.0,
    a flat day is real signal not missing data, same as runner.correlation)

This is read-only: it imports the engines and strategy modules, runs them in
backtest, and writes ONLY to reports/_parent_diversity_corr_results.json.
No protected file is touched.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest import backtest, load_strategy_module_and_params, CostModel
from runner.daily_bars_cache import get_daily

POOL = [
    "breakout_xlk",
    "sma_crossover_qqq",
    "breakout_xlk_regime",
    "sma_crossover_qqq_regime",
    "rsi_oversold_spy",
    "volume_breakout_qqq",
    "macd_momentum_iwm",
]
CANDIDATES = [
    "trend_follow_gld",
    "tqqq_cot_combo",
    "rsi_mean_revert_iwm",
    "momentum_arkk",
]


def zero_cost():
    # CostModel with all frictions zeroed -> correlation = pure signal shape.
    try:
        return CostModel(commission_per_share=0.0, spread_bps=0.0, slippage_bps=0.0)
    except TypeError:
        cm = CostModel()
        for attr in ("commission_per_share", "spread_bps", "slippage_bps",
                     "fee_bps", "commission_bps"):
            if hasattr(cm, attr):
                try:
                    setattr(cm, attr, 0.0)
                except Exception:
                    pass
        return cm


def daily_bars_for(symbol: str):
    raw = get_daily(symbol)
    out = []
    for b in raw:
        ac = b.get("adjclose", b.get("close"))
        out.append({
            "t": b["date"],
            "o": float(ac),
            "h": float(ac),
            "l": float(ac),
            "c": float(ac),
            "v": float(b.get("volume", 0) or 0),
        })
    return out


def return_series(name: str):
    """Return dict[date_str] -> daily equity return for one strategy."""
    module, params = load_strategy_module_and_params(name)
    params = dict(params)
    sym = params.get("symbol", "")
    if not sym:
        return None, "no single-name symbol (multi-sleeve / decide_xsec)"
    params["timeframe"] = "1Day"
    bars = daily_bars_for(sym)
    if not bars:
        return None, f"no daily bars for {sym}"
    res = backtest(name, bars, params, starting_cash=100000.0,
                   decide_fn=module.decide, cost_model=zero_cost())
    eq = res.equity_curve
    # equity_curve has one entry per bar (len == len(bars)); align returns to
    # the bar that PRODUCED them (i.e. return[i] uses bars[i] date).
    series = {}
    for i in range(1, len(eq)):
        prev = eq[i - 1]
        if prev > 0:
            r = (eq[i] - prev) / prev
            series[bars[i]["t"]] = r
    return series, None


def pearson(xs, ys):
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    if dx2 <= 1e-18 or dy2 <= 1e-18:
        return None
    return num / math.sqrt(dx2 * dy2)


def aligned(a, b):
    days = sorted(set(a.keys()) | set(b.keys()))
    xa = [a.get(d, 0.0) for d in days]
    xb = [b.get(d, 0.0) for d in days]
    return xa, xb, len(days)


def main():
    series = {}
    diag = {}
    for nm in POOL + CANDIDATES:
        s, err = return_series(nm)
        if err:
            diag[nm] = {"error": err}
            series[nm] = None
        else:
            nz = sum(1 for v in s.values() if abs(v) > 1e-18)
            diag[nm] = {"n_days": len(s), "n_nonzero": nz}
            series[nm] = s

    # Build pool-average return series (equal-weight of the 7 pool members,
    # over the union of their days). This is "the pool as one book".
    pool_days = set()
    for nm in POOL:
        if series.get(nm):
            pool_days |= set(series[nm].keys())
    pool_days = sorted(pool_days)
    pool_avg = {}
    for d in pool_days:
        vals = [series[nm].get(d, 0.0) for nm in POOL if series.get(nm)]
        pool_avg[d] = sum(vals) / len(vals) if vals else 0.0

    results = {"diag": diag, "candidates": {}}
    # Pairwise: each candidate vs each pool member + vs pool-average.
    for cand in CANDIDATES:
        cs = series.get(cand)
        if not cs:
            results["candidates"][cand] = {"error": diag[cand].get("error")}
            continue
        per_member = {}
        rs = []
        for nm in POOL:
            ms = series.get(nm)
            if not ms:
                per_member[nm] = None
                continue
            xa, xb, _ = aligned(cs, ms)
            r = pearson(xa, xb)
            per_member[nm] = r
            if r is not None:
                rs.append(r)
        xa, xb, ncommon = aligned(cs, pool_avg)
        r_pool = pearson(xa, xb)
        avg_pairwise = sum(rs) / len(rs) if rs else None
        max_pairwise = max(rs) if rs else None
        results["candidates"][cand] = {
            "vs_each_pool_member": per_member,
            "avg_pairwise_to_pool": avg_pairwise,
            "max_pairwise_to_pool": max_pairwise,
            "corr_to_pool_average_book": r_pool,
            "n_common_days_vs_pool_avg": ncommon,
        }

    # Also: intra-pool average pairwise (baseline — how correlated the
    # existing 7 already are to each other).
    intra = []
    for i, a in enumerate(POOL):
        for b in POOL[i + 1:]:
            if series.get(a) and series.get(b):
                xa, xb, _ = aligned(series[a], series[b])
                r = pearson(xa, xb)
                if r is not None:
                    intra.append(r)
    results["intra_pool_avg_pairwise"] = sum(intra) / len(intra) if intra else None
    results["intra_pool_min_pairwise"] = min(intra) if intra else None
    results["intra_pool_max_pairwise"] = max(intra) if intra else None

    out = WS / "reports" / "_parent_diversity_corr_results.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print("WROTE", out)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
