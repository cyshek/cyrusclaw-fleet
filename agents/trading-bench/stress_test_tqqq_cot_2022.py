"""TQQQ+COT combo — 2022 bear-market stress test (focused).

RESEARCH / PAPER ONLY. Never live.

Goal: verify the COT AM-momentum overlay SPECIFICALLY helped (not hurt) during
the 2022 rate-hike drawdown. The aggregate OOS Sharpe (0.960) may mask the 2022
behavior, so we isolate Jan 1 2022 -> Dec 31 2022 and compare four books on the
SAME trading calendar:

  (a) TQQQ buy-and-hold        -- the raw unhedged 3x sleeve (no gate, no vol-tgt)
  (b) TQQQ vol-target sleeve   -- SMA-200 gate + 20d inverse-vol sizing, NO COT
  (c) tqqq_cot_combo           -- (b) AND COT-scale overlay (x0.5 when AM-net WoW down)
  (d) SPX buy-and-hold         -- reference

All curves come from the SAME engine used by the live strategy
(strategies_candidates._archive.tqqq_cot_combo.backtest_combo.run_combo_backtest),
which builds combo / vol-target / SPX on one calendar with the no-lookahead COT
publication-lag guard. We re-slice its equity to 2022 and add the (a) TQQQ
buy-and-hold curve + a day-by-day COT in/out-of-market diagnostic.

NO-LOOKAHEAD: identical to the live engine. The COT scale on held day D+1 is
decided from the most-recent COT report RELEASED on/before D (Tuesday snapshot +
3-day pub lag), via cot_cache release-date bisect. A price/vol move on D+1 cannot
change today's weight.

Run:
  cd /home/azureuser/.openclaw/agents/trading-bench/workspace
  python3 stress_test_tqqq_cot_2022.py
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE))

from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS
from strategies_candidates._archive.tqqq_cot_combo.backtest_combo import (
    run_combo_backtest,
    COT_SCALE_BEARISH,
    COT_SCALE_BULLISH,
)

START_2022 = "2022-01-01"
END_2022 = "2022-12-31"


# --------------------------------------------------------------------------- #
# Curve metric helpers (period total return, CAGR, maxDD, Sharpe, ann vol)
# --------------------------------------------------------------------------- #
def _seg_metrics(eq: List[float]) -> Dict[str, float]:
    """Total return / CAGR / maxDD / Sharpe / ann-vol for an equity SEGMENT
    (eq[0] is the segment's starting NAV). Daily simple returns; population sd."""
    if len(eq) < 2:
        return {"return_pct": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0,
                "sharpe": 0.0, "ann_vol_pct": 0.0}
    total = eq[-1] / eq[0] - 1.0
    yrs = (len(eq) - 1) / TRADING_DAYS
    cagr = ((eq[-1] / eq[0]) ** (1.0 / yrs) - 1.0) if yrs > 0 else 0.0
    # max drawdown
    peak = eq[0]
    mdd = 0.0
    for v in eq:
        if v > peak:
            peak = v
        dd = v / peak - 1.0
        if dd < mdd:
            mdd = dd
    # sharpe / vol
    rets = [eq[k] / eq[k - 1] - 1.0 for k in range(1, len(eq))]
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n
    sd = math.sqrt(var)
    sharpe = (mean / sd) * math.sqrt(TRADING_DAYS) if sd > 0 else 0.0
    ann_vol = sd * math.sqrt(TRADING_DAYS)
    return {"return_pct": total * 100.0, "cagr_pct": cagr * 100.0,
            "maxdd_pct": mdd * 100.0, "sharpe": sharpe,
            "ann_vol_pct": ann_vol * 100.0}


def _slice_idx(dates: List[str], start: str, end: str) -> Tuple[int, int]:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    return lo, hi


# --------------------------------------------------------------------------- #
# TQQQ buy-and-hold on the strategy's exact 2022 calendar (adjclose).
# --------------------------------------------------------------------------- #
def tqqq_buyhold_curve(dates_2022: List[str]) -> List[float]:
    """NAV=1.0 at dates_2022[0], full TQQQ exposure throughout (split+div adj)."""
    sleeve_by = {b["date"]: b for b in bd.dbc.get_daily("TQQQ")}
    eq = [1.0]
    for j in range(1, len(dates_2022)):
        dn, dp = dates_2022[j], dates_2022[j - 1]
        bn, bp = sleeve_by.get(dn), sleeve_by.get(dp)
        r = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
        eq.append(eq[-1] * (1.0 + r))
    return eq


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> Dict:
    print("=" * 86)
    print("TQQQ + COT COMBO — 2022 BEAR-MARKET STRESS TEST")
    print("=" * 86)

    # Run the full-history engine once; it builds combo/voltarget/spx on one
    # calendar with the live no-lookahead COT logic. We then slice 2022.
    res = run_combo_backtest(target_ann_vol=0.40, vol_window=20, w_max=1.0)

    dates = res["combo"]["dates"]
    lo, hi = _slice_idx(dates, START_2022, END_2022)
    dates_22 = dates[lo:hi]
    print(f"\n2022 calendar: {dates_22[0]} -> {dates_22[-1]} ({len(dates_22)} trading days)")

    # Slice each equity curve so each segment starts at NAV=1.0 on the first
    # 2022 trading day (re-base to lo).
    def rebase(eq: List[float]) -> List[float]:
        seg = eq[lo:hi]
        base = seg[0]
        return [v / base for v in seg]

    combo_eq = rebase(res["combo"]["equity"])
    vt_eq = rebase(res["voltarget"]["equity"])
    spx_eq = rebase(res["spx"]["equity"])
    tqqq_bh_eq = tqqq_buyhold_curve(dates_22)  # already NAV=1.0 at start

    m_combo = _seg_metrics(combo_eq)
    m_vt = _seg_metrics(vt_eq)
    m_spx = _seg_metrics(spx_eq)
    m_bh = _seg_metrics(tqqq_bh_eq)

    # ---- COT in/out-of-market diagnostics for 2022 (from pos_log) ----
    # pos_log rows align to held days D+1. w_vt = gate*voltgt (pre-COT),
    # w_combo = w_vt * cot_scale, cot_scale in {1.0, 0.5}.
    pl_22 = [pl for pl in res["pos_log"] if START_2022 <= pl["date"] <= END_2022]
    n_log = len(pl_22)
    cot_bearish_days = sum(1 for pl in pl_22 if pl["cot_scale"] == COT_SCALE_BEARISH)
    cot_bullish_days = sum(1 for pl in pl_22 if pl["cot_scale"] == COT_SCALE_BULLISH)
    # "in market" for the combo = w_combo > 0 ; gate-down OR vol-flat -> 0
    combo_in_mkt = sum(1 for pl in pl_22 if pl["w_combo"] > 0.0)
    vt_in_mkt = sum(1 for pl in pl_22 if pl["w_vt"] > 0.0)
    gate_up_days = sum(1 for pl in pl_22 if pl["trend_up"])
    avg_w_combo = sum(pl["w_combo"] for pl in pl_22) / n_log if n_log else 0.0
    avg_w_vt = sum(pl["w_vt"] for pl in pl_22) / n_log if n_log else 0.0
    # average exposure REDUCTION attributable to COT (where it fired)
    # days COT actively cut exposure (bearish AND vol-target wanted >0)
    cot_active_cut_days = sum(1 for pl in pl_22
                              if pl["cot_scale"] == COT_SCALE_BEARISH and pl["w_vt"] > 0.0)

    # First date in 2022 the COT signal went bearish (the "did it warn early?" Q)
    first_bearish = next((pl["date"] for pl in pl_22
                          if pl["cot_scale"] == COT_SCALE_BEARISH), None)
    # Build a compact bearish-streak timeline (month -> count) for the report.
    from collections import Counter
    bearish_by_month: Counter = Counter()
    for pl in pl_22:
        if pl["cot_scale"] == COT_SCALE_BEARISH:
            bearish_by_month[pl["date"][:7]] += 1

    # ---- Drawdown timing: when did each book bottom in 2022? ----
    def trough_info(eq: List[float], ds: List[str]) -> Tuple[str, float]:
        peak = eq[0]
        mdd = 0.0
        trough_date = ds[0]
        for k, v in enumerate(eq):
            if v > peak:
                peak = v
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
                trough_date = ds[k]
        return trough_date, mdd * 100.0

    bh_trough = trough_info(tqqq_bh_eq, dates_22)
    vt_trough = trough_info(vt_eq, dates_22)
    combo_trough = trough_info(combo_eq, dates_22)

    # ---- print summary table ----
    def row(name, m, extra=""):
        print(f"  {name:<30} ret {m['return_pct']:8.1f}%  maxDD {m['maxdd_pct']:7.1f}%  "
              f"vol {m['ann_vol_pct']:5.1f}%  Sharpe {m['sharpe']:6.3f}{extra}")

    print("\n--- 2022 BOOK COMPARISON (NAV rebased to 1.0 on first 2022 day) ---")
    row("(a) TQQQ buy & hold", m_bh)
    row("(b) TQQQ vol-target (no COT)", m_vt, f"  avgW {avg_w_vt:.3f}")
    row("(c) TQQQ+COT combo", m_combo, f"  avgW {avg_w_combo:.3f}")
    row("(d) SPX buy & hold", m_spx)

    print("\n--- COT FILTER ACTIVITY IN 2022 ---")
    print(f"  decision/held days in 2022 : {n_log}")
    print(f"  SMA-200 gate UP days       : {gate_up_days} "
          f"({100*gate_up_days/max(n_log,1):.1f}%)  [gate-down forces 0 regardless of COT]")
    print(f"  COT bearish days (scale 0.5): {cot_bearish_days} "
          f"({100*cot_bearish_days/max(n_log,1):.1f}%)")
    print(f"  COT bullish days (scale 1.0): {cot_bullish_days} "
          f"({100*cot_bullish_days/max(n_log,1):.1f}%)")
    print(f"  days COT ACTIVELY cut exposure (bearish & VT wanted >0): {cot_active_cut_days}")
    print(f"  combo days w_combo>0 (in market): {combo_in_mkt}  | vt days w_vt>0: {vt_in_mkt}")
    print(f"  avg combo weight {avg_w_combo:.3f}  vs  avg vt weight {avg_w_vt:.3f}  "
          f"(COT shaved {100*(avg_w_vt-avg_w_combo)/max(avg_w_vt,1e-9):.1f}% of avg exposure)")
    print(f"  first COT-bearish day in 2022: {first_bearish}")
    print(f"  bearish days by month: {dict(sorted(bearish_by_month.items()))}")

    print("\n--- DRAWDOWN TROUGH TIMING IN 2022 ---")
    print(f"  (a) TQQQ B&H   trough {bh_trough[0]}  maxDD {bh_trough[1]:.1f}%")
    print(f"  (b) vol-target trough {vt_trough[0]}  maxDD {vt_trough[1]:.1f}%")
    print(f"  (c) COT combo  trough {combo_trough[0]}  maxDD {combo_trough[1]:.1f}%")

    # ---- VERDICT logic ----
    dd_combo = abs(m_combo["maxdd_pct"])
    dd_vt = abs(m_vt["maxdd_pct"])
    ret_combo = m_combo["return_pct"]
    ret_vt = m_vt["return_pct"]
    dd_helped = dd_combo < dd_vt - 0.05         # combo drawdown materially smaller
    ret_helped = ret_combo > ret_vt + 0.05       # combo return materially higher
    if dd_helped and ret_helped:
        verdict = "COT ADDED VALUE (reduced DD AND improved return)"
    elif dd_helped and not ret_helped:
        verdict = "COT ADDED VALUE ON RISK (reduced DD; return ~flat/slightly lower)"
    elif (not dd_helped) and ret_helped:
        verdict = "COT ADDED VALUE ON RETURN (higher return; DD ~unchanged)"
    elif abs(dd_combo - dd_vt) < 0.05 and abs(ret_combo - ret_vt) < 0.05:
        verdict = "COT NEUTRAL in 2022 (did not fire enough to matter)"
    else:
        verdict = "COT HURT in 2022 (worse DD and/or return vs vol-target alone)"

    print("\n" + "=" * 86)
    print(f"VERDICT (2022): {verdict}")
    print("=" * 86)

    out = {
        "window": {"start": dates_22[0], "end": dates_22[-1], "n_days": len(dates_22)},
        "books": {
            "tqqq_buyhold": m_bh,
            "voltarget": m_vt,
            "combo": m_combo,
            "spx": m_spx,
        },
        "cot_activity": {
            "n_decision_days": n_log,
            "gate_up_days": gate_up_days,
            "cot_bearish_days": cot_bearish_days,
            "cot_bullish_days": cot_bullish_days,
            "cot_active_cut_days": cot_active_cut_days,
            "combo_in_market_days": combo_in_mkt,
            "vt_in_market_days": vt_in_mkt,
            "avg_w_combo": avg_w_combo,
            "avg_w_vt": avg_w_vt,
            "first_bearish_day": first_bearish,
            "bearish_by_month": dict(sorted(bearish_by_month.items())),
        },
        "troughs": {
            "tqqq_buyhold": {"date": bh_trough[0], "maxdd_pct": bh_trough[1]},
            "voltarget": {"date": vt_trough[0], "maxdd_pct": vt_trough[1]},
            "combo": {"date": combo_trough[0], "maxdd_pct": combo_trough[1]},
        },
        "verdict": verdict,
        "dd_helped": dd_helped,
        "ret_helped": ret_helped,
    }
    with open("/tmp/tqqq_cot_2022_stress.json", "w") as f:
        json.dump(out, f, indent=2)
    print("JSON -> /tmp/tqqq_cot_2022_stress.json")
    return out


if __name__ == "__main__":
    main()
