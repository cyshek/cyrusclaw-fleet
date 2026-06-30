"""Quick deep-history Turn-of-Month feasibility probe (RAW RETURN bar).

Resolves the 2026-06-04 seasonality REJECT's explicit data-depth caveat (§7):
that test ran on ~5.8yr of IEX data and flagged low-frequency calendar modes as
underpowered. daily_bars_cache uses Yahoo v8 (deep history to inception), so we
now have ~30yr SPY. Question: does TOM timing beat raw buy-and-hold over 30yr?

NOT a promotion. Cheap probe to decide whether a full harness is worth building.
"""
import sys
import datetime as dt

from runner import daily_bars_cache as dbc


def load_adjclose(sym):
    """Return sorted list of (date, adjclose) from the full daily-bar list."""
    bars = dbc.get_daily(sym)
    out = []
    for rec in bars:
        d = rec.get("date")
        px = rec.get("adjclose")
        if px is None:
            px = rec.get("close")
        if px is None:
            continue
        if isinstance(d, str):
            d = dt.date.fromisoformat(d[:10])
        elif isinstance(d, dt.datetime):
            d = d.date()
        out.append((d, float(px)))
    out.sort(key=lambda r: r[0])
    return out


def daily_returns(series):
    rets = []
    for i in range(1, len(series)):
        d0, p0 = series[i - 1]
        d1, p1 = series[i]
        if p0 > 0:
            rets.append((d1, p1 / p0 - 1.0))
    return rets


def is_tom_day(idx, dates, pre=1, post=3):
    """TOM window = last `pre` trading days of month + first `post` of next.

    Decide membership of trading day at position idx by looking at calendar
    month boundaries in the trading-day sequence (no price lookahead — pure
    date function).
    """
    d = dates[idx]
    # last `pre` trading days of THIS month: next `pre` entries cross into next month
    last_of_month = (idx + 1 >= len(dates)) or (dates[idx + 1].month != d.month)
    in_pre = False
    for k in range(1, pre + 1):
        j = idx + k
        if j >= len(dates):
            in_pre = True
            break
        if dates[j].month != d.month:
            in_pre = True
            break
    # first `post` trading days of month: previous `post` entries were prior month
    in_post = False
    for k in range(0, post):
        j = idx - k
        if j <= 0:
            continue
        if dates[j - 1].month != dates[j].month:
            # dates[j] is a first-of-month; idx is within post window if idx-j < post
            if 0 <= idx - j < post:
                in_post = True
            break
    return in_pre or in_post


def ann_stats(rets):
    import statistics as st
    if not rets:
        return 0.0, 0.0, 0.0
    vals = [r for _, r in rets]
    mean = sum(vals) / len(vals)
    sd = st.pstdev(vals) if len(vals) > 1 else 0.0
    ann_ret = (1.0 + mean) ** 252 - 1.0
    ann_sharpe = (mean / sd * (252 ** 0.5)) if sd > 0 else 0.0
    # cumulative
    cum = 1.0
    for v in vals:
        cum *= (1.0 + v)
    return ann_ret, ann_sharpe, cum - 1.0


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    cost_bps = 2.0
    series = load_adjclose(sym)
    print(f"{sym}: {len(series)} daily bars, {series[0][0]} -> {series[-1][0]} "
          f"({(series[-1][0]-series[0][0]).days/365.25:.1f}yr)")
    rets = daily_returns(series)
    dates = [d for d, _ in series]

    # Buy-and-hold raw
    bh_ar, bh_sh, bh_cum = ann_stats(rets)
    print(f"\nBUY&HOLD raw: cum {bh_cum*100:+.1f}%  ann {bh_ar*100:+.2f}%  Sharpe {bh_sh:.3f}")

    print(f"\nTOM timing (long only in TOM window, flat else), {cost_bps}bps one-way:")
    print(f"{'pre,post':>10} {'cum%':>10} {'ann%':>8} {'Sharpe':>8} {'days_in':>8} {'%exposed':>9} {'switches':>9}")
    best = None
    for pre in (1, 2, 3):
        for post in (1, 2, 3, 4):
            mask = [is_tom_day(i, dates, pre, post) for i in range(len(dates))]
            # map mask to return days: return at position k corresponds to dates[k+1]
            tom_rets = []
            switches = 0
            prev_in = False
            for k in range(1, len(dates)):
                in_win = mask[k]  # hold decided by today's date, earn today's ret vs yesterday
                r = 0.0
                # find ret for this date
                # rets is aligned: rets[k-1] = (dates[k], ret)
                _, rr = rets[k - 1]
                if in_win:
                    r = rr
                if in_win != prev_in:
                    switches += 1
                    r -= cost_bps / 10000.0  # pay cost on transition
                prev_in = in_win
                tom_rets.append((dates[k], r))
            ar, sh, cum = ann_stats(tom_rets)
            exposed = sum(1 for _, r in tom_rets if r != 0.0) / len(tom_rets)
            days_in = sum(mask)
            row = (pre, post, cum, ar, sh, days_in, exposed, switches)
            print(f"{pre},{post:>8} {cum*100:>9.1f}% {ar*100:>7.2f}% {sh:>8.3f} "
                  f"{days_in:>8} {exposed*100:>8.1f}% {switches:>9}")
            if best is None or cum > best[2]:
                best = row
    print(f"\nBEST TOM by raw cum: pre={best[0]},post={best[1]} cum {best[2]*100:+.1f}% "
          f"ann {best[3]*100:+.2f}% Sharpe {best[4]:.3f}")
    print(f"vs BUY&HOLD cum {bh_cum*100:+.1f}% ann {bh_ar*100:+.2f}% Sharpe {bh_sh:.3f}")
    verdict = "BEATS B&H raw" if best[2] > bh_cum else "LOSES to B&H raw"
    print(f"VERDICT (raw return bar): TOM {verdict}")


if __name__ == "__main__":
    main()
