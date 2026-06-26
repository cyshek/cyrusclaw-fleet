"""REGIME-CONDITIONAL allocator: tilt the TQQQ-vs-rotation inter-sleeve weight by
a PIT macro regime (NFCI), vs the validated STATIC inv-vol blend.

See report header in reports/REGIME_ALLOCATOR_TQQQ_ROTATION_20260625.md for the
full method writeup. Research-only scratch driver.

ENGINE REUSE (no sleeve-logic reimplementation):
  - Sleeve daily-return streams come from _allocator_blend_tests.build_sleeves()
    (cached in _regime_sleeves.pkl to avoid rebuilding the slow engines).
  - The blend mechanic is _allocator_blend_tests.blend_portfolio() called DIRECTLY.
  - STATIC baseline = promoted 'invvol_63d': w_tqqq = iv0/(iv0+iv1) from trailing
    63d sleeve vols at each month-open (mirrors allocator_paper_tracker).

REGIME (PIT, ALFRED enforces the NFCI ~1wk release lag):
  At month-open D, NFCI via ALFRED realtime_start=realtime_end=D; take LAST obs
  released by D. risk-OFF iff nfci_D > thr.
  thresholds: "zero" (thr=0), "exmed" (expanding PIT median of NFCI known<=D).
  Weight: w_tqqq = clamp(w_static +/- tilt, 0, 1); +tilt risk-ON, -tilt risk-OFF.
  Robustness composite "nfci_baa": risk-OFF iff 0.5*z(NFCI)+0.5*z(BAA10Y)>0 on
  expanding PIT windows.
"""
from __future__ import annotations

import bisect
import json
import math
import pickle
import sys
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, ".")

import _allocator_blend_tests as ab
from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity
from runner import fred_cache as fc
from runner import fp_sharpe as fps

OOS_SPLIT = "2018-12-31"
VOL_LOOKBACK_DAYS = 63
BLEND_COST_BPS = 2.0
TRADING_DAYS = 252
NFCI_FIRSTREL = ".cache/fred/NFCI_pit_firstrelease.json"


def load_sleeves() -> Dict:
    with open("_regime_sleeves.pkl", "rb") as f:
        return pickle.load(f)


def annualized_vol_pop(returns: List[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def month_open_indices(dates: List[str]) -> List[int]:
    seen = set()
    out: List[int] = []
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            out.append(i)
    return out


def static_invvol_w_tqqq(sleeves: List[List[float]], idx: int,
                         lookback: int = VOL_LOOKBACK_DAYS) -> float:
    """w_tqqq for the promoted invvol_63d blend at month-open index idx.
    Lookahead-safe: uses sleeve returns STRICTLY BEFORE idx."""
    if idx < 2:
        return 0.5
    lo = max(0, idx - lookback)
    v0 = annualized_vol_pop(sleeves[0][lo:idx])
    v1 = annualized_vol_pop(sleeves[1][lo:idx])
    if v0 <= 0 or v1 <= 0:
        return 0.5
    iv0, iv1 = 1.0 / v0, 1.0 / v1
    return iv0 / (iv0 + iv1)


def build_nfci_pit(rebal_dates: List[str]) -> Dict[str, Tuple[float, str, str]]:
    """For each rebalance date D return (nfci_value_used, nfci_obs_date,
    nfci_release_date) from the cached FIRST-RELEASE NFCI dict (purest PIT:
    first print, no revision leak). The dict maps obs_date -> [release_date,
    first_value]. At month-open D take the LATEST obs whose RELEASE_DATE <= D
    -- the freshest NFCI a trader could legitimately have acted on at D.

    NFCI's real-time archive begins 2011-05-25 (its first release; ALFRED 400s
    on as-of dates before that). Rebalance dates before the first release get
    no entry here -> caller falls back to the static inv-vol weight. Honest:
    you could not have traded an NFCI regime in 2010.
    """
    with open(NFCI_FIRSTREL) as fh:
        firstrel = json.load(fh)
    recs = sorted(
        ((v[0], k, float(v[1]))
         for k, v in firstrel.items()
         if isinstance(v, list) and v and v[0] is not None and v[1] is not None),
        key=lambda x: x[0])
    rel_dates = [r[0] for r in recs]

    out: Dict[str, Tuple[float, str, str]] = {}
    for D in rebal_dates:
        j = bisect.bisect_right(rel_dates, D) - 1
        if j < 0:
            continue
        rel, obs, val = recs[j]
        out[D] = (val, obs, rel)
    return out

def build_baa_pit(rebal_dates: List[str]) -> Dict[str, Tuple[float, str]]:
    """PIT BAA10Y (daily market spread, effectively unrevised). At month-open D
    use the last obs STRICTLY before D (a prior close)."""
    rows = fc.get_values("BAA10Y", "2008-01-01", "2026-12-31", vintage="latest")
    ds = [r[0] for r in rows]
    vs = [r[1] for r in rows]
    out: Dict[str, Tuple[float, str]] = {}
    for D in rebal_dates:
        j = bisect.bisect_left(ds, D) - 1
        if j >= 0:
            out[D] = (float(vs[j]), ds[j])
    return out


def make_regime_wfn(dates: List[str], sleeves: List[List[float]],
                    nfci_pit: Dict[str, Tuple[float, str, str]],
                    tilt: float, threshold: str,
                    baa_pit: Optional[Dict[str, Tuple[float, str]]] = None,
                    composite: str = "nfci") -> Callable[[int], List[float]]:
    """threshold in {"zero","exmed"}; composite in {"nfci","nfci_baa"}."""
    mo = month_open_indices(dates)
    mo_dates = [dates[i] for i in mo]
    nfci_seq = [(d, nfci_pit[d][0]) for d in mo_dates if d in nfci_pit]
    nfci_dates_ord = [d for d, _ in nfci_seq]
    nfci_vals_ord = [v for _, v in nfci_seq]
    nfci_pos = {d: k for k, d in enumerate(nfci_dates_ord)}

    if composite == "nfci_baa" and baa_pit is not None:
        baa_seq = [(d, baa_pit[d][0]) for d in mo_dates if d in baa_pit]
        baa_dates_ord = [d for d, _ in baa_seq]
        baa_vals_ord = [v for _, v in baa_seq]
        baa_pos = {d: k for k, d in enumerate(baa_dates_ord)}
    else:
        baa_dates_ord, baa_vals_ord, baa_pos = [], [], {}

    def expanding_median(vals: List[float], upto_idx: int) -> float:
        sub = vals[:upto_idx + 1]
        if not sub:
            return 0.0
        s = sorted(sub)
        n = len(s)
        return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

    def expanding_z(vals: List[float], upto_idx: int, x: float) -> float:
        sub = vals[:upto_idx + 1]
        if len(sub) < 3:
            return 0.0
        m = sum(sub) / len(sub)
        var = sum((u - m) ** 2 for u in sub) / len(sub)
        sd = math.sqrt(var)
        return (x - m) / sd if sd > 0 else 0.0

    def fn(idx: int) -> List[float]:
        w_static = static_invvol_w_tqqq(sleeves, idx)
        D = dates[idx]
        if D not in nfci_pos:
            return [w_static, 1.0 - w_static]
        k = nfci_pos[D]
        nfci_v = nfci_vals_ord[k]

        if composite == "nfci_baa" and baa_dates_ord:
            znfci = expanding_z(nfci_vals_ord, k, nfci_v)
            if D in baa_pos:
                bk = baa_pos[D]
                zbaa = expanding_z(baa_vals_ord, bk, baa_vals_ord[bk])
            else:
                zbaa = 0.0
            risk_off = (0.5 * znfci + 0.5 * zbaa) > 0.0
        else:
            if threshold == "zero":
                thr = 0.0
            elif threshold == "exmed":
                thr = expanding_median(nfci_vals_ord, k)
            else:
                raise ValueError("bad threshold %r" % threshold)
            risk_off = nfci_v > thr

        w = (w_static - tilt) if risk_off else (w_static + tilt)
        w = max(0.0, min(1.0, w))
        return [w, 1.0 - w]

    return fn


def make_static_wfn(sleeves: List[List[float]]) -> Callable[[int], List[float]]:
    def fn(idx: int) -> List[float]:
        w = static_invvol_w_tqqq(sleeves, idx)
        return [w, 1.0 - w]
    return fn


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
    rets = fps.equity_curve_returns(equity)
    return fps.sharpe_from_returns(rets, TRADING_DAYS)


def equity_from_returns(rets: List[float]) -> List[float]:
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def summarize(blend: Dict, label: str) -> Dict:
    ds = blend["dates"]
    eq = blend["equity"]
    full = blend["stats"]
    oos = slice_stats(ds, eq, "2019-01-01", "2099-12-31")
    is_ = slice_stats(ds, eq, "2000-01-01", OOS_SPLIT)
    return {
        "label": label,
        "n_rebal": blend.get("n_rebal"),
        "avg_turnover_per_rebal": blend.get("avg_turnover_per_rebal"),
        "full": {
            "total_return_pct": full["total_return_pct"],
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


# --------------------------------------------------------------------------- #
# DRIVER
# --------------------------------------------------------------------------- #
def main() -> None:
    S = load_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]
    sleeves = [tqqq_r, rot_r]

    mo = month_open_indices(dates)
    mo_dates = [dates[i] for i in mo]
    print(">>> common %s -> %s  n=%d  month_opens=%d" % (
        dates[0], dates[-1], len(dates), len(mo)), flush=True)

    print(">>> building PIT NFCI feed (first-release, release_date <= rebal) ...", flush=True)
    nfci_pit = build_nfci_pit(mo_dates)
    print("    NFCI PIT covers %d / %d month-opens (first=%s last=%s)" % (
        len(nfci_pit), len(mo_dates),
        min(nfci_pit) if nfci_pit else None, max(nfci_pit) if nfci_pit else None))
    print(">>> building PIT BAA10Y feed ...", flush=True)
    baa_pit = build_baa_pit(mo_dates)
    print("    BAA10Y PIT covers %d / %d month-opens" % (len(baa_pit), len(mo_dates)))

    out: Dict = {}
    out["meta"] = {
        "common_window": [dates[0], dates[-1]],
        "n_days": len(dates),
        "n_month_opens": len(mo),
        "nfci_pit_coverage": len(nfci_pit),
        "method": "regime tilt around static invvol_63d; ALFRED-PIT NFCI; monthly rebalance; 2bps inter-sleeve cost",
        "tqqq_solo_stats": {k: S["tqqq_solo_stats"][k] for k in ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
        "rot_solo_stats": {k: S["rot_solo_stats"][k] for k in ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
        "spx_solo_stats": {k: S["spx_solo_stats"][k] for k in ("sharpe", "cagr_pct", "max_drawdown_pct", "total_return_pct")},
    }

    # ----- STATIC baseline (the benchmark to beat) -----
    print(">>> STATIC invvol_63d baseline ...", flush=True)
    static_b = ab.blend_portfolio(dates, sleeves, make_static_wfn(sleeves),
                                  blend_cost_bps=BLEND_COST_BPS,
                                  vol_lookback_days=VOL_LOOKBACK_DAYS)
    out["static_invvol_63d"] = summarize(static_b, "static_invvol_63d")
    wl = static_b.get("weight_log", [])
    avg_static_w = sum(w["w"][0] for w in wl) / len(wl) if wl else None
    out["static_invvol_63d"]["avg_w_tqqq"] = avg_static_w
    s = out["static_invvol_63d"]["full"]
    print("    STATIC: totret %.1f%% CAGR %.1f%% Sharpe %.3f (fp %.3f) maxDD %.1f%% | avg w_tqqq %.3f" % (
        s["total_return_pct"], s["cagr_pct"], s["sharpe"], s["fp_cont_sharpe"], s["maxdd_pct"],
        avg_static_w if avg_static_w is not None else float("nan")))

    # ----- SPX floor -----
    spx_eq = equity_from_returns(spx_r)
    spx_dates_aligned = [dates[0]] + dates[:len(spx_r)]
    spx_full = _stats_from_equity(spx_dates_aligned, spx_eq)
    spx_oos = slice_stats(spx_dates_aligned, spx_eq, "2019-01-01", "2099-12-31")
    out["spx_floor"] = {
        "full": {"total_return_pct": spx_full.total_return_pct,
                 "cagr_pct": spx_full.cagr_pct, "sharpe": spx_full.sharpe,
                 "maxdd_pct": spx_full.max_drawdown_pct},
        "oos_2019_today": {"total_return_pct": spx_oos.get("total_return_pct"),
                           "cagr_pct": spx_oos.get("cagr_pct"),
                           "sharpe": spx_oos.get("sharpe")},
    }
    print("    SPX floor: totret %.1f%% CAGR %.1f%% Sharpe %.3f maxDD %.1f%%" % (
        spx_full.total_return_pct, spx_full.cagr_pct, spx_full.sharpe, spx_full.max_drawdown_pct))

    static_totret = out["static_invvol_63d"]["full"]["total_return_pct"]
    static_oos_totret = out["static_invvol_63d"]["oos_2019_today"]["total_return_pct"]

    # ----- REGIME GRID (tilt x threshold, single-NFCI composite) -----
    print(">>> regime grid (tilt x threshold) ...", flush=True)
    tilts = [0.0, 0.15, 0.25, 0.35]
    thresholds = ["zero", "exmed"]
    out["regime_grid"] = {}
    for thr in thresholds:
        for tilt in tilts:
            name = "nfci_%s_tilt%.2f" % (thr, tilt)
            wfn = make_regime_wfn(dates, sleeves, nfci_pit, tilt, thr,
                                  baa_pit=None, composite="nfci")
            b = ab.blend_portfolio(dates, sleeves, wfn,
                                   blend_cost_bps=BLEND_COST_BPS,
                                   vol_lookback_days=VOL_LOOKBACK_DAYS)
            rep = summarize(b, name)
            rep["beats_static_full_totret"] = rep["full"]["total_return_pct"] > static_totret
            rep["beats_static_oos_totret"] = (
                rep["oos_2019_today"]["total_return_pct"] is not None
                and static_oos_totret is not None
                and rep["oos_2019_today"]["total_return_pct"] > static_oos_totret)
            out["regime_grid"][name] = rep
            f = rep["full"]
            print("   %-22s full totret %.1f%% CAGR %.1f%% Sharpe %.3f maxDD %.1f%% | OOS totret %.1f%% Sh %.3f | beat_static full=%s oos=%s" % (
                name, f["total_return_pct"], f["cagr_pct"], f["sharpe"], f["maxdd_pct"],
                rep["oos_2019_today"]["total_return_pct"] or float("nan"),
                rep["oos_2019_today"]["sharpe"] or float("nan"),
                rep["beats_static_full_totret"], rep["beats_static_oos_totret"]))

    # ----- ROBUSTNESS composite: NFCI + BAA10Y z-blend -----
    print(">>> robustness composite nfci_baa (z-blend, > 0 = risk-off) ...", flush=True)
    out["regime_grid_nfci_baa"] = {}
    for tilt in tilts:
        name = "nfci_baa_tilt%.2f" % tilt
        wfn = make_regime_wfn(dates, sleeves, nfci_pit, tilt, "zero",
                              baa_pit=baa_pit, composite="nfci_baa")
        b = ab.blend_portfolio(dates, sleeves, wfn,
                               blend_cost_bps=BLEND_COST_BPS,
                               vol_lookback_days=VOL_LOOKBACK_DAYS)
        rep = summarize(b, name)
        rep["beats_static_full_totret"] = rep["full"]["total_return_pct"] > static_totret
        rep["beats_static_oos_totret"] = (
            rep["oos_2019_today"]["total_return_pct"] is not None
            and static_oos_totret is not None
            and rep["oos_2019_today"]["total_return_pct"] > static_oos_totret)
        out["regime_grid_nfci_baa"][name] = rep
        f = rep["full"]
        print("   %-22s full totret %.1f%% CAGR %.1f%% Sharpe %.3f maxDD %.1f%% | OOS totret %.1f%% Sh %.3f | beat_static full=%s oos=%s" % (
            name, f["total_return_pct"], f["cagr_pct"], f["sharpe"], f["maxdd_pct"],
            rep["oos_2019_today"]["total_return_pct"] or float("nan"),
            rep["oos_2019_today"]["sharpe"] or float("nan"),
            rep["beats_static_full_totret"], rep["beats_static_oos_totret"]))

    # ----- NO-LOOKAHEAD CANARY -----
    print(">>> no-lookahead canary (rebal_date, nfci_value_used, nfci_obs_date, nfci_release_date) ...", flush=True)
    canary_rows = []
    sample_dates = mo_dates[::24]  # ~every 2 years
    for D in sample_dates:
        if D in nfci_pit:
            val, obs, rel = nfci_pit[D]
            clean = (rel != "" and rel <= D)
            canary_rows.append({"rebal_date": D, "nfci_value_used": val,
                                "nfci_obs_date": obs, "nfci_release_date": rel,
                                "release_leq_rebal": clean})
            print("   %s  nfci=%+.3f  obs=%s  released=%s  release<=rebal:%s" % (
                D, val, obs, rel or "?", clean))
    # global canary: every used release date <= its rebal date
    all_clean = all(
        (nfci_pit[D][2] != "" and nfci_pit[D][2] <= D)
        for D in nfci_pit)
    n_with_rel = sum(1 for D in nfci_pit if nfci_pit[D][2] != "")
    out["canary"] = {
        "rows": canary_rows,
        "all_used_releases_leq_rebal": all_clean,
        "n_month_opens_with_release_date": n_with_rel,
        "n_month_opens_total": len(nfci_pit),
    }
    print("   CANARY: all used NFCI releases <= rebal date? %s (release-date coverage %d/%d)" % (
        all_clean, n_with_rel, len(nfci_pit)))

    # ----- VERDICT SCAN -----
    grid_all = dict(out["regime_grid"])
    grid_all.update(out["regime_grid_nfci_baa"])
    nonzero = {k: v for k, v in grid_all.items() if "tilt0.00" not in k}
    n_beat_full = sum(1 for v in nonzero.values() if v["beats_static_full_totret"])
    n_beat_oos = sum(1 for v in nonzero.values() if v["beats_static_oos_totret"])
    best_full = max(grid_all.items(), key=lambda kv: kv[1]["full"]["total_return_pct"])
    out["verdict_scan"] = {
        "static_full_totret_pct": static_totret,
        "static_oos_totret_pct": static_oos_totret,
        "n_nonzero_variants": len(nonzero),
        "n_beat_static_full_totret": n_beat_full,
        "n_beat_static_oos_totret": n_beat_oos,
        "best_full_variant": best_full[0],
        "best_full_totret_pct": best_full[1]["full"]["total_return_pct"],
        "best_full_sharpe": best_full[1]["full"]["sharpe"],
        "best_full_maxdd_pct": best_full[1]["full"]["maxdd_pct"],
    }
    print("")
    print(">>> VERDICT SCAN: static full totret %.1f%% | best variant %s totret %.1f%% (Sharpe %.3f maxDD %.1f%%)" % (
        static_totret, best_full[0], best_full[1]["full"]["total_return_pct"],
        best_full[1]["full"]["sharpe"], best_full[1]["full"]["maxdd_pct"]))
    print("    nonzero variants beating static on RAW totret: full %d/%d | OOS %d/%d" % (
        n_beat_full, len(nonzero), n_beat_oos, len(nonzero)))

    with open("reports/_regime_allocator_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote reports/_regime_allocator_result.json")


if __name__ == "__main__":
    main()
