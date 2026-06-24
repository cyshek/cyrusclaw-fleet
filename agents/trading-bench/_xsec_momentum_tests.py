#!/usr/bin/env python3
"""
Cross-sectional MOMENTUM (Jegadeesh-Titman) kill-test — single-name 104-survivor universe.

J-T (JF 1993): stocks ranked by trailing return persist over 3-12mo horizons. The canonical
academic formation is "12-1 momentum": cumulative return over the trailing 12 months SKIPPING
the most recent 1 month (return from t-12mo to t-1mo), to avoid the well-documented 1-month
short-term reversal. Long the top quintile, short the bottom quintile, equal-weight, monthly
rebalance. Also runs the 6-1 variant (trailing 6mo skip-1) as a robustness check.

HONESTY RAILS (bench standing rules — see MEMORY.md CROSS-SEC FACTOR GATE):
- Signal from PAST-ONLY data, strictly BEFORE the formation date (prior month-end). The skip-1
  month is itself a lookahead guard (the most recent month is excluded from the signal).
- Rank at prior-month-end close; trade the FOLLOWING month. Lookahead canary asserts no peek
  (a cheat variant that INCLUDES the formation/most-recent month must score differently).
- SPY traded on the SAME daily path. FULL continuous-span Sharpe (252d), never median-of-windows.
- 2bps one-way cost + breakeven-bps + turnover computed up front.
- Survivorship: the 104 universe is TODAY's survivors (biased UP). The decisive honest tests are
  (a) the market-neutral L/S spread (survivorship-neutral by construction), reported FIRST, and
  (b) the long-only top-quintile sleeve must beat a no-signal EW-104 hold of its OWN universe,
  OOS net of cost — not merely beat SPY.
- A clean negative is an acceptable, valuable result. Do NOT manufacture a win.

Mirrors machinery from _bab_killtest_tests.py (load_px, month_starts, sharpe/cagr/maxdd/
ann_vol/total_return, breakeven_bps, killer-window slicing, EW-104 control, lookahead canary).
Imports runner/lane_honesty.py for the standing survivorship + OOS-mirage guards.
"""
import os, json, math, bisect, datetime

# import the shared honesty guards (READ-ONLY import of a protected file is allowed)
from runner.lane_honesty import survivorship_verdict, assert_lane_honest, oos_mirage_verdict

WS = os.path.dirname(os.path.abspath(__file__))
YAHOO = os.path.join(WS, "data_cache", "yahoo", "%s_parsed.json")
UNIV_PATH = os.path.join(WS, "data_cache", "edgar_fundamentals", "universe.json")
OUT_JSON = os.path.join(WS, "reports", "_xsec_momentum_result.json")

TRADING_DAYS = 252.0
OOS_SPLIT = "2019-12-31"        # main's spec: IS <=2019-12-31, OOS 2020-01-01+
OOS_SPLIT_ALT = "2018-12-31"    # also report for continuity (like BAB)
START = "2006-01-01"            # matches BAB; 94/104 names available, 252d warmup fine
COST_BPS = 2.0

# ----------------------------- data loading (mirror BAB) -----------------------------
def load_px(sym):
    path = YAHOO % sym
    if not os.path.exists(path):
        return {}
    rows = json.load(open(path))
    out = {}
    for r in rows:
        ac = r.get("adjclose")
        if ac not in (None, 0):
            out[r["date"]] = float(ac)
    return out

def month_starts(dates):
    seen = set(); idx = []
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym); idx.append(i)
    return idx

def quarter_starts(dates):
    seen = set(); idx = []
    for i, d in enumerate(dates):
        y = d[:4]; m = int(d[5:7]); q = (m - 1) // 3 + 1
        if (y, q) not in seen:
            seen.add((y, q)); idx.append(i)
    return idx

# ----------------------------- return series builder (mirror) -----------------------------
def build_daily_returns(px, dates_sorted):
    rets = {}
    for i in range(1, len(dates_sorted)):
        d0 = dates_sorted[i - 1]; d1 = dates_sorted[i]
        p0 = px[d0]; p1 = px[d1]
        if p0 and p0 > 0:
            rets[d1] = p1 / p0 - 1.0
    return rets

# ----------------------------- MOMENTUM signal (PAST-ONLY, skip-1) -----------------------------
def _shift_months(date_str, months_back):
    """Return an ISO date string `months_back` calendar months before date_str (day clamped)."""
    y = int(date_str[:4]); m = int(date_str[5:7]); d = int(date_str[8:10])
    total = (y * 12 + (m - 1)) - months_back
    ny = total // 12; nm = total % 12 + 1
    if nm == 12:
        nxt = datetime.date(ny + 1, 1, 1)
    else:
        nxt = datetime.date(ny, nm + 1, 1)
    last_day = (nxt - datetime.timedelta(days=1)).day
    nd = min(d, last_day)
    return "%04d-%02d-%02d" % (ny, nm, nd)

def _price_asof(px, sorted_dates, target_date):
    """Last available adjclose on or before target_date (strictly using cached data)."""
    j = bisect.bisect_right(sorted_dates, target_date) - 1
    if j < 0:
        return None
    return px[sorted_dates[j]]

def momentum_signal(px, sorted_dates, asof, lookback_m=12, skip_m=1):
    """
    12-1 (or 6-1) momentum measured STRICTLY BEFORE `asof`.

    formation point = last trading day on/before (asof - skip_m months)     [t-1mo]
    start point     = last trading day on/before (asof - lookback_m months)  [t-12mo]
    signal = formation_price / start_price - 1   (cumulative return t-12mo -> t-1mo)

    The most recent `skip_m` months are excluded; `asof` is the prior-month-end at which we
    rank, and we trade the FOLLOWING month. Signal uses only data dated <= (asof - skip_m
    months) < asof. No peek at the formation month or the traded month.
    """
    d_form = _shift_months(asof, skip_m)        # end of measurement window (skip most-recent)
    d_start = _shift_months(asof, lookback_m)   # start of measurement window
    p_form = _price_asof(px, sorted_dates, d_form)
    p_start = _price_asof(px, sorted_dates, d_start)
    if p_form is None or p_start is None or p_start <= 0:
        return None
    return p_form / p_start - 1.0

def momentum_signal_cheat(px, sorted_dates, asof, lookback_m=12, skip_m=1):
    """
    LOOKAHEAD CANARY (deliberate cheat): peek ~1 month FORWARD of the rank date so the signal
    includes the about-to-be-traded month. Must score MEASURABLY differently from the honest
    path; if identical, the honest path is leaking.
    """
    d_form = _shift_months(asof, -1)            # peek 1 month FORWARD of the rank date
    d_start = _shift_months(asof, lookback_m)
    p_form = _price_asof(px, sorted_dates, d_form)
    p_start = _price_asof(px, sorted_dates, d_start)
    if p_form is None or p_start is None or p_start <= 0:
        return None
    return p_form / p_start - 1.0

# ----------------------------- bucket return helper (mirror) -----------------------------
def bucket_ret(names, adj_px, d_prev, d_now):
    if not names:
        return 0.0, 0
    rs = []
    for t in names:
        px = adj_px.get(t, {})
        p0 = px.get(d_prev); p1 = px.get(d_now)
        if p0 and p1 and p0 > 0:
            rs.append(p1 / p0 - 1.0)
    if not rs:
        return 0.0, 0
    return sum(rs) / len(rs), len(rs)

# ----------------------------- stats (mirror BAB exactly) -----------------------------
def sharpe(rets):
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)

def cagr(rets):
    if not rets:
        return 0.0
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    yrs = len(rets) / TRADING_DAYS
    if yrs <= 0 or eq <= 0:
        return 0.0
    return (eq ** (1.0 / yrs) - 1.0) * 100.0

def total_return(rets):
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return (eq - 1.0) * 100.0

def maxdd(rets):
    eq = 1.0; peak = 1.0; mdd = 0.0
    for r in rets:
        eq *= (1.0 + r)
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak
        if dd < mdd:
            mdd = dd
    return mdd * 100.0

def ann_vol(rets):
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS) * 100.0

def stat_block(rets):
    return {"n": len(rets), "sharpe": round(sharpe(rets), 3), "cagr_pct": round(cagr(rets), 2),
            "maxdd_pct": round(maxdd(rets), 2), "total_return_pct": round(total_return(rets), 1),
            "ann_vol_pct": round(ann_vol(rets), 2)}

def slice_rets(dates, rets, start, end):
    sd = []; sr = []
    for d, r in zip(dates, rets):
        if start <= d < end:
            sd.append(d); sr.append(r)
    return sd, sr

def breakeven_bps(gross_rets, turnovers_sum):
    if turnovers_sum <= 0:
        return 0.0
    eq = 1.0
    for r in gross_rets:
        eq *= (1.0 + r)
    gross_total = eq - 1.0
    return (gross_total / turnovers_sum) * 10000.0

KILLER_WINDOWS = [
    ("2008-09 GFC crash",     "2008-09-01", "2009-04-01"),
    ("2009 junk-rally",       "2009-03-01", "2009-09-01"),
    ("2011 debt-ceiling",     "2011-07-01", "2011-10-01"),
    ("2018-Q4 selloff",       "2018-10-01", "2019-01-01"),
    ("2020-Q1 covid crash",   "2020-02-01", "2020-04-01"),
    ("2020-21 high-beta melt","2020-04-01", "2021-04-01"),
    ("2022 bear (full yr)",   "2022-01-01", "2023-01-01"),
    ("2022-H1 bear",          "2022-01-01", "2022-07-01"),
    ("2023-H1 recovery",      "2023-01-01", "2023-07-01"),
    ("2025-Q1 tariff bear",   "2025-02-01", "2025-05-01"),
]

# ----------------------------- core backtest -----------------------------
def run_momentum(univ, adj_px, name_dates, spy_dates, spy_px,
                 lookback_m=12, skip_m=1, bucket=0.2, cadence="M",
                 cost_bps=COST_BPS, start=START, mode="ls", cheat=False):
    """
    mode: 'ls'   -> dollar-neutral long-top-quintile / short-bottom-quintile (canonical J-T)
          'long' -> long-only top-quintile sleeve (for the SPY/EW comparison)
    bucket: fraction per basket (0.2 quintile).
    cheat:  if True, use momentum_signal_cheat (peeks ~1mo forward) — lookahead canary.

    Rank at prior-month-end (asof = rebalance calendar date; signal strictly < asof via skip-1),
    trade the FOLLOWING month. Returns dict with daily net/gross strat ret, SPY path on the same
    calendar, turnover info, signal diagnostics.
    """
    cal = [d for d in spy_dates if d >= start]
    if not cal:
        return None
    rb_idx = month_starts(cal) if cadence == "M" else quarter_starts(cal)
    rb_set = set(rb_idx)
    sigfn = momentum_signal_cheat if cheat else momentum_signal

    spy_path = [0.0]
    for i in range(1, len(cal)):
        p0 = spy_px.get(cal[i - 1]); p1 = spy_px.get(cal[i])
        spy_path.append((p1 / p0 - 1.0) if (p0 and p1 and p0 > 0) else 0.0)

    cur_top = []; cur_bot = []
    strat_net = [0.0]; strat_gross = [0.0]
    turnovers = []; rebal_log = []; prev_set = set()
    sig_top_log = []; sig_bot_log = []; n_univ_log = []

    for i in range(len(cal)):
        d = cal[i]
        if i in rb_set:
            asof = d
            sigs = {}
            for t in univ:
                s = sigfn(adj_px[t], name_dates[t], asof, lookback_m, skip_m)
                if s is not None:
                    sigs[t] = s
            ranked = sorted(sigs.items(), key=lambda kv: kv[1])  # ascending: losers first
            m = len(ranked)
            if m >= 10:
                k = max(1, int(round(m * bucket)))
                bot = [t for t, _ in ranked[:k]]      # lowest momentum (losers) -> short
                top = [t for t, _ in ranked[-k:]]     # highest momentum (winners) -> long
                avg_top = sum(sigs[t] for t in top) / len(top)
                avg_bot = sum(sigs[t] for t in bot) / len(bot)
                sig_top_log.append(avg_top); sig_bot_log.append(avg_bot); n_univ_log.append(m)
                if mode == "ls":
                    new_set = set("L__" + x for x in top) | set("S__" + x for x in bot)
                else:
                    new_set = set("L__" + x for x in top)
                if prev_set:
                    changed = len(new_set.symmetric_difference(prev_set))
                    denom = max(1, len(new_set) + len(prev_set))
                    turn = changed / denom
                else:
                    turn = 1.0
                turnovers.append(turn)
                cur_top = top; cur_bot = bot; prev_set = new_set
                cost = (cost_bps / 10000.0) * turn
                strat_net[-1] = strat_net[-1] - cost
                rebal_log.append({"date": d, "n_top": len(top), "n_bot": len(bot),
                                  "sig_top": round(avg_top, 4), "sig_bot": round(avg_bot, 4),
                                  "turnover": round(turn, 4)})
        if i == 0:
            continue
        rt, nt = bucket_ret(cur_top, adj_px, cal[i - 1], d)
        if mode == "ls" and cur_bot:
            rb, nb = bucket_ret(cur_bot, adj_px, cal[i - 1], d)
            day = rt - rb            # dollar-neutral: +1 long winners, -1 short losers
        else:
            day = rt
        strat_gross.append(day)
        strat_net.append(day)

    avg_turn = sum(turnovers) / len(turnovers) if turnovers else 0.0
    return {"dates": cal, "strat_ret": strat_net, "strat_gross": strat_gross,
            "spy_ret": spy_path, "turnovers": turnovers, "turnover_sum": sum(turnovers),
            "avg_turnover": avg_turn, "n_rebal": len(turnovers), "rebal_log": rebal_log,
            "avg_sig_top": (sum(sig_top_log) / len(sig_top_log)) if sig_top_log else None,
            "avg_sig_bot": (sum(sig_bot_log) / len(sig_bot_log)) if sig_bot_log else None,
            "avg_n_univ": (sum(n_univ_log) / len(n_univ_log)) if n_univ_log else 0}

def run_ew_control(univ, adj_px, spy_dates, start=START, cost_bps=COST_BPS, cadence="M"):
    """No-signal equal-weight hold of the SAME universe (MANDATORY survivorship control)."""
    cal = [d for d in spy_dates if d >= start]
    rb_idx = month_starts(cal) if cadence == "M" else quarter_starts(cal)
    rb_set = set(rb_idx)
    strat = [0.0]; turnovers = []; prev = set(); cur = []
    for i in range(len(cal)):
        d = cal[i]
        if i in rb_set:
            avail = [t for t in univ if d in adj_px.get(t, {})]
            new = set(avail)
            if prev:
                changed = len(new.symmetric_difference(prev)); denom = max(1, len(new) + len(prev))
                turn = changed / denom
            else:
                turn = 1.0
            turnovers.append(turn)
            cur = avail; prev = new
            strat[-1] = strat[-1] - (cost_bps / 10000.0) * turn
        if i == 0:
            continue
        r, _ = bucket_ret(cur, adj_px, cal[i - 1], d)
        strat.append(r)
    return {"dates": cal, "strat_ret": strat, "turnover_sum": sum(turnovers),
            "avg_turnover": sum(turnovers) / len(turnovers) if turnovers else 0.0,
            "n_rebal": len(turnovers)}

# ----------------------------- IS/OOS slicing helper -----------------------------
def series_stats(dts, rets):
    _, is_r = slice_rets(dts, rets, START, "2020-01-01")          # IS <= 2019-12-31
    _, oos_r = slice_rets(dts, rets, "2020-01-01", "2099-01-01")
    _, is_alt_r = slice_rets(dts, rets, START, "2019-01-01")      # alt IS <= 2018-12-31
    _, oos_alt_r = slice_rets(dts, rets, "2019-01-01", "2099-01-01")
    return {
        "full": stat_block(rets),
        "is_2019": (stat_block(is_r) if len(is_r) >= 20 else {"n": len(is_r)}),
        "oos_2020": (stat_block(oos_r) if len(oos_r) >= 20 else {"n": len(oos_r)}),
        "is_2018alt": (stat_block(is_alt_r) if len(is_alt_r) >= 20 else {"n": len(is_alt_r)}),
        "oos_2019alt": (stat_block(oos_alt_r) if len(oos_alt_r) >= 20 else {"n": len(oos_alt_r)}),
    }

def oos_split_index(dates, split_first_oos="2020-01-01"):
    """First index whose date >= split_first_oos (for lane_honesty slicing)."""
    for i, d in enumerate(dates):
        if d >= split_first_oos:
            return i
    return len(dates)

# ----------------------------- main -----------------------------
def main():
    univ = json.load(open(UNIV_PATH))["tickers"]
    spy_px = load_px("SPY")
    spy_dates = sorted(spy_px.keys())

    adj_px = {}; name_dates = {}
    for t in univ:
        px = load_px(t)
        if not px:
            continue
        adj_px[t] = px
        name_dates[t] = sorted(px.keys())
    univ = [t for t in univ if t in adj_px]
    print("universe with prices:", len(univ))

    result = {"meta": {
        "test": "Cross-sectional MOMENTUM (Jegadeesh-Titman) kill-test",
        "universe_n": len(univ),
        "universe_note": ("104-name S&P100-ish; TODAY's survivors (survivorship-biased UP). "
                          "The L/S spread (survivorship-neutral by construction) + the mandatory "
                          "EW-104 control are the honest defenses."),
        "start": START, "oos_split": OOS_SPLIT, "oos_split_alt": OOS_SPLIT_ALT,
        "cost_bps_oneway": COST_BPS, "trading_days": TRADING_DAYS,
        "signal": ("12-1 momentum = cum return t-12mo->t-1mo (skip most recent month); also 6-1. "
                   "Ranked at prior-month-end, trade following month. PAST-ONLY (skip-1 + asof excl)."),
    }}

    series = {}
    cost_analysis = {}

    # --- EW-104 no-signal control (same for both formations) ---
    print("running EW-104 no-signal control ...")
    ew = run_ew_control(univ, adj_px, spy_dates, start=START)
    ew_dates = ew["dates"]; ew_rets = ew["strat_ret"]
    series["ew_control"] = {
        "stats": series_stats(ew_dates, ew_rets),
        "avg_turnover": round(ew["avg_turnover"], 4), "n_rebal": ew["n_rebal"],
    }

    # --- run both formations: 12-1 (primary) and 6-1 (robustness) ---
    runs = {}   # key -> dict(ls=..., lo=...)
    for key, lb in (("mom_12_1", 12), ("mom_6_1", 6)):
        print("running %s L/S (quintile, monthly) ..." % key)
        ls = run_momentum(univ, adj_px, name_dates, spy_dates, spy_px,
                          lookback_m=lb, skip_m=1, bucket=0.2, cadence="M", mode="ls")
        print("running %s long-only top-quintile (monthly) ..." % key)
        lo = run_momentum(univ, adj_px, name_dates, spy_dates, spy_px,
                          lookback_m=lb, skip_m=1, bucket=0.2, cadence="M", mode="long")
        runs[key] = {"ls": ls, "lo": lo, "lookback": lb}

    # SPY path + calendar from the primary 12-1 L/S run (identical across runs)
    prim = runs["mom_12_1"]["ls"]
    dates = prim["dates"]
    spy_series = prim["spy_ret"]
    series["spy"] = {"stats": series_stats(dates, spy_series)}

    for key in ("mom_12_1", "mom_6_1"):
        ls = runs[key]["ls"]; lo = runs[key]["lo"]
        series[key + "_ls"] = {
            "stats": series_stats(ls["dates"], ls["strat_ret"]),
            "avg_turnover": round(ls["avg_turnover"], 4),
            "turnover_sum": round(ls["turnover_sum"], 2),
            "n_rebal": ls["n_rebal"],
            "avg_sig_top": round(ls["avg_sig_top"], 4) if ls["avg_sig_top"] is not None else None,
            "avg_sig_bot": round(ls["avg_sig_bot"], 4) if ls["avg_sig_bot"] is not None else None,
            "avg_n_univ": round(ls["avg_n_univ"], 1),
        }
        series[key + "_long"] = {
            "stats": series_stats(lo["dates"], lo["strat_ret"]),
            "avg_turnover": round(lo["avg_turnover"], 4),
            "turnover_sum": round(lo["turnover_sum"], 2),
            "n_rebal": lo["n_rebal"],
        }
        # breakeven + turnover up front (gross)
        be_ls = breakeven_bps(ls["strat_gross"], ls["turnover_sum"])
        be_lo = breakeven_bps(lo["strat_gross"], lo["turnover_sum"])
        cost_analysis[key + "_ls"] = {
            "avg_turnover_per_rebal_pct": round(ls["avg_turnover"] * 100, 1),
            "turnover_sum": round(ls["turnover_sum"], 2),
            "breakeven_bps_oneway": round(be_ls, 1),
            "cost_bps_charged": COST_BPS,
            "comfortably_above_cost": bool(be_ls > 5 * COST_BPS),
        }
        cost_analysis[key + "_long"] = {
            "avg_turnover_per_rebal_pct": round(lo["avg_turnover"] * 100, 1),
            "turnover_sum": round(lo["turnover_sum"], 2),
            "breakeven_bps_oneway": round(be_lo, 1),
            "cost_bps_charged": COST_BPS,
        }

    result["series"] = series
    result["cost_analysis"] = cost_analysis

    # --- lookahead canary: honest 12-1 L/S vs cheating (forward-peek) path must DIFFER ---
    print("running lookahead canary (forward-peek momentum) ...")
    ls_cheat = run_momentum(univ, adj_px, name_dates, spy_dates, spy_px,
                            lookback_m=12, skip_m=1, bucket=0.2, cadence="M",
                            mode="ls", cheat=True)
    sh_honest = sharpe(prim["strat_ret"])
    sh_cheat = sharpe(ls_cheat["strat_ret"])
    result["lookahead_canary"] = {
        "honest_full_sharpe": round(sh_honest, 3),
        "cheat_forward_peek_full_sharpe": round(sh_cheat, 3),
        "paths_differ": bool(abs(sh_honest - sh_cheat) > 1e-6),
        "honest_lt_cheat": bool(sh_honest < sh_cheat),
        "note": ("Honest path ranks on past-only 12-1 (skip-1) at month-end, trades forward. "
                 "Cheat path peeks ~1mo forward (includes the traded month). If identical, "
                 "leakage suspected; honest should be < cheat."),
    }

    # --- lane_honesty guards on the PRIMARY 12-1 (signal=long-only, ls_spread=L/S) ---
    split_i = oos_split_index(dates, "2020-01-01")
    lo12 = runs["mom_12_1"]["lo"]; ls12 = runs["mom_12_1"]["ls"]
    # align EW control to the same calendar length as the strat (they share SPY calendar+start)
    sv = survivorship_verdict(
        signal_daily=lo12["strat_ret"],
        ew_control_daily=ew_rets,
        oos_split_index=split_i,
        ls_spread_daily=ls12["strat_ret"],
    )
    lane = assert_lane_honest(
        signal_daily=lo12["strat_ret"],
        oos_split_index=split_i,
        ew_control_daily=ew_rets,
        ls_spread_daily=ls12["strat_ret"],
    )
    mir = oos_mirage_verdict(ls12["strat_ret"], split_i)
    result["lane_honesty"] = {
        "survivorship_summary": sv.summary(),
        "survivorship_passed": sv.passed,
        "lane_summary": lane.summary(),
        "lane_passed": lane.passed,
        "lane_failures": lane.failures,
        "oos_mirage_summary_on_ls": mir.summary(),
    }

    # --- killer battery on L/S, long-only, EW, SPY (12-1 primary) ---
    kb = []
    for name, s, e in KILLER_WINDOWS:
        _, lr = slice_rets(dates, ls12["strat_ret"], s, e)
        _, lor = slice_rets(dates, lo12["strat_ret"], s, e)
        _, ewr = slice_rets(ew_dates, ew_rets, s, e)
        _, sr = slice_rets(dates, spy_series, s, e)
        row = {"window": name, "start": s, "end": e, "n": len(lr)}
        if len(lr) >= 5:
            row["ls_total_pct"] = round(total_return(lr), 2)
            row["ls_sharpe"] = round(sharpe(lr), 2)
            row["long_total_pct"] = round(total_return(lor), 2)
            row["ew_total_pct"] = round(total_return(ewr), 2)
            row["spy_total_pct"] = round(total_return(sr), 2)
            row["ls_minus_spy_pct"] = round(total_return(lr) - total_return(sr), 2)
        kb.append(row)
    result["killer_battery"] = kb

    # --- robustness sweep (lookback x bucket x cadence) on L/S ---
    print("running robustness sweep ...")
    sweep = []
    configs = []
    for lb in (6, 9, 12):
        for bucket in (0.2, 0.3333):
            for cadence in ("M", "Q"):
                configs.append((lb, bucket, cadence))
    for (lb, bucket, cadence) in configs:
        r = run_momentum(univ, adj_px, name_dates, spy_dates, spy_px,
                         lookback_m=lb, skip_m=1, bucket=bucket, cadence=cadence, mode="ls")
        if not r:
            continue
        d2 = r["dates"]; rr = r["strat_ret"]
        _, oos_r = slice_rets(d2, rr, "2020-01-01", "2099-01-01")
        _, is_r = slice_rets(d2, rr, START, "2020-01-01")
        sweep.append({
            "lookback_m": lb, "skip_m": 1, "bucket": round(bucket, 3), "cadence": cadence,
            "full_sharpe": round(sharpe(rr), 3),
            "is_sharpe": round(sharpe(is_r), 3) if len(is_r) >= 20 else None,
            "oos_sharpe": round(sharpe(oos_r), 3) if len(oos_r) >= 20 else None,
            "oos_total_pct": round(total_return(oos_r), 1) if len(oos_r) >= 20 else None,
            "full_cagr_pct": round(cagr(rr), 2),
            "avg_turnover_pct": round(r["avg_turnover"] * 100, 1),
        })
    result["robustness_sweep"] = sweep

    # --- VERDICT (4 criteria, evaluated on OOS = 2020+, on the L/S spread) for 12-1 ---
    def verdict_for(key):
        ls_oos = series[key + "_ls"]["stats"]["oos_2020"]
        lo_oos = series[key + "_long"]["stats"]["oos_2020"]
        ew_oos = series["ew_control"]["stats"]["oos_2020"]
        spy_oos = series["spy"]["stats"]["oos_2020"]
        ls_oos_sharpe = ls_oos.get("sharpe", 0.0)
        ls_oos_ret = ls_oos.get("total_return_pct", -999.0)
        ew_oos_ret = ew_oos.get("total_return_pct", -999.0)
        spy_oos_ret = spy_oos.get("total_return_pct", -999.0)
        lo_oos_ret = lo_oos.get("total_return_pct", -999.0)
        c1 = bool(ls_oos_sharpe > 0.5)          # OOS Sharpe of L/S spread > 0.5
        c2 = bool(ls_oos_ret > spy_oos_ret)     # L/S beats SPY OOS net
        c3 = bool(ls_oos_ret > ew_oos_ret)      # L/S beats no-signal EW-104 OOS
        c4 = bool(ls_oos_ret > 0.0)             # L/S spread positive OOS
        passed = bool(c1 and c2 and c3 and c4)
        ls_is_sharpe = series[key + "_ls"]["stats"]["is_2019"].get("sharpe", 0.0)
        decay = bool(ls_is_sharpe - ls_oos_sharpe > 0.3)
        return {
            "PASS": passed,
            "decision": "PASS -> FLAG FOR CYRUS" if passed else "SHELF LANE",
            "criteria": {
                "c1_ls_oos_sharpe_gt_0p5": {"pass": c1, "value": ls_oos_sharpe, "threshold": 0.5},
                "c2_ls_beats_spy_oos": {"pass": c2, "ls_oos_total_pct": ls_oos_ret, "spy_oos_total_pct": spy_oos_ret},
                "c3_ls_beats_ew_control_oos": {"pass": c3, "ls_oos_total_pct": ls_oos_ret, "ew_oos_total_pct": ew_oos_ret},
                "c4_ls_spread_positive_oos": {"pass": c4, "ls_oos_total_pct": ls_oos_ret},
            },
            "long_only_oos_for_context": {
                "sharpe": lo_oos.get("sharpe"), "total_pct": lo_oos_ret,
                "beats_spy": bool(lo_oos_ret > spy_oos_ret),
                "beats_ew_control": bool(lo_oos_ret > ew_oos_ret),
            },
            "crowding_decay_fingerprint": {
                "is_2019_sharpe": ls_is_sharpe, "oos_2020_sharpe": ls_oos_sharpe,
                "material_decay": decay,
            },
        }
    result["verdict"] = {"mom_12_1": verdict_for("mom_12_1"), "mom_6_1": verdict_for("mom_6_1")}

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(result, open(OUT_JSON, "w"), indent=2)

    # ---- print summary ----
    print("\n" + "=" * 78)
    print("XSEC MOMENTUM KILL-TEST SUMMARY  (universe=%d survivors, OOS=2020+)" % len(univ))
    print("=" * 78)
    def pr(label, st):
        f = st["full"]; o = st["oos_2020"]; i = st["is_2019"]
        print("  %-16s FULL sh=%6.3f cagr=%7.2f%% mdd=%8.2f%% tot=%8.1f%% | IS19 sh=%s  OOS20 sh=%s ret=%s%%" % (
            label, f["sharpe"], f["cagr_pct"], f["maxdd_pct"], f["total_return_pct"],
            i.get("sharpe"), o.get("sharpe"), o.get("total_return_pct")))
    for key in ("mom_12_1", "mom_6_1"):
        print("--- %s ---" % key)
        pr(key + " L/S", series[key + "_ls"]["stats"])
        pr(key + " long-only", series[key + "_long"]["stats"])
    pr("EW-104 ctrl", series["ew_control"]["stats"])
    pr("SPY B&H", series["spy"]["stats"])
    print("-" * 78)
    print("  12-1 L/S avg sig top=%s bot=%s | avg turnover/rebal=%.1f%%  breakeven=%.0f bps" % (
        series["mom_12_1_ls"]["avg_sig_top"], series["mom_12_1_ls"]["avg_sig_bot"],
        cost_analysis["mom_12_1_ls"]["avg_turnover_per_rebal_pct"],
        cost_analysis["mom_12_1_ls"]["breakeven_bps_oneway"]))
    print("  Lookahead canary: honest=%.3f cheat=%.3f differ=%s honest<cheat=%s" % (
        result["lookahead_canary"]["honest_full_sharpe"],
        result["lookahead_canary"]["cheat_forward_peek_full_sharpe"],
        result["lookahead_canary"]["paths_differ"],
        result["lookahead_canary"]["honest_lt_cheat"]))
    print("-" * 78)
    print(result["lane_honesty"]["lane_summary"])
    print("-" * 78)
    for key in ("mom_12_1", "mom_6_1"):
        v = result["verdict"][key]
        print("  VERDICT[%s]: %s" % (key, v["decision"]))
        for ck, cv in v["criteria"].items():
            print("    [%s] %s -> %s" % ("PASS" if cv["pass"] else "FAIL", ck,
                                         {k: vv for k, vv in cv.items() if k != "pass"}))
        print("    crowding/decay: IS19 sh=%s OOS20 sh=%s material_decay=%s" % (
            v["crowding_decay_fingerprint"]["is_2019_sharpe"],
            v["crowding_decay_fingerprint"]["oos_2020_sharpe"],
            v["crowding_decay_fingerprint"]["material_decay"]))
    print("  wrote", OUT_JSON)
    return result

if __name__ == "__main__":
    main()
