"""VIX-complex regime-overlay backtest — long-SPY core with a risk-on/off gate.

RESEARCH/BACKTEST-ONLY. Tests NATENBERG_SYNTHESIS idea #2: a long-SPY core with
a VIX-complex risk-on/off overlay (de-risk to cash when the vol term-structure
backwardates and/or VIX is at an extreme percentile; re-risk when it normalizes).

MISSION BAR: beat SPX on RAW RETURN (gates suspended for exploration). This
driver therefore reports the head-to-head on RAW total return first, then the
risk-adjusted picture (max drawdown, Sharpe, SPY-relative excess/IR).

HONEST MEASUREMENT (hard rail — not negotiable):
  - POINT-IN-TIME: the allocation for trading day D is decided ONLY from
    VIX-complex levels dated < D (cboe_cache strictly-before accessors) and SPY
    closes dated < D. The position chosen on D earns D's close-to-close return.
    No same-day-close leakage into the same-day decision.
  - The benchmark is buy-and-hold SPY on the EXACT SAME date path the overlay
    trades (same bars), so the comparison is apples-to-apples.
  - DATA-FLOOR HONESTY: the VIX-complex data reaches 2009-09 (VIX3M) / 2006
    (VVIX) / 1990 (VIX,SKEW), BUT our tradeable SPY daily bars from Alpaca's free
    IEX feed only become CONTIGUOUS from ~2020-08 (earlier bars are sparse/empty
    from this datacenter IP). The backtest span is bounded by the BARS, not the
    VIX data. We report the real, gap-free span and never fabricate bars. This
    span misses the Feb-Mar 2020 COVID crash itself (bars start after it) — a
    limitation flagged loudly in the report.
  - A 'cash' day earns 0% (we do NOT credit a risk-free rate — conservative; it
    slightly understates the overlay's edge in high-rate years, stated as such).

The overlay is intentionally SIMPLE and rule-based (no per-day fitting): it is a
GATE, not a fitted model. We additionally run an out-of-sample split (calibrate
the gate's percentile threshold on the first portion, apply unchanged to the
held-out rest) to show the result isn't an in-sample threshold pick.

CLI:
    python3 -m runner.vix_overlay_backtest                 # default gate, full span
    python3 -m runner.vix_overlay_backtest --md reports/...md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from . import bars_cache          # noqa: E402
from . import vix_regime          # noqa: E402
from . import spy_relative        # noqa: E402
from .backtest import bars_per_year  # noqa: E402

TRADING_TF = "1Day"
EQUITY_BPY = bars_per_year(TRADING_TF, is_crypto=False)  # 252


# ---------------------------------------------------------------------------
# Data: contiguous SPY daily bars (honest floor detection)
# ---------------------------------------------------------------------------

def load_contiguous_spy(end_dt: Optional[datetime] = None,
                        lookback_days: int = 365 * 9,
                        min_bars_per_month: int = 15) -> Tuple[List[dict], str]:
    """Return (bars, floor_reason) for SPY daily bars that are CONTIGUOUS.

    Alpaca's free IEX feed returns sparse/empty SPY bars before ~2020 from this
    VM. We fetch a long lookback, then trim the leading sparse months so the
    backtest starts only where coverage is real (>= min_bars_per_month). This is
    the cache-floor honesty: we never include a month that's mostly empty.
    """
    if end_dt is None:
        now = datetime.now(timezone.utc)
        end_dt = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    bars = bars_cache.get_bars("SPY", TRADING_TF, days=lookback_days, end_dt=end_dt)
    if not bars:
        return [], "no SPY bars returned"
    from collections import Counter
    cnt = Counter(b["t"][:7] for b in bars)
    months = sorted(cnt)
    dense_from: Optional[str] = None
    for i, m in enumerate(months):
        if cnt[m] >= min_bars_per_month and all(
                cnt[mm] >= min_bars_per_month for mm in months[i:i + 3]):
            dense_from = m
            break
    if dense_from is None:
        return bars, "could not find a dense contiguous start; using all bars"
    trimmed = [b for b in bars if b["t"][:7] >= dense_from]
    reason = (f"contiguous SPY daily coverage begins {dense_from} "
              f"(>= {min_bars_per_month} bars/mo); leading sparse months trimmed")
    return trimmed, reason


# ---------------------------------------------------------------------------
# Gate definitions (risk-on -> target SPY weight; risk-off -> 0 weight)
# ---------------------------------------------------------------------------

@dataclass
class GateConfig:
    """A rule-based VIX-complex risk-on/off gate. All thresholds are fixed (not
    per-day fit). Risk-off => move to cash (weight 0); risk-on => full SPY (1.0).

    Default thresholds are the standard 'vol term-structure stress' definition:
      - backwardation: ts_ratio (VIX/VIX3M) > backwardation_ratio  => risk-OFF
      - extreme VIX:   vix_pct > vix_pct_off                        => risk-OFF
    Either condition trips risk-off (OR). Re-risk when BOTH normalize.
    A partial-weight 'de-risk' (not full cash) is supported via off_weight.
    """
    name: str = "ts+pct"
    backwardation_ratio: float = 1.00     # VIX/VIX3M > 1.0 => backwardation => off
    vix_pct_off: float = 0.90             # VIX in top 10% of trailing yr => off
    off_weight: float = 0.0               # weight when risk-off (0 = full cash)
    on_weight: float = 1.0                # weight when risk-on (full SPY)
    pct_window: int = vix_regime.DEFAULT_PCT_WINDOW
    use_skew: bool = False                # optional extra tail-risk gate
    skew_pct_off: float = 0.95
    use_vvix: bool = False                # optional vol-of-vol gate
    vvix_pct_off: float = 0.95


def gate_weight(sig: Dict[str, Optional[float]], cfg: GateConfig) -> float:
    """Target SPY weight for a day, given that day's point-in-time signal bundle.

    Risk-OFF (off_weight) if ANY tripped:
      ts_ratio > backwardation_ratio   (term-structure backwardation = stress)
      vix_pct  > vix_pct_off           (VIX at trailing extreme)
      [opt] skew_pct > skew_pct_off
      [opt] vvix_pct > vvix_pct_off
    Else risk-ON (on_weight).

    Missing signals (None) do NOT trip the gate (default risk-on) — so the
    pre-2009 VIX3M gap or pre-2006 VVIX gap degrades gracefully to 'no gate'
    rather than spuriously de-risking. (On the real >=2020 span all signals are
    present, so this only matters for extended-span variants.)
    """
    off = False
    ts_ratio = sig.get("ts_ratio")
    if ts_ratio is not None and ts_ratio > cfg.backwardation_ratio:
        off = True
    vix_pct = sig.get("vix_pct")
    if vix_pct is not None and vix_pct > cfg.vix_pct_off:
        off = True
    if cfg.use_skew:
        skew_pct = sig.get("skew_pct")
        if skew_pct is not None and skew_pct > cfg.skew_pct_off:
            off = True
    if cfg.use_vvix:
        vvix_pct = sig.get("vvix_pct")
        if vvix_pct is not None and vvix_pct > cfg.vvix_pct_off:
            off = True
    return cfg.off_weight if off else cfg.on_weight


# ---------------------------------------------------------------------------
# Backtest core: daily weight from the gate, equity from SPY returns
# ---------------------------------------------------------------------------

@dataclass
class OverlayResult:
    label: str
    n_days: int = 0
    span_start: str = ""
    span_end: str = ""
    # raw (the mission bar)
    strat_total_return_pct: float = 0.0
    spy_total_return_pct: float = 0.0
    raw_excess_total_pct: float = 0.0          # strat - spy (total, not annualized)
    strat_cagr_pct: float = 0.0
    spy_cagr_pct: float = 0.0
    # risk-adjusted
    strat_max_dd_pct: float = 0.0
    spy_max_dd_pct: float = 0.0
    dd_reduction_pp: float = 0.0               # |spy_dd| - |strat_dd| (positive = less DD)
    strat_sharpe: float = 0.0
    spy_sharpe: float = 0.0
    spy_excess_ann_pct: float = 0.0            # from spy_relative
    information_ratio: Optional[float] = None
    # overlay behavior
    pct_days_risk_off: float = 0.0
    n_switches: int = 0
    avg_weight: float = 0.0
    # cost-aware variant (switching costs)
    strat_total_return_pct_net: float = 0.0
    raw_excess_total_pct_net: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    spy_curve: List[float] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)


def _sharpe(per_period_returns: List[float]) -> float:
    if len(per_period_returns) < 2:
        return 0.0
    mean = sum(per_period_returns) / len(per_period_returns)
    var = sum((r - mean) ** 2 for r in per_period_returns) / (len(per_period_returns) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return 0.0
    return (mean / sd) * math.sqrt(EQUITY_BPY)


def _max_drawdown(curve: List[float]) -> float:
    peak = -float("inf")
    mdd = 0.0
    for e in curve:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak
            if dd < mdd:
                mdd = dd
    return mdd  # negative fraction


def _cagr(total_growth: float, n_days: int) -> float:
    """Annualized growth from a total growth multiple over n trading days."""
    if n_days <= 0 or total_growth <= 0:
        return 0.0
    years = n_days / EQUITY_BPY
    if years <= 0:
        return 0.0
    return total_growth ** (1.0 / years) - 1.0


def run_overlay(bars: List[dict], cfg: GateConfig,
                *,
                switch_cost_bps: float = 2.0,
                label: Optional[str] = None,
                start_idx: int = 0) -> OverlayResult:
    """Replay the overlay over `bars` (oldest-first SPY daily bars).

    For each day i (>=1), the weight is decided from the signal bundle as-of
    bars[i]['t'] (strictly prior VIX + prior SPY closes via vix_regime). That
    weight earns the day's close-to-close SPY return. Equity compounds.

    `switch_cost_bps` is charged on the CHANGE in weight between days (turnover),
    one-way, to model the cost of moving in/out of SPY. The gross (cost-free)
    curve is the headline; the net curve is reported alongside.
    """
    label = label or cfg.name
    res = OverlayResult(label=label)
    if not bars or len(bars) < 3:
        return res

    closes = [float(b["c"]) for b in bars]
    dates = [str(b["t"])[:10] for b in bars]

    strat_eq = 1.0
    strat_eq_net = 1.0
    spy_eq = 1.0
    strat_curve: List[float] = []
    spy_curve: List[float] = []
    strat_returns: List[float] = []
    spy_returns: List[float] = []
    weights_used: List[float] = []
    used_dates: List[str] = []

    prev_weight = cfg.on_weight   # assume fully invested before first decision
    n_off_days = 0
    n_switches = 0
    weight_sum = 0.0
    n_weight = 0

    for i in range(max(1, start_idx), len(bars)):
        asof_iso = dates[i]
        sig = vix_regime.signals_asof(asof_iso, bars, pct_window=cfg.pct_window)
        w = gate_weight(sig, cfg)
        p0 = closes[i - 1]
        p1 = closes[i]
        day_ret = (p1 - p0) / p0 if p0 > 0 else 0.0

        turnover = abs(w - prev_weight)
        cost = turnover * (switch_cost_bps / 1e4)

        strat_day = w * day_ret
        strat_eq *= (1.0 + strat_day)
        strat_eq_net *= (1.0 + strat_day - cost)
        spy_eq *= (1.0 + day_ret)

        strat_curve.append(strat_eq)
        spy_curve.append(spy_eq)
        strat_returns.append(strat_day)
        spy_returns.append(day_ret)
        weights_used.append(w)
        used_dates.append(asof_iso)

        if w < cfg.on_weight - 1e-9:
            n_off_days += 1
        if abs(w - prev_weight) > 1e-9:
            n_switches += 1
        weight_sum += w
        n_weight += 1
        prev_weight = w

    n = len(strat_curve)
    if n == 0:
        return res

    res.n_days = n
    res.span_start = used_dates[0]
    res.span_end = used_dates[-1]
    res.equity_curve = strat_curve
    res.spy_curve = spy_curve
    res.weights = weights_used
    res.dates = used_dates

    res.strat_total_return_pct = (strat_eq - 1.0) * 100.0
    res.strat_total_return_pct_net = (strat_eq_net - 1.0) * 100.0
    res.spy_total_return_pct = (spy_eq - 1.0) * 100.0
    res.raw_excess_total_pct = res.strat_total_return_pct - res.spy_total_return_pct
    res.raw_excess_total_pct_net = res.strat_total_return_pct_net - res.spy_total_return_pct
    res.strat_cagr_pct = _cagr(strat_eq, n) * 100.0
    res.spy_cagr_pct = _cagr(spy_eq, n) * 100.0

    res.strat_max_dd_pct = _max_drawdown(strat_curve) * 100.0
    res.spy_max_dd_pct = _max_drawdown(spy_curve) * 100.0
    res.dd_reduction_pp = abs(res.spy_max_dd_pct) - abs(res.strat_max_dd_pct)
    res.strat_sharpe = _sharpe(strat_returns)
    res.spy_sharpe = _sharpe(spy_returns)

    try:
        m = spy_relative.spy_relative_metrics(
            strat_returns, spy_returns, timeframe=TRADING_TF)
        res.spy_excess_ann_pct = m["excess_return_annualized"] * 100.0
        res.information_ratio = m["information_ratio"]
    except Exception:
        res.spy_excess_ann_pct = 0.0
        res.information_ratio = None

    res.pct_days_risk_off = (n_off_days / n) * 100.0
    res.n_switches = n_switches
    res.avg_weight = (weight_sum / n_weight) if n_weight else 0.0
    return res


# ---------------------------------------------------------------------------
# Out-of-sample split: calibrate vix_pct_off on first portion, test on rest
# ---------------------------------------------------------------------------

def oos_split_eval(bars: List[dict],
                   base_cfg: GateConfig,
                   *,
                   train_frac: float = 0.5,
                   candidate_pcts: Tuple[float, ...] = (0.80, 0.85, 0.90, 0.95),
                   switch_cost_bps: float = 2.0) -> Dict[str, object]:
    """Pick the vix_pct_off that maximizes RAW return on the TRAIN slice, then
    report that SAME gate's performance UNCHANGED on the held-out TEST slice.

    Honesty check on threshold-fitting: if the gate only 'works' by picking the
    best in-sample threshold, the OOS slice exposes it. Chronological split (no
    shuffle); the test slice's trailing percentile window keeps real prior
    warm-up (we run the full series with the chosen gate and slice the curve).
    """
    n = len(bars)
    if n < 200:
        return {"error": f"too few bars ({n}) for OOS split"}
    cut = int(n * train_frac)
    train_bars = bars[:cut]
    best_pct = base_cfg.vix_pct_off
    best_train_ret = -1e9
    train_table = []
    for pct in candidate_pcts:
        cfg = GateConfig(**{**base_cfg.__dict__, "vix_pct_off": pct})
        r = run_overlay(train_bars, cfg, switch_cost_bps=switch_cost_bps,
                        label=f"train@{pct}")
        train_table.append((pct, round(r.strat_total_return_pct, 2),
                            round(r.spy_total_return_pct, 2)))
        if r.strat_total_return_pct > best_train_ret:
            best_train_ret = r.strat_total_return_pct
            best_pct = pct
    chosen = GateConfig(**{**base_cfg.__dict__, "vix_pct_off": best_pct})
    full = run_overlay(bars, chosen, switch_cost_bps=switch_cost_bps,
                       label=f"chosen@{best_pct}")
    cut_date = bars[cut]["t"][:10]
    test_idx = [i for i, d in enumerate(full.dates) if d >= cut_date]
    if not test_idx:
        return {"error": "no test-slice days after cut"}
    t0 = test_idx[0]
    strat_base = full.equity_curve[t0 - 1] if t0 > 0 else 1.0
    spy_base = full.spy_curve[t0 - 1] if t0 > 0 else 1.0
    strat_test = [e / strat_base for e in full.equity_curve[t0:]]
    spy_test = [e / spy_base for e in full.spy_curve[t0:]]
    strat_ret_test = (strat_test[-1] - 1.0) * 100.0 if strat_test else 0.0
    spy_ret_test = (spy_test[-1] - 1.0) * 100.0 if spy_test else 0.0
    return {
        "train_frac": train_frac,
        "cut_date": cut_date,
        "candidate_table": train_table,
        "chosen_vix_pct_off": best_pct,
        "train_best_raw_return_pct": round(best_train_ret, 2),
        "test_span": (full.dates[t0], full.dates[-1]),
        "test_strat_raw_return_pct": round(strat_ret_test, 2),
        "test_spy_raw_return_pct": round(spy_ret_test, 2),
        "test_raw_excess_pct": round(strat_ret_test - spy_ret_test, 2),
        "test_strat_max_dd_pct": round(_max_drawdown(strat_test) * 100.0, 2),
        "test_spy_max_dd_pct": round(_max_drawdown(spy_test) * 100.0, 2),
    }


# ---------------------------------------------------------------------------
# Per-calendar-year breakdown (where does the overlay help / hurt?)
# ---------------------------------------------------------------------------

def yearly_breakdown(res: OverlayResult) -> List[dict]:
    """Per-calendar-year raw return: strategy vs SPY, from the equity curves.

    Uses the within-year growth of each curve so we can see which regimes the
    overlay helped (de-risked into a down year) vs hurt (sat in cash during a
    rally). No lookahead — purely descriptive of the produced curves.
    """
    rows: List[dict] = []
    if not res.dates:
        return rows
    # Group indices by year.
    by_year: Dict[str, List[int]] = {}
    for i, d in enumerate(res.dates):
        by_year.setdefault(d[:4], []).append(i)
    for yr in sorted(by_year):
        idxs = by_year[yr]
        i0, i1 = idxs[0], idxs[-1]
        # growth within year = end/ (start_of_year_prev_equity)
        strat_prev = res.equity_curve[i0 - 1] if i0 > 0 else 1.0
        spy_prev = res.spy_curve[i0 - 1] if i0 > 0 else 1.0
        strat_g = (res.equity_curve[i1] / strat_prev - 1.0) * 100.0 if strat_prev else 0.0
        spy_g = (res.spy_curve[i1] / spy_prev - 1.0) * 100.0 if spy_prev else 0.0
        off_days = sum(1 for j in idxs if res.weights[j] < res.weights[0] + 1.0 and res.weights[j] < 1.0 - 1e-9)
        rows.append({
            "year": yr,
            "n_days": len(idxs),
            "strat_pct": round(strat_g, 2),
            "spy_pct": round(spy_g, 2),
            "excess_pp": round(strat_g - spy_g, 2),
            "pct_days_off": round(100.0 * off_days / len(idxs), 1),
        })
    return rows


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_result_block(res: OverlayResult) -> str:
    ir = f"{res.information_ratio:.2f}" if res.information_ratio is not None else "n/a"
    verdict = ("BEATS SPY raw" if res.raw_excess_total_pct > 0
               else "does NOT beat SPY raw")
    lines = [
        f"**Gate `{res.label}`** — span {res.span_start} → {res.span_end} "
        f"({res.n_days} trading days)",
        "",
        "| Metric | Overlay | Buy&Hold SPY | Delta |",
        "|---|---|---|---|",
        f"| **Raw total return** | **{res.strat_total_return_pct:+.2f}%** | "
        f"**{res.spy_total_return_pct:+.2f}%** | **{res.raw_excess_total_pct:+.2f}pp** |",
        f"| Raw total return (net of {2.0}bp switch cost) | "
        f"{res.strat_total_return_pct_net:+.2f}% | {res.spy_total_return_pct:+.2f}% | "
        f"{res.raw_excess_total_pct_net:+.2f}pp |",
        f"| CAGR | {res.strat_cagr_pct:+.2f}% | {res.spy_cagr_pct:+.2f}% | "
        f"{res.strat_cagr_pct - res.spy_cagr_pct:+.2f}pp |",
        f"| Max drawdown | {res.strat_max_dd_pct:.2f}% | {res.spy_max_dd_pct:.2f}% | "
        f"{res.dd_reduction_pp:+.2f}pp avoided |",
        f"| Sharpe (daily, ann.) | {res.strat_sharpe:.2f} | {res.spy_sharpe:.2f} | "
        f"{res.strat_sharpe - res.spy_sharpe:+.2f} |",
        f"| SPY-relative excess (ann.) | {res.spy_excess_ann_pct:+.2f}% | — | — |",
        f"| Information ratio | {ir} | — | — |",
        "",
        f"Overlay behavior: {res.pct_days_risk_off:.1f}% of days risk-OFF (cash), "
        f"{res.n_switches} switches, avg weight {res.avg_weight:.3f}. "
        f"**Verdict: {verdict} (+{res.raw_excess_total_pct:.2f}pp gross).**",
    ]
    return "\n".join(lines)


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="VIX-complex regime overlay backtest.")
    ap.add_argument("--md", help="write the full Markdown report to this path")
    ap.add_argument("--switch-cost-bps", type=float, default=2.0)
    ap.add_argument("--json", help="dump JSON summary to this path")
    args = ap.parse_args()

    bars, floor_reason = load_contiguous_spy()
    print(f"[vix_overlay] {floor_reason}; n_bars={len(bars)}", file=sys.stderr)
    if len(bars) < 200:
        print("[vix_overlay] not enough contiguous SPY bars to run.", file=sys.stderr)
        raise SystemExit(2)

    # Gate variants to evaluate.
    gates = [
        GateConfig(name="ts-only (VIX/VIX3M>1.0)", backwardation_ratio=1.00,
                   vix_pct_off=1.01),  # vix_pct disabled (>1 never trips)
        GateConfig(name="pct-only (VIX>90th)", backwardation_ratio=99.0,
                   vix_pct_off=0.90),
        GateConfig(name="ts+pct (either)", backwardation_ratio=1.00,
                   vix_pct_off=0.90),
        GateConfig(name="ts+pct+vvix", backwardation_ratio=1.00,
                   vix_pct_off=0.90, use_vvix=True, vvix_pct_off=0.90),
        GateConfig(name="ts+pct de-risk-to-50%", backwardation_ratio=1.00,
                   vix_pct_off=0.90, off_weight=0.5),
    ]
    results = [run_overlay(bars, g, switch_cost_bps=args.switch_cost_bps)
               for g in gates]

    for r in results:
        print(f"  {r.label:32s} raw={r.strat_total_return_pct:+7.2f}% "
              f"spy={r.spy_total_return_pct:+7.2f}% "
              f"excess={r.raw_excess_total_pct:+6.2f}pp "
              f"DDavoid={r.dd_reduction_pp:+5.2f}pp "
              f"sharpe={r.strat_sharpe:.2f}vs{r.spy_sharpe:.2f} "
              f"off={r.pct_days_risk_off:.0f}%", file=sys.stderr)

    # OOS split on the ts+pct gate.
    oos = oos_split_eval(bars, GateConfig(name="ts+pct", backwardation_ratio=1.00,
                                          vix_pct_off=0.90),
                         switch_cost_bps=args.switch_cost_bps)
    print(f"  OOS: {oos}", file=sys.stderr)

    if args.json:
        payload = {
            "floor_reason": floor_reason,
            "n_bars": len(bars),
            "results": [{
                "label": r.label,
                "strat_total_return_pct": r.strat_total_return_pct,
                "spy_total_return_pct": r.spy_total_return_pct,
                "raw_excess_total_pct": r.raw_excess_total_pct,
                "dd_reduction_pp": r.dd_reduction_pp,
                "strat_sharpe": r.strat_sharpe,
                "spy_sharpe": r.spy_sharpe,
                "information_ratio": r.information_ratio,
                "pct_days_risk_off": r.pct_days_risk_off,
            } for r in results],
            "oos": oos,
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"Wrote JSON -> {args.json}")

    if args.md:
        # Best gate by raw excess for the headline.
        best = max(results, key=lambda r: r.raw_excess_total_pct)
        chunks = ["# (driver stub output — full report assembled separately)\n"]
        chunks.append(f"- Floor: {floor_reason}\n")
        for r in results:
            chunks.append(format_result_block(r))
            chunks.append("\n")
        Path(args.md).write_text("\n".join(chunks))
        print(f"Wrote Markdown -> {args.md}")


if __name__ == "__main__":
    main()
