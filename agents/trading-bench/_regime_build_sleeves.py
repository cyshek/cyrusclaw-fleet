"""Build the two validated sleeves via the validated engine and pickle the
date-aligned daily-return streams so the regime-allocator grid can run without
rebuilding the (slow) sleeve engines each time. Research-only scratch."""
from __future__ import annotations

import json
import pickle
import sys
import time

sys.path.insert(0, ".")

import _allocator_blend_tests as ab


def main() -> None:
    t0 = time.time()
    S = ab.build_sleeves()
    print("BUILD OK in %.1fs" % (time.time() - t0), flush=True)
    dates = S["common_dates"]
    print("common window: %s -> %s  n=%d" % (dates[0], dates[-1], len(dates)))

    seen = set()
    mo = []
    for i, d in enumerate(dates):
        if d[:7] not in seen:
            seen.add(d[:7])
            mo.append(d)
    print("n_month_opens: %d  first3=%s  last3=%s" % (len(mo), mo[:3], mo[-3:]))
    print("TQQQ solo Sharpe %.4f | ROT solo Sharpe %.4f | SPX Sharpe %.4f" % (
        S["tqqq_solo"]["stats"]["sharpe"],
        S["rot_solo"]["stats"]["sharpe"],
        S["spx_solo"]["stats"]["sharpe"]))

    payload = {
        "common_dates": dates,
        "tqqq_r": S["tqqq_r"],
        "rot_r": S["rot_r"],
        "spx_r": S["spx_r"],
        "tqqq_solo_stats": S["tqqq_solo"]["stats"],
        "rot_solo_stats": S["rot_solo"]["stats"],
        "spx_solo_stats": S["spx_solo"]["stats"],
    }
    with open("_regime_sleeves.pkl", "wb") as f:
        pickle.dump(payload, f)
    print("pickled sleeves -> _regime_sleeves.pkl")


if __name__ == "__main__":
    main()
