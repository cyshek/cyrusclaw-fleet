#!/usr/bin/env python3
"""COR3M PERCENTILE THROTTLE PROBE (assignment 2026-06-26).

Hypothesis (from backlog / dispersion sprint): COR3M 3M-implied-correlation
rolling LEVEL-PERCENTILE vs trailing 2-3yr acts as a slow equity risk-on/off
throttle. LOW pct = risk-on (hold SPY), HIGH pct = de-risk (cash/flat).
Predicted ~0.05-0.1 turns/yr, orthogonal to 12-1 trend, 2006+ coverage.

NB (prior work 2026-06-24, _disp_ortho_probe.py): the NAIVE RAW-LEVEL quintile
sort was BACKWARDS (Q5 high-corr = HIGHEST fwd SPY return = buy-the-fear) and
level fwd-corr ~zero. The percentile RE-NORMALIZES (de-trends the slow drift in
COR3M's own mean) so it is a genuinely different transform worth a clean test.
We test BOTH directions explicitly and report honest OOS numbers.

NO trading, NO config, NO protected-file touch. Pure measurement -> prints +
JSON. Parent writes the rigor report.

Honesty rails:
 - D+1 LAG: signal from close[t] decides exposure for return[t+1..] (trade next
   bar). No same-bar lookahead.
 - Continuous-span Sharpe (fp_sharpe.sharpe_from_returns equivalent, sqrt252).
 - Real IS/OOS split at 2018-01-01 (calendar, pre-committed).
 - Same-path SPY benchmark (identical day grid).
 - 2 bps one-way cost charged on exposure CHANGES (CostModel.alpaca_stocks).
 - Cash leg earns 0% (conservative floor; real T-bill would only help).
"""
import json, csv, math
from datetime import datetime, timezone

TRADING_DAYS = 252.0
ONE_WAY_BPS = 2.0
OOS_SPLIT = "2018-01-01"

def _utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")

# ---- load SPY adjclose ----
d = json.load(open("/tmp/spy.json"))["chart"]["result"][0]
ts = d["timestamp"]; adj = d["indicators"]["adjclose"][0]["adjclose"]
spy = {}
for t, a in zip(ts, adj):
    if a is None:
        continue
    spy[_utc(t)] = a

# ---- load COR3M close, parse MM/DD/YYYY ----
def load_cor(path):
    out = {}
    for r in list(csv.reader(open(path)))[1:]:
        if len(r) < 5 or not r[4]:
            continue
        mm, dd, yy = r[0].split("/")
        out[f"{yy}-{int(mm):02d}-{int(dd):02d}"] = float(r[4])
    return out

cor = load_cor("data_cache/cboe/COR3M_History.csv")

days = sorted(set(spy) & set(cor))
print(f"common days SPY n COR3M: {len(days)} ({days[0]} -> {days[-1]})")

px = [spy[x] for x in days]
c  = [cor[x] for x in days]
# daily log returns of SPY, aligned so ret[i] is return from day i-1 -> i
ret = [0.0] + [math.log(px[i]/px[i-1]) for i in range(1, len(px))]

def sharpe(rs):
    rs = [x for x in rs if x is not None]
    if len(rs) < 2:
        return float("nan")
    m = sum(rs)/len(rs)
    var = sum((x-m)**2 for x in rs)/(len(rs)-1)
    sd = math.sqrt(var)
    return (m/sd)*math.sqrt(TRADING_DAYS) if sd > 0 else float("nan")

def cagr(rs):
    if not rs:
        return float("nan")
    tot = sum(rs)  # log returns
    yrs = len(rs)/TRADING_DAYS
    return math.exp(tot/yrs) - 1 if yrs > 0 else float("nan")

def total_ret(rs):
    return math.exp(sum(rs)) - 1

def maxdd(rs):
    eq = 1.0; peak = 1.0; mdd = 0.0
    for r in rs:
        eq *= math.exp(r)
        peak = max(peak, eq)
        dd = eq/peak - 1
        mdd = min(mdd, dd)
    return mdd

def corr(a, b):
    n = len(a)
    if n < 2:
        return float("nan")
    ma = sum(a)/n; mb = sum(b)/n
    num = sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in a)); db = math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float("nan")

def rolling_pct(series, win):
    """Percentile rank of series[i] within the trailing `win` values ENDING at i
    (inclusive). Returns None until a full window exists. Strictly backward-looking."""
    out = [None]*len(series)
    for i in range(len(series)):
        if i+1 < win:
            continue
        window = series[i-win+1:i+1]
        cur = window[-1]
        # fraction of window strictly below current (rank percentile 0..1)
        below = sum(1 for v in window if v < cur)
        out[i] = below/(len(window)-1) if len(window) > 1 else None
    return out

oos_idx = next((i for i, x in enumerate(days) if x >= OOS_SPLIT), len(days))
print(f"OOS split {OOS_SPLIT} at index {oos_idx} ({days[oos_idx] if oos_idx < len(days) else 'NA'}); "
      f"IS days={oos_idx}, OOS days={len(days)-oos_idx}")

def backtest(exposure):
    """exposure[i] = target SPY weight DECIDED from data up to & incl close[i].
    Applied to ret[i+1] (D+1 lag). Cash earns 0. 2bps one-way on |Δexposure|.
    Returns dict of strat daily returns aligned to days[1:] and turnover."""
    strat = [None]*len(days)
    prev_w = 0.0
    turns = 0.0
    for i in range(len(days)-1):
        w = exposure[i]
        if w is None:
            strat[i+1] = None
            # do not update prev_w / cost while warming up
            continue
        # cost on change from prev_w -> w, charged on day we trade (i+1)
        dchg = abs(w - prev_w)
        cost = dchg * (ONE_WAY_BPS/1e4)
        turns += dchg
        strat[i+1] = w*ret[i+1] - cost
        prev_w = w
    return strat, turns

def slice_aligned(strat):
    """Return (is_rets, oos_rets, full_rets, first_valid_idx) dropping Nones,
    and the SPY same-path slices over the SAME valid grid."""
    full_s = []; full_b = []; is_s=[]; is_b=[]; oos_s=[]; oos_b=[]
    for i in range(1, len(days)):
        if strat[i] is None:
            continue
        full_s.append(strat[i]); full_b.append(ret[i])
        if i < oos_idx:
            is_s.append(strat[i]); is_b.append(ret[i])
        else:
            oos_s.append(strat[i]); oos_b.append(ret[i])
    return (full_s, full_b, is_s, is_b, oos_s, oos_b)

def report(name, strat, turns):
    fs, fb, iss, isb, oos, oosb = slice_aligned(strat)
    yrs = len(fs)/TRADING_DAYS
    tpy = turns/yrs if yrs > 0 else float("nan")
    avg_exp_changes = tpy/2.0  # full round-trips/yr approx
    row = {
        "name": name,
        "n_days": len(fs),
        "turns_per_yr_oneway": round(tpy, 4),
        "approx_roundtrips_per_yr": round(avg_exp_changes, 4),
        "full": {"sharpe": round(sharpe(fs),3), "cagr": round(cagr(fs),4),
                 "total_ret": round(total_ret(fs),4), "maxdd": round(maxdd(fs),4)},
        "IS":   {"sharpe": round(sharpe(iss),3), "cagr": round(cagr(iss),4),
                 "total_ret": round(total_ret(iss),4), "maxdd": round(maxdd(iss),4)},
        "OOS":  {"sharpe": round(sharpe(oos),3), "cagr": round(cagr(oos),4),
                 "total_ret": round(total_ret(oos),4), "maxdd": round(maxdd(oos),4)},
        "corr_to_spy_daily": round(corr(fs, fb),3),
    }
    return row, fs

# Buy&hold SPY baseline on the common grid (full / IS / OOS)
bh_full = [ret[i] for i in range(1, len(days))]
bh_is   = [ret[i] for i in range(1, oos_idx)]
bh_oos  = [ret[i] for i in range(oos_idx, len(days))]
spy_base = {
    "name": "SPY_buyhold",
    "full": {"sharpe": round(sharpe(bh_full),3), "cagr": round(cagr(bh_full),4),
             "total_ret": round(total_ret(bh_full),4), "maxdd": round(maxdd(bh_full),4)},
    "IS":   {"sharpe": round(sharpe(bh_is),3), "cagr": round(cagr(bh_is),4),
             "total_ret": round(total_ret(bh_is),4), "maxdd": round(maxdd(bh_is),4)},
    "OOS":  {"sharpe": round(sharpe(bh_oos),3), "cagr": round(cagr(bh_oos),4),
             "total_ret": round(total_ret(bh_oos),4), "maxdd": round(maxdd(bh_oos),4)},
}
print("\n=== SPY buy&hold (same common grid) ===")
print(json.dumps(spy_base, indent=2))

results = {"spy_base": spy_base, "configs": []}

# ---- Build percentile series for 2yr & 3yr windows ----
for win_label, win in (("3yr_756d", 756), ("2yr_504d", 504)):
    pct = rolling_pct(c, win)
    valid_n = sum(1 for v in pct if v is not None)
    print(f"\n##### percentile window={win_label}: {valid_n} valid signal days "
          f"(first valid {days[next((i for i,v in enumerate(pct) if v is not None), 0)]})")

    # quintile forward-return sanity (does percentile separate fwd SPY ret?)
    # fwd 21d return by pct bucket, D+1 honest (uses fwd window starting i+1)
    buckets = {q: [] for q in range(5)}
    H = 21
    for i in range(len(days)-H-1):
        p = pct[i]
        if p is None:
            continue
        q = min(4, int(p*5))
        fwd = math.log(px[i+1+H]/px[i+1])  # enter next bar, hold 21d
        buckets[q].append(fwd)
    qsep = {}
    for q in range(5):
        b = buckets[q]
        qsep[q] = {"n": len(b),
                   "mean_fwd21_ann": round((sum(b)/len(b))*(TRADING_DAYS/H), 4) if b else None}
    print(f"  fwd-21d SPY ret by COR3M-pct quintile (Q0=lowest corr ... Q4=highest):")
    for q in range(5):
        print(f"    Q{q}: n={qsep[q]['n']:5d}  mean_fwd21_ann={qsep[q]['mean_fwd21_ann']}")

    cfg_block = {"window": win_label, "quintile_fwd21": qsep, "throttles": []}

    # ---- THROTTLE VARIANTS ----
    # Direction A ("naive", per backlog): LOW pct = risk-on (long), HIGH = cash.
    # Direction B ("inverse"): HIGH pct = risk-on (buy-the-fear, per prior probe).
    def make_binary(thresh, direction):
        exp = [None]*len(days)
        for i in range(len(days)):
            p = pct[i]
            if p is None:
                continue
            if direction == "A":   # low pct -> long
                exp[i] = 1.0 if p <= thresh else 0.0
            else:                  # B: high pct -> long
                exp[i] = 1.0 if p >= (1.0 - thresh) else 0.0
        return exp

    def make_banded(direction):
        # 3-tier: bottom third / middle / top third -> weights
        exp = [None]*len(days)
        for i in range(len(days)):
            p = pct[i]
            if p is None:
                continue
            if direction == "A":
                w = 1.0 if p <= 0.33 else (0.5 if p <= 0.66 else 0.0)
            else:
                w = 1.0 if p >= 0.66 else (0.5 if p >= 0.33 else 0.0)
            exp[i] = w
        return exp

    for thresh in (0.5, 0.8, 0.9):
        for direction in ("A", "B"):
            exp = make_binary(thresh, direction)
            strat, turns = backtest(exp)
            dirname = "lowON" if direction == "A" else "highON"
            row, _ = report(f"binary_{win_label}_{dirname}_thr{thresh}", strat, turns)
            cfg_block["throttles"].append(row)

    for direction in ("A", "B"):
        exp = make_banded(direction)
        strat, turns = backtest(exp)
        dirname = "lowON" if direction == "A" else "highON"
        row, fs = report(f"banded3_{win_label}_{dirname}", strat, turns)
        cfg_block["throttles"].append(row)

    results["configs"].append(cfg_block)

# ---- print all throttle rows compactly ----
print("\n\n================ ALL THROTTLE RESULTS ================")
for cfg in results["configs"]:
    print(f"\n--- window {cfg['window']} ---")
    for r in cfg["throttles"]:
        f = r["full"]; o = r["OOS"]; i = r["IS"]
        print(f"  {r['name']:34s} | full S={f['sharpe']:+.3f} CAGR={f['cagr']*100:+6.2f}% DD={f['maxdd']*100:+6.1f}% "
              f"| IS S={i['sharpe']:+.3f} | OOS S={o['sharpe']:+.3f} CAGR={o['cagr']*100:+6.2f}% "
              f"| turns/yr={r['turns_per_yr_oneway']:.3f} | corrSPY={r['corr_to_spy_daily']:+.2f}")

json.dump(results, open("reports/_cor3m_pct_throttle_results.json", "w"), indent=2)
print("\nwrote reports/_cor3m_pct_throttle_results.json")
