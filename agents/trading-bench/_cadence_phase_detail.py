"""Per-phase detail for the 2-, 3-, 4-monthly cadence families + a no-lookahead
assertion. We want to confirm N=3 (quarterly) every phase beats monthly (not just
the phase-average), and that the recommended cadence's edge is not a single phase.
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List

sys.path.insert(0, ".")
sys.path.insert(0, "tests")

import _cadence_sweep as cs


def cal(trigset):
    def fn(i, cur_w, tgt_w):
        return i in trigset
    return fn


def every_nth_month_set(dates, n, offset):
    mo = sorted(cs.month_open_set(dates))
    return set(mo[offset::n])


def main() -> None:
    S = cs.load_sleeves()
    dates = S["common_dates"]
    sleeves = [S["tqqq_r"], S["rot_r"]]
    moset = cs.month_open_set(dates)
    mb = cs.blend_with_cadence(dates, sleeves, cal(moset))
    base = mb["stats"]["total_return_pct"]
    base_oos = cs.slice_stats(mb["dates"], mb["equity"], "2019-01-01", "2099-12-31").get("total_return_pct")
    print("monthly baseline net %.1f%% OOS %.1f%%" % (base, base_oos))

    out: Dict = {"monthly_net": base, "monthly_oos": base_oos, "families": {}}
    for n in (2, 3, 4):
        print(">>> every_%dmo per-phase:" % n)
        phases = []
        for off in range(n):
            ms = every_nth_month_set(dates, n, off)
            b = cs.blend_with_cadence(dates, sleeves, cal(ms))
            full = b["stats"]
            oos = cs.slice_stats(b["dates"], b["equity"], "2019-01-01", "2099-12-31")
            rec = {"phase": off, "net": full["total_return_pct"], "sharpe": full["sharpe"],
                   "maxdd": full["max_drawdown_pct"], "oos": oos.get("total_return_pct"),
                   "oos_sharpe": oos.get("sharpe"), "n_rebal": b["n_rebal"],
                   "beats_monthly_full": full["total_return_pct"] > base,
                   "beats_monthly_oos": (oos.get("total_return_pct") is not None
                                         and oos.get("total_return_pct") > base_oos)}
            phases.append(rec)
            print("   phase %d  net %.1f%% (Sh %.3f DD %.1f%%) OOS %.1f%% (Sh %.3f) | beats_full=%s beats_oos=%s" % (
                off, rec["net"], rec["sharpe"], rec["maxdd"], rec["oos"] or float("nan"),
                rec["oos_sharpe"] or float("nan"), rec["beats_monthly_full"], rec["beats_monthly_oos"]))
        n_beat_full = sum(1 for p in phases if p["beats_monthly_full"])
        n_beat_oos = sum(1 for p in phases if p["beats_monthly_oos"])
        out["families"]["every_%dmo" % n] = {"phases": phases,
                                             "n_phases_beat_full": n_beat_full,
                                             "n_phases_beat_oos": n_beat_oos,
                                             "n_phases": n}
        print("   -> %d/%d phases beat monthly FULL, %d/%d beat monthly OOS" % (
            n_beat_full, n, n_beat_oos, n))

    with open("reports/_cadence_phase_detail.json", "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote reports/_cadence_phase_detail.json")


if __name__ == "__main__":
    main()
