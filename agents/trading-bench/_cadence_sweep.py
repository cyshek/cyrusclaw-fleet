"""CADENCE SWEEP of the validated/live allocator_blend (invvol_63d).

QUESTION (binary, raw-return mandate): does re-targeting the inv-vol 63d blend
MORE or LESS often than MONTHLY beat the live MONTHLY config on RAW cumulative
return, NET of realistic turnover cost, without wrecking Sharpe / maxDD?

ENGINE REUSE (no sleeve-logic reimplementation):
  - Sleeve daily-return streams come from _allocator_blend_tests.build_sleeves()
    (cached verbatim in _regime_sleeves.pkl, built today 2026-06-25 over the
    common TQQQ-inception calendar). Same caches, same stats as the validated
    backtest. We fall back to a live build_sleeves() if the pkl is stale/missing.
  - The inv-vol 63d target-weight function is IDENTICAL to the promoted
    'invvol_63d' blend and to runner.allocator_paper_tracker.compute_blend_state
    (w_tqqq = iv0/(iv0+iv1) from trailing-63d POPULATION vols at the rebalance
    index; lookahead-safe -> uses sleeve returns STRICTLY BEFORE idx).
  - The MONTHLY baseline is reproduced two ways and CROSS-CHECKED:
      (a) ab.blend_portfolio() called directly (the validated month-open snap), and
      (b) our generalized blend_with_cadence() with a month-open trigger.
    (a) and (b) MUST agree and MUST reproduce the report's
    985 percent / Sharpe ~1.00 / maxDD -23.9 percent -- the faithfulness proof.

WHAT CHANGES vs the validated engine: ONLY the WHEN-to-rebalance. Same sleeve
returns, same inv-vol targets, same drift mechanics, same 2bps one-way
inter-sleeve cost, same _stats_from_equity ruler. Each cadence pays its OWN
turnover. We find the net optimum on RAW total return.

Stats convention: full-period stats via _stats_from_equity (POPULATION stdev,
sqrt(252)) -- the SAME ruler that produced the validated 1.014/1.003, so the
baseline reproduces. We ALSO report fp_sharpe.sharpe_from_returns (SAMPLE stdev,
the canonical FP-continuous ruler) as a documented cross-check column.

Run: python3 _cadence_sweep.py
Writes: reports/_cadence_sweep_result.json
"""
from __future__ import annotations

import bisect
import datetime as dtmod
import json
import math
import os
import pickle
import sys
from typing import Callable, Dict, List

sys.path.insert(0, ".")
sys.path.insert(0, "tests")

import _allocator_blend_tests as ab
from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity
from runner import fp_sharpe as fps

OOS_SPLIT = "2018-12-31"
VOL_LOOKBACK_DAYS = 63
BLEND_COST_BPS = 2.0
TRADING_DAYS = 252
CHURN_FRAC = 0.05
SLEEVE_PKL = "_regime_sleeves.pkl"


def load_sleeves() -> Dict:
    """Prefer the cached build_sleeves() output (built today 2026-06-25), else
    rebuild live. Either path yields the validated engine's verbatim streams."""
    if os.path.exists(SLEEVE_PKL):
        with open(SLEEVE_PKL, "rb") as fh:
            S = pickle.load(fh)
        if S.get("common_dates") and len(S["common_dates"]) == len(S.get("tqqq_r", [])):
            print("[sleeves] loaded cached %s (%s -> %s, n=%d)" % (
                SLEEVE_PKL, S["common_dates"][0], S["common_dates"][-1],
                len(S["common_dates"])), flush=True)
            return S
    print("[sleeves] cache miss/stale -> rebuilding via build_sleeves() ...", flush=True)
    return ab.build_sleeves()


def annualized_vol_pop(returns: List[float]) -> float:
    """Population-stdev annualized -- IDENTICAL to ab.annualized_vol and the live
    tracker's _annualized_vol. This is what the inv-vol weights use."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def invvol_target(sleeves: List[List[float]], idx: int,
                  lookback: int = VOL_LOOKBACK_DAYS) -> List[float]:
    """Inv-vol target weights at index idx. Lookahead-safe: trailing window is
    sleeves[k][idx-lookback : idx] (STRICTLY before idx). Mirrors the promoted
    invvol_wfn and allocator_paper_tracker.invvol_wfn EXACTLY."""
    if idx < 2:
        return [0.5, 0.5]
    lo = max(0, idx - lookback)
    v0 = annualized_vol_pop(sleeves[0][lo:idx])
    v1 = annualized_vol_pop(sleeves[1][lo:idx])
    if v0 <= 0 or v1 <= 0:
        return [0.5, 0.5]
    iv0, iv1 = 1.0 / v0, 1.0 / v1
    s = iv0 + iv1
    return [iv0 / s, iv1 / s]


def month_open_set(dates: List[str]) -> set:
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            out.add(i)
    return out


def quarter_open_set(dates: List[str]) -> set:
    """First trading day of each calendar quarter."""
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        mo = int(d[5:7])
        q = (d[:4], (mo - 1) // 3)
        if q not in seen:
            seen.add(q)
            out.add(i)
    return out


def week_open_set(dates: List[str], anchor_dow: int = 0) -> set:
    """First trading day of each week. anchor_dow selects the weekday that starts
    the week (0=Mon). Default => first trading day of each Mon-anchored week
    (usually Monday; Tuesday after a Monday holiday). anchor_dow is exposed for an
    alternate-anchor robustness spot-check."""
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        dtt = dtmod.date(y, m, dd)
        shifted = dtt - dtmod.timedelta(days=((dtt.weekday() - anchor_dow) % 7))
        key = shifted.isoformat()
        if key not in seen:
            seen.add(key)
            out.add(i)
    return out


def biweekly_open_set(dates: List[str], anchor_dow: int = 0) -> set:
    """Every other week's first trading day (every 2nd week-open chronologically)."""
    wopen = sorted(week_open_set(dates, anchor_dow))
    return set(wopen[::2])


def blend_with_cadence(dates: List[str], sleeves: List[List[float]],
                       should_rebalance: Callable[[int, List[float], List[float]], bool],
                       blend_cost_bps: float = BLEND_COST_BPS,
                       lookback: int = VOL_LOOKBACK_DAYS) -> Dict:
    """Generalized blend: mirrors ab.blend_portfolio EXACTLY but with a pluggable
    rebalance trigger should_rebalance(idx, cur_w, tgt_w) -> bool.
      - cur_w = drifted weights just BEFORE the potential rebalance at idx
      - tgt_w = inv-vol target at idx (computed for the decision; data <= idx-1)
    Cost + drift + stats are IDENTICAL to ab.blend_portfolio, so a month-open
    trigger reproduces the validated baseline."""
    n = len(dates)
    ns = len(sleeves)

    equity = [1.0]
    w0 = invvol_target(sleeves, 0, lookback)
    bucket = [w0[k] for k in range(ns)]
    eq_dates = [dates[0]]
    n_rebal = 0
    turnover_total = 0.0
    weight_log: List[Dict] = []

    for i in range(1, n):
        d = dates[i]
        tot = sum(bucket)
        cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * ns
        tgt = invvol_target(sleeves, i, lookback)
        if should_rebalance(i, cur_w, tgt):
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(ns))
            if turn > 1e-9:
                cost = (blend_cost_bps / 10000.0) * turn
                n_rebal += 1
                turnover_total += turn
                tot_after = tot * (1.0 - cost)
                bucket = [tgt[k] * tot_after for k in range(ns)]
                weight_log.append({"date": d, "w": list(tgt), "turn": turn})
        for k in range(ns):
            bucket[k] *= (1.0 + sleeves[k][i])
        equity.append(sum(bucket))
        eq_dates.append(d)

    in_market = [True] * (len(eq_dates) - 1)
    st = _stats_from_equity(eq_dates, equity, in_market, n_rebal)
    return {
        "dates": eq_dates, "equity": equity,
        "stats": dict(st.__dict__),
        "n_rebal": n_rebal,
        "turnover_total": turnover_total,
        "avg_turnover_per_rebal": (turnover_total / n_rebal) if n_rebal else 0.0,
        "weight_log": weight_log,
    }


def slice_stats(dates: List[str], equity: List[float], start: str, end: str) -> Dict:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    if hi - lo < 3:
        return {"n": hi - lo}
    sub_ds = dates[lo:hi]
    base = equity[lo]
    sub_eq = [v / base for v in equity[lo:hi]]
    st = _stats_from_equity(sub_ds, sub_eq)
    return dict(st.__dict__)


def fp_cont_sharpe(equity: List[float]) -> float:
    """Canonical FP-continuous Sharpe (SAMPLE stdev, sqrt(252)) from
    runner/fp_sharpe.py -- reported as a cross-check column alongside the
    _stats_from_equity (population) Sharpe."""
    rets = fps.equity_curve_returns(equity)
    return fps.sharpe_from_returns(rets, TRADING_DAYS)


def annual_turnover(turnover_total: float, dates: List[str]) -> float:
    if len(dates) < 2:
        return 0.0
    n_years = len(dates) / TRADING_DAYS
    return turnover_total / n_years if n_years > 0 else 0.0


def gross_total_return_pct(dates: List[str], sleeves: List[List[float]],
                           should_rebalance, lookback: int = VOL_LOOKBACK_DAYS) -> float:
    """Same cadence, ZERO cost -> isolates how much turnover eats."""
    b = blend_with_cadence(dates, sleeves, should_rebalance,
                           blend_cost_bps=0.0, lookback=lookback)
    return b["stats"]["total_return_pct"]


def equity_from_returns(rets: List[float]) -> List[float]:
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def summarize(blend: Dict, label: str, dates: List[str], sleeves: List[List[float]],
              should_rebalance) -> Dict:
    ds = blend["dates"]
    eq = blend["equity"]
    full = blend["stats"]
    oos = slice_stats(ds, eq, "2019-01-01", "2099-12-31")
    is_ = slice_stats(ds, eq, "2000-01-01", OOS_SPLIT)
    gross = gross_total_return_pct(dates, sleeves, should_rebalance)
    return {
        "label": label,
        "n_rebal": blend.get("n_rebal"),
        "turnover_total": blend.get("turnover_total"),
        "avg_turnover_per_rebal": blend.get("avg_turnover_per_rebal"),
        "annual_turnover": annual_turnover(blend.get("turnover_total", 0.0), ds),
        "full": {
            "total_return_pct": full["total_return_pct"],
            "total_return_pct_gross": gross,
            "cost_drag_pct": gross - full["total_return_pct"],
            "cagr_pct": full["cagr_pct"],
            "sharpe": full["sharpe"],
            "fp_cont_sharpe": fp_cont_sharpe(eq),
            "maxdd_pct": full["max_drawdown_pct"],
            "vol_pct": full["ann_vol_pct"],
        },
        "is_2010_2018": {"total_return_pct": is_.get("total_return_pct"),
                         "cagr_pct": is_.get("cagr_pct"),
                         "sharpe": is_.get("sharpe"),
                         "maxdd_pct": is_.get("max_drawdown_pct")},
        "oos_2019_today": {"total_return_pct": oos.get("total_return_pct"),
                           "cagr_pct": oos.get("cagr_pct"),
                           "sharpe": oos.get("sharpe"),
                           "maxdd_pct": oos.get("max_drawdown_pct")},
    }


def main() -> None:
    S = load_sleeves()
    dates: List[str] = S["common_dates"]
    tqqq_r: List[float] = S["tqqq_r"]
    rot_r: List[float] = S["rot_r"]
    spx_r: List[float] = S["spx_r"]
    sleeves = [tqqq_r, rot_r]

    moset = month_open_set(dates)
    qset = quarter_open_set(dates)
    wset = week_open_set(dates, anchor_dow=0)
    wset_alt = week_open_set(dates, anchor_dow=2)   # Wed-anchored alt spot-check
    bwset = biweekly_open_set(dates, anchor_dow=0)

    print(">>> common %s -> %s  n=%d | mo=%d q=%d wk=%d biwk=%d" % (
        dates[0], dates[-1], len(dates), len(moset), len(qset), len(wset),
        len(bwset)), flush=True)

    out: Dict = {}
    out["meta"] = {
        "common_window": [dates[0], dates[-1]],
        "n_days": len(dates),
        "n_month_opens": len(moset),
        "n_quarter_opens": len(qset),
        "n_week_opens": len(wset),
        "n_biweek_opens": len(bwset),
        "vol_lookback_days": VOL_LOOKBACK_DAYS,
        "blend_cost_bps": BLEND_COST_BPS,
        "churn_frac": CHURN_FRAC,
        "method": ("inv-vol 63d blend of (TQQQ vol-target + sector-rotation top-2); "
                   "vary ONLY the rebalance cadence; 2bps one-way inter-sleeve cost; "
                   "drift intramonth; _stats_from_equity (pop) ruler + fp_cont_sharpe "
                   "(sample) cross-check"),
        "sleeve_solo_stats": {
            "tqqq": {k: S["tqqq_solo_stats"][k] for k in
                     ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
            "rot": {k: S["rot_solo_stats"][k] for k in
                    ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
            "spx": {k: S["spx_solo_stats"][k] for k in
                    ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
        },
    }

    # ---- HARNESS-FAITHFULNESS: reproduce the validated MONTHLY two ways ----
    print(">>> [sanity] reproducing validated MONTHLY ...", flush=True)
    monthly_ref = ab.blend_portfolio(dates, sleeves, lambda i: invvol_target(sleeves, i),
                                     blend_cost_bps=BLEND_COST_BPS,
                                     vol_lookback_days=VOL_LOOKBACK_DAYS)
    ref_stats = monthly_ref["stats"]

    def trig_monthly(i, cur_w, tgt_w):
        return i in moset

    monthly_b = blend_with_cadence(dates, sleeves, trig_monthly)
    repro_totret = abs(monthly_b["stats"]["total_return_pct"]
                       - ref_stats["total_return_pct"]) < 1e-6
    repro_sharpe = abs(monthly_b["stats"]["sharpe"] - ref_stats["sharpe"]) < 1e-9
    print("    ab.blend_portfolio : totret %.2f%% Sharpe %.4f maxDD %.2f%%" % (
        ref_stats["total_return_pct"], ref_stats["sharpe"], ref_stats["max_drawdown_pct"]))
    print("    blend_with_cadence : totret %.2f%% Sharpe %.4f maxDD %.2f%%  [match tot=%s sh=%s]" % (
        monthly_b["stats"]["total_return_pct"], monthly_b["stats"]["sharpe"],
        monthly_b["stats"]["max_drawdown_pct"], repro_totret, repro_sharpe))
    wl = monthly_ref.get("weight_log", [])
    avg_w_tqqq = sum(w["w"][0] for w in wl) / len(wl) if wl else None
    print("    avg target w_tqqq = %.4f  (report says ~0.349)" % (
        avg_w_tqqq if avg_w_tqqq is not None else float("nan")))

    out["harness_faithfulness"] = {
        "ab_blend_portfolio": {"total_return_pct": ref_stats["total_return_pct"],
                               "sharpe": ref_stats["sharpe"],
                               "fp_cont_sharpe": fp_cont_sharpe(monthly_ref["equity"]),
                               "maxdd_pct": ref_stats["max_drawdown_pct"],
                               "cagr_pct": ref_stats["cagr_pct"]},
        "blend_with_cadence_monthly": {
            "total_return_pct": monthly_b["stats"]["total_return_pct"],
            "sharpe": monthly_b["stats"]["sharpe"],
            "maxdd_pct": monthly_b["stats"]["max_drawdown_pct"]},
        "reproduces_totret": repro_totret,
        "reproduces_sharpe": repro_sharpe,
        "avg_w_tqqq": avg_w_tqqq,
        "target_validated_sharpe_approx": 1.003,
        "target_validated_maxdd_approx": -23.9,
        "target_validated_totret_approx": 985.0,
    }

    spx_eq = equity_from_returns(spx_r)
    spx_dates_aligned = [dates[0]] + dates[:len(spx_r)]
    spx_full = _stats_from_equity(spx_dates_aligned, spx_eq)
    out["spx_floor"] = {"total_return_pct": spx_full.total_return_pct,
                        "cagr_pct": spx_full.cagr_pct, "sharpe": spx_full.sharpe,
                        "maxdd_pct": spx_full.max_drawdown_pct}

    # ---- trigger factories ----
    def cal_trigger(trigset):
        def fn(i, cur_w, tgt_w):
            return i in trigset
        return fn

    def drift_l1_trigger(tau):
        def fn(i, cur_w, tgt_w):
            l1 = sum(abs(cur_w[k] - tgt_w[k]) for k in range(len(cur_w)))
            return l1 > tau
        return fn

    def drift_maxleg_trigger(tau):
        def fn(i, cur_w, tgt_w):
            mx = max(abs(cur_w[k] - tgt_w[k]) for k in range(len(cur_w)))
            return mx > tau
        return fn

    # daily-churn-guarded: evaluate every day, trade only if past the live 5%
    # churn guard (max-leg drift > churn_frac). This is drift_maxleg at tau=0.05.
    def daily_churn_trigger():
        return drift_maxleg_trigger(CHURN_FRAC)

    # ---- run the cadence grid ----
    print(">>> cadence grid ...", flush=True)
    out["cadences"] = {}
    cadence_specs = {
        "monthly_baseline": cal_trigger(moset),
        "weekly":           cal_trigger(wset),
        "biweekly":         cal_trigger(bwset),
        "quarterly":        cal_trigger(qset),
        "daily_churn5pct":  daily_churn_trigger(),
    }
    for name, trig in cadence_specs.items():
        b = blend_with_cadence(dates, sleeves, trig)
        out["cadences"][name] = summarize(b, name, dates, sleeves, trig)
        f = out["cadences"][name]["full"]
        print("   %-18s net %.1f%% (gross %.1f%%, drag %.1f%%) CAGR %.1f%% Sh %.3f (fp %.3f) "
              "maxDD %.1f%% | OOS %.1f%% Sh %.3f | turn/yr %.2f n_rebal %d" % (
                  name, f["total_return_pct"], f["total_return_pct_gross"], f["cost_drag_pct"],
                  f["cagr_pct"], f["sharpe"], f["fp_cont_sharpe"], f["maxdd_pct"],
                  out["cadences"][name]["oos_2019_today"]["total_return_pct"] or float("nan"),
                  out["cadences"][name]["oos_2019_today"]["sharpe"] or float("nan"),
                  out["cadences"][name]["annual_turnover"], out["cadences"][name]["n_rebal"]))

    # ---- drift-threshold tau grid (L1 and max-leg) ----
    print(">>> drift-threshold tau grid ...", flush=True)
    out["drift_threshold"] = {"l1": {}, "maxleg": {}}
    tau_grid = [0.02, 0.05, 0.10, 0.15, 0.20, 0.25]
    for tau in tau_grid:
        t_l1 = drift_l1_trigger(tau)
        b1 = blend_with_cadence(dates, sleeves, t_l1)
        out["drift_threshold"]["l1"]["tau_%.2f" % tau] = summarize(
            b1, "drift_l1_%.2f" % tau, dates, sleeves, t_l1)
        t_mx = drift_maxleg_trigger(tau)
        b2 = blend_with_cadence(dates, sleeves, t_mx)
        out["drift_threshold"]["maxleg"]["tau_%.2f" % tau] = summarize(
            b2, "drift_maxleg_%.2f" % tau, dates, sleeves, t_mx)
        f1 = out["drift_threshold"]["l1"]["tau_%.2f" % tau]["full"]
        f2 = out["drift_threshold"]["maxleg"]["tau_%.2f" % tau]["full"]
        print("   tau %.2f | L1   net %.1f%% Sh %.3f maxDD %.1f%% turn/yr %.2f nreb %d || "
              "MAX net %.1f%% Sh %.3f maxDD %.1f%% turn/yr %.2f nreb %d" % (
                  tau, f1["total_return_pct"], f1["sharpe"], f1["maxdd_pct"],
                  out["drift_threshold"]["l1"]["tau_%.2f" % tau]["annual_turnover"],
                  out["drift_threshold"]["l1"]["tau_%.2f" % tau]["n_rebal"],
                  f2["total_return_pct"], f2["sharpe"], f2["maxdd_pct"],
                  out["drift_threshold"]["maxleg"]["tau_%.2f" % tau]["annual_turnover"],
                  out["drift_threshold"]["maxleg"]["tau_%.2f" % tau]["n_rebal"]))

    # ---- weekly alt-anchor spot-check (Wed-anchored) ----
    print(">>> weekly alt-anchor (Wed) spot-check ...", flush=True)
    t_walt = cal_trigger(wset_alt)
    b_walt = blend_with_cadence(dates, sleeves, t_walt)
    out["weekly_alt_anchor_wed"] = summarize(b_walt, "weekly_wed", dates, sleeves, t_walt)
    fwa = out["weekly_alt_anchor_wed"]["full"]
    print("   weekly(Wed) net %.1f%% Sh %.3f maxDD %.1f%% turn/yr %.2f n_rebal %d" % (
        fwa["total_return_pct"], fwa["sharpe"], fwa["maxdd_pct"],
        out["weekly_alt_anchor_wed"]["annual_turnover"],
        out["weekly_alt_anchor_wed"]["n_rebal"]))

    # ---- verdict scan ----
    base_net = out["cadences"]["monthly_baseline"]["full"]["total_return_pct"]
    base_oos = out["cadences"]["monthly_baseline"]["oos_2019_today"]["total_return_pct"]
    base_sh = out["cadences"]["monthly_baseline"]["full"]["sharpe"]
    base_dd = out["cadences"]["monthly_baseline"]["full"]["maxdd_pct"]
    all_variants = {}
    for k, v in out["cadences"].items():
        if k != "monthly_baseline":
            all_variants[k] = v
    for fam in ("l1", "maxleg"):
        for k, v in out["drift_threshold"][fam].items():
            all_variants["drift_%s_%s" % (fam, k)] = v
    beats_net = {k: v for k, v in all_variants.items()
                 if v["full"]["total_return_pct"] > base_net}
    beats_net_oos = {k: v for k, v in all_variants.items()
                     if (v["oos_2019_today"]["total_return_pct"] is not None
                         and base_oos is not None
                         and v["oos_2019_today"]["total_return_pct"] > base_oos)}
    best = max(all_variants.items(), key=lambda kv: kv[1]["full"]["total_return_pct"])
    out["verdict_scan"] = {
        "monthly_baseline_net_totret_pct": base_net,
        "monthly_baseline_oos_totret_pct": base_oos,
        "monthly_baseline_full_sharpe": base_sh,
        "monthly_baseline_maxdd_pct": base_dd,
        "n_variants": len(all_variants),
        "n_beat_baseline_net_full": len(beats_net),
        "n_beat_baseline_net_oos": len(beats_net_oos),
        "variants_beating_full": sorted(beats_net.keys()),
        "variants_beating_oos": sorted(beats_net_oos.keys()),
        "best_variant": best[0],
        "best_variant_net_totret_pct": best[1]["full"]["total_return_pct"],
        "best_variant_full_sharpe": best[1]["full"]["sharpe"],
        "best_variant_maxdd_pct": best[1]["full"]["maxdd_pct"],
        "best_variant_oos_totret_pct": best[1]["oos_2019_today"]["total_return_pct"],
    }
    print("")
    print(">>> VERDICT SCAN: monthly baseline NET %.1f%% (Sh %.3f maxDD %.1f%%, OOS %.1f%%)" % (
        base_net, base_sh, base_dd, base_oos or float("nan")))
    print("    variants beating baseline NET: full %d/%d | OOS %d/%d" % (
        len(beats_net), len(all_variants), len(beats_net_oos), len(all_variants)))
    print("    best by NET totret: %s -> %.1f%% (Sh %.3f maxDD %.1f%% OOS %.1f%%)" % (
        best[0], best[1]["full"]["total_return_pct"], best[1]["full"]["sharpe"],
        best[1]["full"]["maxdd_pct"], best[1]["oos_2019_today"]["total_return_pct"] or float("nan")))

    os.makedirs("reports", exist_ok=True)
    with open("reports/_cadence_sweep_result.json", "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote reports/_cadence_sweep_result.json")


if __name__ == "__main__":
    main()
