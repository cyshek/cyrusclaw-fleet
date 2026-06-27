#!/usr/bin/env python3
"""
H1 CROSS-ASSET CARRY -- FX RATE-DIFFERENTIAL CARRY LEG (feasibility / kill-test).

Candidate SECOND uncorrelated carry leg for the documented bond-curve-carry NEAR-MISS
(reports/H1_CARRY_BONDLEG_20260623T191733Z.md). Bond leg PASSED its controls + is orthogonal
but missed the 0.5 standalone Sharpe (OOS 0.434). Commodity-carry leg ALREADY FAILED the 2nd-leg
role (CLOSED 2026-06-23). This tests whether classic G10 FX rate-differential carry is the leg.

THE BAR (bond-leg report section 9, applied to FX):
  (a) FX-carry standalone OOS Sharpe >~ 0.4
  (b) corr <~ 0.3 between FX-carry daily returns and bond-leg daily returns
  (c) FX leg must BEAT its own EW-of-same-pairs control OOS net of cost (mandatory)
  (d) survive 2008/2020/2022 stress slices net of cost
  IF (a)+(b): build equal-risk 50/50 bond+FX inverse-vol carry sleeve and re-run FULL c1-c4 on
  the COMBINED daily series (combined OOS Sharpe >0.5, beats combined-EW, |corr|<0.5 to SPY/TQQQ,
  positive return). That combined-PASS is the prize.

METHODOLOGY -- MIRRORS bond-leg engine (.scratch_archive/_h1_carry_bondleg_tests.py):
  adjclose ONLY; daily aligned panel; month-end rebalance; 1-day signal lag; rate obs lagged for
  publication; sleeve daily ret = spot-return-long-foreign + carry accrual (rate_diff/252);
  vol-target ~9% (20d realized, cap 1.0x); cost (bps/1e4)*sum|dw|; Sharpe (mean/std)*sqrt(252)
  ddof=1 continuous-span (mirrors runner/fp_sharpe.py).

SELF-CONTAINED: imports nothing from runner/ EXCEPT fred_cache (read-only). PROTECTED dirs untouched.
Run: python3 reports/_fx_carry_leg_driver.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
YH = WORKSPACE / "data_cache" / "yahoo"
FX = WORKSPACE / "data_cache" / "yahoo_fx"
sys.path.insert(0, str(WORKSPACE))
from runner.fred_cache import get_values  # noqa: E402

TRADING_DAYS = 252.0
SQRT_252 = math.sqrt(TRADING_DAYS)
OOS_SPLIT = "2018-12-31"

# quote flag True => cached spot is USD-per-foreign (adjclose up => foreign up => long-foreign=+ret)
# False => foreign-per-USD (adjclose up => USD up => long-foreign = reciprocal return)
PAIRS = {
    "AUD": ("AUDUSD_X", True),
    "EUR": ("EURUSD_X", True),
    "GBP": ("GBPUSD_X", True),
    "NZD": ("NZDUSD_X", True),
    "CAD": ("USDCAD_X", False),
    "CHF": ("USDCHF_X", False),
    "JPY": ("USDJPY_X", False),
}
RATE_SERIES = {
    "USD": "IR3TIB01USM156N",
    "EUR": "IR3TIB01EZM156N",
    "GBP": "IR3TIB01GBM156N",
    "JPY": "IR3TIB01JPM156N",
    "CAD": "IR3TIB01CAM156N",
    "AUD": "IR3TIB01AUM156N",
    "CHF": "IR3TIB01CHM156N",
    "NZD": "IR3TIB01NZM156N",
}
FOREIGN = ["AUD", "EUR", "GBP", "NZD", "CAD", "CHF", "JPY"]
BOND_PRIMARY = dict(long_sleeve="TLT", scale=1.5, vol_target=0.09, vol_lookback=20, cost_bps=2.0,
                    slope_series="T10Y2Y")
STRESS = {
    "2008_GFC": ("2008-01-01", "2009-06-30"),
    "2020_covid": ("2020-02-01", "2020-06-30"),
    "2022_rateshock": ("2022-01-01", "2022-12-31"),
}


def load_adjclose(path: Path) -> Tuple[List[str], List[float]]:
    rows = json.loads(path.read_text())
    rows = [r for r in rows if r.get("adjclose") is not None]
    rows.sort(key=lambda r: r["date"])
    return [r["date"][:10] for r in rows], [float(r["adjclose"]) for r in rows]


def load_fx(pair_file: str) -> Tuple[List[str], List[float]]:
    return load_adjclose(FX / (pair_file + "_parsed.json"))


def load_equity(ticker: str) -> Tuple[List[str], List[float]]:
    return load_adjclose(YH / (ticker + "_parsed.json"))


def sharpe(returns: Sequence[float], bpy: float = TRADING_DAYS) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(bpy)


def cagr(returns: Sequence[float]) -> float:
    if not returns:
        return 0.0
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
    yrs = len(returns) / TRADING_DAYS
    if yrs <= 0 or eq <= 0:
        return 0.0
    return eq ** (1.0 / yrs) - 1.0


def total_return(returns: Sequence[float]) -> float:
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
    return eq - 1.0


def max_drawdown(returns: Sequence[float]) -> float:
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def ann_vol(returns: Sequence[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(var) * SQRT_252


def realized_vol_ann(daily_rets: List[float], end_i: int, lookback: int) -> Optional[float]:
    lo = max(1, end_i - lookback + 1)
    seg = daily_rets[lo:end_i + 1]
    if len(seg) < max(5, lookback // 2):
        return None
    n = len(seg)
    mean = sum(seg) / n
    var = sum((r - mean) ** 2 for r in seg) / (n - 1)
    if var <= 0:
        return None
    return math.sqrt(var) * SQRT_252


def corr(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[:n]
    b = b[:n]
    ma = sum(a) / n
    mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def metrics(daily_net: List[float], daily_dates: List[str]) -> Dict[str, object]:
    return {
        "sharpe": round(sharpe(daily_net), 4),
        "cagr": round(cagr(daily_net), 4),
        "total_return": round(total_return(daily_net), 4),
        "max_drawdown": round(max_drawdown(daily_net), 4),
        "ann_vol": round(ann_vol(daily_net), 4),
        "n_days": len(daily_net),
        "start": daily_dates[0] if daily_dates else None,
        "end": daily_dates[-1] if daily_dates else None,
    }


def _next_day(d: str) -> str:
    y, m, dd = map(int, d.split("-"))
    return date.fromordinal(date(y, m, dd).toordinal() + 1).isoformat()


def slice_window(daily_net: List[float], daily_dates: List[str], lo: str, hi: str):
    r, d = [], []
    for x, dt in zip(daily_net, daily_dates):
        if lo <= dt <= hi:
            r.append(x)
            d.append(dt)
    return r, d


def is_oos(daily: List[float], dd: List[str]):
    full = metrics(daily, dd)
    isr, isd = slice_window(daily, dd, "1900-01-01", OOS_SPLIT)
    oosr, oosd = slice_window(daily, dd, _next_day(OOS_SPLIT), "2999-12-31")
    return full, metrics(isr, isd), metrics(oosr, oosd)


def _shift_months_back(d: str, months: int) -> str:
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    total = (y * 12 + (m - 1)) - months
    ny, nm = total // 12, total % 12 + 1
    return "%04d-%02d-%02d" % (ny, nm, dd)


class RateSeries:
    """Monthly OECD 3-mo interbank rate, queried PIT with a publication lag.

    OECD monthly series dated by observation month (2026-05-01 = May reading), released with a
    lag. We require the observation date <= (month-end T shifted back extra_months) so on T we
    never use a value that would not yet have been published. Value in DECIMAL/yr (percent/100).
    """

    def __init__(self, series_id: str, start: str, end: str, extra_months: int = 1):
        vv = get_values(series_id, start, end, vintage="latest", drop_missing=True)
        vv.sort(key=lambda t: t[0])
        self.dates = [d[:10] for d, _ in vv]
        self.values = [float(v) / 100.0 for _, v in vv]
        self.extra_months = extra_months

    def asof(self, d: str) -> Optional[float]:
        cutoff = _shift_months_back(d, self.extra_months)
        i = bisect_right(self.dates, cutoff) - 1
        return self.values[i] if i >= 0 else None


class FXPanel:
    """Daily aligned adjclose for the 7 pairs + per-pair LONG-FOREIGN daily spot return."""

    def __init__(self):
        per_px: Dict[str, Dict[str, float]] = {}
        common: Optional[set] = None
        for ccy in FOREIGN:
            pair_file, _ = PAIRS[ccy]
            d, p = load_fx(pair_file)
            per_px[ccy] = dict(zip(d, p))
            s = set(d)
            common = s if common is None else (common & s)
        self.dates = sorted(common)
        self.idx = {dt: i for i, dt in enumerate(self.dates)}
        self.px: Dict[str, List[float]] = {c: [per_px[c][dt] for dt in self.dates] for c in FOREIGN}
        self.long_spot_ret: Dict[str, List[float]] = {}
        for ccy in FOREIGN:
            _pf, usd_per_foreign = PAIRS[ccy]
            p = self.px[ccy]
            r = [0.0]
            for i in range(1, len(p)):
                if usd_per_foreign:
                    r.append((p[i] / p[i - 1] - 1.0) if p[i - 1] else 0.0)
                else:
                    r.append((p[i - 1] / p[i] - 1.0) if p[i] else 0.0)
            self.long_spot_ret[ccy] = r

    def __len__(self):
        return len(self.dates)


def month_end_indices(dates: List[str]) -> List[int]:
    out: List[int] = []
    for i in range(len(dates)):
        ym = dates[i][:7]
        is_last = (i == len(dates) - 1) or (dates[i + 1][:7] != ym)
        if is_last:
            out.append(i)
    return out


def carry_at(rates: Dict[str, "RateSeries"], d: str) -> Dict[str, float]:
    """carry_ccy = (foreign 3-mo rate - USD 3-mo rate) decimal/yr, PIT at as-of d."""
    usd = rates["USD"].asof(d)
    out: Dict[str, float] = {}
    if usd is None:
        return out
    for ccy in FOREIGN:
        fr = rates[ccy].asof(d)
        if fr is not None:
            out[ccy] = fr - usd
    return out


def _sleeve_spot_daily(fx: "FXPanel", static_w: Dict[str, float]) -> List[float]:
    n = len(fx.dates)
    out = [0.0] * n
    for i in range(n):
        s = 0.0
        for c, w in static_w.items():
            if w != 0.0:
                s += w * fx.long_spot_ret[c][i]
        out[i] = s
    return out


def build_carry_weights(fx, rates, me_idx, *, mode="longshort", topn=3, botn=3,
                        vol_target=0.09, vol_lookback=20, extra_lag_months=0):
    """Return (rebal_weights, rebal_carry) keyed by month-end index.

    At month-end T (rate data <= as-of with publication lag): rank FOREIGN by carry; long top-N
    (+w), short bottom-N (-w), EW per side (longshort, dollar-neutral); or long all positive-carry
    EW (longonly_positive). Then vol-target the raw sleeve to vol_target (20d realized, cap 1.0x).
    """
    dates = fx.dates
    weights: Dict[int, Dict[str, float]] = {}
    carries: Dict[int, Dict[str, float]] = {}
    for T in me_idx:
        d = dates[T]
        d_eff = _shift_months_back(d, extra_lag_months) if extra_lag_months else d
        cmap = carry_at(rates, d_eff)
        if len(cmap) < max(topn, botn) + 1:
            continue
        ranked = sorted(cmap.items(), key=lambda kv: kv[1], reverse=True)
        raw: Dict[str, float] = {c: 0.0 for c in FOREIGN}
        if mode == "longshort":
            longs = [c for c, _ in ranked[:topn]]
            shorts = [c for c, _ in ranked[-botn:]]
            for c in longs:
                raw[c] += 1.0 / len(longs)
            for c in shorts:
                raw[c] -= 1.0 / len(shorts)
        elif mode == "longonly_positive":
            pos = [c for c, v in ranked if v > 0]
            if not pos:
                weights[T] = {c: 0.0 for c in FOREIGN}
                carries[T] = cmap
                continue
            for c in pos:
                raw[c] += 1.0 / len(pos)
        else:
            raise ValueError(mode)
        sleeve_daily = _sleeve_spot_daily(fx, raw)
        rv = realized_vol_ann(sleeve_daily, T, vol_lookback)
        scaler = 1.0 if (rv is None or rv <= 1e-9) else min(1.0, vol_target / rv)
        weights[T] = {c: w * scaler for c, w in raw.items()}
        carries[T] = cmap
    return weights, carries


def control_ew_fx(fx, me_idx, *, vol_target=0.09, vol_lookback=20):
    """No-signal control: EW LONG all 7 foreign currencies vs USD, vol-targeted, monthly rebal.

    NO carry accrual differential is harvested by ranking -- but a long-all-foreign basket DOES
    earn the average carry, so for honesty the EW control accrues the AVERAGE rate diff (it is the
    being-long-FX baseline). We pass rebal_carry = average-of-all so the EW control's accrual is the
    naive long-FX carry, and the signal must beat THAT (carry-timing alpha, not just long-FX beta).
    """
    weights: Dict[int, Dict[str, float]] = {}
    raw = {c: 1.0 / len(FOREIGN) for c in FOREIGN}
    sleeve_daily = _sleeve_spot_daily(fx, raw)
    for T in me_idx:
        rv = realized_vol_ann(sleeve_daily, T, vol_lookback)
        scaler = 1.0 if (rv is None or rv <= 1e-9) else min(1.0, vol_target / rv)
        weights[T] = {c: w * scaler for c, w in raw.items()}
    return weights


def backtest_fx(fx, rebal_weights, rebal_carry, *, cost_bps_roundtrip=2.0, lag_days=1,
                include_accrual=True):
    """Returns (daily_net, daily_dates, avg_turnover_per_rebal, n_rebals).

    Anti-lookahead (mirrors bond-leg backtest_weights): rebal_weights[T] from rate data <= as-of
    (pub-lagged); effective at T+lag_days; held constant daily; freshly-traded weights do NOT
    capture the trade-day's already-realized return. Daily mark per held ccy =
      w * spot_long_foreign_ret[i]  +  (if accrual) w * carry_ccy/252   (accrual earned each day
    held, on the SIGNED weight: long earns +diff/252, short earns -diff/252). Cost = (bps/1e4)*sum|dw|.
    """
    dates = fx.dates
    n = len(dates)
    me_sorted = sorted(rebal_weights.keys())
    sched = []
    carry_of_eff: Dict[int, Dict[str, float]] = {}
    for T in me_sorted:
        eff = T + lag_days
        if eff >= n:
            continue
        sched.append((eff, rebal_weights[T]))
        carry_of_eff[eff] = rebal_carry.get(T, {})
    sched.sort(key=lambda x: x[0])
    if not sched:
        return [], [], 0.0, 0
    first_eff = sched[0][0]
    cur_w: Dict[str, float] = {c: 0.0 for c in FOREIGN}
    cur_carry: Dict[str, float] = {c: 0.0 for c in FOREIGN}
    sched_ptr = 0
    daily_net: List[float] = []
    daily_dates: List[str] = []
    turnovers: List[float] = []
    for i in range(first_eff, n):
        gross = 0.0
        for c, w in cur_w.items():
            if w != 0.0:
                gross += w * fx.long_spot_ret[c][i]
                if include_accrual:
                    gross += w * cur_carry.get(c, 0.0) / TRADING_DAYS
        cost_today = 0.0
        while sched_ptr < len(sched) and sched[sched_ptr][0] == i:
            new_w_raw = sched[sched_ptr][1]
            new_w = {c: float(new_w_raw.get(c, 0.0)) for c in FOREIGN}
            dw = sum(abs(new_w[c] - cur_w.get(c, 0.0)) for c in FOREIGN)
            cost_today += (cost_bps_roundtrip / 1e4) * dw
            turnovers.append(dw)
            cur_w = new_w
            cur_carry = {c: float(carry_of_eff[i].get(c, 0.0)) for c in FOREIGN}
            sched_ptr += 1
        daily_net.append(gross - cost_today)
        daily_dates.append(dates[i])
    avg_turn = (sum(turnovers) / len(turnovers)) if turnovers else 0.0
    return daily_net, daily_dates, avg_turn, len(turnovers)
    return daily_net, daily_dates, avg_turn, len(turnovers)


# ---------------------------------------------------------------------------
# BOND-LEG RECONSTRUCTION (primary config) -- mirror the bond engine exactly so
# the corr(FX, bond) is computed against the real bond-leg daily series.
# ---------------------------------------------------------------------------

class BondPanel:
    def __init__(self, tickers):
        per = {}
        common = None
        for t in tickers:
            d, p = load_equity(t)
            per[t] = dict(zip(d, p))
            s = set(d)
            common = s if common is None else (common & s)
        self.tickers = list(tickers)
        self.dates = sorted(common)
        self.px = {t: [per[t][dt] for dt in self.dates] for t in tickers}
        self.ret = {}
        for t in tickers:
            p = self.px[t]
            r = [0.0]
            for i in range(1, len(p)):
                r.append(p[i] / p[i - 1] - 1.0 if p[i - 1] else 0.0)
            self.ret[t] = r

    def __len__(self):
        return len(self.dates)


class SlopeSeries:
    def __init__(self, series_id, start, end):
        vv = get_values(series_id, start, end, vintage="latest", drop_missing=True)
        vv.sort(key=lambda t: t[0])
        self.dates = [d[:10] for d, _ in vv]
        self.values = [float(v) for _, v in vv]

    def asof(self, d):
        i = bisect_right(self.dates, d) - 1
        return self.values[i] if i >= 0 else None


def _bond_sleeve_daily(panel, static_w):
    n = len(panel.dates)
    out = [0.0] * n
    for i in range(n):
        s = 0.0
        for t, w in static_w.items():
            s += w * panel.ret[t][i]
        out[i] = s
    return out


def build_bond_weights(panel, slope, me_idx, long_sleeve="TLT", scale=1.5,
                       vol_target=0.09, vol_lookback=20):
    dates = panel.dates
    weights = {}
    if long_sleeve == "TLT":
        dur_legs = {"TLT": 1.0}
    elif long_sleeve == "TLTIEF":
        dur_legs = {"TLT": 0.5, "IEF": 0.5}
    else:
        raise ValueError(long_sleeve)
    for T in me_idx:
        d = dates[T]
        steep = slope.asof(d)
        if steep is None:
            continue
        w_dur = min(1.0, max(0.0, steep) / scale)
        raw = {}
        for leg, frac in dur_legs.items():
            raw[leg] = w_dur * frac
        raw["SHY"] = max(0.0, 1.0 - w_dur)
        leg_daily = _bond_sleeve_daily(panel, raw)
        rv = realized_vol_ann(leg_daily, T, vol_lookback)
        scaler = 1.0 if (rv is None or rv <= 1e-9) else min(1.0, vol_target / rv)
        weights[T] = {t: w * scaler for t, w in raw.items()}
    return weights


def backtest_bond(panel, rebal_weights, cost_bps_roundtrip=2.0, lag_days=1):
    dates = panel.dates
    n = len(dates)
    tickers = panel.tickers
    me_sorted = sorted(rebal_weights.keys())
    sched = []
    for T in me_sorted:
        eff = T + lag_days
        if eff >= n:
            continue
        sched.append((eff, rebal_weights[T]))
    sched.sort(key=lambda x: x[0])
    if not sched:
        return [], []
    first_eff = sched[0][0]
    cur_w = {t: 0.0 for t in tickers}
    sched_ptr = 0
    daily_net = []
    daily_dates = []
    for i in range(first_eff, n):
        gross = 0.0
        for t, w in cur_w.items():
            if w != 0.0:
                gross += w * panel.ret[t][i]
        cost_today = 0.0
        while sched_ptr < len(sched) and sched[sched_ptr][0] == i:
            new_w_raw = sched[sched_ptr][1]
            new_w = {t: float(new_w_raw.get(t, 0.0)) for t in tickers}
            dw = sum(abs(new_w[t] - cur_w.get(t, 0.0)) for t in tickers)
            cost_today += (cost_bps_roundtrip / 1e4) * dw
            cur_w = new_w
            sched_ptr += 1
        daily_net.append(gross - cost_today)
        daily_dates.append(dates[i])
    return daily_net, daily_dates


# ---------------------------------------------------------------------------
# Daily-series alignment + combined equal-risk sleeve + corr helpers
# ---------------------------------------------------------------------------

def to_map(daily, dates):
    return dict(zip(dates, daily))


def aligned_daily_corr(a_daily, a_dates, b_daily, b_dates, lo="1900-01-01", hi="2999-12-31"):
    am = to_map(a_daily, a_dates)
    bm = to_map(b_daily, b_dates)
    keys = sorted(set(am.keys()) & set(bm.keys()))
    keys = [k for k in keys if lo <= k <= hi]
    xa = [am[k] for k in keys]
    xb = [bm[k] for k in keys]
    return round(corr(xa, xb), 4), len(keys), (keys[0] if keys else None), (keys[-1] if keys else None)


def inverse_vol_combined(a_daily, a_dates, b_daily, b_dates, vol_lookback=20):
    """Equal-RISK 50/50 inverse-vol combined sleeve on the OVERLAPPING calendar.

    Each day i (on the intersection), weight each leg by 1/realized_vol (trailing vol_lookback,
    data <= i-1 to avoid same-bar leak), normalized to sum 1; combined_ret[i] = wa*ra + wb*rb.
    This is the standard equal-risk-contribution-ish inverse-vol blend, rebalanced daily on lagged
    vols. Returns (combined_daily, combined_dates).
    """
    am = to_map(a_daily, a_dates)
    bm = to_map(b_daily, b_dates)
    keys = sorted(set(am.keys()) & set(bm.keys()))
    ra = [am[k] for k in keys]
    rb = [bm[k] for k in keys]
    out = []
    for i in range(len(keys)):
        va = realized_vol_ann(ra, i - 1, vol_lookback) if i >= vol_lookback else None
        vb = realized_vol_ann(rb, i - 1, vol_lookback) if i >= vol_lookback else None
        if va and vb and va > 1e-9 and vb > 1e-9:
            ia, ib = 1.0 / va, 1.0 / vb
            wa, wb = ia / (ia + ib), ib / (ia + ib)
        else:
            wa, wb = 0.5, 0.5
        out.append(wa * ra[i] + wb * rb[i])
    return out, keys


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run_fx_config(fx, rates, me_idx, mode, topn, botn, vol_target, cost_bps, extra_lag_months=0):
    w, c = build_carry_weights(fx, rates, me_idx, mode=mode, topn=topn, botn=botn,
                               vol_target=vol_target, extra_lag_months=extra_lag_months)
    daily, dd, turn, nreb = backtest_fx(fx, w, c, cost_bps_roundtrip=cost_bps)
    full, isb, oos = is_oos(daily, dd)
    return {"daily": daily, "dates": dd, "full": full, "is": isb, "oos": oos,
            "turn": round(turn, 4), "nreb": nreb,
            "config": {"mode": mode, "topn": topn, "botn": botn, "vol_target": vol_target,
                       "cost_bps": cost_bps, "extra_lag_months": extra_lag_months}}


def main():
    stamp = os.environ.get("UTCSTAMP") or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print("[FX carry leg] UTC stamp =", stamp)

    fx = FXPanel()
    print("[fx panel] %d aligned days %s -> %s" % (len(fx), fx.dates[0], fx.dates[-1]))
    me_idx = month_end_indices(fx.dates)
    print("[fx panel] %d month-end rebalances" % len(me_idx))

    end_d = fx.dates[-1]
    rates = {ccy: RateSeries(sid, "1990-01-01", end_d, extra_months=1)
             for ccy, sid in RATE_SERIES.items()}
    for ccy in RATE_SERIES:
        rs = rates[ccy]
        print("[rate] %s %d obs %s -> %s" % (ccy, len(rs.dates),
              rs.dates[0] if rs.dates else "NA", rs.dates[-1] if rs.dates else "NA"))

    # --- PRIMARY: long-short dollar-neutral, top3/bottom3, 9% vt, 2bps ---
    primary = run_fx_config(fx, rates, me_idx, "longshort", 3, 3, 0.09, 2.0)
    print("[primary FX] FULL Sh %.4f  OOS Sh %.4f  OOS tot %.4f  turn %.4f  nreb %d" % (
        primary["full"]["sharpe"], primary["oos"]["sharpe"], primary["oos"]["total_return"],
        primary["turn"], primary["nreb"]))

    # --- long-only-positive variant (completeness) ---
    longonly = run_fx_config(fx, rates, me_idx, "longonly_positive", 3, 3, 0.09, 2.0)
    print("[longonly+ FX] FULL Sh %.4f  OOS Sh %.4f  OOS tot %.4f" % (
        longonly["full"]["sharpe"], longonly["oos"]["sharpe"], longonly["oos"]["total_return"]))

    # --- EW control: long all 7 foreign, naive long-FX carry accrual (avg diff), vol-targeted ---
    ew_w = control_ew_fx(fx, me_idx, vol_target=0.09)
    # EW accrual = average carry diff across all foreign at each T (the being-long-FX carry)
    _, carry_full = build_carry_weights(fx, rates, me_idx, mode="longshort", topn=3, botn=3)
    ew_carry = {}
    for T in me_idx:
        cm = carry_full.get(T, {})
        if cm:
            avg = sum(cm.values()) / len(cm)
            ew_carry[T] = {c: avg for c in FOREIGN}
        else:
            ew_carry[T] = {c: 0.0 for c in FOREIGN}
    ew_daily, ew_dd, ew_turn, ew_nreb = backtest_fx(fx, ew_w, ew_carry, cost_bps_roundtrip=2.0)
    ew_full, ew_is, ew_oos = is_oos(ew_daily, ew_dd)
    print("[EW control] FULL Sh %.4f  OOS Sh %.4f  OOS tot %.4f" % (
        ew_full["sharpe"], ew_oos["sharpe"], ew_oos["total_return"]))

    sig_oos = primary["oos"]
    delta_ew_oos = round(sig_oos["sharpe"] - ew_oos["sharpe"], 4)
    delta_ew_oos_tot = round(sig_oos["total_return"] - ew_oos["total_return"], 4)

    # --- BOND-LEG reconstruction (primary config) for corr ---
    bp = BondPanel(["TLT", "IEF", "SHY"])
    bme = month_end_indices(bp.dates)
    slope = SlopeSeries("T10Y2Y", "1990-01-01", bp.dates[-1])
    bw = build_bond_weights(bp, slope, bme, long_sleeve="TLT", scale=1.5,
                            vol_target=0.09, vol_lookback=20)
    bond_daily, bond_dd = backtest_bond(bp, bw, cost_bps_roundtrip=2.0)
    bond_full, bond_is, bond_oos = is_oos(bond_daily, bond_dd)
    print("[bond recon] FULL Sh %.4f  OOS Sh %.4f (target ~0.578 / ~0.434)" % (
        bond_full["sharpe"], bond_oos["sharpe"]))

    # --- corr(FX, bond) on overlapping OOS window (the decisive number) ---
    corr_bond_full, n_full, _, _ = aligned_daily_corr(primary["daily"], primary["dates"],
                                                      bond_daily, bond_dd)
    corr_bond_oos, n_oos, oos_lo, oos_hi = aligned_daily_corr(
        primary["daily"], primary["dates"], bond_daily, bond_dd,
        lo=_next_day(OOS_SPLIT), hi="2999-12-31")
    print("[corr FX<->bond] FULL %.4f (n=%d)  OOS %.4f (n=%d, %s..%s)" % (
        corr_bond_full, n_full, corr_bond_oos, n_oos, oos_lo, oos_hi))

    # --- corr to SPY / TQQQ (orthogonality to live book) ---
    spy_dates, spy_px = load_equity("SPY")
    spy_ret = [0.0] + [(spy_px[i] / spy_px[i - 1] - 1.0) if spy_px[i - 1] else 0.0
                       for i in range(1, len(spy_px))]
    tq_dates, tq_px = load_equity("TQQQ")
    tq_ret = [0.0] + [(tq_px[i] / tq_px[i - 1] - 1.0) if tq_px[i - 1] else 0.0
                      for i in range(1, len(tq_px))]
    corr_spy, _, _, _ = aligned_daily_corr(primary["daily"], primary["dates"], spy_ret, spy_dates)
    corr_tqqq, _, _, _ = aligned_daily_corr(primary["daily"], primary["dates"], tq_ret, tq_dates)
    print("[orthogonality FX] corr->SPY %.4f  corr->TQQQ %.4f" % (corr_spy, corr_tqqq))

    # --- cost grid (monotonic) ---
    cost_grid = []
    for c in [0.0, 1.0, 2.0, 5.0]:
        r = run_fx_config(fx, rates, me_idx, "longshort", 3, 3, 0.09, c)
        cost_grid.append({"cost_bps": c, "full_sharpe": r["full"]["sharpe"],
                          "oos_sharpe": r["oos"]["sharpe"], "full_total": r["full"]["total_return"]})
    print("[cost grid]", cost_grid)

    # --- stress windows (primary FX vs EW), total return ---
    stress = {}
    for name, (lo, hi) in STRESS.items():
        s_r, _ = slice_window(primary["daily"], primary["dates"], lo, hi)
        e_r, _ = slice_window(ew_daily, ew_dd, lo, hi)
        b_r, _ = slice_window(bond_daily, bond_dd, lo, hi)
        stress[name] = {"window": [lo, hi], "n_days": len(s_r),
                        "fx_total": round(total_return(s_r), 4),
                        "fx_sharpe": round(sharpe(s_r), 4),
                        "ew_total": round(total_return(e_r), 4),
                        "bond_total": round(total_return(b_r), 4)}
    print("[stress]", json.dumps(stress))

    # --- CANARY: +1 EXTRA month lag on the rate as-of; edge must survive ---
    canary = run_fx_config(fx, rates, me_idx, "longshort", 3, 3, 0.09, 2.0, extra_lag_months=1)
    canary_oos = canary["oos"]["sharpe"]
    print("[canary +1mo extra lag] OOS Sh %.4f  (primary OOS %.4f)" % (canary_oos, sig_oos["sharpe"]))

    # --- ROBUSTNESS sweep ---
    sweep = []
    for mode in ["longshort", "longonly_positive"]:
        for (tn, bn) in [(2, 2), (3, 3)]:
            for vt in [0.08, 0.10]:
                r = run_fx_config(fx, rates, me_idx, mode, tn, bn, vt, 2.0)
                sweep.append({"mode": mode, "topn": tn, "botn": bn, "vol_target": vt,
                              "full_sharpe": r["full"]["sharpe"], "oos_sharpe": r["oos"]["sharpe"],
                              "oos_total": r["oos"]["total_return"]})
    oos_sweep = [s["oos_sharpe"] for s in sweep]
    sweep_stats = {"n": len(sweep), "oos_min": round(min(oos_sweep), 4),
                   "oos_median": round(sorted(oos_sweep)[len(oos_sweep) // 2], 4),
                   "oos_max": round(max(oos_sweep), 4),
                   "n_oos_above_0.4": sum(1 for x in oos_sweep if x > 0.4),
                   "n_oos_above_0.5": sum(1 for x in oos_sweep if x > 0.5)}
    print("[sweep stats]", sweep_stats)

    # --- gate (a)+(b): build COMBINED equal-risk sleeve if FX qualifies ---
    gate_a = sig_oos["sharpe"] >= 0.4
    gate_b = abs(corr_bond_oos) <= 0.3
    combined_block = {"built": False, "gate_a_oos_sharpe_ge_0.4": bool(gate_a),
                      "gate_b_corr_bond_le_0.3": bool(gate_b),
                      "corr_bond_oos": corr_bond_oos, "fx_oos_sharpe": sig_oos["sharpe"]}
    if gate_a and gate_b:
        comb_daily, comb_dates = inverse_vol_combined(primary["daily"], primary["dates"],
                                                      bond_daily, bond_dd, vol_lookback=20)
        comb_full, comb_is, comb_oos = is_oos(comb_daily, comb_dates)
        # combined EW control = 50/50 inverse-vol of FX-EW + bond series
        cew_daily, cew_dates = inverse_vol_combined(ew_daily, ew_dd, bond_daily, bond_dd,
                                                    vol_lookback=20)
        cew_full, cew_is, cew_oos = is_oos(cew_daily, cew_dates)
        corr_comb_spy, _, _, _ = aligned_daily_corr(comb_daily, comb_dates, spy_ret, spy_dates)
        corr_comb_tqqq, _, _, _ = aligned_daily_corr(comb_daily, comb_dates, tq_ret, tq_dates)
        c1 = comb_oos["sharpe"] > 0.5
        c2 = (comb_oos["sharpe"] - cew_oos["sharpe"]) > 0
        c3 = abs(corr_comb_spy) < 0.5 and abs(corr_comb_tqqq) < 0.5
        c4 = comb_oos["total_return"] > 0
        combined_block.update({"built": True, "combined_full": comb_full, "combined_oos": comb_oos,
                               "combined_ew_oos": cew_oos,
                               "delta_vs_combined_ew_oos_sharpe": round(comb_oos["sharpe"] - cew_oos["sharpe"], 4),
                               "corr_spy": corr_comb_spy, "corr_tqqq": corr_comb_tqqq,
                               "c1_oos_sharpe_gt_0.5": bool(c1), "c2_beats_combined_ew": bool(c2),
                               "c3_orthogonal_book": bool(c3), "c4_positive_return": bool(c4),
                               "combined_PASS": bool(c1 and c2 and c3 and c4)})
        print("[COMBINED] OOS Sh %.4f (c1 %s)  vs combined-EW %.4f (c2 %s)  corrSPY %.3f corrTQQQ %.3f  PASS=%s" % (
            comb_oos["sharpe"], c1, cew_oos["sharpe"], c2, corr_comb_spy, corr_comb_tqqq,
            combined_block["combined_PASS"]))
    else:
        print("[COMBINED] NOT built (gate_a=%s gate_b=%s)" % (gate_a, gate_b))

    # --- FX standalone verdict (a)-(d) ---
    fx_verdict = {
        "a_oos_sharpe_ge_0.4": {"pass": bool(gate_a), "oos_sharpe": sig_oos["sharpe"]},
        "b_corr_bond_le_0.3": {"pass": bool(gate_b), "corr_bond_oos": corr_bond_oos},
        "c_beats_EW_oos": {"pass": bool(delta_ew_oos > 0), "delta_sharpe": delta_ew_oos,
                           "delta_total": delta_ew_oos_tot, "fx_oos": sig_oos["sharpe"],
                           "ew_oos": ew_oos["sharpe"]},
        "d_stress_survive": stress,
    }

    result = {
        "meta": {"utc_stamp": stamp,
                 "hypothesis": "H1 cross-asset carry -- FX rate-differential leg (2nd leg test)",
                 "bond_leg_ref": "reports/H1_CARRY_BONDLEG_20260623T191733Z.md",
                 "fx_pairs": {c: PAIRS[c][0] for c in FOREIGN},
                 "rate_series": RATE_SERIES,
                 "fx_panel_span": [fx.dates[0], fx.dates[-1]],
                 "n_fx_aligned_days": len(fx), "n_month_end_rebals": len(me_idx),
                 "oos_split": OOS_SPLIT,
                 "sharpe_convention": "(mean/std)*sqrt(252) ddof=1 continuous-span (mirrors runner/fp_sharpe.py)",
                 "signal_lag_days": 1, "rate_pub_lag_months": 1, "adjclose_only": True,
                 "carry_accrual_included": True,
                 "primary_config": primary["config"]},
        "primary_fx": {"full": primary["full"], "is": primary["is"], "oos": primary["oos"],
                       "turn": primary["turn"], "nreb": primary["nreb"]},
        "longonly_positive": {"full": longonly["full"], "oos": longonly["oos"]},
        "ew_control": {"full": ew_full, "oos": ew_oos,
                       "delta_signal_minus_ew_oos_sharpe": delta_ew_oos,
                       "delta_signal_minus_ew_oos_total": delta_ew_oos_tot},
        "bond_recon": {"full": bond_full, "oos": bond_oos,
                       "note": "reconstructed primary bond config TLT/sc1.5/9%vt/T10Y2Y/2bps"},
        "corr_fx_bond": {"full": corr_bond_full, "oos": corr_bond_oos, "n_oos": n_oos,
                         "oos_window": [oos_lo, oos_hi]},
        "orthogonality": {"corr_spy": corr_spy, "corr_tqqq": corr_tqqq},
        "cost_grid": cost_grid,
        "stress_windows": stress,
        "canary_extra_month_lag": {"oos_sharpe": canary_oos, "primary_oos_sharpe": sig_oos["sharpe"],
                                   "edge_survives": bool(canary_oos >= 0.30)},
        "robustness_sweep": {"stats": sweep_stats, "grid": sweep},
        "fx_standalone_verdict": fx_verdict,
        "combined_sleeve": combined_block,
    }
    out_json = WORKSPACE / "reports" / "_fx_carry_leg_result.json"
    out_json.write_text(json.dumps(result, indent=2))
    print("[written]", out_json)
    return result


if __name__ == "__main__":
    main()
