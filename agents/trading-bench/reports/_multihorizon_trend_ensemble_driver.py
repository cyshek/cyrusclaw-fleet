"""Multi-horizon TREND ENSEMBLE test on the live TQQQ vol-target sleeve.

ASSIGNED: main, 2026-06-27. Scoped per the 06-26 research note
(memory/2026-06-26.md#L336): a 3-horizon EW trend vote vs the single SMA-200
gate, SAME honest harness, 1-day-lag canary, EW-only (no per-horizon weight
optimization). Promote ONLY if it beats the single-window baseline OOS net of
cost AND the Sharpe-gain survives the +1-extra-day-lag canary.

DESIGN (all EW-across-horizons — the honesty constraint; no horizon is
weighted/tuned):
  Horizons = SMA-50 / SMA-100 / SMA-200 on the UNDERLYING (QQQ) adjclose,
  evaluated lookahead-safe through decision day D (reuses the engine's
  `under_closes_through`). Each horizon votes up (last > its SMA) or down.

  Three gates compared, all stacked with the SAME inverse-realized-vol
  target_weight sizing (target 25% ann, 20d rvol, w_max 1.0) the live sleeve
  uses:
    - BASELINE   : single SMA-200 (the live sleeve gate). trend_up = (last>SMA200)
    - ENS_MAJORITY: trend_up = (>=2 of 3 horizons up)  [binary, drop-in]
    - ENS_FRACTION: weight = target_weight(any_up) * (n_up/3)  [continuous EW vote;
                    exposure scales with cross-horizon agreement]

HARNESS (identical to the live sleeve; nothing re-tuned):
  - D+1 lag: decide on closes<=D_prev, hold day D (engine convention, preserved).
  - 2bps switch cost on |dw|; T-bill cash on the (1-w) sleeve.
  - FULL + IS(<=2018-12-31) + OOS(>2018-12-31) FP-continuous Sharpe & CAGR & maxDD.
  - +1-EXTRA-DAY-LAG CANARY: re-run every gate deciding on closes<=D_prev-1
    (i.e. trend computed one extra day stale). The lethal cheap test that killed
    VIX-term and SKEW: if the ensemble's edge evaporates (or flips) under one
    extra day of staleness, it was a lookahead/timing artifact, not a real edge.

READ-ONLY: imports the engine's loaders/stats; does NOT modify any engine,
runner, strategy, or config file. Writes only this driver + a JSON datapack +
a verdict report. No orders, no spend.
"""
from __future__ import annotations

import bisect
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WS = Path(__file__).resolve().parents[1]  # workspace root (reports/ is under it)
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, realized_ann_vol, target_weight, _stats_from_equity,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import _sma

OOS_SPLIT = "2018-12-31"
HORIZONS = [50, 100, 200]
TARGET_VOL = 0.25
VOL_WINDOW = 20
W_MAX = 1.0
SWITCH_BPS = 2.0


def _sma_through(closes: List[float], window: int) -> Optional[float]:
    return _sma(closes, window)


def _fp_sharpe(daily_rets: List[float]) -> float:
    """Full-period continuous annualized Sharpe (daily, sqrt(252)). The canonical
    honest metric (runner/fp_sharpe.py convention)."""
    if len(daily_rets) < 2:
        return 0.0
    mu = statistics.mean(daily_rets)
    sd = statistics.stdev(daily_rets)
    if sd <= 0:
        return 0.0
    return (mu / sd) * (252 ** 0.5)


def _cagr(equity: List[float], n_days: int) -> float:
    if n_days <= 0 or equity[-1] <= 0 or equity[0] <= 0:
        return 0.0
    yrs = n_days / 252.0
    return (equity[-1] / equity[0]) ** (1.0 / max(yrs, 1e-9)) - 1.0


def _maxdd(equity: List[float]) -> float:
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd


def simulate(gate: str, extra_lag: int = 0) -> Dict:
    """Run the vol-target sleeve with the chosen GATE. extra_lag>0 shifts the
    decision window back that many extra trading days (the canary).

    Returns per-day dated returns + equity, so we can split IS/OOS on dates.
    """
    p = VolTargetParams(
        sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
        target_ann_vol=TARGET_VOL, vol_window=VOL_WINDOW, w_max=W_MAX,
        gate_mode="sma200", sma_window=200,
        use_tbill_cash=True, switch_cost_bps=SWITCH_BPS,
    )
    sleeve_bars = bd.dbc.get_daily(p.sleeve)
    under_bars = bd.dbc.get_daily(p.underlying)
    sleeve_by = {b["date"]: b for b in sleeve_bars}

    start = sleeve_bars[0]["date"]
    end = sleeve_bars[-1]["date"]
    cal = [b["date"] for b in sleeve_bars if start <= b["date"] <= end]

    under_dates = [b["date"] for b in under_bars]
    under_close = [b["adjclose"] for b in under_bars]

    def under_closes_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(under_dates, d_iso)
        return under_close[:idx]

    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [b["adjclose"] for b in sleeve_bars]
    sret_end_dates: List[str] = []
    sret_vals: List[float] = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end_dates.append(sleeve_dates[k])
            sret_vals.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)

    def sleeve_rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end_dates, d_iso)
        return sret_vals[:idx]

    def vote(uc: List[float]) -> Tuple[int, bool]:
        """Returns (n_up, sma200_up) for the underlying closes-through series."""
        if not uc:
            return 0, False
        last = uc[-1]
        n_up = 0
        sma200_up = False
        for h in HORIZONS:
            s = _sma_through(uc, h)
            up_h = (s is not None) and (last > s)
            if up_h:
                n_up += 1
            if h == 200:
                sma200_up = up_h
        return n_up, sma200_up

    equity = [1.0]
    dated_rets: List[Tuple[str, float]] = []
    prev_w = 0.0
    n_rebal = 0

    for i in range(1, len(cal)):
        d_prev = cal[i - 1]
        d = cal[i]
        # decision index with optional extra staleness (canary)
        dec_idx = (i - 1) - extra_lag
        if dec_idx < 0:
            # not enough history yet for the lagged decision -> flat
            equity.append(equity[-1])
            dated_rets.append((d, 0.0))
            continue
        d_dec = cal[dec_idx]
        uc = under_closes_through(d_dec)
        n_up, sma200_up = vote(uc)

        rv = realized_ann_vol(sleeve_rets_through(d_dec), VOL_WINDOW)

        if gate == "baseline":
            w = target_weight(sma200_up, rv, TARGET_VOL, W_MAX)
        elif gate == "ens_majority":
            trend_up = n_up >= 2
            w = target_weight(trend_up, rv, TARGET_VOL, W_MAX)
        elif gate == "ens_fraction":
            base = target_weight(n_up > 0, rv, TARGET_VOL, W_MAX)
            w = base * (n_up / len(HORIZONS))
        else:
            raise ValueError(gate)

        b_now = sleeve_by.get(d)
        b_prev = sleeve_by.get(d_prev)
        if b_now and b_prev and b_prev["adjclose"] > 0:
            sleeve_ret = b_now["adjclose"] / b_prev["adjclose"] - 1.0
        else:
            sleeve_ret = 0.0
        cash_ret = bd._tbill_daily_rate(d_prev) if p.use_tbill_cash else 0.0
        blended = w * sleeve_ret + (1.0 - w) * cash_ret

        dw = abs(w - prev_w)
        cost = (SWITCH_BPS / 10000.0) * dw
        if dw > 1e-9:
            n_rebal += 1
        new_eq = equity[-1] * (1.0 + blended) * (1.0 - cost)
        equity.append(new_eq)
        dated_rets.append((d, blended - (cost)))  # net daily return incl cost drag
        prev_w = w

    return {"dates": [cal[0]] + [d for d, _ in dated_rets],
            "equity": equity,
            "dated_rets": dated_rets,
            "n_rebalances": n_rebal}


def split_metrics(sim: Dict) -> Dict:
    """FP-continuous Sharpe / CAGR / maxDD for FULL, IS(<=split), OOS(>split)."""
    dated = sim["dated_rets"]
    full_rets = [r for _, r in dated]
    is_rets = [r for d, r in dated if d <= OOS_SPLIT]
    oos_rets = [r for d, r in dated if d > OOS_SPLIT]

    def eq_from(rets: List[float]) -> List[float]:
        eq = [1.0]
        for r in rets:
            eq.append(eq[-1] * (1.0 + r))
        return eq

    full_eq = sim["equity"]
    is_eq = eq_from(is_rets)
    oos_eq = eq_from(oos_rets)
    return {
        "full": {"sharpe": round(_fp_sharpe(full_rets), 4),
                 "cagr": round(_cagr(full_eq, len(full_rets)), 4),
                 "maxdd": round(_maxdd(full_eq), 4),
                 "total_ret": round(full_eq[-1] / full_eq[0] - 1.0, 4),
                 "n_days": len(full_rets)},
        "is": {"sharpe": round(_fp_sharpe(is_rets), 4),
               "cagr": round(_cagr(is_eq, len(is_rets)), 4),
               "maxdd": round(_maxdd(is_eq), 4),
               "total_ret": round(is_eq[-1] / is_eq[0] - 1.0, 4),
               "n_days": len(is_rets)},
        "oos": {"sharpe": round(_fp_sharpe(oos_rets), 4),
                "cagr": round(_cagr(oos_eq, len(oos_rets)), 4),
                "maxdd": round(_maxdd(oos_eq), 4),
                "total_ret": round(oos_eq[-1] / oos_eq[0] - 1.0, 4),
                "n_days": len(oos_rets)},
        "n_rebalances": sim["n_rebalances"],
        "window": [sim["dates"][0], sim["dates"][-1]],
    }


def main() -> None:
    out = {"test": "multi_horizon_trend_ensemble",
           "sleeve": "TQQQ vol-target (target 25% / 20d rvol / w_max 1.0 / 2bps / T-bill cash)",
           "horizons": HORIZONS, "oos_split": OOS_SPLIT,
           "design": "EW-across-horizons, no per-horizon weight tuning",
           "gates": {}, "canary": {}}

    gates = ["baseline", "ens_majority", "ens_fraction"]
    for g in gates:
        sim = simulate(g, extra_lag=0)
        out["gates"][g] = split_metrics(sim)
    # +1 extra-day-lag canary
    for g in gates:
        sim = simulate(g, extra_lag=1)
        out["canary"][g] = split_metrics(sim)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
