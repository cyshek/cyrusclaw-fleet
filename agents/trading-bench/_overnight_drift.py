"""Overnight drift in leveraged ETFs (Lou, Polk, Skouras 2019) — TQQQ.

Hypothesis: leveraged-ETF returns are NOT uniformly distributed across the
trading day. LPS document a persistent OVERNIGHT (close->open) vs INTRADAY
(open->close) asymmetry. If TQQQ's edge is concentrated overnight (or intraday),
a session-selective hold could beat buy&hold and/or feed the vol-target sleeve.

Decomposition (SPLIT-SAFE — TQQQ splits often, so raw open/close span split
boundaries and must be rescaled by the adjclose factor):

  adj_factor[t]   = adjclose[t] / close[t]          # cumulative split+div factor
  adj_open[t]     = open[t]  * adj_factor[t]         # open on the adjclose scale
  overnight_ret[t]= adj_open[t] / adjclose[t-1] - 1  # close[t-1] -> open[t]
  intraday_ret[t] = adjclose[t] / adj_open[t] - 1    # open[t]   -> close[t]
  (1+overnight)(1+intraday) == adjclose[t]/adjclose[t-1]  (identity check)

Arms (all post-2020 = TQQQ-era that matters; also full 2010+; 2bps/side; SMA-200
gate on QQQ same as the live engine; T-bill cash when flat/out-of-session):

  buyhold_tqqq         : hold TQQQ every day (adjclose-to-adjclose).
  overnight_only       : capture ONLY the overnight leg each day (in at close,
                         out at open) — 1 round-trip/day cost.
  intraday_only        : capture ONLY the intraday leg (in at open, out at close).
  overnight_gated      : overnight leg ONLY when QQQ>200d SMA (trend filter),
                         else T-bill. The plausible vol-target feed.
  intraday_gated       : intraday leg ONLY when QQQ>200d SMA, else T-bill.

Reports mean/day, annualized, FP-cont Sharpe, and which session carries the
edge. PAPER/RESEARCH ONLY. No orders.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from typing import Dict, List, Optional

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc

TRADING_DAYS = 252
COST_BPS = 2.0
OOS_START = "2018-01-01"
ERA_START = "2020-01-01"


def decompose(symbol: str) -> List[Dict]:
    d = dbc.get_daily(symbol)
    out = []
    for i in range(1, len(d)):
        prev, cur = d[i - 1], d[i]
        if prev["adjclose"] <= 0 or cur["close"] <= 0 or cur["open"] <= 0:
            continue
        adj_factor = cur["adjclose"] / cur["close"]
        adj_open = cur["open"] * adj_factor
        overnight = adj_open / prev["adjclose"] - 1.0
        intraday = cur["adjclose"] / adj_open - 1.0
        total = cur["adjclose"] / prev["adjclose"] - 1.0
        out.append({"date": cur["date"], "overnight": overnight,
                    "intraday": intraday, "total": total})
    return out


def build_sma_gate(symbol: str, window: int = 200):
    d = dbc.get_daily(symbol)
    dates = [b["date"] for b in d]
    closes = [b["adjclose"] for b in d]
    sma_at: List[Optional[float]] = [None] * len(closes)
    run = 0.0
    for i in range(len(closes)):
        run += closes[i]
        if i >= window:
            run -= closes[i - window]
        if i >= window - 1:
            sma_at[i] = run / window

    def is_up(day: str) -> bool:
        idx = bisect.bisect_left(dates, day) - 1  # strictly prior daily close
        if idx < 0 or sma_at[idx] is None:
            return False
        return closes[idx] > sma_at[idx]

    return is_up


def tbill_daily(day: str) -> float:
    try:
        import backtest_daily as bd
        return bd._tbill_daily_rate(day)
    except Exception:
        return 0.0


def fp_sharpe(rets: List[float]) -> float:
    n = len(rets)
    if n < 2:
        return 0.0
    m = sum(rets) / n
    v = sum((x - m) ** 2 for x in rets) / (n - 1)
    if v <= 0:
        return 0.0
    return (m / math.sqrt(v)) * math.sqrt(TRADING_DAYS)


def equity_stats(rets: List[float]) -> Dict:
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1.0 + r))
    peak = -1e18
    mdd = 0.0
    for e in eq:
        peak = max(peak, e)
        if peak > 0:
            mdd = min(mdd, e / peak - 1.0)
    return {
        "fp_sharpe": fp_sharpe(rets),
        "total_ret_pct": (eq[-1] - 1.0) * 100.0,
        "maxdd_pct": mdd * 100.0,
        "ann_mean_pct": (sum(rets) / len(rets) * TRADING_DAYS * 100.0) if rets else 0.0,
        "n_days": len(rets),
    }


def build_arm(rows: List[Dict], arm: str, gate=None,
              start: Optional[str] = None, end: Optional[str] = None) -> Dict:
    c = COST_BPS / 10000.0
    rets = []
    for r in rows:
        d = r["date"]
        if start and d < start:
            continue
        if end and d > end:
            continue
        if arm == "buyhold_tqqq":
            rets.append(r["total"])               # no per-day switch
        elif arm == "overnight_only":
            # in at close, out at open => capture overnight, pay 2 sides/day
            rets.append((1.0 + r["overnight"]) * (1.0 - c) * (1.0 - c) - 1.0)
        elif arm == "intraday_only":
            rets.append((1.0 + r["intraday"]) * (1.0 - c) * (1.0 - c) - 1.0)
        elif arm == "overnight_gated":
            if gate(d):
                rets.append((1.0 + r["overnight"]) * (1.0 - c) * (1.0 - c) - 1.0)
            else:
                rets.append(tbill_daily(d))
        elif arm == "intraday_gated":
            if gate(d):
                rets.append((1.0 + r["intraday"]) * (1.0 - c) * (1.0 - c) - 1.0)
            else:
                rets.append(tbill_daily(d))
    return equity_stats(rets)


def main():
    rows = decompose("TQQQ")
    gate = build_sma_gate("QQQ", 200)
    print(f"TQQQ decomposed days: {len(rows)}  {rows[0]['date']} -> {rows[-1]['date']}")

    # identity check
    bad = 0
    for r in rows[:500]:
        recon = (1 + r["overnight"]) * (1 + r["intraday"]) - 1
        if abs(recon - r["total"]) > 1e-9:
            bad += 1
    print(f"identity check (overnight*intraday==total): {bad} mismatches in first 500 (want 0)")

    # raw session means (no cost) — where is the edge?
    for label, s, e in [("FULL 2010+", None, None), ("ERA 2020+", ERA_START, None),
                        ("OOS 2018+", OOS_START, None)]:
        sub = [r for r in rows if (not s or r["date"] >= s) and (not e or r["date"] <= e)]
        on = sum(r["overnight"] for r in sub) / len(sub)
        ind = sum(r["intraday"] for r in sub) / len(sub)
        tot = sum(r["total"] for r in sub) / len(sub)
        print(f"\n[{label}] mean/day  overnight={on*1e4:+.2f}bps  intraday={ind*1e4:+.2f}bps  total={tot*1e4:+.2f}bps "
              f"| ann: ON={on*TRADING_DAYS*100:+.1f}% IN={ind*TRADING_DAYS*100:+.1f}% TOT={tot*TRADING_DAYS*100:+.1f}%")

    arms = ["buyhold_tqqq", "overnight_only", "intraday_only", "overnight_gated", "intraday_gated"]
    res = {}
    for span_name, s, e in [("full", None, None), ("era2020", ERA_START, None),
                            ("oos2018", OOS_START, None)]:
        res[span_name] = {}
        print(f"\n===== {span_name} (cost {COST_BPS}bps/side) =====")
        for arm in arms:
            st = build_arm(rows, arm, gate=gate, start=s, end=e)
            res[span_name][arm] = st
            print(f"  {arm:18s} fpS={st['fp_sharpe']:+.3f} ret={st['total_ret_pct']:9.1f}% "
                  f"maxDD={st['maxdd_pct']:7.2f}% annMean={st['ann_mean_pct']:+.1f}% n={st['n_days']}")

    json.dump(res, open("_overnight_drift_results.json", "w"), indent=2, default=str)
    print("\nwrote _overnight_drift_results.json")


if __name__ == "__main__":
    main()
