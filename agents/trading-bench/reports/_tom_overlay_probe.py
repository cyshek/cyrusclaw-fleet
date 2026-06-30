"""TOM as an OVERLAY (not flat-elsewhere): always-long base + extra tilt in TOM window.

The flat-elsewhere TOM probe LOST to B&H raw because sitting out 62-86% of the
month forfeits beta. But the data shows TOM days carry disproportionate return.
Honest overlay question: does a base-100%-long book that adds a modest extra
tilt during the TOM window (financed conceptually as higher exposure those days)
beat plain 100%-long B&H raw, net of the extra turnover cost?

We model: base exposure = 1.0 every day; during TOM window exposure = 1.0 + tilt.
Return each day = exposure * daily_ret - cost on exposure CHANGES.
This is the 'concentrate leverage where returns cluster' framing. Still honest:
no price lookahead (pure date function), cost paid on every exposure transition.

NOT a promotion. Probe to decide if the overlay framing rescues the dead flat-TOM lane.
"""
import sys
import datetime as dt
import statistics as st

from runner import daily_bars_cache as dbc


def load_adjclose(sym):
    bars = dbc.get_daily(sym)
    out = []
    for rec in bars:
        d = rec.get("date")
        px = rec.get("adjclose") or rec.get("close")
        if px is None:
            continue
        if isinstance(d, str):
            d = dt.date.fromisoformat(d[:10])
        elif isinstance(d, dt.datetime):
            d = d.date()
        out.append((d, float(px)))
    out.sort(key=lambda r: r[0])
    return out


def tom_mask(dates, pre, post):
    n = len(dates)
    mask = [False] * n
    for idx in range(n):
        d = dates[idx]
        in_pre = False
        for k in range(1, pre + 1):
            j = idx + k
            if j >= n or dates[j].month != d.month:
                in_pre = True
                break
        in_post = False
        for k in range(0, post):
            j = idx - k
            if j <= 0:
                continue
            if dates[j - 1].month != dates[j].month:
                if 0 <= idx - j < post:
                    in_post = True
                break
        mask[idx] = in_pre or in_post
    return mask


def stats(rets):
    vals = [r for _, r in rets]
    if not vals:
        return 0.0, 0.0, 0.0
    mean = sum(vals) / len(vals)
    sd = st.pstdev(vals) if len(vals) > 1 else 0.0
    ann_ret = (1.0 + mean) ** 252 - 1.0
    sh = (mean / sd * (252 ** 0.5)) if sd > 0 else 0.0
    cum = 1.0
    for v in vals:
        cum *= (1.0 + v)
    return ann_ret, sh, cum - 1.0


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    cost_bps = 2.0
    series = load_adjclose(sym)
    dates = [d for d, _ in series]
    rets = []
    for i in range(1, len(series)):
        p0 = series[i - 1][1]
        p1 = series[i][1]
        if p0 > 0:
            rets.append((dates[i], p1 / p0 - 1.0))
    print(f"{sym}: {len(series)} bars {series[0][0]}->{series[-1][0]} "
          f"({(series[-1][0]-series[0][0]).days/365.25:.1f}yr), {cost_bps}bps")

    bh_ar, bh_sh, bh_cum = stats(rets)
    print(f"\nBUY&HOLD (1.0x always): cum {bh_cum*100:+.1f}%  ann {bh_ar*100:+.2f}%  Sharpe {bh_sh:.3f}")

    print(f"\nTOM OVERLAY: base 1.0x + extra tilt in TOM window (pre=2,post=3):")
    print(f"{'tilt':>6} {'cum%':>11} {'ann%':>8} {'Sharpe':>8} {'maxlev':>7} {'switch':>7}")
    pre, post = 2, 3
    mask = tom_mask(dates, pre, post)
    for tilt in (0.25, 0.5, 1.0, 2.0):
        ov = []
        prev_exp = 1.0
        for k in range(1, len(dates)):
            exp = 1.0 + (tilt if mask[k] else 0.0)
            r = exp * rets[k - 1][1]
            if exp != prev_exp:
                r -= abs(exp - prev_exp) * cost_bps / 10000.0
            prev_exp = exp
            ov.append((dates[k], r))
        ar, sh, cum = stats(ov)
        print(f"{tilt:>6.2f} {cum*100:>10.1f}% {ar*100:>7.2f}% {sh:>8.3f} {1.0+tilt:>7.2f} {sum(1 for i in range(1,len(mask)) if mask[i]!=mask[i-1]):>7}")

    print("\nNOTE: leverage>1 implies margin/financing cost NOT modeled here (optimistic).")
    print("If even the optimistic (no-financing) overlay barely beats B&H, the lane is dead.")


if __name__ == "__main__":
    main()
