"""FX LANE verdict driver — runs TSMOM (per-symbol + basket), carry-proxy note,
the +1-bar canary, IS/OOS split, and SPY-correlation. Prints a structured
result block the report is built from. Throwaway scratch driver.
"""
from __future__ import annotations

import json

from runner.fx_strategies import (
    aligned_closes,
    cagr,
    fx_cost_model,
    max_drawdown,
    pearson_corr,
    run_basket,
    run_basket_buyhold,
    run_single,
    sharpe,
    split_is_oos,
    spy_returns,
    total_return,
    tsmom_signal,
    align_returns_by_date,
)
from runner.fx_bars_cache import FX_MAJORS

FX7 = list(FX_MAJORS) + ["NZDUSD=X"]   # 6 majors + NZD for the basket
OOS_BOUNDARY = "2018-01-01"


def _fmt(res, label):
    sh = sharpe(res.rets)
    is_r, oos_r = split_is_oos(res, OOS_BOUNDARY)
    sh_is = sharpe(is_r)
    sh_oos = sharpe(oos_r)
    tr = total_return(res.rets)
    cg = cagr(res.rets)
    mdd = max_drawdown(res.equity)
    avg_turn = sum(res.turnover) / len(res.turnover) if res.turnover else 0.0
    return {
        "label": label, "n": res.n,
        "first": res.dates[0] if res.dates else None,
        "last": res.dates[-1] if res.dates else None,
        "sharpe_full": round(sh, 3),
        "sharpe_is": round(sh_is, 3), "n_is": len(is_r),
        "sharpe_oos": round(sh_oos, 3), "n_oos": len(oos_r),
        "total_return": round(tr, 4), "cagr": round(cg, 4),
        "maxdd": round(mdd, 4), "avg_turnover": round(avg_turn, 4),
        "_rets": res.rets, "_dates": res.dates,
    }


def _canary(symbols_or_sym, lookback, skip, allow_short, basket=True):
    """Return (base_sharpe_full, lagged_sharpe_full). Lag the SIGNAL one extra
    bar: position into r_t now uses closes[:t-1]. Implemented by shifting the
    position array right by 1 (insert a leading 0)."""
    def sig(c):
        return tsmom_signal(c, lookback=lookback, skip=skip, allow_short=allow_short)

    def sig_lagged(c):
        p = tsmom_signal(c, lookback=lookback, skip=skip, allow_short=allow_short)
        return [0.0] + p[:-1]   # shift right -> one extra bar of lag

    if basket:
        base = run_basket(symbols_or_sym, sig)
        lag = run_basket(symbols_or_sym, sig_lagged)
    else:
        dates, closes = aligned_closes([symbols_or_sym])
        c = closes[symbols_or_sym]
        base = run_single(c, dates, sig(c))
        lag = run_single(c, dates, sig_lagged(c))
    return round(sharpe(base.rets), 3), round(sharpe(lag.rets), 3)


def main():
    out = {"strategies": [], "per_symbol": {}, "canary": {}, "spy_corr": {}}
    cost = fx_cost_model()  # 1bp one-way

    # ---- 1. TSMOM basket, several lookbacks, long-short and long-flat ----
    for lb, lab in [(63, "3mo"), (126, "6mo"), (252, "12mo")]:
        for short, stag in [(True, "LS"), (False, "LF")]:
            sig = (lambda L, S: (lambda c: tsmom_signal(c, lookback=L, allow_short=S)))(lb, short)
            res = run_basket(FX7, sig, cost=cost)
            out["strategies"].append(_fmt(res, f"TSMOM-basket {lab} {stag}"))
    # classic 12-1 (skip=21)
    sig121 = lambda c: tsmom_signal(c, lookback=252, skip=21, allow_short=True)
    out["strategies"].append(_fmt(run_basket(FX7, sig121, cost=cost), "TSMOM-basket 12-1 LS"))

    # ---- 2. Per-symbol TSMOM 12mo LS (the core hypothesis per name) ----
    for sym in FX7:
        dates, closes = aligned_closes([sym])
        c = closes[sym]
        sig = tsmom_signal(c, lookback=252, allow_short=True)
        res = run_single(c, dates, sig, cost=cost)
        out["per_symbol"][sym] = _fmt(res, f"{sym} TSMOM 12mo LS")

    # ---- 3. Benchmarks on the same path ----
    bh = run_basket_buyhold(FX7)
    out["strategies"].append(_fmt(bh, "BASKET buy-hold (long-only EW)"))

    # ---- 4. Mean-reversion (short-horizon) basket: contrarian 5d ----
    def mr5(c):
        # short the recent 5d move: position = -sign(5d past return), lookback 5
        p = tsmom_signal(c, lookback=5, skip=0, allow_short=True)
        return [-x for x in p]
    out["strategies"].append(_fmt(run_basket(FX7, mr5, cost=cost), "MR-basket 5d contrarian"))

    # ---- 5. +1-bar CANARY on the headline basket configs ----
    out["canary"]["basket_12mo_LS"] = _canary(FX7, 252, 0, True, basket=True)
    out["canary"]["basket_3mo_LS"] = _canary(FX7, 63, 0, True, basket=True)
    out["canary"]["basket_12-1_LS"] = _canary(FX7, 252, 21, True, basket=True)
    out["canary"]["MR_5d"] = (
        round(sharpe(run_basket(FX7, mr5, cost=cost).rets), 3),
        round(sharpe(run_basket(FX7, lambda c: [0.0] + mr5(c)[:-1], cost=cost).rets), 3),
    )

    # ---- 6. SPY correlation (best basket config vs SPY, same dates) ----
    best_lab = "TSMOM-basket 12mo LS"
    best = next(s for s in out["strategies"] if s["label"] == best_lab)
    spy_d, spy_r = spy_returns(set(best["_dates"]))
    a, b = align_returns_by_date(best["_dates"], best["_rets"], spy_d, spy_r)
    out["spy_corr"]["TSMOM_12mo_LS"] = {
        "corr": round(pearson_corr(a, b) or 0.0, 4), "n_overlap": len(a),
    }
    # also buyhold corr
    spy_d2, spy_r2 = spy_returns(set(bh.dates))
    a2, b2 = align_returns_by_date(bh.dates, bh.rets, spy_d2, spy_r2)
    out["spy_corr"]["BASKET_buyhold"] = {
        "corr": round(pearson_corr(a2, b2) or 0.0, 4), "n_overlap": len(a2),
    }

    # strip the heavy series before dumping
    for s in out["strategies"]:
        s.pop("_rets", None); s.pop("_dates", None)
    for k in out["per_symbol"]:
        out["per_symbol"][k].pop("_rets", None); out["per_symbol"][k].pop("_dates", None)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
