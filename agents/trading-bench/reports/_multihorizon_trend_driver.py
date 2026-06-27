"""THROWAWAY driver — multi-horizon trend-ENSEMBLE gate vs single-SMA-200 gate
on the live TQQQ vol-target sleeve.

PAPER RESEARCH ONLY. No live orders, no spend. Reads runner/strategies caches;
writes only reports/_multihorizon_trend_result.json + a markdown report.

THE QUESTION
============
Our live sleeve `leveraged_long_trend_paper` gates on a SINGLE window: QQQ
SMA-200. AQR "A Century of Evidence on Trend-Following" + Man Group show that
COMBINING short/medium/long horizons (e.g. SMA-50/100/200, or 3/6/12mo TSMOM)
lifts Sharpe via HORIZON DIVERSIFICATION. Does a 3-horizon EQUAL-WEIGHT ensemble
gate beat the single SMA-200 gate on TQQQ, OUT-OF-SAMPLE, net of cost, in a way
that survives the +1-day canary?

ENGINE REUSE (apples-to-apples, no reinvention)
===============================================
We REUSE the validated engine `backtest_daily_voltarget.run_backtest_voltarget`
mechanics EXACTLY (vol-target 0.25, vol_window 20, w_max 1.0, 2bps-on-abs-weight
cost, T-bill cash, D->D+1 lag). The ONLY thing we change is the GATE:

  BASELINE   : participation g(D) = 1.0 if QQQ_close(D) > SMA200(QQQ,D) else 0.0
  SMA-ENS    : g(D) = mean[ price>SMA50, price>SMA100, price>SMA200 ] in {0,1/3,2/3,1}
  MAJORITY   : g(D) = 1.0 iff >=2 of the 3 SMA votes True, else 0.0  (binary)
  TSMOM-ENS  : g(D) = mean[ ret_63>0, ret_126>0, ret_252>0 ]          in {0,1/3,2/3,1}

The participation fraction g multiplies the vol-target weight:
      w_final(D+1) = g(D) * clamp(0.25 / realized_vol20_TQQQ(D), 0, 1.0)
So 2/3-on = hold 2/3 of the vol-targeted position. This is the honest
EW-across-horizons construction: NO per-horizon weight optimization.

GATE IS ON THE UNDERLYING (QQQ), like the live sleeve. The SMA windows and the
TSMOM lookbacks are computed on QQQ ADJCLOSE, lookahead-safe (closes through D).
realized vol is on the SLEEVE (TQQQ) own returns, identical to the engine.

NO-LOOKAHEAD: gate decided from QQQ closes with date <= D; weight applied to the
TQQQ return D->D+1. CANARY shifts the gate ONE EXTRA day (g(D-1) applied into
D+1) -> a real edge survives, a leak/luck collapses.

SHARPE: headline = runner.fp_sharpe.sharpe_from_returns (ddof=1, sqrt(252)) on
the concatenated daily equity returns over the span (full / IS / OOS). We ALSO
carry the engine's own _stats_from_equity Sharpe (ddof=0) for cross-check.

OOS SPLIT = 2018-01-01 (frozen, matches validate_oos_voltarget.py & the live
sleeve's documented OOS).

Output: reports/_multihorizon_trend_result.json
"""
from __future__ import annotations

import bisect
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, realized_ann_vol, _clamp,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    LevLongParams, trend_is_up, TRADING_DAYS,
)
from runner.fp_sharpe import sharpe_from_returns

WORKSPACE = Path(__file__).resolve().parent.parent
OUT = WORKSPACE / "reports" / "_multihorizon_trend_result.json"

# ---- baseline params, IDENTICAL to the live sleeve / validated engine --------
SLEEVE = "TQQQ"
UNDERLYING = "QQQ"
BENCH = "^GSPC"
TARGET_VOL = 0.25
VOL_WINDOW = 20
W_MAX = 1.0
COST_BPS = 2.0            # one-way, charged on ABS change in weight (engine convention)
SPLIT = "2018-01-01"     # frozen OOS split (matches validate_oos_voltarget)
BPY = float(TRADING_DAYS)

# SMA horizons for the ensemble
SMA_HORIZONS = [50, 100, 200]
# TSMOM lookbacks (trading days ~ 3mo/6mo/12mo)
TSMOM_LB = [63, 126, 252]


# ============================================================================ #
# Helpers: lookahead-safe SMA / return on a price series indexed by date
# ============================================================================ #
def _sma_through(closes: List[float], i: int, n: int) -> Optional[float]:
    """SMA of closes[i-n+1 .. i] inclusive (decision close i). None if short."""
    if i + 1 < n:
        return None
    return sum(closes[i - n + 1: i + 1]) / n


def build_qqq_gate_paths(cal: List[str]) -> Dict[str, List[float]]:
    """Compute every gate's participation fraction g(D) for each sleeve date D in
    `cal`, using NATIVE QQQ adjclose history (SMA/return windows in QQQ trading
    days), lookahead-safe (closes through D). Returns dict name->[g per cal date].

    For a sleeve date D, we take QQQ's most-recent trading index k with
    qqq_date[k] <= D and evaluate SMA/return at index k on the native series.
    This is exactly how the engine slices `under_closes_through(D)` then looks at
    the last element / SMA. So our baseline gate reproduces the engine's gate.
    """
    qbars = bd.dbc.get_daily(UNDERLYING)
    qdates = [b["date"] for b in qbars]
    qadj = [float(b["adjclose"]) for b in qbars]

    # Precompute, at each native QQQ index k, the booleans / fraction.
    nq = len(qadj)
    sma_vals: Dict[int, List[Optional[float]]] = {}
    for h in SMA_HORIZONS:
        col = [None] * nq
        for k in range(nq):
            if k + 1 >= h:
                col[k] = sum(qadj[k - h + 1: k + 1]) / h
        sma_vals[h] = col
    # TSMOM: ret over lb trading days = qadj[k]/qadj[k-lb]-1 > 0
    tsmom_pos: Dict[int, List[Optional[bool]]] = {}
    for lb in TSMOM_LB:
        col = [None] * nq
        for k in range(nq):
            if k - lb >= 0 and qadj[k - lb] > 0:
                col[k] = (qadj[k] / qadj[k - lb] - 1.0) > 0
        tsmom_pos[lb] = col

    # For each sleeve cal date, find native qqq index k (<= D)
    g_base: List[float] = []
    g_sma_frac: List[float] = []
    g_sma_majority: List[float] = []
    g_tsmom_frac: List[float] = []

    j = 0  # pointer into qdates
    last_k = -1
    for d in cal:
        while j < nq and qdates[j] <= d:
            last_k = j
            j += 1
        k = last_k
        if k < 0:
            g_base.append(0.0); g_sma_frac.append(0.0)
            g_sma_majority.append(0.0); g_tsmom_frac.append(0.0)
            continue
        price = qadj[k]
        # SMA votes
        votes = []
        for h in SMA_HORIZONS:
            s = sma_vals[h][k]
            votes.append(1.0 if (s is not None and price > s) else 0.0)
        # baseline = SMA-200 vote only
        s200 = sma_vals[200][k]
        g_base.append(1.0 if (s200 is not None and price > s200) else 0.0)
        # ensemble fraction = mean of the 3 votes
        g_sma_frac.append(sum(votes) / len(votes))
        # discrete majority (>=2 of 3)
        g_sma_majority.append(1.0 if sum(votes) >= 2 else 0.0)
        # TSMOM fraction = mean of 3 lookback-positive votes
        tvotes = []
        for lb in TSMOM_LB:
            b = tsmom_pos[lb][k]
            tvotes.append(1.0 if (b is True) else 0.0)
        g_tsmom_frac.append(sum(tvotes) / len(tvotes))

    return {
        "baseline": g_base,
        "sma_frac": g_sma_frac,
        "sma_majority": g_sma_majority,
        "tsmom_frac": g_tsmom_frac,
    }


# ============================================================================ #
# The simulation: identical to run_backtest_voltarget EXCEPT w_final = g * w_vol.
# Returns the full daily equity-return series + dates so we can compute
# fp_sharpe over arbitrary subspans and turnover.
# ============================================================================ #
def simulate(g_path: List[float], gate_lag_extra: int = 0) -> Dict:
    """Simulate the gated vol-target sleeve over the full TQQQ calendar.

    g_path[i] is the gate fraction DECIDED at close cal[i] (date D). With
    gate_lag_extra=0 it is applied to the return cal[i]->cal[i+1] (the engine's
    standard 1-day lag, since the engine decides at D and holds into D+1). With
    gate_lag_extra=1 (CANARY) we use g_path[i-1] instead (one extra day stale).

    The vol-target weight w_vol(D) uses realized vol of TQQQ returns ending <= D,
    exactly like the engine. w_final = g * w_vol, clamped to [0, w_max].

    Cost = COST_BPS/1e4 * abs(w_final(D+1) - w_final(D)) — engine's abs-weight model.
    Cash return = T-bill (0.0 in this data), (1-w_final) in cash.

    Returns dates, daily equity-return series (net), weights, turnover, n_rebal.
    """
    sbars = bd.dbc.get_daily(SLEEVE)
    cal = [b["date"] for b in sbars]
    sadj = [float(b["adjclose"]) for b in sbars]
    sby = {b["date"]: b for b in sbars}

    # sleeve daily returns indexed by END date (for realized vol "through D")
    sret_end: List[str] = []
    sret_val: List[float] = []
    for k in range(1, len(sadj)):
        if sadj[k - 1] > 0:
            sret_end.append(cal[k])
            sret_val.append(sadj[k] / sadj[k - 1] - 1.0)

    def rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end, d_iso)
        return sret_val[:idx]

    rets: List[float] = []         # net daily equity returns (post-cost)
    rdates: List[str] = []         # the date of the HELD day D+1 (return date)
    weights: List[float] = []
    prev_w = 0.0
    turnover_sum = 0.0             # sum of |dw| (one-way notional turnover units)
    n_rebal = 0
    REBAL_EPS = 1e-9

    for i in range(1, len(cal)):
        d_prev = cal[i - 1]        # decision day D
        d = cal[i]                 # held day D+1

        # gate fraction decided at D (or D-gate_lag_extra for canary)
        gi = i - 1 - gate_lag_extra
        g = g_path[gi] if gi >= 0 else 0.0

        # vol-target weight from TQQQ realized vol ending <= D
        rv = realized_ann_vol(rets_through(d_prev), VOL_WINDOW)
        if rv is None or rv <= 0:
            w_vol = 0.0
        else:
            w_vol = _clamp(TARGET_VOL / rv, 0.0, W_MAX)
        w = _clamp(g * w_vol, 0.0, W_MAX)

        # sleeve return D->D+1
        bn = sby.get(d); bp = sby.get(d_prev)
        if bn and bp and bp["adjclose"] > 0:
            sleeve_ret = bn["adjclose"] / bp["adjclose"] - 1.0
        else:
            sleeve_ret = 0.0
        cash_ret = bd._tbill_daily_rate(d_prev)
        blended = w * sleeve_ret + (1.0 - w) * cash_ret

        dw = abs(w - prev_w)
        cost = (COST_BPS / 1e4) * dw
        if dw > REBAL_EPS:
            n_rebal += 1
            turnover_sum += dw

        net = (1.0 + blended) * (1.0 - cost) - 1.0
        rets.append(net)
        rdates.append(d)
        weights.append(w)
        prev_w = w

    return {
        "dates": rdates, "rets": rets, "weights": weights,
        "turnover_sum": turnover_sum, "n_rebal": n_rebal,
    }


# ---- benchmark buy&hold on the same calendar (for context) ------------------
def buyhold(sym: str, cal_dates: List[str]) -> Dict:
    bars = bd.dbc.get_daily(sym)
    by = {b["date"]: b for b in bars}
    rets, rdates = [], []
    for i in range(1, len(cal_dates)):
        dn, dp = cal_dates[i], cal_dates[i - 1]
        bn, bp = by.get(dn), by.get(dp)
        r = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
        rets.append(r); rdates.append(dn)
    return {"dates": rdates, "rets": rets}


# ============================================================================ #
# Metrics over a [lo,hi) span of a (dates, rets) series
# ============================================================================ #
def _span_idx(dates: List[str], start: Optional[str], end: Optional[str]) -> Tuple[int, int]:
    lo = 0 if start is None else bisect.bisect_left(dates, start)
    hi = len(dates) if end is None else bisect.bisect_right(dates, end)
    return lo, hi


def metrics(dates: List[str], rets: List[float], weights: Optional[List[float]],
            start: Optional[str] = None, end: Optional[str] = None) -> Dict:
    lo, hi = _span_idx(dates, start, end)
    seg = rets[lo:hi]
    if len(seg) < 2:
        return {"n": len(seg)}
    # equity
    eq = 1.0
    curve = [1.0]
    for r in seg:
        eq *= (1.0 + r)
        curve.append(eq)
    total = (eq - 1.0) * 100.0
    yrs = len(seg) / BPY
    cagr = ((eq) ** (1.0 / yrs) - 1.0) * 100.0 if (yrs > 0 and eq > 0) else None
    # fp_sharpe (ddof=1) — HEADLINE
    sh_fp = sharpe_from_returns(seg, BPY)
    # engine-style (ddof=0) for cross-check
    m = sum(seg) / len(seg)
    var0 = sum((r - m) ** 2 for r in seg) / len(seg)
    sd0 = math.sqrt(var0)
    sh_pop = (m / sd0) * math.sqrt(BPY) if sd0 > 0 else 0.0
    ann_vol = sd0 * math.sqrt(BPY) * 100.0
    # maxDD (NAV)
    peak = curve[0]; mdd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    out = {
        "n": len(seg),
        "first": dates[lo], "last": dates[hi - 1],
        "total_ret_pct": total,
        "cagr_pct": cagr,
        "sharpe_fp": sh_fp,        # ddof=1 headline
        "sharpe_pop": sh_pop,      # ddof=0 engine cross-check
        "ann_vol_pct": ann_vol,
        "maxdd_pct": mdd * 100.0,
    }
    if weights is not None:
        wseg = weights[lo:hi]
        out["avg_weight"] = sum(wseg) / len(wseg) if wseg else 0.0
    return out


def turnover_stats(sim: Dict, start: Optional[str], end: Optional[str]) -> Dict:
    """Sum of |dw| over the span + annualized turnover (one-way) + n_rebal."""
    dates = sim["dates"]; w = sim["weights"]
    lo, hi = _span_idx(dates, start, end)
    tsum = 0.0; nreb = 0
    prev = w[lo - 1] if lo > 0 else 0.0
    for i in range(lo, hi):
        dw = abs(w[i] - prev)
        if dw > 1e-9:
            tsum += dw; nreb += 1
        prev = w[i]
    yrs = (hi - lo) / BPY if hi > lo else 0.0
    return {"turnover_sum": tsum, "ann_turnover": (tsum / yrs if yrs > 0 else None),
            "n_rebal": nreb, "n_days": hi - lo}


def cost_sensitivity(g_path: List[str], bps_list: List[float]) -> Dict:
    """Re-run the sim at different one-way bps, report full/OOS fp-Sharpe + total."""
    global COST_BPS
    saved = COST_BPS
    out = {}
    for bps in bps_list:
        COST_BPS = bps
        sim = simulate(g_path, gate_lag_extra=0)
        full = metrics(sim["dates"], sim["rets"], sim["weights"])
        oos = metrics(sim["dates"], sim["rets"], sim["weights"], start=SPLIT)
        out[f"{bps}bps"] = {
            "full_sharpe_fp": full["sharpe_fp"], "full_total_pct": full["total_ret_pct"],
            "oos_sharpe_fp": oos["sharpe_fp"], "oos_total_pct": oos["total_ret_pct"],
        }
    COST_BPS = saved
    return out


# ============================================================================ #
# Per-calendar-year attribution: total return + avg weight per year, baseline vs
# a comparison gate, on the SAME span. The economic story (where horizon
# diversification helps vs hurts).
# ============================================================================ #
def yearly_attribution(sim_a: Dict, sim_b: Dict) -> List[Dict]:
    dates = sim_a["dates"]
    years = sorted({d[:4] for d in dates})
    rows: List[Dict] = []
    for y in years:
        ma = metrics(sim_a["dates"], sim_a["rets"], sim_a["weights"], f"{y}-01-01", f"{y}-12-31")
        mb = metrics(sim_b["dates"], sim_b["rets"], sim_b["weights"], f"{y}-01-01", f"{y}-12-31")
        if ma.get("n", 0) < 2 or mb.get("n", 0) < 2:
            continue
        rows.append({
            "year": y,
            "base_ret_pct": ma["total_ret_pct"], "base_avgW": ma.get("avg_weight"),
            "base_maxdd_pct": ma["maxdd_pct"],
            "ens_ret_pct": mb["total_ret_pct"], "ens_avgW": mb.get("avg_weight"),
            "ens_maxdd_pct": mb["maxdd_pct"],
            "delta_ret_pct": mb["total_ret_pct"] - ma["total_ret_pct"],
        })
    return rows


# ============================================================================ #
# Driver
# ============================================================================ #
def _block(sim: Dict) -> Dict:
    full = metrics(sim["dates"], sim["rets"], sim["weights"])
    is_ = metrics(sim["dates"], sim["rets"], sim["weights"], end="2017-12-31")
    oos = metrics(sim["dates"], sim["rets"], sim["weights"], start=SPLIT)
    return {
        "full": full, "is": is_, "oos": oos,
        "turnover_full": turnover_stats(sim, None, None),
        "turnover_oos": turnover_stats(sim, SPLIT, None),
    }


def main() -> Dict:
    sbars = bd.dbc.get_daily(SLEEVE)
    cal = [b["date"] for b in sbars]
    gates = build_qqq_gate_paths(cal)

    # simulate each gate at baseline cost (2bps), standard 1-day lag
    sims = {name: simulate(gpath, gate_lag_extra=0) for name, gpath in gates.items()}
    # canary: each gate at +1 extra day lag
    sims_canary = {name: simulate(gpath, gate_lag_extra=1) for name, gpath in gates.items()}

    bh_spx = buyhold(BENCH, cal)
    bh_tqqq = buyhold(SLEEVE, cal)

    result: Dict = {
        "meta": {
            "sleeve": SLEEVE, "underlying": UNDERLYING, "benchmark": BENCH,
            "target_vol": TARGET_VOL, "vol_window": VOL_WINDOW, "w_max": W_MAX,
            "cost_bps_oneway": COST_BPS, "split": SPLIT,
            "sma_horizons": SMA_HORIZONS, "tsmom_lookbacks": TSMOM_LB,
            "span": {"first": cal[0], "last": cal[-1], "n": len(cal)},
            "sharpe_convention": "headline=fp_sharpe ddof=1 sqrt(252); sharpe_pop=ddof0 engine xcheck",
        },
        "gates": {},
        "canary": {},
        "benchmarks": {
            "spx_full": metrics(bh_spx["dates"], bh_spx["rets"], None),
            "spx_oos": metrics(bh_spx["dates"], bh_spx["rets"], None, start=SPLIT),
            "tqqq_bh_full": metrics(bh_tqqq["dates"], bh_tqqq["rets"], None),
            "tqqq_bh_oos": metrics(bh_tqqq["dates"], bh_tqqq["rets"], None, start=SPLIT),
        },
    }

    for name, sim in sims.items():
        result["gates"][name] = _block(sim)
    for name, sim in sims_canary.items():
        b = metrics(sim["dates"], sim["rets"], sim["weights"])
        o = metrics(sim["dates"], sim["rets"], sim["weights"], start=SPLIT)
        result["canary"][name] = {"full": b, "oos": o}

    bps_list = [0.0, 2.0, 5.0]
    result["cost_sensitivity"] = {
        "baseline": cost_sensitivity(gates["baseline"], bps_list),
        "sma_frac": cost_sensitivity(gates["sma_frac"], bps_list),
        "tsmom_frac": cost_sensitivity(gates["tsmom_frac"], bps_list),
    }

    result["yearly_baseline_vs_smaFrac"] = yearly_attribution(sims["baseline"], sims["sma_frac"])
    result["yearly_baseline_vs_tsmomFrac"] = yearly_attribution(sims["baseline"], sims["tsmom_frac"])

    base_oos = result["gates"]["baseline"]["oos"]
    deltas: Dict = {}
    for name in ("sma_frac", "sma_majority", "tsmom_frac"):
        g = result["gates"][name]["oos"]
        deltas[name] = {
            "d_sharpe_fp_oos": g["sharpe_fp"] - base_oos["sharpe_fp"],
            "d_total_oos_pct": g["total_ret_pct"] - base_oos["total_ret_pct"],
            "d_maxdd_oos_pct": g["maxdd_pct"] - base_oos["maxdd_pct"],
        }
    base_can = result["canary"]["baseline"]["oos"]
    for name in ("sma_frac", "sma_majority", "tsmom_frac"):
        g = result["canary"][name]["oos"]
        deltas[name]["d_sharpe_fp_oos_canary"] = g["sharpe_fp"] - base_can["sharpe_fp"]
    result["oos_deltas_vs_baseline"] = deltas

    OUT.write_text(json.dumps(result, indent=2, default=lambda o: None))
    return result


if __name__ == "__main__":
    res = main()
    m = res["meta"]
    print(f"[driver] wrote {OUT}")
    print(f"span {m['span']['first']}..{m['span']['last']} n={m['span']['n']} split@{m['split']}")
    print()
    hdr = f"{'GATE':<14}{'full_Sfp':>9}{'IS_Sfp':>8}{'OOS_Sfp':>9}{'OOS_tot%':>11}{'OOS_mdd%':>10}{'OOS_avgW':>9}{'OOS_turn':>9}"
    print(hdr)
    for name in ("baseline", "sma_frac", "sma_majority", "tsmom_frac"):
        gb = res["gates"][name]
        f, i_, o = gb["full"], gb["is"], gb["oos"]
        to = gb["turnover_oos"]
        print(f"{name:<14}{f['sharpe_fp']:>9.3f}{i_['sharpe_fp']:>8.3f}{o['sharpe_fp']:>9.3f}"
              f"{o['total_ret_pct']:>11.1f}{o['maxdd_pct']:>10.2f}{o.get('avg_weight',0):>9.3f}"
              f"{to['ann_turnover'] or 0:>9.2f}")
    print()
    print("CANARY (+1 extra day lag) OOS fp-Sharpe:")
    for name in ("baseline", "sma_frac", "sma_majority", "tsmom_frac"):
        base_o = res["gates"][name]["oos"]["sharpe_fp"]
        can_o = res["canary"][name]["oos"]["sharpe_fp"]
        print(f"  {name:<14} 1d={base_o:>7.3f}  +1d={can_o:>7.3f}  Δ={can_o-base_o:>+7.3f}")
    print()
    print("OOS deltas vs baseline (ens - baseline):")
    for name, d in res["oos_deltas_vs_baseline"].items():
        print(f"  {name:<14} ΔSfp={d['d_sharpe_fp_oos']:>+7.3f}  Δtot%={d['d_total_oos_pct']:>+9.1f}"
              f"  Δmdd%={d['d_maxdd_oos_pct']:>+7.2f}  ΔSfp(canary)={d['d_sharpe_fp_oos_canary']:>+7.3f}")
