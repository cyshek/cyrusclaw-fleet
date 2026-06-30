"""TOM OVERLAY — honest version: OOS split + financing cost + +1bar canary.

The optimistic overlay (no financing) beat B&H on return AND Sharpe with Sharpe
RISING in tilt. Before believing it, apply the three lethal tests:
  1. FINANCING COST on the levered portion (the extra `tilt` exposure is borrowed):
     charge a daily financing rate on the >1.0 exposure. Use ~5%/yr (broker margin
     ballpark) as the haircut; also show 7% as stress.
  2. OOS SPLIT: IS = pre-2013, OOS = 2013+ (decorrelated from the 1993-2012 sample
     the TOM literature was built on). Edge must survive OOS.
  3. +1BAR CANARY: shift the TOM mask forward by 1 trading day. If the 'edge' is a
     real calendar effect it should DEGRADE when we tilt on the WRONG days; if it
     IMPROVES or is unchanged under the lag, it was alignment noise.

Honest construction: exposure is a pure function of the date (no price lookahead);
cost on exposure changes (2bps) + financing on borrowed exposure.
NOT a promotion. Verdict probe.
"""
import sys
import datetime as dt
import statistics as st

from runner import daily_bars_cache as dbc

COST_BPS = 2.0


def load(sym):
    out = []
    for rec in dbc.get_daily(sym):
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


def tom_mask(dates, pre, post, shift=0):
    n = len(dates)
    base = [False] * n
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
        base[idx] = in_pre or in_post
    if shift == 0:
        return base
    shifted = [False] * n
    for i in range(n):
        src = i - shift
        if 0 <= src < n:
            shifted[i] = base[src]
    return shifted


def stats(rets):
    vals = [r for _, r in rets]
    if not vals:
        return 0.0, 0.0, 0.0
    mean = sum(vals) / len(vals)
    sd = st.pstdev(vals) if len(vals) > 1 else 0.0
    ann = (1.0 + mean) ** 252 - 1.0
    sh = (mean / sd * (252 ** 0.5)) if sd > 0 else 0.0
    cum = 1.0
    for v in vals:
        cum *= (1.0 + v)
    return ann, sh, cum - 1.0


def run_overlay(dates, rets, mask, tilt, fin_apy):
    """Return list of (date, net_ret) for the overlay with financing on >1 exposure."""
    fin_daily = fin_apy / 252.0
    out = []
    prev_exp = 1.0
    for k in range(1, len(dates)):
        exp = 1.0 + (tilt if mask[k] else 0.0)
        r = exp * rets[k - 1][1]
        borrowed = max(0.0, exp - 1.0)
        r -= borrowed * fin_daily            # financing on the levered portion
        if exp != prev_exp:
            r -= abs(exp - prev_exp) * COST_BPS / 10000.0
        prev_exp = exp
        out.append((dates[k], r))
    return out


def split(rets, cut=dt.date(2013, 1, 1)):
    is_r = [(d, r) for d, r in rets if d < cut]
    oos_r = [(d, r) for d, r in rets if d >= cut]
    return is_r, oos_r


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    series = load(sym)
    dates = [d for d, _ in series]
    rets = []
    for i in range(1, len(series)):
        p0 = series[i - 1][1]
        if p0 > 0:
            rets.append((dates[i], series[i][1] / p0 - 1.0))
    print(f"{sym}: {len(series)} bars {series[0][0]}->{series[-1][0]} "
          f"({(series[-1][0]-series[0][0]).days/365.25:.1f}yr); cut=2013-01-01")

    pre, post, tilt = 2, 3, 1.0
    mask = tom_mask(dates, pre, post, shift=0)
    mask_lag = tom_mask(dates, pre, post, shift=1)

    # B&H reference per span
    def show(label, rr):
        ar, sh, cum = stats(rr)
        return f"{label:>22}: cum {cum*100:>9.1f}%  ann {ar*100:>6.2f}%  Sharpe {sh:.3f}"

    bh = [(d, r) for d, r in rets]
    is_bh, oos_bh = split(bh)
    print("\n--- BUY & HOLD (1.0x) ---")
    print(show("FULL", bh)); print(show("IS<2013", is_bh)); print(show("OOS>=2013", oos_bh))

    for fin in (0.0, 0.05, 0.07):
        ov = run_overlay(dates, rets, mask, tilt, fin)
        is_ov, oos_ov = split(ov)
        print(f"\n--- TOM OVERLAY tilt={tilt} fin={fin*100:.0f}%/yr (pre={pre},post={post}) ---")
        print(show("FULL", ov)); print(show("IS<2013", is_ov)); print(show("OOS>=2013", oos_ov))
        # canary at the realistic financing level only
        if abs(fin - 0.05) < 1e-9:
            ovc = run_overlay(dates, rets, mask_lag, tilt, fin)
            is_c, oos_c = split(ovc)
            print("   +1BAR CANARY (tilt on WRONG days):")
            print("  " + show("FULL(lag)", ovc)); print("  " + show("OOS(lag)", oos_c))
            _, sh_oos, _ = stats(oos_ov)
            _, sh_lag, _ = stats(oos_c)
            tag = ("PASS (lag degrades OOS Sharpe %.3f->%.3f)" % (sh_oos, sh_lag)
                   if sh_lag < sh_oos else
                   "FAIL (lag does NOT degrade: %.3f->%.3f = alignment noise)" % (sh_oos, sh_lag))
            print("   CANARY VERDICT:", tag)


if __name__ == "__main__":
    main()
