"""TOM mechanism diagnostics: is the in-window return ACTUALLY higher (the timing
edge), or is the overlay's outperformance purely 'more leverage = more return'?

Three skeptic checks:
  A. IN-WINDOW vs OUT-WINDOW mean daily return (the raw mechanism). If TOM days
     carry materially higher mean return at similar/lower vol, the effect is real.
     Report the t-stat on the mean-difference. Also the fraction of all calendar
     days that fall in-window (the 'concentration').
  B. WINDOW-PARAM ROBUSTNESS: sweep (pre,post) and report the in-window mean and
     the FULL margin@5% cum vs B&H. If the edge only exists at one (2,3) cell it's
     cherry-picked; if it's broad it's a real calendar band.
  C. TILT SCALING (margin@5%): does FULL cum rise monotonically and sensibly with
     tilt, and does the in-window Sharpe edge persist? (A pure-leverage artifact
     would just scale return AND drawdown together with no timing content; the
     canary already addresses this, but the in/out split is the direct evidence.)
"""
from __future__ import annotations

import datetime as dt
import statistics as st

from reports._tom_overlay_harness import (
    load, daily_returns, tom_mask, stats, overlay_margin, split2, line,
)

PRE, POST = 2, 3


def welch_t(a, b):
    """Welch t-stat for difference of means (a - b)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    ma, mb = sum(a) / na, sum(b) / nb
    va = st.pvariance(a) * na / (na - 1)
    vb = st.pvariance(b) * nb / (nb - 1)
    se = (va / na + vb / nb) ** 0.5
    return (ma - mb) / se if se > 0 else 0.0


def main():
    for sym in ("SPY", "QQQ", "^GSPC", "^NDX"):
        series = load(sym)
        dates = [d for d, _ in series]
        rets = daily_returns(series)
        mask = tom_mask(dates, PRE, POST, shift=0)
        # rets[i] corresponds to dates[i+1]; mask is on dates. align: ret on day k
        # (dates[k]) uses mask[k].
        in_r = [rets[k - 1][1] for k in range(1, len(dates)) if mask[k]]
        out_r = [rets[k - 1][1] for k in range(1, len(dates)) if not mask[k]]
        mi, mo = sum(in_r) / len(in_r), sum(out_r) / len(out_r)
        t = welch_t(in_r, out_r)
        frac = len(in_r) / (len(in_r) + len(out_r))
        # annualized mean per regime (per-day mean * 252)
        print(f"\n{'='*70}\n{sym}  (in-window days = {frac*100:.1f}% of all days)\n{'='*70}")
        print(f"  IN-window  mean/day {mi*100:+.4f}%  (~{((1+mi)**252-1)*100:+.1f}%/yr if every day)")
        print(f"  OUT-window mean/day {mo*100:+.4f}%  (~{((1+mo)**252-1)*100:+.1f}%/yr if every day)")
        print(f"  diff {(mi-mo)*100:+.4f}%/day   Welch t = {t:.2f}  "
              f"({'SIGNIFICANT' if abs(t) > 2 else 'weak'})")
        # ratio of how much of total simple return comes from in-window days
        tot_in = sum(in_r)
        tot_all = sum(r for _, r in rets)
        print(f"  in-window days deliver {tot_in/tot_all*100:.1f}% of cumulative simple return "
              f"while being {frac*100:.1f}% of days")

        # B. window-param robustness (FULL margin@5% cum vs B&H)
        _, _, bh_cum, _ = stats([(d, r) for d, r in rets])
        print("  -- window-param robustness (margin@5% FULL cum vs B&H {:.0f} pct) --".format(bh_cum*100))
        for pp in ((1, 1), (2, 2), (2, 3), (3, 3), (1, 4), (4, 1), (3, 5)):
            m = tom_mask(dates, pp[0], pp[1], shift=0)
            iw = [rets[k - 1][1] for k in range(1, len(dates)) if m[k]]
            mi2 = sum(iw) / len(iw)
            ov = overlay_margin(dates, rets, m, 1.0, 0.05)
            _, _, c, _ = stats(ov)
            beat = "BEAT" if c > bh_cum else "lose"
            print(f"     pre={pp[0]} post={pp[1]} ({len(iw)/len(rets)*100:4.1f}% days): "
                  f"in-win {mi2*100:+.4f}%/day  margin@5% cum {c*100:+9.1f}%  [{beat}]")

        # C. tilt scaling (margin@5%)
        print("  -- tilt scaling (margin@5%, pre=2,post=3) --")
        m = tom_mask(dates, PRE, POST, shift=0)
        for tilt in (0.0, 0.5, 1.0, 1.5, 2.0):
            ov = overlay_margin(dates, rets, m, tilt, 0.05)
            ar, sh, c, mdd = stats(ov)
            print(f"     tilt={tilt:>3.1f}: cum {c*100:>10.1f}%  ann {ar*100:>6.2f}%  "
                  f"Sharpe {sh:.3f}  maxDD {mdd*100:.1f}%")


if __name__ == "__main__":
    main()
