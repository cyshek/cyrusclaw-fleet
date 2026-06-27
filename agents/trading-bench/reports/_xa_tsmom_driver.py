"""Self-contained driver: CROSS-ASSET 12-1 ABSOLUTE (time-series) MOMENTUM.

Universe: SPY (equity), TLT (bonds), GLD (gold), DBC (commodities), UUP (USD).
Signal:   12-1 absolute momentum = trailing 12m total return SKIPPING the most
          recent month (return from month-end t-12 to month-end t-1).
Rule:     HOLD each asset whose 12-1 momentum > 0; equal-weight the survivors.
          If none positive -> cash (0% that month). Classic Antonacci absolute TSMOM.
Cadence:  Monthly rebalance at month-end close.

HONESTY:
  * D+1 LAG (monthly framing): signal from returns THROUGH end of month M sets the
    weights HELD DURING month M+1, earning month M+1's return. No same-bar lookahead.
  * COST: 2 bps per side on TURNOVER each rebalance. turnover = sum|w_new - w_old|
    over assets INCLUDING the cash leg. cost = turnover * 0.0002 deducted that month.
  * IS/OOS split at 2018-01-01. FULL / IS / OOS reported separately. OOS load-bearing.
  * Benchmark = SPY buy&hold total return on the SAME monthly date path.

Sharpe: monthly mean/std * sqrt(12), full continuous series (NOT median-of-windows).
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from datetime import datetime, timezone

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.daily_bars_cache import get_daily

UNIVERSE = ["SPY", "TLT", "GLD", "DBC", "UUP"]
BENCH = "SPY"
OOS_START = "2018-01-01"
COST_PER_SIDE = 0.0002  # 2 bps one-way on turnover


# ----------------------------------------------------------------------------
# Build monthly adjclose series (last trading day of each month) per symbol.
# ----------------------------------------------------------------------------
def monthly_adjclose(symbol):
    """Return ordered list of (ym, iso_date, adjclose) = last trading day / month."""
    bars = get_daily(symbol)
    by_month = {}  # 'YYYY-MM' -> (iso_date, adjclose)  keep the LATEST date in month
    for b in bars:
        d = b["date"]  # 'YYYY-MM-DD'
        ac = b.get("adjclose")
        if ac is None:
            continue
        ym = d[:7]
        prev = by_month.get(ym)
        if prev is None or d > prev[0]:
            by_month[ym] = (d, float(ac))
    out = []
    for ym in sorted(by_month.keys()):
        iso, ac = by_month[ym]
        out.append((ym, iso, ac))
    return out


def build_panel():
    """Return (months, panel) where months is the sorted list of 'YYYY-MM' common
    to ALL symbols, and panel[symbol] = {ym: (iso_date, adjclose)} for those months."""
    series = {s: monthly_adjclose(s) for s in UNIVERSE}
    sets = [set(ym for ym, _, _ in series[s]) for s in UNIVERSE]
    common = set.intersection(*sets)
    months = sorted(common)
    panel = {}
    for s in UNIVERSE:
        m = {ym: (iso, ac) for ym, iso, ac in series[s] if ym in common}
        panel[s] = m
    return months, panel


# ----------------------------------------------------------------------------
# 12-1 (skip) absolute momentum, generic lookback L and skip K.
#   mom = adjclose[t-K] / adjclose[t-(L+K)] - 1   (return over L months ending K
#   months ago).  For 12-1: L=12, K=1 -> price[t-1]/price[t-13]-1.
#   For 12-0 no-skip: L=12, K=0 -> price[t]/price[t-12]-1.
# Signal at month index i uses prices at indices i-K and i-(L+K), all <= i, so it
# is fully known at end of month i. Weights set at end of month i are HELD during
# month i+1 and earn month i+1's return -> the D+1 lag.
# ----------------------------------------------------------------------------
def momentum_at(prices, i, L, K):
    """prices: list of floats (monthly adjclose). i: current month index.
    Returns the L-month return ending K months ago, or None if not enough history."""
    a = i - K            # recent endpoint (K months ago)
    b = i - (L + K)      # far endpoint
    if b < 0:
        return None
    p_recent = prices[a]
    p_far = prices[b]
    if p_far <= 0:
        return None
    return p_recent / p_far - 1.0


def run_backtest(L=12, K=1, cost_per_side=COST_PER_SIDE, verbose_example=False):
    """Vectorized monthly absolute-TSMOM backtest.

    Returns dict with monthly records, equity curve, and the SPY benchmark on the
    SAME date path. Each month-record m corresponds to the return EARNED in that
    month using weights decided at the PRIOR month-end.
    """
    months, panel = build_panel()
    prices = {s: [panel[s][ym][1] for ym in months] for s in UNIVERSE}
    isodates = [panel[UNIVERSE[0]][ym][0] for ym in months]  # any sym; same month-end-ish

    n = len(months)
    # Pre-compute per-asset monthly simple returns (price[i]/price[i-1]-1), earned in month i.
    rets = {s: [None] + [prices[s][i] / prices[s][i - 1] - 1.0 for i in range(1, n)] for s in UNIVERSE}

    # First month index at which we can compute the signal: need index i-(L+K) >= 0
    # at DECISION time = end of month i. The decided weights earn month i+1.
    first_decision_i = L + K  # smallest i with i-(L+K)>=0
    # weights held going INTO month (first_decision_i + 1).

    records = []
    prev_w = {s: 0.0 for s in UNIVERSE}
    prev_w_cash = 1.0
    equity = 1.0
    eq_curve = [(months[first_decision_i], 1.0)]  # equity stamped at decision month-end (pre first earned month)

    worked_example = None

    for i in range(first_decision_i, n - 1):
        # DECISION at end of month i (index i). Compute 12-1 mom per asset.
        signals = {}
        for s in UNIVERSE:
            signals[s] = momentum_at(prices[s], i, L, K)
        positive = [s for s in UNIVERSE if signals[s] is not None and signals[s] > 0.0]
        if positive:
            w = {s: (1.0 / len(positive) if s in positive else 0.0) for s in UNIVERSE}
            w_cash = 0.0
        else:
            w = {s: 0.0 for s in UNIVERSE}
            w_cash = 1.0

        # Turnover vs previously-held weights (incl cash leg).
        turnover = sum(abs(w[s] - prev_w[s]) for s in UNIVERSE) + abs(w_cash - prev_w_cash)
        cost = turnover * cost_per_side

        # These weights are HELD during month i+1, earning month i+1's returns.
        earn_i = i + 1
        gross = w_cash * 0.0 + sum(w[s] * rets[s][earn_i] for s in UNIVERSE)
        net = gross - cost
        equity *= (1.0 + net)

        rec = {
            "decision_month": months[i],
            "decision_date": isodates[i],
            "earn_month": months[earn_i],
            "earn_date": isodates[earn_i],
            "held": positive[:],
            "weights": {s: w[s] for s in UNIVERSE},
            "w_cash": w_cash,
            "signals": {s: signals[s] for s in UNIVERSE},
            "turnover": turnover,
            "cost": cost,
            "gross_ret": gross,
            "net_ret": net,
            "equity": equity,
            "n_held": len(positive),
            "all_cash": (w_cash == 1.0),
            "fully_invested": (len(positive) == len(UNIVERSE)),
        }
        records.append(rec)
        eq_curve.append((months[earn_i], equity))

        prev_w = w
        prev_w_cash = w_cash

        # Capture one worked example for the lookahead audit (first month with >=1 holding).
        if verbose_example and worked_example is None and positive:
            worked_example = {
                "decision_month_i": months[i],
                "decision_date": isodates[i],
                "lookback_L": L, "skip_K": K,
                "recent_endpoint_month": months[i - K],
                "far_endpoint_month": months[i - (L + K)],
                "recent_endpoint_date": isodates[i - K],
                "far_endpoint_date": isodates[i - (L + K)],
                "signals": {s: signals[s] for s in UNIVERSE},
                "weights": {s: w[s] for s in UNIVERSE},
                "earns_month": months[earn_i],
                "earns_date": isodates[earn_i],
                "note": ("Signal uses prices at decision_date (index i) and earlier ONLY; "
                         "weights earn the NEXT month's return -> D+1 lag, no lookahead."),
            }

    # Benchmark: SPY buy&hold on the SAME earned-month path.
    bench_curve = [(records[0]["decision_month"], 1.0)]
    beq = 1.0
    for rec in records:
        earn_month = rec["earn_month"]
        r = rets[BENCH][months.index(earn_month)]
        beq *= (1.0 + r)
        bench_curve.append((earn_month, beq))

    return {
        "L": L, "K": K,
        "months": months,
        "isodates": isodates,
        "records": records,
        "equity_curve": eq_curve,
        "bench_curve": bench_curve,
        "rets": {BENCH: rets[BENCH]},
        "worked_example": worked_example,
        "first_decision_i": first_decision_i,
    }


# ----------------------------------------------------------------------------
# Metrics. Sharpe = monthly mean/std * sqrt(12). Split FULL / IS / OOS by EARN month.
# ----------------------------------------------------------------------------
def _sharpe(monthly_rets):
    rr = [r for r in monthly_rets if r is not None]
    if len(rr) < 2:
        return 0.0
    m = sum(rr) / len(rr)
    var = sum((r - m) ** 2 for r in rr) / (len(rr) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return 0.0
    return (m / sd) * math.sqrt(12.0)


def _total_return(monthly_rets):
    eq = 1.0
    for r in monthly_rets:
        if r is not None:
            eq *= (1.0 + r)
    return eq - 1.0


def _cagr(monthly_rets):
    rr = [r for r in monthly_rets if r is not None]
    if not rr:
        return 0.0
    eq = 1.0
    for r in rr:
        eq *= (1.0 + r)
    yrs = len(rr) / 12.0
    if yrs <= 0 or eq <= 0:
        return 0.0
    return eq ** (1.0 / yrs) - 1.0


def _maxdd(monthly_rets):
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in monthly_rets:
        if r is None:
            continue
        eq *= (1.0 + r)
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd


def split_metrics(result):
    """Compute FULL/IS/OOS metrics for strategy AND SPY benchmark, split by EARN month."""
    recs = result["records"]
    months = result["months"]
    bench_rets_all = result["rets"][BENCH]

    strat_full, strat_is, strat_oos = [], [], []
    bench_full, bench_is, bench_oos = [], [], []
    earn_months_full = []
    for rec in recs:
        em = rec["earn_month"]
        earn_iso = rec["earn_date"]
        sr = rec["net_ret"]
        br = bench_rets_all[months.index(em)]
        strat_full.append(sr)
        bench_full.append(br)
        earn_months_full.append(em)
        is_oos = earn_iso >= OOS_START
        if is_oos:
            strat_oos.append(sr)
            bench_oos.append(br)
        else:
            strat_is.append(sr)
            bench_is.append(br)

    def pack(rets):
        return {
            "n_months": len([r for r in rets if r is not None]),
            "total_return": _total_return(rets),
            "cagr": _cagr(rets),
            "sharpe": _sharpe(rets),
            "maxdd": _maxdd(rets),
        }

    return {
        "strategy": {"FULL": pack(strat_full), "IS": pack(strat_is), "OOS": pack(strat_oos)},
        "benchmark": {"FULL": pack(bench_full), "IS": pack(bench_is), "OOS": pack(bench_oos)},
        "first_earn_month": earn_months_full[0] if earn_months_full else None,
        "last_earn_month": earn_months_full[-1] if earn_months_full else None,
    }


def regime_stats(result):
    recs = result["records"]
    n = len(recs)
    if n == 0:
        return {}
    all_cash = sum(1 for r in recs if r["all_cash"])
    fully = sum(1 for r in recs if r["fully_invested"])
    avg_n = sum(r["n_held"] for r in recs) / n
    avg_turn = sum(r["turnover"] for r in recs) / n
    # 2022 calendar-year strategy return (earn months in 2022)
    rets_2022 = [r["net_ret"] for r in recs if r["earn_date"][:4] == "2022"]
    spy_2022 = []
    months = result["months"]
    bench_rets_all = result["rets"][BENCH]
    for r in recs:
        if r["earn_date"][:4] == "2022":
            spy_2022.append(bench_rets_all[months.index(r["earn_month"])])
    return {
        "n_rebalances": n,
        "pct_all_cash": all_cash / n,
        "pct_fully_invested": fully / n,
        "avg_assets_held": avg_n,
        "avg_turnover": avg_turn,
        "ret_2022_strategy": _total_return(rets_2022),
        "ret_2022_spy": _total_return(spy_2022),
        "n_months_2022": len(rets_2022),
    }


def main():
    # Primary run: 12-1 with worked example.
    base = run_backtest(L=12, K=1, verbose_example=True)
    metrics = split_metrics(base)
    regime = regime_stats(base)

    # Robustness: lookback variants. OOS Sharpe + OOS total return for each.
    variants = [("6-1", 6, 1), ("9-1", 9, 1), ("12-1", 12, 1), ("12-0", 12, 0)]
    robustness = {}
    for label, L, K in variants:
        r = run_backtest(L=L, K=K)
        m = split_metrics(r)
        robustness[label] = {
            "OOS_sharpe": m["strategy"]["OOS"]["sharpe"],
            "OOS_total_return": m["strategy"]["OOS"]["total_return"],
            "FULL_sharpe": m["strategy"]["FULL"]["sharpe"],
            "FULL_total_return": m["strategy"]["FULL"]["total_return"],
            "IS_sharpe": m["strategy"]["IS"]["sharpe"],
            "IS_total_return": m["strategy"]["IS"]["total_return"],
        }

    out = {
        "universe": UNIVERSE,
        "oos_split": OOS_START,
        "cost_per_side_bps": COST_PER_SIDE * 1e4,
        "data_span": {
            "first_common_month": base["months"][0],
            "last_common_month": base["months"][-1],
            "n_common_months": len(base["months"]),
            "first_decision_month": base["records"][0]["decision_month"],
            "first_earn_month": base["records"][0]["earn_month"],
            "last_earn_month": base["records"][-1]["earn_month"],
            "n_rebalances": len(base["records"]),
        },
        "metrics_12_1": metrics,
        "regime": regime,
        "robustness": robustness,
        "worked_example": base["worked_example"],
    }

    # Sanity prints
    print("=== DATA SPAN ===")
    print(json.dumps(out["data_span"], indent=2))
    print("\n=== WORKED LOOKAHEAD-AUDIT EXAMPLE ===")
    print(json.dumps(base["worked_example"], indent=2, default=str))
    print("\n=== 12-1 METRICS (strategy vs SPY) ===")
    for seg in ("FULL", "IS", "OOS"):
        s = metrics["strategy"][seg]; b = metrics["benchmark"][seg]
        print(f"[{seg}] n={s['n_months']:3}  STRAT tot={s['total_return']*100:8.2f}%  "
              f"CAGR={s['cagr']*100:6.2f}%  Sharpe={s['sharpe']:5.2f}  maxDD={s['maxdd']*100:7.2f}%   "
              f"|| SPY tot={b['total_return']*100:8.2f}%  CAGR={b['cagr']*100:6.2f}%  "
              f"Sharpe={b['sharpe']:5.2f}  maxDD={b['maxdd']*100:7.2f}%")
    print("\n=== REGIME ===")
    print(json.dumps(regime, indent=2))
    print("\n=== ROBUSTNESS (lookback variants) ===")
    for label, _, _ in variants:
        rb = robustness[label]
        print(f"  {label:5}  OOS Sharpe={rb['OOS_sharpe']:5.2f}  OOS tot={rb['OOS_total_return']*100:8.2f}%   "
              f"FULL Sharpe={rb['FULL_sharpe']:5.2f}  FULL tot={rb['FULL_total_return']*100:8.2f}%")

    # Dump raw results
    res_path = WS / "reports" / "_xa_tsmom_result.json"
    res_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[wrote] {res_path}")

    return out, base, metrics, regime, robustness


if __name__ == "__main__":
    main()
