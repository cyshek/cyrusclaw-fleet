#!/usr/bin/env python3
"""GATE-tracker dashboard.

Renders a single self-contained HTML page showing, per live/paper strategy:
  * progress against the dormant Bar E real-money graduation criteria
    (the eventual go-live gate — currently SUSPENDED under explore-first mode,
    shown as a progress tracker, NOT a binding gate), and
  * live-paper performance vs SPX from the paper-tracker DBs.

Two rails that ACTUALLY hold today (not Bar E) are surfaced at the top:
  (1) paper-only broker + STOP_TRADING killswitch,
  (2) honest measurement (no lookahead/leakage, real OOS, PIT data).

Data sources (all live, read at generation time):
  * tournament.db `trades`  -> round-trip / fill counts per live-roster strategy
  * allocator_paper.db / xa_tsmom_paper.db / tsmom_blend_paper.db -> cum ret vs SPX
  * runner.edge_calibrator.LIVE_ROSTER -> canonical live universe
  * BACKTEST_METRICS below -> backtested Sharpe / maxDD / OOS / CAGR, each with a
    Source: pointer to the report/MEMORY line it came from (honest provenance).

Backtested metrics are NOT recomputed here (that is the vetting harness's job);
this dashboard READS the validated numbers and tracks live progress toward the
gate. Every backtested number carries a `source` so it can be audited.

Usage:
    python3 runner/gate_dashboard.py            # writes reports/gate_dashboard.html
    python3 runner/gate_dashboard.py --out X    # custom out path
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# Synthetic-row guard (standing rule: tournament.db carries test/seed rows).
# ---------------------------------------------------------------------------
_SYNTH_STRATS = {"any", "backstop_test", "bp2"}
_SYNTH_ORDERS = {"order-1", "ord-seed"}


def _is_synthetic(strategy: str, order_id) -> bool:
    if strategy in _SYNTH_STRATS:
        return True
    if order_id is None:
        return True
    if order_id in _SYNTH_ORDERS:
        return True
    if len(str(order_id)) < 20:
        return True
    return False


# ---------------------------------------------------------------------------
# Canonical live roster (import from the single source of truth; fall back to a
# hardcoded copy if the import path is unavailable so the dashboard never dies).
# ---------------------------------------------------------------------------
def _live_roster() -> list[str]:
    try:
        sys.path.insert(0, ROOT)
        from runner.edge_calibrator import LIVE_ROSTER  # type: ignore
        return sorted(LIVE_ROSTER)
    except Exception:
        return sorted({
            "breakout_xlk__mut_c382b1", "sma_crossover_qqq_regime",
            "sma_crossover_qqq_rth", "rsi_oversold_spy", "volume_breakout_qqq",
            "macd_momentum_iwm", "tqqq_cot_combo", "allocator_blend",
        })


# ---------------------------------------------------------------------------
# Backtested gate metrics, per strategy. Each value carries a `source` pointer
# for audit. These are READ (validated elsewhere), not recomputed here.
#   full_sharpe : full-period continuous-span Sharpe (the honest one)
#   oos_sharpe  : out-of-sample Sharpe (None if not separately measured)
#   max_dd_pct  : backtested max drawdown, negative %
#   cagr_pct    : backtested CAGR / annualized return %
#   oos_regimes : count of distinct OOS regime windows passed
#   note        : one-line characterization
# ---------------------------------------------------------------------------
BACKTEST_METRICS: dict[str, dict] = {
    "allocator_blend": {
        "full_sharpe": 1.029, "oos_sharpe": 1.150, "max_dd_pct": -20.02,
        "cagr_pct": 15.9, "oos_regimes": 3,
        "note": "TQQQ vol-target x sector-rotation inv-vol blend; breadth{30,90,180} gate live",
        "source": "MEMORY.md ALLOCATOR BLEND / reports/ALLOCATOR_BREADTH_PORT_20260627T215035Z.md",
    },
    "tqqq_cot_combo": {
        "full_sharpe": 0.842, "oos_sharpe": None, "max_dd_pct": -19.8,
        "cagr_pct": None, "oos_regimes": 3,
        "note": "TQQQ vol-target sleeve + COT leveraged-fund-net throttle; 2022 DD -26.5->-19.8",
        "source": "MEMORY.md TQQQ+COT / reports/TQQQ_COT_2022_STRESSTEST_20260621.md",
    },
    "sma_crossover_qqq_regime": {
        "full_sharpe": None, "oos_sharpe": None, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": None,
        "note": "SMA crossover on QQQ with SPY-regime gate (trend-following core)",
        "source": "live roster (cron tick); backtested metrics not separately pinned",
    },
    "sma_crossover_qqq_rth": {
        "full_sharpe": None, "oos_sharpe": None, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": None,
        "note": "SMA crossover on QQQ, regular-trading-hours variant",
        "source": "live roster (cron tick); backtested metrics not separately pinned",
    },
    "volume_breakout_qqq": {
        "full_sharpe": None, "oos_sharpe": None, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": None,
        "note": "Volume-confirmed breakout on QQQ",
        "source": "live roster (cron tick); backtested metrics not separately pinned",
    },
    "macd_momentum_iwm": {
        "full_sharpe": None, "oos_sharpe": None, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": None,
        "note": "MACD momentum on IWM (small-cap leg, de-correlator)",
        "source": "live roster (cron tick); backtested metrics not separately pinned",
    },
    "rsi_oversold_spy": {
        "full_sharpe": None, "oos_sharpe": None, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": None,
        "note": "RSI-oversold mean-reversion on SPY 1h; AQR trend-gate critique REBUTTED at our horizon",
        "source": "live roster; MEMORY closed-lane (hold-the-dip rebuttal 2026-06-26/27)",
    },
    "breakout_xlk__mut_c382b1": {
        "full_sharpe": None, "oos_sharpe": -0.089, "max_dd_pct": None,
        "cagr_pct": None, "oos_regimes": 0,
        "note": "Donchian breakout on XLK w/ regime stop; OOS-NEGATIVE 2024-26 (dead weight, pull recommended)",
        "source": "reports/_breakout_xlk_mut_oos_check.json (OOS Sharpe -0.089, 42% win)",
    },
}

# Paper-tracker strategies that ALSO run as standalone trackers (separate DBs).
# These are paper diversifiers, not on the 8-name cron line, but tracked live.
PAPER_TRACKER_DBS: dict[str, dict] = {
    "allocator_blend": {
        "db": "allocator_paper.db",
        "note": "On live cron AND has its own daily NAV tracker.",
    },
    "xa_tsmom_12_1": {
        "db": "xa_tsmom_paper.db",
        "note": "5-asset 12-1 TSMOM. Risk-orthogonal diversifier (raw LOSES SPY by design).",
    },
    "tsmom_blend": {
        "db": "tsmom_blend_paper.db",
        "note": "TSMOM blend paper tracker.",
    },
}

# ---------------------------------------------------------------------------
# Bar E (dormant) real-money graduation criteria — the eventual go-live gate.
# SUSPENDED under explore-first mode; shown as progress, not enforced.
# ---------------------------------------------------------------------------
BAR_E = [
    ("paper_days", ">= 1 week live paper"),
    ("trips", ">= 20 round-trip trades"),
    ("bt_sharpe", "backtest Sharpe >= 1.0 (full WF incl. held-out)"),
    ("max_dd", "backtest max drawdown < 20%"),
    ("oos_regimes", "passes >= 2 distinct OOS regime windows"),
    ("cyrus", "explicit per-request Cyrus approval (never standing)"),
]


def _q(db_path: str, sql: str, params=()):
    if not os.path.exists(db_path):
        return []
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


def _trip_stats(tournament_db: str) -> dict[str, dict]:
    """Per-strategy fill/round-trip counts + first/last dates (synthetic-filtered)."""
    rows = _q(tournament_db,
              "SELECT strategy, alpaca_order_id, side, status, substr(ts_utc,1,10) d "
              "FROM trades")
    agg: dict[str, dict] = {}
    for strat, oid, side, status, d in rows:
        if _is_synthetic(strat, oid):
            continue
        a = agg.setdefault(strat, {"fills": 0, "buys": 0, "sells": 0,
                                   "first": d, "last": d})
        a["fills"] += 1
        if (side or "").lower() in ("buy",):
            a["buys"] += 1
        elif (side or "").lower() in ("sell", "close"):
            a["sells"] += 1
        if d and (a["first"] is None or d < a["first"]):
            a["first"] = d
        if d and (a["last"] is None or d > a["last"]):
            a["last"] = d
    # round trips ~= min(buys, sells); fall back to fills//2
    for a in agg.values():
        a["round_trips"] = min(a["buys"], a["sells"]) if (a["buys"] or a["sells"]) else a["fills"] // 2
        if a["first"] and a["last"]:
            try:
                d0 = datetime.strptime(a["first"], "%Y-%m-%d")
                d1 = datetime.strptime(a["last"], "%Y-%m-%d")
                a["span_days"] = (d1 - d0).days
            except Exception:
                a["span_days"] = None
        else:
            a["span_days"] = None
    return agg


def _paper_perf(db_path: str) -> dict | None:
    rows = _q(db_path,
              "SELECT date, cum_ret_since_start, cum_spx_since_start, engine_full_sharpe "
              "FROM daily_snapshots ORDER BY date")
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    return {
        "n_days": len(rows),
        "first_date": first[0],
        "last_date": last[0],
        "cum_strat_pct": (last[1] or 0.0) * 100.0,
        "cum_spx_pct": (last[2] or 0.0) * 100.0,
        "alpha_pct": ((last[1] or 0.0) - (last[2] or 0.0)) * 100.0,
        "full_sharpe": last[3],
        "series": [(r[0], (r[1] or 0.0) * 100.0, (r[2] or 0.0) * 100.0) for r in rows],
    }


# ---------------------------------------------------------------------------
# Per-criterion status: returns ("pass" | "fail" | "pending" | "na", detail).
# ---------------------------------------------------------------------------
def _crit_status(strat: str, key: str, trips: dict, bt: dict) -> tuple[str, str]:
    if key == "paper_days":
        span = trips.get("span_days")
        if span is None:
            return ("pending", "no live fills yet")
        return ("pass" if span >= 7 else "pending", f"{span}d live span")
    if key == "trips":
        rt = trips.get("round_trips", 0)
        return ("pass" if rt >= 20 else "pending", f"{rt} round trips")
    if key == "bt_sharpe":
        s = bt.get("full_sharpe")
        if s is None:
            return ("na", "not separately pinned")
        return ("pass" if s >= 1.0 else "fail", f"full S {s:.3f}")
    if key == "max_dd":
        dd = bt.get("max_dd_pct")
        if dd is None:
            return ("na", "not separately pinned")
        return ("pass" if dd > -20.0 else "fail", f"maxDD {dd:.1f}%")
    if key == "oos_regimes":
        n = bt.get("oos_regimes")
        if n is None:
            return ("na", "not separately pinned")
        if n == 0:
            return ("fail", "OOS-negative / 0 regimes")
        return ("pass" if n >= 2 else "fail", f"{n} OOS regimes")
    if key == "cyrus":
        return ("pending", "Cyrus call (never standing)")
    return ("na", "")


_BADGE = {
    "pass": ('#1b5e20', '#a5d6a7', '\u2714'),     # green check
    "fail": ('#7f1d1d', '#fca5a5', '\u2718'),     # red x
    "pending": ('#78560a', '#fcd34d', '\u25cb'),  # amber circle
    "na": ('#374151', '#9ca3af', '\u2013'),       # gray dash
}


def _badge(status: str, detail: str) -> str:
    fg, bg, glyph = _BADGE.get(status, _BADGE["na"])
    return (f'<span class="badge" style="background:{bg};color:{fg}" '
            f'title="{detail}">{glyph} {detail}</span>')


def _spark(series: list[tuple[str, float, float]], w=180, h=40) -> str:
    """Tiny inline SVG sparkline: strat (blue) vs spx (gray), cum % over time."""
    if not series or len(series) < 2:
        return '<span class="muted">n/a</span>'
    xs = list(range(len(series)))
    strat = [s[1] for s in series]
    spx = [s[2] for s in series]
    allv = strat + spx
    lo, hi = min(allv), max(allv)
    if hi - lo < 1e-9:
        hi = lo + 1.0
    pad = 3

    def pts(vals):
        out = []
        for i, v in zip(xs, vals):
            x = pad + (w - 2 * pad) * (i / (len(series) - 1))
            y = (h - pad) - (h - 2 * pad) * ((v - lo) / (hi - lo))
            out.append(f"{x:.1f},{y:.1f}")
        return " ".join(out)

    return (f'<svg width="{w}" height="{h}" class="spark">'
            f'<polyline fill="none" stroke="#9ca3af" stroke-width="1" points="{pts(spx)}"/>'
            f'<polyline fill="none" stroke="#2563eb" stroke-width="1.6" points="{pts(strat)}"/>'
            f'</svg>')


def build_html() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tournament_db = os.path.join(ROOT, "tournament.db")
    trips_all = _trip_stats(tournament_db)
    roster = _live_roster()
    killswitch = os.path.exists(os.path.join(ROOT, "STOP_TRADING"))

    # ---- header / rails ----
    ks_txt = ('<b style="color:#b91c1c">PRESENT — runners halted</b>' if killswitch
              else '<b style="color:#15803d">absent — runners live (paper)</b>')
    parts: list[str] = []
    parts.append(f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tessera — GATE Tracker</title>
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{ font: 14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
        margin: 0; padding: 24px; background:#0b0e14; color:#e6e8eb; }}
h1 {{ font-size: 22px; margin:0 0 4px; }}
h2 {{ font-size: 16px; margin: 26px 0 10px; color:#cbd5e1; border-bottom:1px solid #1f2937; padding-bottom:6px; }}
.sub {{ color:#94a3b8; font-size:12px; margin-bottom:16px; }}
.rails {{ display:flex; gap:12px; flex-wrap:wrap; margin:14px 0 4px; }}
.rail {{ background:#111827; border:1px solid #1f2937; border-radius:10px; padding:12px 14px; flex:1 1 320px; }}
.rail h3 {{ margin:0 0 6px; font-size:13px; color:#f1f5f9; }}
.rail p {{ margin:0; font-size:12.5px; color:#cbd5e1; }}
.note {{ background:#1a1205; border:1px solid #3f2d0a; color:#fbbf24; border-radius:10px;
         padding:10px 14px; font-size:12.5px; margin:14px 0; }}
table {{ border-collapse:collapse; width:100%; margin:6px 0 4px; font-size:12.5px; }}
th,td {{ text-align:left; padding:7px 9px; border-bottom:1px solid #1f2937; vertical-align:top; }}
th {{ color:#94a3b8; font-weight:600; font-size:11.5px; text-transform:uppercase; letter-spacing:.03em; }}
td.name {{ font-weight:600; color:#f8fafc; white-space:nowrap; }}
.badge {{ display:inline-block; padding:1px 7px; border-radius:999px; font-size:11px; font-weight:600;
          white-space:nowrap; }}
.muted {{ color:#64748b; }}
.pos {{ color:#4ade80; font-weight:600; }}
.neg {{ color:#f87171; font-weight:600; }}
.src {{ color:#64748b; font-size:10.5px; }}
.spark {{ vertical-align:middle; }}
.legend {{ font-size:11.5px; color:#94a3b8; margin:4px 0 0; }}
code {{ background:#1f2937; padding:1px 5px; border-radius:4px; font-size:11.5px; }}
</style></head><body>
<h1>\U0001F4CA Tessera — GATE / Graduation Tracker</h1>
<div class="sub">Generated {now} &middot; live data from <code>tournament.db</code> + paper-tracker DBs</div>

<div class="rails">
  <div class="rail"><h3>\U0001F6E1\uFE0F Rail 1 — Paper-only + killswitch</h3>
    <p>Broker wrapper refuses a non-paper base URL. <code>STOP_TRADING</code>: {ks_txt}.<br>
    Real-money go-live is <b>Cyrus's explicit call</b> — never standing, never pre-baked.</p></div>
  <div class="rail"><h3>\U0001F50E Rail 2 — Honest measurement</h3>
    <p>No lookahead/leakage, real out-of-sample walk-forward, point-in-time data,
    benchmark on the same path. These stop a backtest from lying — they don't reject ideas.</p></div>
</div>

<div class="note"><b>\u26A0 Explore-first mode (Cyrus, 2026-06-07):</b> the Bar E real-money bars below are
<b>SUSPENDED as binding constraints</b>. This table tracks <i>progress toward eventual go-live</i>, not a
gate you must pass now. Mission = <b>beat SPX on raw return</b>; the only things that truly hold are the two rails above.</div>
""")

    # ---- Bar E criteria reference ----
    parts.append('<h2>Bar E — real-money graduation criteria (dormant)</h2>')
    parts.append('<table><tr><th>#</th><th>Criterion</th></tr>')
    for i, (_, label) in enumerate(BAR_E, 1):
        parts.append(f'<tr><td class="muted">{i}</td><td>{label}</td></tr>')
    parts.append('</table>')

    # ---- per-strategy gate matrix ----
    parts.append('<h2>Live roster — progress vs Bar E</h2>')
    crit_keys = [k for k, _ in BAR_E]
    head = ''.join(f'<th>{lbl.split("(")[0].strip()[:18]}</th>' for _, lbl in BAR_E)
    parts.append(f'<table><tr><th>Strategy</th>{head}</tr>')
    for strat in roster:
        bt = BACKTEST_METRICS.get(strat, {})
        trips = trips_all.get(strat, {})
        cells = []
        for key in crit_keys:
            st, detail = _crit_status(strat, key, trips, bt)
            cells.append(f'<td>{_badge(st, detail)}</td>')
        parts.append(f'<tr><td class="name">{strat}</td>{"".join(cells)}</tr>')
    parts.append('</table>')
    parts.append('<p class="legend">\u2714 pass &middot; \u2718 fail &middot; '
                 '\u25cb pending/not-yet &middot; \u2013 not separately pinned (live-cron strategy '
                 'without a standalone backtested-gate report)</p>')

    # ---- backtested metrics w/ provenance ----
    parts.append('<h2>Backtested metrics (read, not recomputed — with provenance)</h2>')
    parts.append('<table><tr><th>Strategy</th><th>Full Sharpe</th><th>OOS Sharpe</th>'
                 '<th>Max DD</th><th>CAGR</th><th>OOS regimes</th><th>Note / Source</th></tr>')
    for strat in roster:
        bt = BACKTEST_METRICS.get(strat, {})

        def fmt(v, suf="", nd=3):
            if v is None:
                return '<span class="muted">&ndash;</span>'
            return f"{v:.{nd}f}{suf}"

        fs = bt.get("full_sharpe")
        fs_cls = "pos" if (fs is not None and fs >= 1.0) else ("neg" if fs is not None else "")
        dd = bt.get("max_dd_pct")
        dd_cls = "pos" if (dd is not None and dd > -20.0) else ("neg" if dd is not None else "")
        note = bt.get("note", "")
        src = bt.get("source", "")
        parts.append(
            f'<tr><td class="name">{strat}</td>'
            f'<td class="{fs_cls}">{fmt(fs)}</td>'
            f'<td>{fmt(bt.get("oos_sharpe"))}</td>'
            f'<td class="{dd_cls}">{fmt(dd, "%", 1)}</td>'
            f'<td>{fmt(bt.get("cagr_pct"), "%", 1)}</td>'
            f'<td>{bt.get("oos_regimes") if bt.get("oos_regimes") is not None else "&ndash;"}</td>'
            f'<td>{note}<br><span class="src">Source: {src}</span></td></tr>'
        )
    parts.append('</table>')

    # ---- live paper performance vs SPX ----
    parts.append('<h2>Live paper performance vs SPX (standalone trackers)</h2>')
    parts.append('<table><tr><th>Tracker</th><th>Days</th><th>Span</th>'
                 '<th>Strat cum%</th><th>SPX cum%</th><th>Alpha</th>'
                 '<th>Engine full Sharpe</th><th>Trend (strat vs SPX)</th><th>Note</th></tr>')
    for name, meta in PAPER_TRACKER_DBS.items():
        perf = _paper_perf(os.path.join(ROOT, meta["db"]))
        if not perf:
            parts.append(f'<tr><td class="name">{name}</td>'
                         f'<td colspan="8" class="muted">no snapshots yet ({meta["db"]})</td></tr>')
            continue
        a = perf["alpha_pct"]
        a_cls = "pos" if a >= 0 else "neg"
        sc = "pos" if perf["cum_strat_pct"] >= 0 else "neg"
        pc = "pos" if perf["cum_spx_pct"] >= 0 else "neg"
        fsh = perf["full_sharpe"]
        parts.append(
            f'<tr><td class="name">{name}</td>'
            f'<td>{perf["n_days"]}</td>'
            f'<td class="muted">{perf["first_date"]}&rarr;{perf["last_date"]}</td>'
            f'<td class="{sc}">{perf["cum_strat_pct"]:+.2f}%</td>'
            f'<td class="{pc}">{perf["cum_spx_pct"]:+.2f}%</td>'
            f'<td class="{a_cls}">{a:+.2f}pp</td>'
            f'<td>{("%.3f" % fsh) if fsh is not None else "&ndash;"}</td>'
            f'<td>{_spark(perf["series"])}</td>'
            f'<td class="muted">{meta["note"]}</td></tr>'
        )
    parts.append('</table>')
    parts.append('<p class="legend">Blue line = strategy cum return, gray = SPX cum return, '
                 'same path. Short panels (single-digit days) are noise — the paper clock just started.</p>')

    # ---- raw fill counts ----
    parts.append('<h2>Live fills on tournament.db (synthetic rows filtered)</h2>')
    parts.append('<table><tr><th>Strategy</th><th>Fills</th><th>Buys</th><th>Sells/closes</th>'
                 '<th>Round trips</th><th>First</th><th>Last</th><th>Span</th></tr>')
    for strat in roster:
        t = trips_all.get(strat)
        if not t:
            parts.append(f'<tr><td class="name">{strat}</td>'
                         f'<td colspan="7" class="muted">no live fills yet</td></tr>')
            continue
        parts.append(
            f'<tr><td class="name">{strat}</td>'
            f'<td>{t["fills"]}</td><td>{t["buys"]}</td><td>{t["sells"]}</td>'
            f'<td>{t["round_trips"]}</td>'
            f'<td class="muted">{t.get("first","")}</td>'
            f'<td class="muted">{t.get("last","")}</td>'
            f'<td class="muted">{t.get("span_days") if t.get("span_days") is not None else "&ndash;"}d</td></tr>'
        )
    parts.append('</table>')

    parts.append('<p class="sub" style="margin-top:24px">Tessera \U0001F4CA &middot; '
                 'GATE bars suspended (explore-first); two rails hold. '
                 'Regenerate: <code>python3 runner/gate_dashboard.py</code></p>')
    parts.append('</body></html>')
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "gate_dashboard.html"))
    args = ap.parse_args()
    html = build_html()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[gate_dashboard] wrote {args.out} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
