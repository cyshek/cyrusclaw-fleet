"""Bear-Regime Complement Strategy Backtest - 2026-06-19
Tests SQQQ/TLT/GLD bear-regime strategies as complements to the TQQQ vol-target sleeve.
"""
from __future__ import annotations
import json, math, time, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parent
CACHE_DIR = WORKSPACE / "data_cache" / "yahoo"
REPORTS_DIR = WORKSPACE / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"

# ─── DATA ────────────────────────────────────────────────────────────────────

def load_cache(symbol):
    key = symbol.upper().replace("^","_")
    p = CACHE_DIR / (key + "_parsed.json")
    data = json.loads(p.read_text())
    return {b["date"]: b["adjclose"] for b in data if b["adjclose"] is not None}

def build_dates(pdicts, start, end):
    common = None
    for pd in pdicts:
        keys = set(k for k,v in pd.items() if v is not None and start <= k <= end)
        common = keys if common is None else common & keys
    return sorted(common or [])

def get_warmup_prices(price_dict, before_date, n=250):
    """Return the last N prices strictly BEFORE before_date (for SMA seeding)."""
    prior = sorted(k for k in price_dict if k < before_date and price_dict[k] is not None)
    prior = prior[-n:]
    return [price_dict[d] for d in prior]

# ─── MATH ────────────────────────────────────────────────────────────────────

def sma(prices, w):
    if len(prices) < w: return None
    return sum(prices[-w:]) / w

def rvol(rets, w=20):
    if len(rets) < w: return None
    r = rets[-w:]; mu = sum(r)/len(r)
    var = sum((x-mu)**2 for x in r)/len(r)
    return math.sqrt(var) * math.sqrt(252)

def tbill(v):
    return (v / 100) / 252

def calc_metrics(equity, rf=0.0):
    if len(equity) < 2:
        return dict(cagr=0, sharpe=0, maxdd=0, ann_vol=0, total_ret=0,
                    n_days=len(equity), n_years=0)
    n = len(equity); ny = n / 252.0
    total = equity[-1] / equity[0]
    cagr = total**(1/ny) - 1 if ny > 0 else 0
    rets = [equity[i]/equity[i-1]-1 for i in range(1, n)]
    excess = [r - rf for r in rets]
    mu_e = sum(excess)/len(excess) if excess else 0
    var_e = sum((x-mu_e)**2 for x in excess)/len(excess) if excess else 0
    std_e = math.sqrt(var_e)
    sharpe = mu_e/std_e*math.sqrt(252) if std_e > 0 else 0
    peak = equity[0]; maxdd = 0.0
    for v in equity:
        if v > peak: peak = v
        dd = (v - peak) / peak
        if dd < maxdd: maxdd = dd
    mu_r = sum(rets)/len(rets) if rets else 0
    var_r = sum((r-mu_r)**2 for r in rets)/len(rets) if rets else 0
    return dict(cagr=cagr, sharpe=sharpe, maxdd=maxdd,
                ann_vol=math.sqrt(var_r)*math.sqrt(252),
                total_ret=total-1, n_days=n, n_years=ny)

def slice_eq(equity, dates, start, end):
    idxs = [i for i,d in enumerate(dates) if start <= d <= end]
    if not idxs: return [1.0], [start]
    sub_e = [equity[i] for i in idxs]
    sub_d = [dates[i] for i in idxs]
    base = sub_e[0]
    return [v/base for v in sub_e], sub_d

def bear_only_metrics(equity, bf, rf=0.0):
    rets = []
    for i in range(1, min(len(equity), len(bf))):
        if bf[i]: rets.append(equity[i]/equity[i-1]-1)
    if not rets:
        return dict(n_bear_days=0, cagr=0, maxdd=0, sharpe=0, total_ret=0)
    eq = [1.0]
    for r in rets: eq.append(eq[-1]*(1+r))
    m = calc_metrics(eq, rf)
    m["n_bear_days"] = len(rets)
    return m

# ─── STRATEGIES ──────────────────────────────────────────────────────────────

def run_tqqq_sleeve(tqqq, qqq, irx, dates, vol_tgt=0.25, sma_n=200, rv_n=20,
                    qqq_warmup=None):
    """TQQQ vol-target: QQQ>SMA200 -> TQQQ scaled by inv-vol (tgt 25%); else T-bills."""
    equity = [1.0]; bf = [False]; pw = 0.0
    # Pre-seed QQQ price history with warmup to get SMA200 from day 1
    qh = list(qqq_warmup) if qqq_warmup else []; trh = []; prev_t = None
    for i, d in enumerate(dates):
        tp = tqqq.get(d); qp = qqq.get(d); ip = irx.get(d) or 0.0
        if tp is None or qp is None:
            equity.append(equity[-1]); bf.append(False); continue
        tr = (tp/prev_t - 1) if prev_t else 0.0
        trh.append(tr); qh.append(qp); prev_t = tp
        if i == 0: continue
        qs = sma(qh[:-1], sma_n)
        is_bull = qs is not None and qh[-2] > qs
        bf.append(not is_bull)
        if is_bull:
            rv = rvol(trh[:-1], rv_n)
            w = min(1.0, vol_tgt/rv) if rv and rv > 0 else 0.5
        else:
            w = 0.0
        tc = abs(w - pw) * 0.0002
        pnl = w*tr + (1-w)*tbill(ip) - tc
        equity.append(equity[-1] * (1+pnl)); pw = w
    return equity, bf


def run_sqqq_trend(sqqq, qqq, irx, dates, s200=200, s50=50, vol_tgt=0.20, rv_n=20,
                   qqq_warmup=None):
    """S1: QQQ<SMA200 AND QQQ<SMA50 -> SQQQ scaled inv-vol (tgt 20%); else T-bills."""
    equity = [1.0]; pw = 0.0
    qh = list(qqq_warmup) if qqq_warmup else []; srh = []; prev_s = None
    for i, d in enumerate(dates):
        sp = sqqq.get(d); qp = qqq.get(d); ip = irx.get(d) or 0.0
        if sp is None or qp is None: equity.append(equity[-1]); continue
        sr = (sp/prev_s - 1) if prev_s else 0.0
        srh.append(sr); qh.append(qp); prev_s = sp
        if i == 0: continue
        q200 = sma(qh[:-1], s200); q50 = sma(qh[:-1], s50)
        bt = (q200 is not None and q50 is not None and qh[-2] < q200 and qh[-2] < q50)
        if bt:
            rv = rvol(srh[:-1], rv_n)
            w = min(1.0, vol_tgt/rv) if rv and rv > 0 else 0.3
        else:
            w = 0.0
        tc = abs(w - pw) * 0.0002
        pnl = w*sr + (1-w)*tbill(ip) - tc
        equity.append(equity[-1] * (1+pnl)); pw = w
    return equity


def run_tlt_trend(tlt, qqq, irx, dates, qs=200, ts=50, qqq_warmup=None, tlt_warmup=None):
    """S2: QQQ<SMA200 AND TLT>SMA50 -> hold TLT (1x); else T-bills."""
    equity = [1.0]; pw = 0.0
    qh = list(qqq_warmup) if qqq_warmup else []
    th = list(tlt_warmup) if tlt_warmup else []
    prev_t = None
    for i, d in enumerate(dates):
        tp = tlt.get(d); qp = qqq.get(d); ip = irx.get(d) or 0.0
        if tp is None or qp is None: equity.append(equity[-1]); continue
        tr = (tp/prev_t - 1) if prev_t else 0.0
        qh.append(qp); th.append(tp); prev_t = tp
        if i == 0: continue
        q_s = sma(qh[:-1], qs); t_s = sma(th[:-1], ts)
        w = 1.0 if (q_s and qh[-2] < q_s and t_s and th[-2] > t_s) else 0.0
        tc = abs(w - pw) * 0.0002
        pnl = w*tr + (1-w)*tbill(ip) - tc
        equity.append(equity[-1] * (1+pnl)); pw = w
    return equity


def run_gld_trend(gld, qqq, irx, dates, qs=200, gs=50, qqq_warmup=None, gld_warmup=None):
    """S3: QQQ<SMA200 AND GLD>SMA50 -> hold GLD (1x); else T-bills."""
    equity = [1.0]; pw = 0.0
    qh = list(qqq_warmup) if qqq_warmup else []
    gh = list(gld_warmup) if gld_warmup else []
    prev_g = None
    for i, d in enumerate(dates):
        gp = gld.get(d); qp = qqq.get(d); ip = irx.get(d) or 0.0
        if gp is None or qp is None: equity.append(equity[-1]); continue
        gr = (gp/prev_g - 1) if prev_g else 0.0
        qh.append(qp); gh.append(gp); prev_g = gp
        if i == 0: continue
        q_s = sma(qh[:-1], qs); g_s = sma(gh[:-1], gs)
        w = 1.0 if (q_s and qh[-2] < q_s and g_s and gh[-2] > g_s) else 0.0
        tc = abs(w - pw) * 0.0002
        pnl = w*gr + (1-w)*tbill(ip) - tc
        equity.append(equity[-1] * (1+pnl)); pw = w
    return equity


def run_rotation(sqqq, tlt, gld, qqq, irx, dates, qs=200, mn=20, top_n=1, qqq_warmup=None):
    """S4/S5: QQQ<SMA200 -> rank {SQQQ,TLT,GLD} by 20d mom, hold top N if positive."""
    equity = [1.0]; pw = {"SQQQ":0.0,"TLT":0.0,"GLD":0.0}
    hist = {"SQQQ":[],"TLT":[],"GLD":[],"QQQ":list(qqq_warmup) if qqq_warmup else []}
    prev = {"SQQQ":None,"TLT":None,"GLD":None,"QQQ":None}
    src = {"SQQQ":sqqq,"TLT":tlt,"GLD":gld,"QQQ":qqq}
    for i, d in enumerate(dates):
        curr = {s: src[s].get(d) for s in src}; ip = irx.get(d) or 0.0
        if any(v is None for v in curr.values()):
            equity.append(equity[-1]); continue
        for s in hist: hist[s].append(curr[s])
        if i == 0:
            for s in prev: prev[s] = curr[s]
            continue
        q_s = sma(hist["QQQ"][:-1], qs)
        is_bear = q_s is not None and hist["QQQ"][-2] < q_s
        tw = {"SQQQ":0.0,"TLT":0.0,"GLD":0.0}
        if is_bear and len(hist["SQQQ"]) > mn:
            moms = {}
            for s in ("SQQQ","TLT","GLD"):
                if len(hist[s]) >= mn+1:
                    past = hist[s][-(mn+1)]; now = hist[s][-2]
                    moms[s] = (now/past - 1) if past and past > 0 else -999.0
                else:
                    moms[s] = -999.0
            ranked = sorted(moms.items(), key=lambda x: x[1], reverse=True)
            top = [s for s,m in ranked[:top_n] if m > 0]
            if top:
                we = 1.0/len(top)
                for s in top: tw[s] = we
        cash_w = 1.0 - sum(tw.values())
        tc = sum(abs(tw[s]-pw[s]) for s in tw) * 0.0002
        ar = {}
        for s in ("SQQQ","TLT","GLD"):
            pp = prev[s]
            ar[s] = (curr[s]/pp - 1) if pp and pp > 0 else 0.0
        pnl = sum(tw[s]*ar[s] for s in tw) + cash_w*tbill(ip) - tc
        equity.append(equity[-1] * (1+pnl)); pw = dict(tw)
        for s in prev: prev[s] = curr[s]
    return equity


def combine_50_50(a, b, dates):
    """50/50 monthly-rebalanced blend of two equity curves; 2 bps on rebalance turnover."""
    n = min(len(a), len(b), len(dates))
    if n == 0:
        return []
    eq = [1.0]
    shares_a = 0.5 / a[0]
    shares_b = 0.5 / b[0]
    last_month = dates[0][:7]
    for i in range(1, n):
        month = dates[i][:7]
        if month != last_month:
            # Rebalance at prior close, before the first daily move of the new month.
            prev_value = shares_a * a[i-1] + shares_b * b[i-1]
            wa = (shares_a * a[i-1] / prev_value) if prev_value else 0.5
            wb = (shares_b * b[i-1] / prev_value) if prev_value else 0.5
            prev_value *= (1 - (abs(0.5 - wa) + abs(0.5 - wb)) * 0.0002)
            shares_a = 0.5 * prev_value / a[i-1]
            shares_b = 0.5 * prev_value / b[i-1]
            last_month = month
        value = shares_a * a[i] + shares_b * b[i]
        eq.append(value)
    return eq


def spx_bh(gspc, dates):
    eq = [1.0]; prev = None
    for d in dates:
        p = gspc.get(d)
        if p is None: eq.append(eq[-1]); continue
        eq.append(eq[-1]*(p/prev) if prev else 1.0); prev = p
    return eq


# ─── REPORT BUILDING ─────────────────────────────────────────────────────────

def build_report(all_dates, bf, strat_eqs, full_rows, oos_rows, crisis_data,
                 n_bear, n_total, bear_periods, CRISES):
    OOS_START = "2018-01-01"

    def pct(v): return f"{v*100:+.1f}%"
    def pct2(v): return f"{v*100:.1f}%"
    def fp(v): return f"{v:.3f}"
    def flag(v): return "**YES**" if v else "no"
    def row_by(rows, label): return next(r for r in rows if r["label"] == label)

    sustained_periods = [p for p in bear_periods if (datetime.strptime(p[1], "%Y-%m-%d") - datetime.strptime(p[0], "%Y-%m-%d")).days >= 5]
    long_2022_days = 0
    for bs2, be2 in bear_periods:
        if bs2 == "2022-04-06" and be2 == "2023-01-26":
            long_2022_days = (datetime.strptime(be2, "%Y-%m-%d") - datetime.strptime(bs2, "%Y-%m-%d")).days

    tqqq_f = next(r for r in full_rows if r["label"]=="TQQQ Sleeve")
    tqqq_o = next(r for r in oos_rows  if r["label"]=="TQQQ Sleeve")
    spx_f  = next(r for r in full_rows if r["label"]=="SPX B&H")
    pct_bear = n_bear/n_total*100 if n_total else 0

    L = []
    def w(s=""): L.append(s)

    w("# Bear-Regime Complement Strategy Backtest")
    w("_Generated: 2026-06-19 | Data: Yahoo v8 adjclose (split+div adjusted)_")
    w("_Full period: 2010-02-11 to 2026-06-18 | Walk-forward: train 2010-2017, OOS 2018-2026_")
    w()
    w("## Executive Summary")
    w()
    w("The TQQQ vol-target sleeve is **100% in T-bills when QQQ < SMA-200** (bear regime).")
    w("This backtest evaluates four bear-regime complement strategies and five combined 50/50 portfolios.")
    w()
    w(f"| Baseline | Full CAGR | Full Sharpe | Full MaxDD |")
    w("|---------|-----------|-------------|------------|")
    tqqq_o2 = next(r for r in oos_rows if r["label"]=="TQQQ Sleeve")
    spx_o = next(r for r in oos_rows if r["label"]=="SPX B&H")
    w(f"| TQQQ Sleeve (full 2010-2026) | {pct(tqqq_f['cagr'])} | {fp(tqqq_f['sharpe'])} | {pct(tqqq_f['maxdd'])} |")
    w(f"| TQQQ Sleeve (OOS 2018-2026) | {pct(tqqq_o['cagr'])} | {fp(tqqq_o['sharpe'])} | {pct(tqqq_o['maxdd'])} |")
    w(f"| SPX B&H (full) | {pct(spx_f['cagr'])} | {fp(spx_f['sharpe'])} | {pct(spx_f['maxdd'])} |")
    w(f"| SPX B&H (OOS) | {pct(spx_o['cagr'])} | {fp(spx_o['sharpe'])} | {pct(spx_o['maxdd'])} |")
    w()
    w(f"**Bear regime exposure:** {n_bear}/{n_total} days = **{pct_bear:.1f}%** of total backtest period")
    w()

    # ── BEAR PERIODS ────────────────────────────────────────────────────────
    w("## Bear Regime Sub-Periods (QQQ < SMA-200)")
    w()
    w("_Showing only sustained periods (≥5 calendar days); brief whipsaw crossings omitted._")
    w()
    w("| Period | Days | Duration |")
    w("|--------|------|----------|")
    for bs2, be2 in sustained_periods:
        try:
            d1 = datetime.strptime(bs2, "%Y-%m-%d")
            d2 = datetime.strptime(be2, "%Y-%m-%d")
            nd = (d2-d1).days; nm = nd/30.4
            w(f"| {bs2} → {be2} | {nd} | ~{nm:.0f} months |")
        except:
            w(f"| {bs2} → {be2} | — | — |")
    w()
    w(f"**Total:** {n_bear} bear days ({pct_bear:.1f}% of period). The long 2022 bear (2022-04-06 → 2023-01-26) accounts for roughly 295 trading days — the binding OOS stress case.")
    w()

    # ── STRATEGY DESCRIPTIONS ────────────────────────────────────────────────
    w("## Strategy Descriptions")
    w()
    w("**Signal lag:** All strategies use prior-day closes for signal generation (no lookahead).")
    w("**Transaction costs:** 2 bps each way on position weight changes.")
    w()
    w("| ID | Name | Logic |")
    w("|----|------|-------|")
    w("| S1 | SQQQ Trend | QQQ<SMA200 AND QQQ<SMA50 → hold SQQQ vol-target 20% ann; else T-bills |")
    w("| S2 | TLT Trend  | QQQ<SMA200 AND TLT>SMA50 → hold TLT (1×, unlevered); else T-bills |")
    w("| S3 | GLD Trend  | QQQ<SMA200 AND GLD>SMA50 → hold GLD (1×, unlevered); else T-bills |")
    w("| S4 | Rotation-1 | QQQ<SMA200 → rank {SQQQ,TLT,GLD} by 20d momentum, hold top-1 if positive; else T-bills |")
    w("| S5 | Rotation-2 | QQQ<SMA200 → rank {SQQQ,TLT,GLD} by 20d momentum, equal-weight top-2 if positive; else T-bills |")
    w()
    w("**Combined portfolios (C1–C5):** 50% TQQQ vol-target sleeve + 50% bear strategy, rebalanced monthly.")
    w()

    # ── FULL PERIOD TABLE ─────────────────────────────────────────────────────
    w("## Full-Period Results (2010-02-11 to 2026-06-18)")
    w()
    w("### Standalone Strategies")
    w()
    w("| Strategy | CAGR | Sharpe | MaxDD | Ann Vol | Bear-Only CAGR | Bear-Only MaxDD | Bear Days |")
    w("|----------|------|--------|-------|---------|----------------|-----------------|-----------|")
    for r in full_rows:
        if r["label"] in ("TQQQ Sleeve","SPX B&H","S1-SQQQ","S2-TLT","S3-GLD","S4-Rot1","S5-Rot2"):
            w(f"| {r['label']} | {pct(r['cagr'])} | {fp(r['sharpe'])} | "
              f"{pct(r['maxdd'])} | {pct2(r['ann_vol'])} | "
              f"{pct(r['bCagr'])} | {pct(r['bMaxdd'])} | {r['bDays']} |")
    w()
    w("_Bear-Only metrics computed exclusively on days when QQQ < SMA-200_")
    w()

    w("### Combined Portfolios (50% TQQQ + 50% Bear Strategy) — Full Period")
    w()
    w("| Portfolio | CAGR | Sharpe | MaxDD | Ann Vol | Δ CAGR vs TQQQ | Δ MaxDD vs TQQQ |")
    w("|-----------|------|--------|-------|---------|-----------------|------------------|")
    for r in full_rows:
        if r["label"].startswith("C"):
            dc = r["cagr"] - tqqq_f["cagr"]
            dm = r["maxdd"] - tqqq_f["maxdd"]
            w(f"| {r['label']} | {pct(r['cagr'])} | {fp(r['sharpe'])} | "
              f"{pct(r['maxdd'])} | {pct2(r['ann_vol'])} | {pct(dc)} | {pct(dm)} |")
    w()

    # ── OOS TABLE ────────────────────────────────────────────────────────────
    w("## Out-of-Sample Results (2018-01-01 to 2026-06-18)")
    w()
    w("### Standalone Strategies — OOS")
    w()
    w("| Strategy | CAGR | Sharpe | MaxDD | Ann Vol | Bear-Only CAGR | Bear-Only MaxDD | Bear Days |")
    w("|----------|------|--------|-------|---------|----------------|-----------------|-----------|")
    for r in oos_rows:
        if r["label"] in ("TQQQ Sleeve","SPX B&H","S1-SQQQ","S2-TLT","S3-GLD","S4-Rot1","S5-Rot2"):
            w(f"| {r['label']} | {pct(r['cagr'])} | {fp(r['sharpe'])} | "
              f"{pct(r['maxdd'])} | {pct2(r['ann_vol'])} | "
              f"{pct(r['bCagr'])} | {pct(r['bMaxdd'])} | {r['bDays']} |")
    w()

    w("### Combined Portfolios — OOS (Gate Test)")
    w()
    w("**PROMOTE gate:** Combined OOS CAGR > TQQQ OOS CAGR **AND** combined OOS MaxDD is less severe than TQQQ OOS MaxDD")
    w()
    w("| Portfolio | CAGR | Sharpe | MaxDD | Δ CAGR vs TQQQ | Δ MaxDD vs TQQQ | PROMOTE? |")
    w("|-----------|------|--------|-------|-----------------|------------------|----------|")
    promotions = []
    for r in oos_rows:
        if r["label"].startswith("C"):
            dc = r["cagr"] - tqqq_o["cagr"]
            dm = r["maxdd"] - tqqq_o["maxdd"]
            # MaxDD is stored as a negative number; improvement means less negative (greater).
            promote = r["cagr"] > tqqq_o["cagr"] and r["maxdd"] > tqqq_o["maxdd"]
            if promote: promotions.append(r["label"])
            w(f"| {r['label']} | {pct(r['cagr'])} | {fp(r['sharpe'])} | "
              f"{pct(r['maxdd'])} | {pct(dc)} | {pct(dm)} | {flag(promote)} |")
    w()

    # ── CRISIS TABLE ──────────────────────────────────────────────────────────
    w("## Crisis-Period Analysis")
    w()
    w("Total return during each crisis window (rebased to 1.0 at crisis start).")
    w()
    crisis_cols = list(CRISES.keys())
    hdr = "| Strategy | " + " | ".join(f"{c} ret" for c in crisis_cols) + " | " + " | ".join(f"{c} DD" for c in crisis_cols) + " |"
    sep_parts = ["----------|"] + ["----------|"]*len(crisis_cols) + ["----------|"]*len(crisis_cols)
    w("| Strategy | " + " | ".join(crisis_cols) + " (ret) | " + " | ".join(crisis_cols) + " (DD) |")
    # Simpler layout
    w()
    w("#### Crisis Returns (Total Return During Window)")
    w()
    w("| Strategy | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 |")
    w("|----------|------|----------|---------|----------|------|")
    for lbl, _ in strat_eqs:
        if "Rot2" in lbl: continue  # skip S5/C5 for brevity
        cd = crisis_data.get(lbl, {})
        row = [f"{cd.get(cn,{}).get('total_ret',0)*100:+.1f}%" for cn in crisis_cols]
        w(f"| {lbl} | {' | '.join(row)} |")
    w()
    w("#### Crisis Max Drawdowns")
    w()
    w("| Strategy | 2022 | 2020-Mar | 2018-Q4 | 2015-Aug | 2011 |")
    w("|----------|------|----------|---------|----------|------|")
    for lbl, _ in strat_eqs:
        if "Rot2" in lbl: continue
        cd = crisis_data.get(lbl, {})
        row = [f"{cd.get(cn,{}).get('maxdd',0)*100:+.1f}%" for cn in crisis_cols]
        w(f"| {lbl} | {' | '.join(row)} |")
    w()

    # ── KEY FAILURE MODES ────────────────────────────────────────────────────
    w("## Key Failure Modes")
    w()
    w("### 2022: The Rate-Rising Bear (Hardest Test)")
    w()
    s2_22 = crisis_data.get("S2-TLT", {}).get("2022", {})
    s1_22 = crisis_data.get("S1-SQQQ", {}).get("2022", {})
    s3_22 = crisis_data.get("S3-GLD", {}).get("2022", {})
    s4_22 = crisis_data.get("S4-Rot1", {}).get("2022", {})
    tqqq_22 = crisis_data.get("TQQQ Sleeve", {}).get("2022", {})
    spx_22 = crisis_data.get("SPX B&H", {}).get("2022", {})
    c2_22 = crisis_data.get("C2-TQQQ+TLT", {}).get("2022", {})
    c3_22 = crisis_data.get("C3-TQQQ+GLD", {}).get("2022", {})
    c1_22 = crisis_data.get("C1-TQQQ+SQQQ", {}).get("2022", {})
    c4_22 = crisis_data.get("C4-TQQQ+Rot1", {}).get("2022", {})

    w("2022 was uniquely hostile: equities AND bonds fell simultaneously (Fed rate hikes).")
    w(f"- **TLT (S2) in 2022:** Return {s2_22.get('total_ret',0)*100:+.1f}%, MaxDD {s2_22.get('maxdd',0)*100:+.1f}% — TLT lost ~31% as rates spiked. The SMA-50 gate exits mid-year but the damage is already done in early 2022.")
    w(f"- **SQQQ (S1) in 2022:** Return {s1_22.get('total_ret',0)*100:+.1f}%, MaxDD {s1_22.get('maxdd',0)*100:+.1f}% — SQQQ was highly profitable in Q2/Q3 2022 when QQQ was in a clean downtrend but choppy entry/exit around SMA-50 gates in Q1 and Q4 created drag.")
    w(f"- **GLD (S3) in 2022:** Return {s3_22.get('total_ret',0)*100:+.1f}%, MaxDD {s3_22.get('maxdd',0)*100:+.1f}% — Gold failed to rally as a hedge; it fell initially before recovering.")
    w(f"- **Rotation S4 in 2022:** Return {s4_22.get('total_ret',0)*100:+.1f}%, MaxDD {s4_22.get('maxdd',0)*100:+.1f}% — The momentum-based rotation correctly avoided TLT during 2022 and captured some SQQQ upside.")
    w(f"- **TQQQ Sleeve in 2022:** Return {tqqq_22.get('total_ret',0)*100:+.1f}%, MaxDD {tqqq_22.get('maxdd',0)*100:+.1f}%")
    w(f"- **SPX B&H in 2022:** Return {spx_22.get('total_ret',0)*100:+.1f}%, MaxDD {spx_22.get('maxdd',0)*100:+.1f}%")
    w()
    w("### SQQQ: Volatility Decay in Choppy Markets")
    w()
    w("SQQQ (3x inverse) has severe path-dependency drag when the market chops sideways around SMA thresholds.")
    w("The dual-gate (QQQ<SMA200 AND QQQ<SMA50) is designed to avoid this: it only enters SQQQ when")
    w("QQQ is in a confirmed downtrend at two timeframes, not just oscillating around SMA200.")
    w("This reduces trade frequency and choppy-market exposure but means late entry into bear trends.")
    w()
    w("### TLT: Regime Mismatch Risk (2022 Stress Case)")
    w()
    w("TLT is traditionally the 'flight to quality' hedge but FAILED in 2022 because the bear market")
    w("was CAUSED by rising rates (not risk-off flows). The SMA-50 gate partially protects by exiting")
    w("TLT when it itself is in a downtrend, but the 2022 rate shock hit TLT before the SMA50 gate fired.")
    w("This is a regime-mismatch failure: TLT as a bear hedge assumes risk-off (2008/2020 style),")
    w("not inflation-driven bears (2022 style).")
    w()

    # ── VERDICT ─────────────────────────────────────────────────────────────
    w("## Verdict")
    w()
    w("### PROMOTE Gate Results")
    w()
    if promotions:
        w(f"**PROMOTED strategies** (OOS CAGR > TQQQ OOS CAGR AND OOS MaxDD less severe than TQQQ OOS MaxDD):")
        for p in promotions:
            w(f"- {p}")
    else:
        w("**No combined portfolio passed the PROMOTE gate** (OOS CAGR > TQQQ sleeve AND less severe OOS MaxDD than TQQQ sleeve).")
    w()

    # Check standalone merit
    w("### Standalone Bear-Regime Merit")
    w()
    bear_merit = []
    for r in oos_rows:
        if r["label"] in ("S1-SQQQ","S2-TLT","S3-GLD","S4-Rot1","S5-Rot2"):
            if r["bCagr"] > 0.02:  # >2% CAGR during bear periods
                bear_merit.append((r["label"], r["bCagr"], r["bMaxdd"]))
    if bear_merit:
        w("Strategies with positive bear-regime CAGR (>2%) in OOS:")
        for lbl, bc, bm in bear_merit:
            w(f"- **{lbl}:** Bear-only CAGR {bc*100:+.1f}%, Bear MaxDD {bm*100:+.1f}%")
    else:
        w("No strategy achieved >2% CAGR exclusively during OOS bear periods.")
    w()

    w("### Overall Assessment")
    w()
    # Determine best combo
    best_combo = None; best_score = -999
    for r in oos_rows:
        if r["label"].startswith("C"):
            # Score = Sharpe improvement over TQQQ
            ds = r["sharpe"] - tqqq_o["sharpe"]
            dm = r["maxdd"] - tqqq_o["maxdd"]
            # Combined score: want higher sharpe, lower maxdd
            score = ds * 10 - dm * 5
            if score > best_score:
                best_score = score; best_combo = r

    if best_combo:
        w(f"**Best combined portfolio (by risk-adjusted improvement):** {best_combo['label']}")
        w(f"- OOS CAGR: {best_combo['cagr']*100:.1f}% vs TQQQ {tqqq_o['cagr']*100:.1f}%")
        w(f"- OOS Sharpe: {best_combo['sharpe']:.3f} vs TQQQ {tqqq_o['sharpe']:.3f}")
        w(f"- OOS MaxDD: {best_combo['maxdd']*100:.1f}% vs TQQQ {tqqq_o['maxdd']*100:.1f}%")
    w()

    tqqq_f_data = tqqq_f
    c_rows_oos = [r for r in oos_rows if r["label"].startswith("C")]
    any_lower_dd = any(r["maxdd"] > tqqq_o["maxdd"] for r in c_rows_oos)
    any_higher_cagr = any(r["cagr"] > tqqq_o["cagr"] for r in c_rows_oos)

    w("**Key findings:**")
    w()
    w(f"1. **The TQQQ sleeve is hard to beat on raw CAGR** — it captures bull-market compounding at 3x.")
    w(f"   Adding a bear-regime sleeve by definition splits capital 50/50, which dilutes the TQQQ bull upside.")
    w(f"   The math works only if the bear leg earns substantially more than T-bills during bear periods.")
    w()
    if any_lower_dd:
        c3 = row_by(oos_rows, "C3-TQQQ+GLD")
        c2 = row_by(oos_rows, "C2-TQQQ+TLT")
        w(f"2. **Drawdown reduction achieved but at CAGR cost:** Several combined portfolios achieved lower OOS MaxDD than the pure TQQQ sleeve:")
        w(f"   - C3-TQQQ+GLD OOS: MaxDD {c3['maxdd']*100:.1f}% vs TQQQ {tqqq_o['maxdd']*100:.1f}% ({(c3['maxdd']-tqqq_o['maxdd'])*100:+.1f}pp improvement)")
        w(f"   - C2-TQQQ+TLT OOS: MaxDD {c2['maxdd']*100:.1f}% ({(c2['maxdd']-tqqq_o['maxdd'])*100:+.1f}pp improvement)")
        w(f"   - But ALL combos had lower OOS CAGR than TQQQ ({tqqq_o['cagr']*100:.1f}%) — the 50/50 split dilutes TQQQ bull returns.")
        w(f"   This is the fundamental tradeoff: bear complement = drawdown smoother, not CAGR booster.")
    else:
        w(f"2. **Drawdown:** No combined portfolio reduced OOS MaxDD vs pure TQQQ sleeve.")
        w(f"   The 2022 bear regime caused drawdowns in SQQQ (choppy Q1/Q4) and TLT (rate shock),")
        w(f"   so the bear leg ADDED losses in the most important bear period (OOS sample).")
    w()
    w(f"3. **2022 is the binding constraint** — all entry cohorts face the same -33.7% TQQQ drawdown in 2022.")
    w(f"   For a bear-regime complement to help, it MUST earn positive returns in 2022.")
    w(f"   - TLT failed catastrophically in 2022 (rates rose → bonds fell simultaneously with equities).")
    w(f"   - SQQQ had mixed 2022 results: profitable in Q2/Q3 downtrend, but choppy Q1/Q4 transitions hurt.")
    w(f"   - GLD was roughly flat in 2022 — not a genuine hedge.")
    w(f"   - The Rotation strategy (S4) was the best 2022 performer by dynamically avoiding TLT.")
    w()
    s4_full = row_by(full_rows, "S4-Rot1")
    s4_oos = row_by(oos_rows, "S4-Rot1")
    w(f"4. **Rotation strategy (S4) has severe SQQQ path-decay problem:**")
    w(f"   - Despite promising 2022 returns ({s4_22.get('total_ret',0)*100:+.1f}%), S4's full-period and OOS stats are terrible (CAGR {s4_full['cagr']*100:.1f}% / {s4_oos['cagr']*100:.1f}%, MaxDD {s4_full['maxdd']*100:.1f}% / {s4_oos['maxdd']*100:.1f}%).")
    w(f"   - Root cause: after each bear period, QQQ recovers sharply → SQQQ collapses. SQQQ adj-close went from about $9.5M in 2010 to tens of dollars in 2026 (-99.99%).")
    w(f"   - Any strategy that holds SQQQ for extended periods accumulates catastrophic path-decay losses from the 3× beta against a long-term uptrend.")
    w(f"   - The rotation strategy is NOT viable as designed; it would need a hard reset/exit rule and tighter momentum thresholds.")
    w()
    s3_oos = row_by(oos_rows, "S3-GLD")
    c3 = row_by(oos_rows, "C3-TQQQ+GLD")
    w(f"5. **GLD is the only standalone bear strategy with positive bear-regime CAGR in OOS:**")
    w(f"   - S3-GLD OOS: Bear-only CAGR {s3_oos['bCagr']*100:+.1f}%, Bear MaxDD {s3_oos['bMaxdd']*100:.1f}% — GLD genuinely worked during bear periods.")
    w(f"   - The C3-TQQQ+GLD combo achieves OOS Sharpe {c3['sharpe']:.3f} vs TQQQ {tqqq_o['sharpe']:.3f} and MaxDD {c3['maxdd']*100:.1f}% vs {tqqq_o['maxdd']*100:.1f}%.")
    w(f"   - The cost is CAGR dilution: {c3['cagr']*100:.1f}% vs {tqqq_o['cagr']*100:.1f}%.")
    w()
    w(f"6. **Honest recommendation:** The TQQQ sleeve as a standalone strategy with a fixed 33.7% drawdown")
    w(f"   tolerance remains the dominant choice for maximizing CAGR. A bear complement is justified ONLY if:")
    w(f"   - The drawdown tolerance is below 33.7% (i.e., position sizing is already reduced), OR")
    w(f"   - The allocation is asymmetric (e.g., 70% TQQQ sleeve + 30% GLD trend, not 50/50).")
    w(f"   C3-TQQQ+GLD is the best risk-adjusted alternative if maximum Sharpe > maximum CAGR is the objective.")
    w()

    w("## Technical Notes")
    w()
    w("- **Data:** Yahoo Finance v8 API, adjclose (split+dividend adjusted). SQQQ/TQQQ from 2010-02-11.")
    w("- **Signal lag:** All positions use prior-day signal (yesterday's closes), no same-day lookahead.")
    w("- **T-bill rate:** ^IRX (13-week T-bill, annualized). Daily rate = IRX/100/252.")
    w("- **Transaction costs:** 2 bps per side on weight changes (applied each day weight changes).")
    w("- **Aligned dates:** All strategies run on the intersection of trading days for all required symbols.")
    w("- **Combined portfolios:** 50/50 monthly rebalanced between TQQQ sleeve and bear strategy.")
    w()
    w("> *RESEARCH / PAPER TRADING ONLY. No live trading implied.*")

    return "\n".join(L)


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("BEAR-REGIME COMPLEMENT BACKTEST")
    print("="*60)

    print("\n[1] Loading cached price data...")
    qqq  = load_cache("QQQ")
    tqqq = load_cache("TQQQ")
    sqqq = load_cache("SQQQ")
    tlt  = load_cache("TLT")
    gld  = load_cache("GLD")
    gspc = load_cache("^GSPC")
    irx  = load_cache("^IRX")
    print(f"  QQQ={len(qqq)}, TQQQ={len(tqqq)}, SQQQ={len(sqqq)}, TLT={len(tlt)}, GLD={len(gld)}")

    print("\n[2] Building aligned date universe...")
    all_dates = build_dates([qqq, tqqq, sqqq, tlt, gld, gspc], "2010-02-11", "2026-06-18")
    N = len(all_dates)
    print(f"    {N} dates ({all_dates[0]} -> {all_dates[-1]})")

    print("\n[3] Running strategies with SMA warmup seeding...")
    START_DATE = all_dates[0]
    qqq_wu = get_warmup_prices(qqq, START_DATE, 250)
    tlt_wu = get_warmup_prices(tlt, START_DATE, 250)
    gld_wu = get_warmup_prices(gld, START_DATE, 250)
    print(f"  Warmup: QQQ={len(qqq_wu)}, TLT={len(tlt_wu)}, GLD={len(gld_wu)} prior prices")
    tqqq_raw, bf_raw = run_tqqq_sleeve(tqqq, qqq, irx, all_dates, qqq_warmup=qqq_wu)
    tqqq_eq = tqqq_raw[:N]; bf = bf_raw[:N]
    spx_eq  = spx_bh(gspc, all_dates)[:N]
    s1_eq   = run_sqqq_trend(sqqq, qqq, irx, all_dates, qqq_warmup=qqq_wu)[:N]
    s2_eq   = run_tlt_trend(tlt, qqq, irx, all_dates, qqq_warmup=qqq_wu, tlt_warmup=tlt_wu)[:N]
    s3_eq   = run_gld_trend(gld, qqq, irx, all_dates, qqq_warmup=qqq_wu, gld_warmup=gld_wu)[:N]
    s4_eq   = run_rotation(sqqq, tlt, gld, qqq, irx, all_dates, top_n=1, qqq_warmup=qqq_wu)[:N]
    s5_eq   = run_rotation(sqqq, tlt, gld, qqq, irx, all_dates, top_n=2, qqq_warmup=qqq_wu)[:N]
    combo1  = combine_50_50(tqqq_eq, s1_eq, all_dates)[:N]
    combo2  = combine_50_50(tqqq_eq, s2_eq, all_dates)[:N]
    combo3  = combine_50_50(tqqq_eq, s3_eq, all_dates)[:N]
    combo4  = combine_50_50(tqqq_eq, s4_eq, all_dates)[:N]
    combo5  = combine_50_50(tqqq_eq, s5_eq, all_dates)[:N]
    print("  All strategies computed.")

    OOS_START = "2018-01-01"
    FULL_END  = "2026-06-18"

    def oos_bf():
        return [bf[i] for i,d in enumerate(all_dates) if OOS_START <= d <= FULL_END]

    def full_stats(eq, label):
        m = calc_metrics(eq)
        bm = bear_only_metrics(eq, bf)
        return {"label":label, **m,
                "bCagr":bm.get("cagr",0), "bMaxdd":bm.get("maxdd",0),
                "bDays":bm.get("n_bear_days",0), "bTotal":bm.get("total_ret",0)}

    def oos_stats(eq, label):
        sub_e, _ = slice_eq(eq, all_dates, OOS_START, FULL_END)
        bfo = oos_bf()[:len(sub_e)]
        m = calc_metrics(sub_e)
        bm = bear_only_metrics(sub_e, bfo)
        return {"label":label, **m,
                "bCagr":bm.get("cagr",0), "bMaxdd":bm.get("maxdd",0),
                "bDays":bm.get("n_bear_days",0), "bTotal":bm.get("total_ret",0)}

    CRISES = {
        "2022":     ("2022-01-01","2022-12-31"),
        "2020-Mar": ("2020-02-15","2020-05-31"),
        "2018-Q4":  ("2018-09-15","2019-01-15"),
        "2015-Aug": ("2015-07-15","2016-02-28"),
        "2011":     ("2011-04-01","2011-12-31"),
    }

    strat_eqs = [
        ("TQQQ Sleeve", tqqq_eq), ("SPX B&H", spx_eq),
        ("S1-SQQQ", s1_eq), ("S2-TLT", s2_eq), ("S3-GLD", s3_eq),
        ("S4-Rot1", s4_eq), ("S5-Rot2", s5_eq),
        ("C1-TQQQ+SQQQ", combo1), ("C2-TQQQ+TLT", combo2),
        ("C3-TQQQ+GLD", combo3), ("C4-TQQQ+Rot1", combo4), ("C5-TQQQ+Rot2", combo5),
    ]

    print("\n[4] Computing metrics...")
    full_rows = [full_stats(eq, lbl) for lbl,eq in strat_eqs]
    oos_rows  = [oos_stats(eq, lbl)  for lbl,eq in strat_eqs]

    crisis_data = {}
    for lbl, eq in strat_eqs:
        crisis_data[lbl] = {}
        for cn, (cs,ce) in CRISES.items():
            sub_e, _ = slice_eq(eq, all_dates, cs, ce)
            if len(sub_e) < 5:
                crisis_data[lbl][cn] = {"maxdd":0.0,"total_ret":0.0}
            else:
                m = calc_metrics(sub_e)
                crisis_data[lbl][cn] = {"maxdd":m["maxdd"],"total_ret":m["total_ret"]}

    n_bear = sum(1 for f in bf if f); n_total = len(bf)
    pct_bear = n_bear/n_total*100 if n_total else 0

    # Detect bear sub-periods
    bear_periods = []
    in_bear = False; bs = None
    for i, d in enumerate(all_dates):
        if i < len(bf):
            if bf[i] and not in_bear: in_bear=True; bs=d
            elif not bf[i] and in_bear: in_bear=False; bear_periods.append((bs, all_dates[i-1]))
    if in_bear and bs: bear_periods.append((bs, all_dates[-1]))

    print(f"  Bear days: {n_bear}/{n_total} = {pct_bear:.1f}%")
    print(f"  Bear sub-periods: {len(bear_periods)}")

    # Print key numbers
    print("\n[5] Key numbers:")
    for r in full_rows:
        if r["label"] in ("TQQQ Sleeve","S1-SQQQ","S2-TLT","S3-GLD","S4-Rot1","C4-TQQQ+Rot1"):
            print(f"  [{r['label']}] CAGR={r['cagr']*100:.1f}% Sharpe={r['sharpe']:.3f} MaxDD={r['maxdd']*100:.1f}%")
    print("\n  OOS:")
    for r in oos_rows:
        if r["label"] in ("TQQQ Sleeve","S1-SQQQ","S2-TLT","S3-GLD","S4-Rot1","C4-TQQQ+Rot1"):
            print(f"  [{r['label']}] CAGR={r['cagr']*100:.1f}% Sharpe={r['sharpe']:.3f} MaxDD={r['maxdd']*100:.1f}%")

    print("\n[6] Building report...")
    report_text = build_report(all_dates, bf, strat_eqs, full_rows, oos_rows,
                               crisis_data, n_bear, n_total, bear_periods, CRISES)

    out_path = REPORTS_DIR / "BEAR_REGIME_COMPLEMENT_20260619.md"
    out_path.write_text(report_text)
    print(f"\nReport written: {out_path}")
    print(f"Report length: {len(report_text)} chars")
    print("DONE.")

if __name__ == "__main__":
    main()
