"""Standalone relabel-guard diagnostic — RUN FIRST, decides everything.

Computes, over the aligned common dates of the breadth panel vs SPY:
  corr(breadth_z, SPY trailing realized vol)
  corr(breadth_z, SPY trailing return / momentum)
  corr(breadth_z, SPY forward 1-day return)   [does it lead? informational]

For EACH breadth_mode candidate and a couple of z_lookbacks. If |corr| to vol
OR momentum is high, breadth is a relabel of an already-dead lane -> RELABEL.

import-only; composes the candidate's PUBLIC breadth functions + bars_cache.
No protected edits. No backtest here — pure signal diagnostics.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner import bars_cache  # noqa: E402

CDIR = WS / "strategies_candidates" / "breadth_internals"
spec = importlib.util.spec_from_file_location("cand_breadth", str(CDIR / "strategy.py"))
B = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = B
spec.loader.exec_module(B)


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spy_closes_by_date():
    bars = bars_cache.get_bars("SPY", "1Day", days=3000) or []
    return [(str(b["t"])[:10], float(b["c"])) for b in bars if float(b.get("c", 0)) > 0]


def realized_vol(closes, lookback):
    if len(closes) < lookback + 1:
        return None
    w = closes[-(lookback + 1):]
    rets = []
    for i in range(1, len(w)):
        if w[i - 1] > 0 and w[i] > 0:
            rets.append(math.log(w[i] / w[i - 1]))
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252.0) if var >= 0 else None


def trailing_return(closes, lookback):
    if len(closes) < lookback + 1:
        return None
    c0 = closes[-(lookback + 1)]
    c1 = closes[-1]
    return (c1 / c0 - 1.0) if c0 > 0 else None


def main():
    spy = spy_closes_by_date()
    spy_dates = [d for d, _ in spy]
    spy_close = {d: c for d, c in spy}
    spy_idx = {d: i for i, d in enumerate(spy_dates)}
    spy_vals = [c for _, c in spy]

    VOL_LB = 20      # SPY trailing realized vol lookback (the vol-level relabel)
    MOM_LB = 20      # SPY trailing return lookback (the momentum relabel)

    results = {}
    configs = [
        {"breadth_mode": "pct_above_50sma", "sma_len": 50, "z_lookback": 60},
        {"breadth_mode": "pct_above_50sma", "sma_len": 50, "z_lookback": 120},
        {"breadth_mode": "pct_above_200sma", "sma_len": 200, "z_lookback": 60},
        {"breadth_mode": "pct_above_200sma", "sma_len": 200, "z_lookback": 120},
        {"breadth_mode": "ad_line", "ad_slope_lb": 10, "z_lookback": 60},
        {"breadth_mode": "ad_line", "ad_slope_lb": 20, "z_lookback": 120},
    ]

    for cfg in configs:
        params = dict(cfg)
        series = B._breadth_series(params)
        # Build aligned arrays over SPY dates where breadth_z, vol, mom all exist.
        bz, vv, mm, fwd = [], [], [], []
        raw_level = []
        for d in spy_dates:
            if d not in series and params["breadth_mode"] != "ad_line":
                # pct modes: series keyed by universe dates; require presence
                pass
            z = B._zscore_at(series, d, params)
            if z is None:
                continue
            i = spy_idx[d]
            closes_upto = spy_vals[: i + 1]
            rv = realized_vol(closes_upto, VOL_LB)
            tr = trailing_return(closes_upto, MOM_LB)
            if rv is None or tr is None:
                continue
            # forward 1-day SPY return (informational lead check)
            f = None
            if i + 1 < len(spy_vals) and spy_vals[i] > 0:
                f = spy_vals[i + 1] / spy_vals[i] - 1.0
            bz.append(z)
            vv.append(rv)
            mm.append(tr)
            raw_level.append(series.get(d))
            fwd.append(f)
        c_vol = pearson(bz, vv)
        c_mom = pearson(bz, mm)
        # forward-return corr over rows where fwd exists
        bz_f = [z for z, ff in zip(bz, fwd) if ff is not None]
        ff_f = [ff for ff in fwd if ff is not None]
        c_fwd = pearson(bz_f, ff_f)
        label = f"{cfg['breadth_mode']}/z{cfg['z_lookback']}"
        results[label] = {
            "n_aligned": len(bz),
            "corr_breadthz_vol": None if c_vol is None else round(c_vol, 3),
            "corr_breadthz_mom": None if c_mom is None else round(c_mom, 3),
            "corr_breadthz_fwd1d": None if c_fwd is None else round(c_fwd, 4),
            "first_date": spy_dates[spy_idx[min(spy_dates, key=lambda d: spy_idx[d] if (B._zscore_at(series, d, params) is not None) else 10**9)]] if bz else None,
        }
        print(f"{label:28s} n={len(bz):4d} "
              f"corr_vol={results[label]['corr_breadthz_vol']!s:>7} "
              f"corr_mom={results[label]['corr_breadthz_mom']!s:>7} "
              f"corr_fwd1d={results[label]['corr_breadthz_fwd1d']!s:>8}")

    (WS / "reports" / "_breadth_relabel_corrs.json").write_text(
        json.dumps(results, indent=2, default=str))
    print("\nwrote reports/_breadth_relabel_corrs.json")
    print("\nRELABEL RULE: |corr_vol| or |corr_mom| high (>~0.5) => relabel of a "
          "dead lane => RELABEL-REJECT. Low to BOTH => breadth is orthogonal, "
          "earns a real backtest.")


if __name__ == "__main__":
    main()
