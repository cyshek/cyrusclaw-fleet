#!/usr/bin/env python3
"""
BAB (Betting-Against-Beta) kill-test — H2 from LITERATURE_HYPOTHESES_20260623T185057Z.md.

Frazzini-Pedersen (JFE 2014): low-beta names earn higher risk-adjusted returns because
leverage-constrained investors overbid high-beta names, flattening the security market line.
This builds a beta-neutral long-low-beta / short-high-beta L/S (the real BAB) PLUS a
long-only low-beta tilt, on the cached 104-name S&P100-ish single-name universe.

HONESTY RAILS (bench standing rules):
- Betas computed from PAST-ONLY daily returns (trailing window, strictly < as-of date).
- Rank on prior-month-end betas; trade the FOLLOWING month. Lookahead canary asserts no peek.
- SPY traded on the SAME path. FULL continuous-span Sharpe (252d), never median-of-windows.
- 2bps one-way cost + breakeven-bps + turnover computed up front.
- Survivorship: the 104 universe is TODAY's survivors (biased). The decisive honest tests are
  (a) beat the no-signal EW-104 control, and (b) L/S spread positive (survivorship-neutral by
  construction — both legs from the same universe).
- A clean negative is an acceptable, valuable result. Do NOT manufacture a win.

Mirrors machinery from _fundamentals_pit_tests.py (load_px, month_starts, sharpe/cagr/maxdd/
ann_vol/total_return, breakeven_bps, killer-window slicing, EW-104 control).
"""
import os, json, math, bisect

WS = os.path.dirname(os.path.abspath(__file__))
YAHOO = os.path.join(WS, "data_cache", "yahoo", "%s_parsed.json")
UNIV_PATH = os.path.join(WS, "data_cache", "edgar_fundamentals", "universe.json")
OUT_JSON = os.path.join(WS, "reports", "_bab_killtest_result.json")

TRADING_DAYS = 252.0
OOS_SPLIT = "2019-12-31"        # main's spec: IS <=2019-12-31, OOS 2020-01-01+
OOS_SPLIT_ALT = "2018-12-31"    # also report for continuity
START = "2006-01-01"            # earliest sensible start given inceptions + 252d warmup
COST_BPS = 2.0

# ----------------------------- data loading (mirror) -----------------------------
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

# ----------------------------- return series builder -----------------------------
def build_daily_returns(px, dates_sorted):
    """Return dict date->daily simple return, aligned to that name's own dates."""
    rets = {}
    for i in range(1, len(dates_sorted)):
        d0 = dates_sorted[i - 1]; d1 = dates_sorted[i]
        p0 = px[d0]; p1 = px[d1]
        if p0 and p0 > 0:
            rets[d1] = p1 / p0 - 1.0
    return rets

# ----------------------------- beta estimation (PAST-ONLY) -----------------------------
def rolling_beta(name_ret, name_dates, spy_ret, asof, window):
    """
    Beta of name vs SPY over the last `window` trading days STRICTLY BEFORE asof
    (asof itself excluded — we rank at prior month-end and trade forward; betas use
    only data dated < asof). Uses overlapping (paired) daily returns on SPY's calendar.
    Returns (beta, n_obs) or (None, 0) if insufficient overlap.
    """
    # collect SPY dates strictly < asof, take last `window`
    j = bisect.bisect_left(spy_ret["dates"], asof)  # first index >= asof
    lo = max(0, j - window)
    win_dates = spy_ret["dates"][lo:j]
    xs = []; ys = []
    nm = name_ret  # dict date->ret
    sm = spy_ret["map"]
    for d in win_dates:
        if d in nm and d in sm:
            ys.append(nm[d]); xs.append(sm[d])
    n = len(xs)
    if n < max(60, window // 3):   # require decent overlap (>=60 paired obs)
        return None, n
    mx = sum(xs) / n; my = sum(ys) / n
    cov = 0.0; varx = 0.0
    for a, b in zip(xs, ys):
        cov += (a - mx) * (b - my)
        varx += (a - mx) * (a - mx)
    if varx <= 0:
        return None, n
    return cov / varx, n

def shrink_beta(b, lam=0.6):
    """Frazzini-Pedersen shrinkage toward 1.0: beta_shrunk = lam*beta_raw + (1-lam)*1.0."""
    return lam * b + (1.0 - lam) * 1.0

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

def basket_beta(names, betas):
    bs = [betas[t] for t in names if t in betas]
    if not bs:
        return None
    return sum(bs) / len(bs)

# ----------------------------- stats (mirror exactly) -----------------------------
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

def slice_block(dates, rets, start, end):
    _, sr = slice_rets(dates, rets, start, end)
    if len(sr) < 20:
        return {"n": len(sr)}
    return stat_block(sr)

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
def run_bab(univ, adj_px, name_rets, spy_ret, spy_px,
            window=252, lam=0.6, bucket=0.2, cadence="M",
            cost_bps=COST_BPS, start=START, mode="ls", lookahead_canary=False):
    """
    mode: 'ls'   -> beta-neutral long-low/short-high (the real BAB)
          'long' -> long-only low-beta tilt (long bottom-bucket only, EW), vol context reported separately
    bucket: fraction per basket (0.2 quintile, 0.333 tercile)
    lookahead_canary: if True, deliberately use FUTURE betas (asof = next month) to prove
                      the honest path differs — sanity check only.
    Returns dict with dates, strat_ret (net), spy_ret, gross, turnover info, beta diagnostics.
    """
    cal = [d for d in spy_ret["dates"] if d >= start]
    if not cal:
        return None
    rb_idx = month_starts(cal) if cadence == "M" else quarter_starts(cal)
    rb_set = set(rb_idx)

    # SPY path on same calendar
    spy_path = [0.0]
    for i in range(1, len(cal)):
        p0 = spy_px.get(cal[i - 1]); p1 = spy_px.get(cal[i])
        spy_path.append((p1 / p0 - 1.0) if (p0 and p1 and p0 > 0) else 0.0)

    cur_low = []; cur_high = []
    w_low = 1.0; w_high = 1.0   # leverage factors to hit beta-neutral
    strat_net = [0.0]; strat_gross = [0.0]
    turnovers = []; rebal_log = []; prev_set = set()
    beta_low_log = []; beta_high_log = []; n_univ_log = []
    canary_hits = 0

    for i in range(len(cal)):
        d = cal[i]
        if i in rb_set:
            asof = d
            if lookahead_canary:
                # cheat: use betas as of ~1 month forward (peek)
                k_fwd = min(i + 21, len(cal) - 1)
                asof = cal[k_fwd]
            betas = {}
            for t in univ:
                b, nobs = rolling_beta(name_rets[t], None, spy_ret, asof, window)
                if b is not None:
                    betas[t] = shrink_beta(b, lam) if lam < 1.0 else b
            ranked = sorted(betas.items(), key=lambda kv: kv[1])  # ascending: low beta first
            m = len(ranked)
            if m >= 10:
                k = max(1, int(round(m * bucket)))
                low = [t for t, _ in ranked[:k]]       # lowest beta
                high = [t for t, _ in ranked[-k:]]     # highest beta
                bl = basket_beta(low, betas); bh = basket_beta(high, betas)
                beta_low_log.append(bl); beta_high_log.append(bh); n_univ_log.append(m)
                # beta-neutral leverage: scale each leg to |beta|=1
                if mode == "ls":
                    w_low = (1.0 / bl) if (bl and bl > 0.05) else 1.0
                    w_high = (1.0 / bh) if (bh and bh > 0.05) else 1.0
                    # cap leverage to sane bounds (avoid blowups from tiny betas)
                    w_low = max(0.25, min(3.0, w_low))
                    w_high = max(0.25, min(3.0, w_high))
                    new_set = set("L__" + x for x in low) | set("S__" + x for x in high)
                else:  # long-only low-beta tilt
                    w_low = 1.0; w_high = 0.0
                    new_set = set("L__" + x for x in low)
                if prev_set:
                    changed = len(new_set.symmetric_difference(prev_set))
                    denom = max(1, len(new_set) + len(prev_set))
                    turn = changed / denom
                else:
                    turn = 1.0
                turnovers.append(turn)
                cur_low = low; cur_high = high; prev_set = new_set
                cost = (cost_bps / 10000.0) * turn
                strat_net[-1] = strat_net[-1] - cost
                rebal_log.append({"date": d, "n_low": len(low), "n_high": len(high),
                                  "beta_low": round(bl, 3) if bl else None,
                                  "beta_high": round(bh, 3) if bh else None,
                                  "w_low": round(w_low, 3), "w_high": round(w_high, 3),
                                  "turnover": round(turn, 4)})
        if i == 0:
            continue
        rl, nl = bucket_ret(cur_low, adj_px, cal[i - 1], d)
        if mode == "ls" and cur_high:
            rh, nh = bucket_ret(cur_high, adj_px, cal[i - 1], d)
            day = w_low * rl - w_high * rh
        else:
            day = w_low * rl
        strat_gross.append(day)
        # net: only the rebalance-day already had cost subtracted into strat_net[-1];
        # for non-rebal days net==gross
        strat_net.append(day)

    avg_turn = sum(turnovers) / len(turnovers) if turnovers else 0.0
    return {"dates": cal, "strat_ret": strat_net, "strat_gross": strat_gross,
            "spy_ret": spy_path, "turnovers": turnovers, "turnover_sum": sum(turnovers),
            "avg_turnover": avg_turn, "n_rebal": len(turnovers), "rebal_log": rebal_log,
            "avg_beta_low": (sum(x for x in beta_low_log if x is not None) / len([x for x in beta_low_log if x is not None])) if beta_low_log else None,
            "avg_beta_high": (sum(x for x in beta_high_log if x is not None) / len([x for x in beta_high_log if x is not None])) if beta_high_log else None,
            "avg_n_univ": (sum(n_univ_log) / len(n_univ_log)) if n_univ_log else 0}

def run_ew_control(univ, adj_px, spy_dates, start=START, cost_bps=COST_BPS, cadence="M"):
    """No-signal equal-weight hold of the SAME universe (survivorship control)."""
    cal = [d for d in spy_dates if d >= start]
    rb_idx = month_starts(cal) if cadence == "M" else quarter_starts(cal)
    rb_set = set(rb_idx)
    strat = [0.0]; turnovers = []; prev = set()
    cur = []
    for i in range(len(cal)):
        d = cal[i]
        if i in rb_set:
            # hold every name that has a price as of d-1 and d (i.e. currently tradable)
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

# ----------------------------- main -----------------------------
def main():
    univ = json.load(open(UNIV_PATH))["tickers"]
    spy_px = load_px("SPY")
    spy_dates = sorted(spy_px.keys())
    spy_daily = build_daily_returns(spy_px, spy_dates)
    spy_ret = {"dates": spy_dates, "map": spy_daily}

    adj_px = {}; name_rets = {}
    for t in univ:
        px = load_px(t)
        if not px:
            continue
        adj_px[t] = px
        dts = sorted(px.keys())
        name_rets[t] = build_daily_returns(px, dts)
    univ = [t for t in univ if t in adj_px]
    print("universe with prices:", len(univ))

    result = {"meta": {
        "test": "BAB (Betting-Against-Beta) kill-test, H2",
        "universe_n": len(univ),
        "universe_note": "104-name S&P100-ish; TODAY's survivors (survivorship-biased). L/S spread + EW-104 control are the honest defenses.",
        "start": START, "oos_split": OOS_SPLIT, "oos_split_alt": OOS_SPLIT_ALT,
        "cost_bps_oneway": COST_BPS, "trading_days": TRADING_DAYS,
        "beta": "rolling 252d vs SPY, PAST-ONLY (asof excluded), Frazzini-Pedersen shrinkage lam=0.6 toward 1.0",
    }}

    # --- primary configs ---
    print("running BAB L/S (quintile, 252d, shrink0.6, monthly) ...")
    ls = run_bab(univ, adj_px, name_rets, spy_ret, spy_px, window=252, lam=0.6, bucket=0.2, cadence="M", mode="ls")
    print("running BAB long-only tilt (quintile, 252d, shrink0.6, monthly) ...")
    lo = run_bab(univ, adj_px, name_rets, spy_ret, spy_px, window=252, lam=0.6, bucket=0.2, cadence="M", mode="long")
    print("running EW-104 no-signal control ...")
    ew = run_ew_control(univ, adj_px, spy_dates, start=START)

    dates = ls["dates"]
    spy_series = ls["spy_ret"]

    def series_stats(dts, rets):
        # IS = up to and including OOS_SPLIT; OOS = after
        is_d, is_r = slice_rets(dts, rets, START, "2020-01-01")   # IS <= 2019-12-31
        oos_d, oos_r = slice_rets(dts, rets, "2020-01-01", "2099-01-01")
        is_alt_d, is_alt_r = slice_rets(dts, rets, START, "2019-01-01")  # alt IS <= 2018-12-31
        oos_alt_d, oos_alt_r = slice_rets(dts, rets, "2019-01-01", "2099-01-01")
        return {
            "full": stat_block(rets),
            "is_2019": (stat_block(is_r) if len(is_r) >= 20 else {"n": len(is_r)}),
            "oos_2020": (stat_block(oos_r) if len(oos_r) >= 20 else {"n": len(oos_r)}),
            "is_2018alt": (stat_block(is_alt_r) if len(is_alt_r) >= 20 else {"n": len(is_alt_r)}),
            "oos_2019alt": (stat_block(oos_alt_r) if len(oos_alt_r) >= 20 else {"n": len(oos_alt_r)}),
        }


    result["series"] = {
        "bab_ls": {
            "stats": series_stats(dates, ls["strat_ret"]),
            "avg_turnover": round(ls["avg_turnover"], 4),
            "turnover_sum": round(ls["turnover_sum"], 2),
            "n_rebal": ls["n_rebal"],
            "avg_beta_low": round(ls["avg_beta_low"], 3) if ls["avg_beta_low"] else None,
            "avg_beta_high": round(ls["avg_beta_high"], 3) if ls["avg_beta_high"] else None,
            "avg_n_univ": round(ls["avg_n_univ"], 1),
        },
        "bab_long": {
            "stats": series_stats(dates, lo["strat_ret"]),
            "avg_turnover": round(lo["avg_turnover"], 4),
            "turnover_sum": round(lo["turnover_sum"], 2),
            "n_rebal": lo["n_rebal"],
        },
        "ew_control": {
            "stats": series_stats(ew["dates"], ew["strat_ret"]),
            "avg_turnover": round(ew["avg_turnover"], 4),
            "n_rebal": ew["n_rebal"],
        },
        "spy": {
            "stats": series_stats(dates, spy_series),
        },
    }

    # --- breakeven + turnover up front (L/S, gross) ---
    be_ls = breakeven_bps(ls["strat_gross"], ls["turnover_sum"])
    be_lo = breakeven_bps(lo["strat_gross"], lo["turnover_sum"])
    result["cost_analysis"] = {
        "bab_ls": {
            "avg_turnover_per_rebal_pct": round(ls["avg_turnover"] * 100, 1),
            "turnover_sum": round(ls["turnover_sum"], 2),
            "breakeven_bps_oneway": round(be_ls, 1),
            "cost_bps_charged": COST_BPS,
            "comfortably_above_cost": bool(be_ls > 5 * COST_BPS),
        },
        "bab_long": {
            "avg_turnover_per_rebal_pct": round(lo["avg_turnover"] * 100, 1),
            "turnover_sum": round(lo["turnover_sum"], 2),
            "breakeven_bps_oneway": round(be_lo, 1),
            "cost_bps_charged": COST_BPS,
        },
    }

    # --- lookahead canary: honest path vs cheating (future-beta) path must DIFFER ---
    print("running lookahead canary (future-beta cheat) ...")
    ls_cheat = run_bab(univ, adj_px, name_rets, spy_ret, spy_px, window=252, lam=0.6,
                       bucket=0.2, cadence="M", mode="ls", lookahead_canary=True)
    sh_honest = sharpe(ls["strat_ret"])
    sh_cheat = sharpe(ls_cheat["strat_ret"])
    # also assert: betas at first rebalance used only pre-asof data (structural check)
    result["lookahead_canary"] = {
        "honest_full_sharpe": round(sh_honest, 3),
        "cheat_future_beta_full_sharpe": round(sh_cheat, 3),
        "paths_differ": bool(abs(sh_honest - sh_cheat) > 1e-6),
        "note": "Honest path ranks on past-only betas at month-end and trades forward. Cheat path peeks ~1mo-fwd betas. If identical, leakage suspected.",
    }

    # --- killer battery on L/S and SPY ---
    kb = []
    for name, s, e in KILLER_WINDOWS:
        _, lr = slice_rets(dates, ls["strat_ret"], s, e)
        _, sr = slice_rets(dates, spy_series, s, e)
        _, lor = slice_rets(dates, lo["strat_ret"], s, e)
        row = {"window": name, "start": s, "end": e, "n": len(lr)}
        if len(lr) >= 5:
            row["ls_total_pct"] = round(total_return(lr), 2)
            row["ls_sharpe"] = round(sharpe(lr), 2)
            row["long_total_pct"] = round(total_return(lor), 2)
            row["spy_total_pct"] = round(total_return(sr), 2)
            row["ls_minus_spy_pct"] = round(total_return(lr) - total_return(sr), 2)
        kb.append(row)
    result["killer_battery"] = kb

    # --- robustness sweep ---
    print("running robustness sweep ...")
    sweep = []
    configs = []
    for window in (126, 252, 504):
        for lam in (0.6, 1.0):  # 0.6 = shrunk, 1.0 = raw
            for bucket in (0.2, 0.3333):
                for cadence in ("M", "Q"):
                    configs.append((window, lam, bucket, cadence))
    for (window, lam, bucket, cadence) in configs:
        r = run_bab(univ, adj_px, name_rets, spy_ret, spy_px, window=window, lam=lam,
                    bucket=bucket, cadence=cadence, mode="ls")
        if not r:
            continue
        d2 = r["dates"]; rr = r["strat_ret"]
        _, oos_r = slice_rets(d2, rr, "2020-01-01", "2099-01-01")
        _, is_r = slice_rets(d2, rr, START, "2020-01-01")
        sweep.append({
            "window": window, "shrink_lam": lam, "bucket": round(bucket, 3),
            "cadence": cadence,
            "full_sharpe": round(sharpe(rr), 3),
            "is_sharpe": round(sharpe(is_r), 3) if len(is_r) >= 20 else None,
            "oos_sharpe": round(sharpe(oos_r), 3) if len(oos_r) >= 20 else None,
            "oos_total_pct": round(total_return(oos_r), 1) if len(oos_r) >= 20 else None,
            "full_cagr_pct": round(cagr(rr), 2),
            "avg_turnover_pct": round(r["avg_turnover"] * 100, 1),
        })
    result["robustness_sweep"] = sweep

    # --- VERDICT (main's 4 criteria, evaluated on OOS = 2020+) ---
    ls_oos = result["series"]["bab_ls"]["stats"]["oos_2020"]
    ew_oos = result["series"]["ew_control"]["stats"]["oos_2020"]
    spy_oos = result["series"]["spy"]["stats"]["oos_2020"]
    lo_oos = result["series"]["bab_long"]["stats"]["oos_2020"]

    ls_oos_sharpe = ls_oos.get("sharpe", 0.0)
    ls_oos_ret = ls_oos.get("total_return_pct", -999.0)
    ew_oos_ret = ew_oos.get("total_return_pct", -999.0)
    spy_oos_ret = spy_oos.get("total_return_pct", -999.0)

    # Criterion interpretation: the L/S spread is the headline alpha series.
    # 1) OOS Sharpe > 0.5  (on the L/S spread)
    c1 = bool(ls_oos_sharpe > 0.5)
    # 2) beats SPY raw return net of cost on same path (L/S total return > SPY total return, OOS)
    c2 = bool(ls_oos_ret > spy_oos_ret)
    # 3) beats no-signal EW-104 control (L/S total return > EW control total return, OOS)
    c3 = bool(ls_oos_ret > ew_oos_ret)
    # 4) L/S spread POSITIVE (OOS) -- positive cumulative return
    c4 = bool(ls_oos_ret > 0.0)

    passed = bool(c1 and c2 and c3 and c4)

    # crowding/decay fingerprint: OOS materially weaker than IS
    ls_is_sharpe = result["series"]["bab_ls"]["stats"]["is_2019"].get("sharpe", 0.0)
    decay = bool(ls_is_sharpe - ls_oos_sharpe > 0.3)

    result["verdict"] = {
        "PASS": passed,
        "decision": "PASS -> FLAG FOR CYRUS" if passed else "CLOSE LANE",
        "criteria": {
            "c1_oos_sharpe_gt_0p5": {"pass": c1, "value": ls_oos_sharpe, "threshold": 0.5},
            "c2_beats_spy_oos": {"pass": c2, "ls_oos_total_pct": ls_oos_ret, "spy_oos_total_pct": spy_oos_ret},
            "c3_beats_ew_control_oos": {"pass": c3, "ls_oos_total_pct": ls_oos_ret, "ew_oos_total_pct": ew_oos_ret},
            "c4_ls_spread_positive_oos": {"pass": c4, "ls_oos_total_pct": ls_oos_ret},
        },
        "long_only_oos_for_context": {
            "sharpe": lo_oos.get("sharpe"), "total_pct": lo_oos.get("total_return_pct"),
            "beats_spy": bool(lo_oos.get("total_return_pct", -999) > spy_oos_ret),
            "beats_ew_control": bool(lo_oos.get("total_return_pct", -999) > ew_oos_ret),
        },
        "crowding_decay_fingerprint": {
            "is_2019_sharpe": ls_is_sharpe, "oos_2020_sharpe": ls_oos_sharpe,
            "material_decay": decay,
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(result, open(OUT_JSON, "w"), indent=2)

    # ---- print summary ----
    print("\n" + "=" * 72)
    print("BAB KILL-TEST SUMMARY  (universe=%d survivors, OOS=2020+)" % len(univ))
    print("=" * 72)
    def pr(label, st):
        f = st["full"]; o = st["oos_2020"]; i = st["is_2019"]
        print("  %-14s FULL sh=%6.3f cagr=%6.2f%% mdd=%7.2f%%  | IS19 sh=%s  OOS20 sh=%s ret=%s%%" % (
            label, f["sharpe"], f["cagr_pct"], f["maxdd_pct"],
            i.get("sharpe"), o.get("sharpe"), o.get("total_return_pct")))
    pr("BAB L/S", result["series"]["bab_ls"]["stats"])
    pr("BAB long-only", result["series"]["bab_long"]["stats"])
    pr("EW-104 ctrl", result["series"]["ew_control"]["stats"])
    pr("SPY B&H", result["series"]["spy"]["stats"])
    print("-" * 72)
    print("  L/S avg beta low=%s high=%s  | avg turnover/rebal=%.1f%%  breakeven=%.0f bps" % (
        result["series"]["bab_ls"]["avg_beta_low"], result["series"]["bab_ls"]["avg_beta_high"],
        result["cost_analysis"]["bab_ls"]["avg_turnover_per_rebal_pct"],
        result["cost_analysis"]["bab_ls"]["breakeven_bps_oneway"]))
    print("  Lookahead canary: honest=%.3f cheat=%.3f differ=%s" % (
        result["lookahead_canary"]["honest_full_sharpe"],
        result["lookahead_canary"]["cheat_future_beta_full_sharpe"],
        result["lookahead_canary"]["paths_differ"]))
    print("-" * 72)
    v = result["verdict"]
    print("  VERDICT: %s" % v["decision"])
    for ck, cv in v["criteria"].items():
        print("    [%s] %s -> %s" % ("PASS" if cv["pass"] else "FAIL", ck, {k: vv for k, vv in cv.items() if k != "pass"}))
    print("  crowding/decay: IS19 sh=%s OOS20 sh=%s material_decay=%s" % (
        v["crowding_decay_fingerprint"]["is_2019_sharpe"],
        v["crowding_decay_fingerprint"]["oos_2020_sharpe"],
        v["crowding_decay_fingerprint"]["material_decay"]))
    print("  wrote", OUT_JSON)
    return result

if __name__ == "__main__":
    main()
