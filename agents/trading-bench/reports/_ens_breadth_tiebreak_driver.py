"""TIEBREAK driver — settle ens_sma_breadth{50,100,200} vs the LIVE single-SMA-200
vol-target sleeve through the REAL engine, ONE consistent convention, apples-to-apples.

PAPER RESEARCH ONLY. Reads runner/strategies caches read-only. Writes only
reports/_ens_breadth_tiebreak_result.json + the markdown verdict. Does NOT edit
the engine, the live sleeve, runner/, crontab, or any *.db.

============================================================================
WHY THIS EXISTS
============================================================================
Two 2026-06-27 drivers disagreed on whether a 3-horizon SMA-breadth scaler beats
the live SMA-200 vol-target sleeve OOS:
  - PASS  (_ensemble_trend_driver.py): vix_gate=TRUE, OOS by COLD-RESIM-from-2018.
          base full +1262%/fpS 0.774, ens beats (dS +0.027), maxDD -25.99 vs -34.88.
  - NEG   (_multihorizon_trend_driver.py): NO VIX gate, OOS by CONTINUOUS-SLICE.
          base OOS fpS 0.858, ens sma_frac dS -0.025 (LOSES).
They differ on BOTH axes at once (VIX gate AND OOS-slicing). This driver fixes
BOTH to ONE convention that MATCHES THE LIVE SLEEVE + the engine's own OOS
validator, and runs base vs breadth identically so the sign is unambiguous.

============================================================================
GROUND TRUTH (verified before writing this):
============================================================================
  * LIVE sleeve params.json: vix_gate = FALSE, sma_window=200, target_vol=0.25,
    vol_window=20, w_max=1.0, cost 2bps-on-abs-weight, T-bill cash.
  * Engine run_backtest_voltarget(vix_gate=False) reproduces the documented anchor
    EXACTLY: FULL +2002.1% / Sharpe(pop) 0.854 / maxDD -34.52%. (vix_gate=True gives
    +1262%/0.774 -- that is NOT the live sleeve; the PASS driver baselined the wrong
    config.)
  * The engine's OWN OOS validator validate_oos_voltarget.py uses subwindow_stats
    on the CONTINUOUS full-span equity (slice @ 2018-01-01), vix default FALSE.
    => THE mandated convention = continuous-span sim, slice OOS. Same as NEG driver.

So the apples-to-apples question is: under the LIVE config (vix_gate=FALSE) and the
validator's continuous-slice OOS, does ens_sma_breadth{50,100,200} beat base?
The NEG driver said NO under exactly this regime. We confirm/deny via the engine.

============================================================================
CONVENTION (ONE, for BOTH gates)
============================================================================
  - Reuse the engine's EXACT helpers (bd.dbc adjclose, bd.trend_is_up,
    bd._vix_risk_off, bd._tbill_daily_rate, realized_ann_vol, target_weight,
    _clamp, _stats_from_equity) -- no reinvented math.
  - Simulate the FULL TQQQ span CONTINUOUSLY once per gate. Slice IS(<=2017-12-31)
    and OOS(>=2018-01-01) FROM THAT CONTINUOUS EQUITY (no cold-resim-from-2018).
  - D->D+1 lag. 2bps/side cost on ABS change in weight. T-bill cash.
  - VIX gate handling EXACTLY as engine: if vix_gate and risk-off as-of D, force
    the scaler g=0 (full de-risk), same _vix_risk_off as run_backtest_voltarget.
  - Sleeve weight = clamp(g * voltarget_weight, 0, w_max), with
       g_base   = 1.0 if QQQ_close(D) > SMA200(QQQ,D) else 0.0    (engine binary)
       g_breadth= mean[QQQ>SMA_w for w in TRIPLE] in {0,1/3,2/3,1} (continuous)
    voltarget_weight = clamp(0.25 / realized_vol20(TQQQ<=D), 0, 1.0).
  - Metrics: fp-Sharpe = runner.fp_sharpe.sharpe_from_returns (ddof=1, sqrt252) on
    the concatenated daily equity returns of the span; PLUS engine pop-Sharpe
    (ddof=0) for cross-check; total return; maxDD; avg weight; annual turnover.
  - PARITY GUARD: g_base path is reconciled against the REAL engine
    run_backtest_voltarget(vix_gate=...) -- equity must match to ~1e-9 so we KNOW
    the wrapper is the true engine, not a near-copy.

============================================================================
CANARY + ROBUSTNESS
============================================================================
  - 1-day-lag canary: shift the gate decision ONE EXTRA trading day; a real edge
    survives, an artifact collapses. Reported for base + every triple.
  - 6-8 nearby SMA triples under the SAME convention+canary -> is {50,100,200} a
    robust mid-of-pack win or a knife-edge.
  - Per-year OOS table (base vs {50,100,200}): Sharpe/maxDD/return 2018..2026.

Run: python3 reports/_ens_breadth_tiebreak_driver.py
"""
from __future__ import annotations

import bisect
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget, realized_ann_vol,
    target_weight, _clamp,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    LevLongParams, _stats_from_equity, TRADING_DAYS,
)
from runner.fp_sharpe import sharpe_from_returns

WORKSPACE = Path(__file__).resolve().parent.parent
OUT = WORKSPACE / "reports" / "_ens_breadth_tiebreak_result.json"

# ---- LIVE-sleeve config (params.json) -------------------------------------
SLEEVE = "TQQQ"
UNDERLYING = "QQQ"
BENCH = "^GSPC"
TARGET_VOL = 0.25
VOL_WINDOW = 20
W_MAX = 1.0
COST_BPS = 2.0
SPLIT = "2018-01-01"
BPY = float(TRADING_DAYS)
VIX_GATE_LIVE = False          # <-- the LIVE sleeve + the documented anchor
VIX_RATIO_THR = 1.0

PRIMARY_TRIPLE = (50, 100, 200)
NEARBY_TRIPLES = [
    (50, 100, 200),     # primary
    (40, 100, 200),
    (60, 120, 200),
    (50, 100, 150),
    (50, 125, 250),
    (30, 90, 180),
    (75, 150, 250),
    (20, 100, 200),
]


def _sma(values: List[float], n: int) -> Optional[float]:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


# ---------------------------------------------------------------------------
# Continuous full-span simulation reusing the ENGINE's exact helpers. The gate
# is a pluggable scaler g(under_closes_through_D) in [0,1]. VIX handling is the
# engine's: vix_gate AND risk-off(D) => g forced to 0.
# ---------------------------------------------------------------------------
def simulate(scaler, vix_gate: bool, lag_extra: int = 0) -> Dict:
    sleeve_bars = bd.dbc.get_daily(SLEEVE)
    under_bars = bd.dbc.get_daily(UNDERLYING)
    sleeve_by = {b["date"]: b for b in sleeve_bars}

    cal = [b["date"] for b in sleeve_bars]

    under_dates = [b["date"] for b in under_bars]
    under_close = [float(b["adjclose"]) for b in under_bars]

    def under_closes_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(under_dates, d_iso)
        return under_close[:idx]

    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [float(b["adjclose"]) for b in sleeve_bars]
    sret_end: List[str] = []
    sret_val: List[float] = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end.append(sleeve_dates[k])
            sret_val.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)

    def sleeve_rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end, d_iso)
        return sret_val[:idx]

    # canary: step the DECISION date back lag_extra trading days
    def decision_date(d_prev: str) -> str:
        if lag_extra <= 0:
            return d_prev
        idx = bisect.bisect_right(cal, d_prev) - 1
        j = max(0, idx - lag_extra)
        return cal[j]

    equity = [1.0]
    dates = [cal[0]]
    weights: List[float] = []
    in_market: List[bool] = []
    prev_w = 0.0
    n_rebal = 0
    turnover_sum = 0.0
    REBAL_EPS = 1e-9

    for i in range(1, len(cal)):
        d_prev = cal[i - 1]
        d = cal[i]
        dec = decision_date(d_prev)

        uc = under_closes_through(dec)
        g = scaler(uc)
        # engine VIX gate: force g=0 on risk-off as-of the decision date
        if vix_gate and g > 0 and bd._vix_risk_off(dec, VIX_RATIO_THR):
            g = 0.0

        rv = realized_ann_vol(sleeve_rets_through(dec), VOL_WINDOW)
        vt = target_weight(True, rv, TARGET_VOL, W_MAX)  # vol-target weight (trend factored via g)
        w = _clamp(g * vt, 0.0, W_MAX)

        b_now = sleeve_by.get(d)
        b_prev = sleeve_by.get(d_prev)
        sleeve_ret = (b_now["adjclose"] / b_prev["adjclose"] - 1.0) \
            if (b_now and b_prev and b_prev["adjclose"] > 0) else 0.0
        cash_ret = bd._tbill_daily_rate(dec)
        blended = w * sleeve_ret + (1.0 - w) * cash_ret

        dw = abs(w - prev_w)
        cost = (COST_BPS / 1e4) * dw
        if dw > REBAL_EPS:
            n_rebal += 1
            turnover_sum += dw

        equity.append(equity[-1] * (1.0 + blended) * (1.0 - cost))
        dates.append(d)
        weights.append(w)
        in_market.append(w > 0.0)
        prev_w = w

    return {
        "dates": dates, "equity": equity, "weights": weights,
        "in_market": in_market, "n_rebal": n_rebal, "turnover_sum": turnover_sum,
    }


# ---------------------------------------------------------------------------
# Gate scalers (continuous risk-on g in [0,1] from QQQ closes through D)
# ---------------------------------------------------------------------------
def make_base_scaler():
    def g(uc: List[float]) -> float:
        s = _sma(uc, 200)
        if s is None:
            return 0.0
        return 1.0 if uc[-1] > s else 0.0
    return g


def make_breadth_scaler(triple: Tuple[int, int, int]):
    ws = list(triple)

    def g(uc: List[float]) -> float:
        if not uc:
            return 0.0
        last = uc[-1]
        agree = 0
        for w in ws:
            s = _sma(uc, w)
            if s is not None and last > s:
                agree += 1
        return agree / len(ws)
    return g


# ---------------------------------------------------------------------------
# Metrics on a [start,end] slice of a CONTINUOUS equity curve (slice, no resim)
# ---------------------------------------------------------------------------
def slice_metrics(sim: Dict, start: Optional[str] = None,
                  end: Optional[str] = None) -> Dict:
    dates = sim["dates"]
    eq = sim["equity"]
    lo = 0 if start is None else bisect.bisect_left(dates, start)
    hi = len(dates) if end is None else bisect.bisect_right(dates, end)
    if hi - lo < 2:
        return {"n": hi - lo}
    seg_eq = eq[lo:hi]
    # daily simple returns WITHIN the slice (continuous: ret[j] uses eq[lo+j-1])
    rets = [seg_eq[j] / seg_eq[j - 1] - 1.0 for j in range(1, len(seg_eq))]
    total = (seg_eq[-1] / seg_eq[0] - 1.0) * 100.0
    yrs = len(rets) / BPY
    cagr = ((seg_eq[-1] / seg_eq[0]) ** (1.0 / yrs) - 1.0) * 100.0 if (yrs > 0 and seg_eq[0] > 0) else None
    sh_fp = sharpe_from_returns(rets, BPY)
    # engine pop-Sharpe (ddof=0) cross-check
    m = sum(rets) / len(rets)
    var0 = sum((r - m) ** 2 for r in rets) / len(rets)
    sd0 = math.sqrt(var0)
    sh_pop = (m / sd0) * math.sqrt(BPY) if sd0 > 0 else 0.0
    ann_vol = sd0 * math.sqrt(BPY) * 100.0
    peak = seg_eq[0]
    mdd = 0.0
    for v in seg_eq:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    # avg weight + annual turnover over the slice. weights align to days 1..N
    # (weights[k] is the weight held over dates[k+1]); for the slice take the
    # weights whose HELD date is in [start,end].
    wsel = []
    tsel = 0.0
    prevw = None
    for k in range(len(sim["weights"])):
        held_date = dates[k + 1]
        if (start is None or held_date >= start) and (end is None or held_date <= end):
            w = sim["weights"][k]
            wsel.append(w)
            if prevw is not None:
                tsel += abs(w - prevw)
            prevw = w
        else:
            prevw = sim["weights"][k]
    avg_w = (sum(wsel) / len(wsel)) if wsel else 0.0
    ann_turn = (tsel / yrs) if yrs > 0 else None
    return {
        "n": hi - lo, "first": dates[lo], "last": dates[hi - 1],
        "total_ret_pct": total, "cagr_pct": cagr,
        "sharpe_fp": sh_fp, "sharpe_pop": sh_pop, "ann_vol_pct": ann_vol,
        "maxdd_pct": mdd * 100.0, "avg_weight": avg_w, "ann_turnover": ann_turn,
    }


def block(sim: Dict) -> Dict:
    return {
        "full": slice_metrics(sim, None, None),
        "is": slice_metrics(sim, None, "2017-12-31"),
        "oos": slice_metrics(sim, SPLIT, None),
    }


# ---------------------------------------------------------------------------
# PARITY: confirm the base wrapper == the REAL engine run_backtest_voltarget
# ---------------------------------------------------------------------------
def parity_check(vix_gate: bool) -> Dict:
    sim = simulate(make_base_scaler(), vix_gate=vix_gate, lag_extra=0)
    p = VolTargetParams(sleeve=SLEEVE, underlying=UNDERLYING, benchmark=BENCH,
                        gate_mode="sma200", sma_window=200, vix_gate=vix_gate,
                        vix_ratio_thr=VIX_RATIO_THR, switch_cost_bps=COST_BPS,
                        use_tbill_cash=True, target_ann_vol=TARGET_VOL,
                        vol_window=VOL_WINDOW, w_max=W_MAX)
    r = run_backtest_voltarget(p)
    eng_eq = r["strategy"]["equity"]
    eng_dates = r["strategy"]["dates"]
    # align by date (engine span may start at cal[0] too)
    wrap_by = dict(zip(sim["dates"], sim["equity"]))
    maxdiff = 0.0
    n_cmp = 0
    worst_date = None
    for dt, e in zip(eng_dates, eng_eq):
        w = wrap_by.get(dt)
        if w is None:
            continue
        d = abs(w - e)
        n_cmp += 1
        if d > maxdiff:
            maxdiff = d
            worst_date = dt
    eng_full = r["strategy"]["stats"]
    return {
        "vix_gate": vix_gate,
        "n_compared": n_cmp,
        "max_abs_equity_diff": maxdiff,
        "worst_date": worst_date,
        "engine_full_total_pct": eng_full["total_return_pct"],
        "engine_full_sharpe_pop": eng_full["sharpe"],
        "engine_full_maxdd_pct": eng_full["max_drawdown_pct"],
        "engine_avg_weight": eng_full["avg_weight"],
        "wrapper_full_total_pct": slice_metrics(sim)["total_ret_pct"],
        "wrapper_full_sharpe_pop": slice_metrics(sim)["sharpe_pop"],
        "wrapper_full_maxdd_pct": slice_metrics(sim)["maxdd_pct"],
    }


# ---------------------------------------------------------------------------
# Per-year OOS attribution (base vs a triple)
# ---------------------------------------------------------------------------
def yearly(sim_base: Dict, sim_ens: Dict) -> List[Dict]:
    years = [str(y) for y in range(2018, 2027)]
    rows = []
    for y in years:
        a = slice_metrics(sim_base, f"{y}-01-01", f"{y}-12-31")
        b = slice_metrics(sim_ens, f"{y}-01-01", f"{y}-12-31")
        if a.get("n", 0) < 2 or b.get("n", 0) < 2:
            continue
        rows.append({
            "year": y,
            "base_ret_pct": a["total_ret_pct"], "ens_ret_pct": b["total_ret_pct"],
            "base_sharpe_fp": a["sharpe_fp"], "ens_sharpe_fp": b["sharpe_fp"],
            "base_maxdd_pct": a["maxdd_pct"], "ens_maxdd_pct": b["maxdd_pct"],
            "base_avgW": a["avg_weight"], "ens_avgW": b["avg_weight"],
        })
    return rows


# ---------------------------------------------------------------------------
# Benchmark buy&hold (context for the anchor check)
# ---------------------------------------------------------------------------
def buyhold_metrics(sym: str, dates_ref: List[str]) -> Dict:
    bars = bd.dbc.get_daily(sym)
    by = {b["date"]: b for b in bars}
    eq = [1.0]
    ds = [dates_ref[0]]
    for j in range(1, len(dates_ref)):
        dn, dp = dates_ref[j], dates_ref[j - 1]
        bn, bp = by.get(dn), by.get(dp)
        r = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
        eq.append(eq[-1] * (1.0 + r))
        ds.append(dn)
    sim = {"dates": ds, "equity": eq, "weights": []}
    return {"full": slice_metrics(sim), "oos": slice_metrics(sim, SPLIT, None)}


def main() -> Dict:
    result: Dict = {"meta": {
        "sleeve": SLEEVE, "underlying": UNDERLYING, "benchmark": BENCH,
        "target_vol": TARGET_VOL, "vol_window": VOL_WINDOW, "w_max": W_MAX,
        "cost_bps_oneway": COST_BPS, "split": SPLIT,
        "vix_gate_live": VIX_GATE_LIVE, "vix_ratio_thr": VIX_RATIO_THR,
        "primary_triple": list(PRIMARY_TRIPLE),
        "convention": "continuous full-span sim, slice OOS @2018 (matches engine validate_oos_voltarget); fp_sharpe ddof=1 sqrt252; live vix_gate=False",
    }}

    # --- PARITY: prove the base wrapper IS the engine (both vix settings) ---
    result["parity"] = {
        "vix_off": parity_check(False),
        "vix_on": parity_check(True),
    }

    # --- PRIMARY: live convention (vix_gate=False) ---
    base_sim = simulate(make_base_scaler(), vix_gate=VIX_GATE_LIVE, lag_extra=0)
    base_can = simulate(make_base_scaler(), vix_gate=VIX_GATE_LIVE, lag_extra=1)
    result["base"] = {**block(base_sim),
                      "canary_full": slice_metrics(base_can),
                      "canary_oos": slice_metrics(base_can, SPLIT, None),
                      "n_rebal": base_sim["n_rebal"]}

    # benchmark anchor context (buy&hold SPX / TQQQ on the base span)
    result["benchmarks"] = {
        "spx": buyhold_metrics(BENCH, base_sim["dates"]),
        "tqqq_bh": buyhold_metrics(SLEEVE, base_sim["dates"]),
    }

    # --- every nearby triple under the SAME convention + canary ---
    triples_out: Dict[str, Dict] = {}
    primary_sim = None
    for tr in NEARBY_TRIPLES:
        key = "-".join(str(x) for x in tr)
        sim = simulate(make_breadth_scaler(tr), vix_gate=VIX_GATE_LIVE, lag_extra=0)
        can = simulate(make_breadth_scaler(tr), vix_gate=VIX_GATE_LIVE, lag_extra=1)
        if tuple(tr) == PRIMARY_TRIPLE:
            primary_sim = sim
        blk = block(sim)
        blk["canary_full"] = slice_metrics(can)
        blk["canary_oos"] = slice_metrics(can, SPLIT, None)
        blk["n_rebal"] = sim["n_rebal"]
        triples_out[key] = blk
    result["triples"] = triples_out

    # --- deltas vs base (OOS + full), and canary survival, per triple ---
    b_oos = result["base"]["oos"]
    b_full = result["base"]["full"]
    b_can_oos = result["base"]["canary_oos"]
    deltas: Dict[str, Dict] = {}
    for key, blk in triples_out.items():
        o = blk["oos"]; f = blk["full"]; c = blk["canary_oos"]
        d_oos_fp = o["sharpe_fp"] - b_oos["sharpe_fp"]
        d_full_fp = f["sharpe_fp"] - b_full["sharpe_fp"]
        d_oos_dd = o["maxdd_pct"] - b_oos["maxdd_pct"]  # +ve => ens SHALLOWER (maxdd negative)
        d_full_dd = f["maxdd_pct"] - b_full["maxdd_pct"]
        canary_drop = c["sharpe_fp"] - o["sharpe_fp"]   # ens canary OOS minus ens OOS
        # canary survival: ens still beats base under +1d, and own drop small + sign-stable
        ens_beats_base_canary = (c["sharpe_fp"] - b_can_oos["sharpe_fp"]) > 0
        canary_robust = abs(canary_drop) <= 0.10 and ((o["sharpe_fp"] >= 0) == (c["sharpe_fp"] >= 0))
        deltas[key] = {
            "d_oos_sharpe_fp": d_oos_fp,
            "d_full_sharpe_fp": d_full_fp,
            "d_oos_maxdd_pp": d_oos_dd,
            "d_full_maxdd_pp": d_full_dd,
            "oos_canary_drop": canary_drop,
            "ens_beats_base_under_canary": ens_beats_base_canary,
            "canary_self_robust": canary_robust,
            "beats_oos_sharpe": d_oos_fp > 0,
            "beats_oos_dd": d_oos_dd > 0,
        }
    result["deltas_vs_base"] = deltas

    # --- per-year OOS table: base vs PRIMARY triple ---
    if primary_sim is not None:
        result["yearly_base_vs_primary"] = yearly(base_sim, primary_sim)

    OUT.write_text(json.dumps(result, indent=2, default=lambda o: None))
    return result


def _fmt(x, w=8, p=3):
    if x is None:
        return " " * (w - 3) + "n/a"
    return f"{x:>{w}.{p}f}"


if __name__ == "__main__":
    res = main()
    m = res["meta"]
    print("=" * 100)
    print(f"ENS-BREADTH TIEBREAK  (LIVE convention: vix_gate={m['vix_gate_live']}, continuous-slice OOS @ {m['split']})")
    print("=" * 100)

    # parity
    for tag in ("vix_off", "vix_on"):
        p = res["parity"][tag]
        print(f"PARITY {tag}: wrapper-vs-engine max|Δequity|={p['max_abs_equity_diff']:.2e} "
              f"over {p['n_compared']} days (worst {p['worst_date']}) | "
              f"engine FULL tot={p['engine_full_total_pct']:.1f}% Sharpe(pop)={p['engine_full_sharpe_pop']:.3f} "
              f"maxDD={p['engine_full_maxdd_pct']:.2f}%")
    print()

    b = res["base"]
    print("BASE (engine binary SMA-200, live vix-off):")
    for seg in ("full", "is", "oos"):
        s = b[seg]
        print(f"  {seg.upper():<4} fpS={s['sharpe_fp']:.3f} popS={s['sharpe_pop']:.3f} "
              f"tot={s['total_ret_pct']:9.1f}% maxDD={s['maxdd_pct']:.2f}% avgW={s['avg_weight']:.3f} "
              f"turn={(s['ann_turnover'] or 0):.2f}")
    print(f"  canary OOS fpS={b['canary_oos']['sharpe_fp']:.3f} (drop {b['canary_oos']['sharpe_fp']-b['oos']['sharpe_fp']:+.3f})")
    print(f"  anchor check: SPX OOS tot={res['benchmarks']['spx']['oos']['total_ret_pct']:.1f}% | "
          f"FULL SPX tot={res['benchmarks']['spx']['full']['total_ret_pct']:.1f}%")
    print()

    hdr = f"{'TRIPLE':<14}{'OOS_fpS':>9}{'dOOSfp':>8}{'OOS_mdd%':>10}{'dMdd_pp':>9}{'OOS_tot%':>11}{'canOOS':>8}{'canDrop':>8}{'avgW':>7}{'turn':>7}"
    print(hdr)
    for key, blk in res["triples"].items():
        o = blk["oos"]; d = res["deltas_vs_base"][key]; c = blk["canary_oos"]
        star = " *" if key == "-".join(str(x) for x in m["primary_triple"]) else "  "
        print(f"{key+star:<14}{o['sharpe_fp']:>9.3f}{d['d_oos_sharpe_fp']:>+8.3f}{o['maxdd_pct']:>10.2f}"
              f"{d['d_oos_maxdd_pp']:>+9.2f}{o['total_ret_pct']:>11.1f}{c['sharpe_fp']:>8.3f}"
              f"{d['oos_canary_drop']:>+8.3f}{o['avg_weight']:>7.3f}{(o['ann_turnover'] or 0):>7.2f}")
    print()
    print("VERDICT per triple (beats base OOS on Sharpe? on maxDD? canary-robust? still-beats-under-canary?):")
    for key, d in res["deltas_vs_base"].items():
        verdict = "PASS" if (d["beats_oos_sharpe"] and d["canary_self_robust"] and d["ens_beats_base_under_canary"]) else \
                  ("DD-ONLY" if (d["beats_oos_dd"] and not d["beats_oos_sharpe"]) else "REJECT")
        print(f"  {key:<14} {verdict:<8} dOOSfp={d['d_oos_sharpe_fp']:+.3f} dMdd={d['d_oos_maxdd_pp']:+.2f}pp "
              f"beatsDD={d['beats_oos_dd']} canRobust={d['canary_self_robust']} beatsUnderCanary={d['ens_beats_base_under_canary']}")
    print()
    if "yearly_base_vs_primary" in res:
        print("PER-YEAR OOS  base vs primary {50,100,200}:")
        print(f"{'year':<6}{'base_ret%':>11}{'ens_ret%':>11}{'base_Sfp':>10}{'ens_Sfp':>10}{'base_mdd%':>11}{'ens_mdd%':>11}")
        for row in res["yearly_base_vs_primary"]:
            print(f"{row['year']:<6}{row['base_ret_pct']:>11.1f}{row['ens_ret_pct']:>11.1f}"
                  f"{row['base_sharpe_fp']:>10.3f}{row['ens_sharpe_fp']:>10.3f}"
                  f"{row['base_maxdd_pct']:>11.2f}{row['ens_maxdd_pct']:>11.2f}")
    print()
    print(f"[driver] wrote {OUT}")
