#!/usr/bin/env python3
"""FUNDAMENTALS-PIT QUALITY/VALUE cross-sectional composite (candidate research).

First genuinely orthogonal-to-OHLCV return engine this bench has tried. Point-in-time
fundamentals from SEC EDGAR (filed-date masked, no lookahead), ranked cross-sectionally
into a quality+value composite, monthly/quarterly rebalanced long-top-bucket equal-weight,
vs buy-and-hold SPY net of 2bps. Long/short spread also reported.

HONESTY RAILS: PIT-select on EDGAR filed date (asserted via lookahead canary); ranks from
PAST-only data; SPY on the SAME traded path; FULL continuous-span Sharpe; 2bps one-way cost
+ breakeven analysis; explicit survivorship-bias disclosure (universe=TODAY S&P100-ish).

Candidate/scratch -- touches NO runner/*.py, strategies/*, crontab, *.db, paper clock.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

WS = os.path.dirname(os.path.abspath(__file__))
EDGAR_DIR = os.path.join(WS, "data_cache", "edgar_fundamentals")
YAHOO = os.path.join(WS, "data_cache", "yahoo", "%s_parsed.json")
UA = "trading-bench-research azureuser@example.com"
OOS_SPLIT = "2018-12-31"
TRADING_DAYS = 252.0
os.makedirs(EDGAR_DIR, exist_ok=True)

CONCEPTS = [
    "NetIncomeLoss", "StockholdersEquity", "Assets", "Liabilities",
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "GrossProfit", "AssetsCurrent", "LiabilitiesCurrent",
    "CashAndCashEquivalentsAtCarryingValue", "LongTermDebtNoncurrent",
    "CostOfRevenue", "CostOfGoodsAndServicesSold",
]

_LAST_FETCH = [0.0]

def _throttle(min_spacing=0.13):
    dt = time.time() - _LAST_FETCH[0]
    if dt < min_spacing:
        time.sleep(min_spacing - dt)
    _LAST_FETCH[0] = time.time()

def fetch_concept(ticker, cik, concept):
    safe = ticker.replace("/", "_").replace(".", "_")
    cache = os.path.join(EDGAR_DIR, safe + "__" + concept + ".json")
    if os.path.exists(cache) and os.path.getsize(cache) >= 2:
        try:
            return json.load(open(cache))
        except Exception:
            pass
    url = "https://data.sec.gov/api/xbrl/companyconcept/CIK" + cik + "/us-gaap/" + concept + ".json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    facts = []
    try:
        _throttle()
        r = urllib.request.urlopen(req, timeout=40)
        raw = r.read().decode("utf-8", "replace")
        r.close()
        payload = json.loads(raw)
        units = payload.get("units", {})
        bucket = units.get("USD")
        if not bucket:
            bucket = units.get("USD/shares")
        if not bucket:
            for k, v in units.items():
                bucket = v
                break
        facts = bucket or []
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.stderr.write("[edgar] " + ticker + " " + concept + " HTTP " + str(e.code) + chr(10))
        facts = []
    except Exception as e:
        sys.stderr.write("[edgar] " + ticker + " " + concept + " ERR " + str(e) + chr(10))
        facts = []
    try:
        json.dump(facts, open(cache, "w"))
    except Exception:
        pass
    return facts

def _norm_facts(facts):
    rows = []
    for f in facts:
        filed = f.get("filed"); end = f.get("end"); val = f.get("val")
        fy = f.get("fy"); fp = f.get("fp")
        if filed and val is not None:
            rows.append((filed, end or "", fy or 0, fp or "", float(val)))
    rows.sort(key=lambda x: (x[0], x[1]))
    return rows

def pit_latest(rows, asof):
    best = None
    for filed, end, fy, fp, val in rows:
        if filed <= asof:
            if best is None or (filed, end) >= (best[0], best[1]):
                best = (filed, end, val)
        else:
            break
    if best is None:
        return None
    return (best[1], best[2])

def _filed_used(rows, asof):
    best = None
    for filed, end, fy, fp, val in rows:
        if filed <= asof:
            if best is None or (filed, end) >= (best[0], best[1]):
                best = (filed, end, val)
        else:
            break
    return best[0] if best else None

def _months_between(a, b):
    try:
        da = datetime.strptime(a, "%Y-%m-%d"); db = datetime.strptime(b, "%Y-%m-%d")
        return abs((db.year - da.year) * 12 + (db.month - da.month))
    except Exception:
        return 999.0

def pit_ttm_flow(rows, asof):
    avail = [(f, e, fy, fp, v) for (f, e, fy, fp, v) in rows if f <= asof]
    if not avail:
        return None
    by_end = {}
    for f, e, fy, fp, v in avail:
        if e not in by_end or f >= by_end[e][0]:
            by_end[e] = (f, fy, fp, v)
    latest_end = max(by_end.keys())
    fy_rows = [(e, vv[0], vv[1], vv[2], vv[3]) for e, vv in by_end.items() if vv[2] == "FY"]
    fy_rows.sort(key=lambda x: x[0])
    if fy_rows:
        fend = fy_rows[-1][0]; fval = fy_rows[-1][4]
        if _months_between(fend, latest_end) <= 15:
            return fval
    q_rows = [(e, vv[3]) for e, vv in by_end.items() if vv[2] in ("Q1", "Q2", "Q3", "Q4")]
    q_rows.sort(key=lambda x: x[0])
    if len(q_rows) >= 4:
        return sum(v for e, v in q_rows[-4:])
    return None

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

def load_raw_close(sym):
    path = YAHOO % sym
    if not os.path.exists(path):
        return {}
    rows = json.load(open(path))
    out = {}
    for r in rows:
        c = r.get("close")
        if c not in (None, 0):
            out[r["date"]] = float(c)
    return out

def asof_price(px, dates_sorted, asof):
    i = bisect.bisect_right(dates_sorted, asof) - 1
    if i < 0:
        return None
    return px[dates_sorted[i]]

def fetch_shares(ticker, cik):
    safe = ticker.replace("/", "_").replace(".", "_")
    cache = os.path.join(EDGAR_DIR, safe + "__shares.json")
    facts = None
    if os.path.exists(cache) and os.path.getsize(cache) >= 2:
        try:
            facts = json.load(open(cache))
        except Exception:
            facts = None
    if facts is None:
        url = ("https://data.sec.gov/api/xbrl/companyconcept/CIK" + cik +
               "/dei/EntityCommonStockSharesOutstanding.json")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            _throttle()
            r = urllib.request.urlopen(req, timeout=40)
            raw = r.read().decode("utf-8", "replace")
            r.close()
            payload = json.loads(raw)
            facts = payload.get("units", {}).get("shares", [])
        except urllib.error.HTTPError as e:
            facts = []
        except Exception:
            facts = []
        try:
            json.dump(facts, open(cache, "w"))
        except Exception:
            pass
    rows = []
    for f in (facts or []):
        filed = f.get("filed"); val = f.get("val")
        if filed and val:
            rows.append((filed, float(val)))
    rows.sort()
    return rows

def shares_asof(rows, asof):
    val = None
    for filed, v in rows:
        if filed <= asof:
            val = v
        else:
            break
    return val

def build_fundamentals(univ, verbose=True):
    data = {}
    n = len(univ)
    for i, (tkr, cik) in enumerate(univ.items()):
        rec = {}
        for concept in CONCEPTS:
            rec[concept] = _norm_facts(fetch_concept(tkr, cik, concept))
        rec["shares"] = fetch_shares(tkr, cik)
        data[tkr] = rec
        if verbose and (i % 10 == 0 or i == n - 1):
            sys.stderr.write("[fund] " + str(i + 1) + "/" + str(n) + " " + tkr + chr(10))
            sys.stderr.flush()
    return data

_CANARY = []

def pit_snapshot(rec, asof):
    out = {"max_filed": None}
    def stock(concept):
        rows = rec.get(concept, [])
        r = pit_latest(rows, asof)
        f = _filed_used(rows, asof)
        if f is not None:
            if out["max_filed"] is None or f > out["max_filed"]:
                out["max_filed"] = f
            if f > asof:
                _CANARY.append((concept, f, asof))
        return r[1] if r else None
    def flow(concept):
        rows = rec.get(concept, [])
        v = pit_ttm_flow(rows, asof)
        f = _filed_used(rows, asof)
        if f is not None:
            if out["max_filed"] is None or f > out["max_filed"]:
                out["max_filed"] = f
            if f > asof:
                _CANARY.append((concept, f, asof))
        return v
    out["equity"] = stock("StockholdersEquity")
    out["assets"] = stock("Assets")
    out["liabilities"] = stock("Liabilities")
    out["cash"] = stock("CashAndCashEquivalentsAtCarryingValue")
    out["ltd"] = stock("LongTermDebtNoncurrent")
    out["ni_ttm"] = flow("NetIncomeLoss")
    rev = flow("Revenues")
    if rev is None:
        rev = flow("RevenueFromContractWithCustomerExcludingAssessedTax")
    out["rev_ttm"] = rev
    out["gross_profit_ttm"] = flow("GrossProfit")
    cogs = flow("CostOfRevenue")
    if cogs is None:
        cogs = flow("CostOfGoodsAndServicesSold")
    out["cogs_ttm"] = cogs
    return out

def noa_from_snap(s):
    a = s.get("assets"); cash = s.get("cash"); liab = s.get("liabilities"); ltd = s.get("ltd")
    if a is None:
        return None
    op_assets = a - (cash or 0.0)
    op_liab = liab
    if op_liab is None:
        eq = s.get("equity")
        if eq is not None:
            op_liab = a - eq
        else:
            return None
    op_liab = op_liab - (ltd or 0.0)
    return op_assets - op_liab

def _yago(asof):
    y, m, d = asof.split("-")
    return "%04d-%s-%s" % (int(y) - 1, m, d)

def _median(xs):
    s = sorted(xs); n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

def _zscores(vals):
    items = []
    for k, v in vals.items():
        if v is None:
            continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            continue
        items.append((k, v))
    if len(items) < 5:
        return {}
    xs = [v for _, v in items]
    med = _median(xs)
    mad = _median([abs(v - med) for v in xs]) or 1e-9
    sd = 1.4826 * mad
    out = {}
    for k, v in items:
        z = (v - med) / sd
        if z > 3:
            z = 3.0
        if z < -3:
            z = -3.0
        out[k] = z
    return out

def compute_factors(data, univ_keys, asof, raw_close, px_dates):
    snaps = {}; noa_now = {}; noa_prev = {}; mktcap = {}
    yago = _yago(asof)
    for t in univ_keys:
        rec = data.get(t)
        if not rec:
            continue
        s = pit_snapshot(rec, asof)
        snaps[t] = s
        sh = shares_asof(rec.get("shares", []), asof)
        rc = raw_close.get(t, {}); rcd = px_dates.get(t, [])
        price = asof_price(rc, rcd, asof)
        if sh and price and sh > 0 and price > 0:
            mktcap[t] = sh * price
        noa_now[t] = noa_from_snap(s)
        noa_prev[t] = noa_from_snap(pit_snapshot(rec, yago))
    ep = {}; bp = {}; roe = {}; roa = {}; gprof = {}; lowlev = {}; lowacc = {}
    for t, s in snaps.items():
        mc = mktcap.get(t)
        ni = s.get("ni_ttm"); eq = s.get("equity"); a = s.get("assets")
        if mc and ni is not None:
            ep[t] = ni / mc
        if mc and eq is not None and eq > 0:
            bp[t] = eq / mc
        if ni is not None and eq and eq > 0:
            roe[t] = ni / eq
        if ni is not None and a and a > 0:
            roa[t] = ni / a
        gp = s.get("gross_profit_ttm")
        if gp is None:
            rev = s.get("rev_ttm"); cogs = s.get("cogs_ttm")
            if rev is not None and cogs is not None:
                gp = rev - cogs
        if gp is not None and a and a > 0:
            gprof[t] = gp / a
        if eq is not None and a and a > 0:
            lowlev[t] = eq / a
        nn = noa_now.get(t); npv = noa_prev.get(t)
        if nn is not None and npv is not None and a and a > 0:
            lowacc[t] = -((nn - npv) / a)
    z_ep = _zscores(ep); z_bp = _zscores(bp)
    z_roe = _zscores(roe); z_roa = _zscores(roa); z_gp = _zscores(gprof)
    z_lev = _zscores(lowlev); z_acc = _zscores(lowacc)
    out = {}
    for t in snaps:
        vparts = [z for z in (z_ep.get(t), z_bp.get(t)) if z is not None]
        qparts = [z for z in (z_roe.get(t), z_roa.get(t), z_gp.get(t), z_lev.get(t), z_acc.get(t)) if z is not None]
        if not vparts and not qparts:
            continue
        vz = sum(vparts) / len(vparts) if vparts else None
        qz = sum(qparts) / len(qparts) if qparts else None
        cp = [x for x in (vz, qz) if x is not None]
        comp = sum(cp) / len(cp) if cp else None
        if comp is None:
            continue
        out[t] = {"composite": comp, "value_z": vz if vz is not None else 0.0,
                  "quality_z": qz if qz is not None else 0.0,
                  "n_value": len(vparts), "n_quality": len(qparts)}
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

def _bucket_ret(names, adj_px, d_prev, d_now):
    if not names:
        return 0.0
    rs = []
    for t in names:
        px = adj_px.get(t, {})
        p0 = px.get(d_prev); p1 = px.get(d_now)
        if p0 and p1 and p0 > 0:
            rs.append(p1 / p0 - 1.0)
    if not rs:
        return 0.0
    return sum(rs) / len(rs)

def run_backtest(data, univ_keys, adj_px, adj_dates, raw_close, raw_dates,
                 spy_px, spy_dates, cadence="M", bucket=0.2, long_short=False,
                 signal="composite", cost_bps=2.0, start="2010-06-01"):
    cal = [d for d in spy_dates if d >= start]
    if not cal:
        return None
    rb_idx = month_starts(cal) if cadence == "M" else quarter_starts(cal)
    rb_set = set(rb_idx)
    spy_ret = [0.0]
    for i in range(1, len(cal)):
        p0 = spy_px.get(cal[i - 1]); p1 = spy_px.get(cal[i])
        spy_ret.append((p1 / p0 - 1.0) if (p0 and p1 and p0 > 0) else 0.0)
    cur_long = []; cur_short = []
    strat_ret = [0.0]
    turnovers = []; rebal_log = []; prev_set = set(); n_names_log = []
    for i in range(len(cal)):
        d = cal[i]
        if i in rb_set:
            fac = compute_factors(data, univ_keys, d, raw_close, raw_dates)
            ranked = sorted(fac.items(), key=lambda kv: kv[1][signal], reverse=True)
            m = len(ranked)
            if m >= 10:
                k = max(1, int(round(m * bucket)))
                top = [t for t, _ in ranked[:k]]
                bot = [t for t, _ in ranked[-k:]] if long_short else []
                new_set = set(top) | set("S__" + x for x in bot)
                if prev_set:
                    changed = len(new_set.symmetric_difference(prev_set))
                    denom = max(1, len(new_set) + len(prev_set))
                    turn = changed / denom
                else:
                    turn = 1.0
                turnovers.append(turn)
                cur_long = top; cur_short = bot; prev_set = new_set
                n_names_log.append(len(top))
                cost = (cost_bps / 10000.0) * turn
                strat_ret[-1] = strat_ret[-1] - cost
                rebal_log.append({"date": d, "n_long": len(top), "n_short": len(bot), "turnover": turn})
        if i == 0:
            continue
        rl = _bucket_ret(cur_long, adj_px, cal[i - 1], d)
        if long_short and cur_short:
            rs = _bucket_ret(cur_short, adj_px, cal[i - 1], d)
            day = rl - rs
        else:
            day = rl
        strat_ret.append(day)
    avg_turn = sum(turnovers) / len(turnovers) if turnovers else 0.0
    return {"dates": cal, "strat_ret": strat_ret, "spy_ret": spy_ret,
            "avg_turnover": avg_turn, "n_rebal": len(turnovers),
            "rebal_log": rebal_log,
            "avg_n_long": (sum(n_names_log) / len(n_names_log) if n_names_log else 0)}

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

def stat_block(dates, rets):
    return {"n": len(rets), "sharpe": round(sharpe(rets), 3), "cagr_pct": round(cagr(rets), 2),
            "maxdd_pct": round(maxdd(rets), 2), "total_return_pct": round(total_return(rets), 1),
            "ann_vol_pct": round(ann_vol(rets), 2)}

def slice_block(dates, rets, start, end):
    sd = []; sr = []
    for d, r in zip(dates, rets):
        if start <= d < end:
            sd.append(d); sr.append(r)
    if len(sr) < 20:
        return {"n": len(sr)}
    return stat_block(sd, sr)

def breakeven_bps(gross_rets, turnovers_sum):
    if turnovers_sum <= 0:
        return 0.0
    eq = 1.0
    for r in gross_rets:
        eq *= (1.0 + r)
    gross_total = eq - 1.0
    return (gross_total / turnovers_sum) * 10000.0

KILLER_WINDOWS = [
    ("2020-Q1 covid crash",  "2020-02-01", "2020-04-01"),
    ("2022 bear (full yr)",  "2022-01-01", "2023-01-01"),
    ("2022-H1 bear",         "2022-01-01", "2022-07-01"),
    ("2025-Q1 tariff bear",  "2025-02-01", "2025-05-01"),
    ("2011 debt-ceiling",    "2011-07-01", "2011-10-01"),
    ("2018-Q4 selloff",      "2018-10-01", "2019-01-01"),
    ("2023-H1 recovery",     "2023-01-01", "2023-07-01"),
    ("2024-Q2 bull",         "2024-04-01", "2024-07-01"),
]

def _load_prices(univ_keys):
    adj_px = {}; adj_dates = {}; raw_close = {}; raw_dates = {}
    for t in univ_keys:
        ap = load_px(t)
        if ap:
            adj_px[t] = ap; adj_dates[t] = sorted(ap.keys())
        rc = load_raw_close(t)
        if rc:
            raw_close[t] = rc; raw_dates[t] = sorted(rc.keys())
    return adj_px, adj_dates, raw_close, raw_dates

def main():
    t0 = time.time()
    univ = json.load(open(os.path.join(EDGAR_DIR, "universe.json")))
    ticker_cik = univ["ticker_cik"]
    univ_keys = list(ticker_cik.keys())
    sys.stderr.write("[main] universe " + str(len(univ_keys)) + " names" + chr(10))
    data = build_fundamentals(ticker_cik, verbose=True)
    adj_px, adj_dates, raw_close, raw_dates = _load_prices(univ_keys)
    spy_px = load_px("SPY"); spy_dates = sorted(spy_px.keys())
    sys.stderr.write("[main] prices: " + str(len(adj_px)) + " adj, SPY " + str(len(spy_dates)) + " days" + chr(10))
    results = {"meta": {"universe_n": len(univ_keys), "universe": univ_keys,
                        "survivorship_note": univ.get("note"),
                        "oos_split": OOS_SPLIT, "cost_bps_oneway": 2.0,
                        "as_of_build": datetime.now(timezone.utc).isoformat()}}
    START = "2010-06-01"
    prim = run_backtest(data, univ_keys, adj_px, adj_dates, raw_close, raw_dates,
                        spy_px, spy_dates, cadence="M", bucket=0.2, long_short=False,
                        signal="composite", cost_bps=2.0, start=START)
    dts = prim["dates"]; sret = prim["strat_ret"]; spyret = prim["spy_ret"]
    full_s = stat_block(dts, sret); full_spy = stat_block(dts, spyret)
    is_s = slice_block(dts, sret, "2000-01-01", "2019-01-01")
    is_spy = slice_block(dts, spyret, "2000-01-01", "2019-01-01")
    oos_s = slice_block(dts, sret, "2019-01-01", "2099-01-01")
    oos_spy = slice_block(dts, spyret, "2019-01-01", "2099-01-01")
    prim_gross = run_backtest(data, univ_keys, adj_px, adj_dates, raw_close, raw_dates,
                              spy_px, spy_dates, cadence="M", bucket=0.2, long_short=False,
                              signal="composite", cost_bps=0.0, start=START)
    turn_sum = prim["avg_turnover"] * prim["n_rebal"]
    be = breakeven_bps(prim_gross["strat_ret"], turn_sum)
    results["primary"] = {
        "config": "monthly, top-quintile (20%), long-only, combined composite, 2bps",
        "avg_turnover_per_rebal": round(prim["avg_turnover"], 4),
        "n_rebal": prim["n_rebal"], "avg_n_long": round(prim["avg_n_long"], 1),
        "breakeven_bps_oneway": round(be, 1),
        "full": {"strat": full_s, "spy": full_spy,
                 "beats_spy_raw": full_s["total_return_pct"] > full_spy["total_return_pct"]},
        "is_pre2019": {"strat": is_s, "spy": is_spy},
        "oos_2019plus": {"strat": oos_s, "spy": oos_spy,
                         "beats_spy_raw": (oos_s.get("total_return_pct", -1e9) > oos_spy.get("total_return_pct", 1e9))}}
    battery = {}
    for label, st, en in KILLER_WINDOWS:
        battery[label] = {"strat": slice_block(dts, sret, st, en), "spy": slice_block(dts, spyret, st, en)}
    results["killer_battery"] = battery
    ls = run_backtest(data, univ_keys, adj_px, adj_dates, raw_close, raw_dates,
                      spy_px, spy_dates, cadence="M", bucket=0.2, long_short=True,
                      signal="composite", cost_bps=2.0, start=START)
    results["long_short_spread"] = {
        "config": "monthly, top-minus-bottom quintile, combined composite, 2bps",
        "full": stat_block(ls["dates"], ls["strat_ret"]),
        "oos_2019plus": slice_block(ls["dates"], ls["strat_ret"], "2019-01-01", "2099-01-01"),
        "avg_turnover_per_rebal": round(ls["avg_turnover"], 4)}
    sweep = []
    for cad in ("M", "Q"):
        for buck in (0.2, 0.333):
            for sig in ("composite", "value_z", "quality_z"):
                rb = run_backtest(data, univ_keys, adj_px, adj_dates, raw_close, raw_dates,
                                  spy_px, spy_dates, cadence=cad, bucket=buck, long_short=False,
                                  signal=sig, cost_bps=2.0, start=START)
                fb = stat_block(rb["dates"], rb["strat_ret"])
                ob = slice_block(rb["dates"], rb["strat_ret"], "2019-01-01", "2099-01-01")
                sb = stat_block(rb["dates"], rb["spy_ret"])
                sweep.append({"cadence": cad, "bucket": buck, "signal": sig,
                              "full_sharpe": fb["sharpe"], "full_ret_pct": fb["total_return_pct"],
                              "full_maxdd_pct": fb["maxdd_pct"],
                              "oos_sharpe": ob.get("sharpe"), "oos_ret_pct": ob.get("total_return_pct"),
                              "spy_full_ret_pct": sb["total_return_pct"],
                              "beats_spy_full": fb["total_return_pct"] > sb["total_return_pct"],
                              "avg_turnover": round(rb["avg_turnover"], 4)})
    results["robustness_sweep"] = sweep
    results["lookahead_canary"] = {"violations": len(_CANARY), "sample": _CANARY[:5],
                                   "passed": len(_CANARY) == 0}
    results["runtime_sec"] = round(time.time() - t0, 1)
    outp = os.path.join(WS, "reports", "_fundamentals_pit_result.json")
    json.dump(results, open(outp, "w"), indent=2)
    sys.stderr.write("[main] wrote " + outp + chr(10))
    p = results["primary"]
    print("=" * 70)
    print("FUNDAMENTALS-PIT QUALITY/VALUE -- PRIMARY (monthly top-quintile long-only)")
    print("  Universe: " + str(len(univ_keys)) + " names (survivorship-biased: today S&P100-ish)")
    print("  Lookahead canary: " + ("PASS" if results["lookahead_canary"]["passed"] else "FAIL") + " (" + str(results["lookahead_canary"]["violations"]) + " violations)")
    print("  Avg turnover/rebal: %.1f%%  n_rebal=%d  breakeven=%.0f bps one-way" % (p["avg_turnover_per_rebal"]*100, p["n_rebal"], p["breakeven_bps_oneway"]))
    print("  FULL : strat Sharpe %.2f CAGR %.1f%% maxDD %.1f%% rawRet %.0f%%  |  SPY Sharpe %.2f rawRet %.0f%%  beats=%s" % (
        p["full"]["strat"]["sharpe"], p["full"]["strat"]["cagr_pct"], p["full"]["strat"]["maxdd_pct"], p["full"]["strat"]["total_return_pct"],
        p["full"]["spy"]["sharpe"], p["full"]["spy"]["total_return_pct"], p["full"]["beats_spy_raw"]))
    oss = p["oos_2019plus"]["strat"]; osp = p["oos_2019plus"]["spy"]
    print("  OOS  : strat Sharpe " + str(oss.get("sharpe")) + " rawRet " + str(oss.get("total_return_pct")) + "%  |  SPY Sharpe " + str(osp.get("sharpe")) + " rawRet " + str(osp.get("total_return_pct")) + "%  beats=" + str(p["oos_2019plus"]["beats_spy_raw"]))
    print("  L/S spread FULL Sharpe %.2f rawRet %.0f%%" % (results["long_short_spread"]["full"]["sharpe"], results["long_short_spread"]["full"]["total_return_pct"]))
    print("=" * 70)
    return results

if __name__ == "__main__":
    main()

