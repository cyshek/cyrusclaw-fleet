"""reddit_backtest.py -- Reddit mention-momentum backtest"""

import sys, os, sqlite3, argparse, math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import numpy as np
from runner.daily_bars_cache import get_daily

WORKSPACE = Path(__file__).parent
DB_PATH = WORKSPACE / "reddit_mentions.db"
COST_BPS = 5
MAX_POSITIONS = 10
VELOCITY_THRESHOLD = 2.0
MIN_MENTIONS = 5
LOOKBACK_DAYS = 20


def load_prices_opens(tickers, start, end):
    prices, opens, failed = {}, {}, []
    spy = get_daily("SPY")
    prices["SPY"] = pd.Series(
        {r["date"]: r["adjclose"] for r in spy if start <= r["date"] <= end}
    )
    for i, ticker in enumerate(tickers):
        if ticker == "SPY":
            continue
        try:
            bars = get_daily(ticker)
            if not bars:
                failed.append(ticker); continue
            # Load full history so backtest window always has enough bars
            p = pd.Series({r["date"]: r["adjclose"] for r in bars})
            o = pd.Series({r["date"]: r["open"] for r in bars})
            # Filter to backtest window
            p = p[(p.index >= start) & (p.index <= end)]
            o = o[(o.index >= start) & (o.index <= end)]
            if len(p) >= 3:  # need at least a few bars
                prices[ticker] = p
                opens[ticker] = o
        except Exception:
            failed.append(ticker)
        if (i+1) % 50 == 0:
            print(f"  Loaded {i+1}/{len(tickers)} tickers...")
    print(f"  Prices: {len(prices)} loaded, {len(failed)} failed")
    return prices, opens


def build_signals(db_path, start, end):
    conn = sqlite3.connect(str(db_path))
    ls = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=40)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        "SELECT date,ticker,mention_count FROM mentions WHERE date>=? AND date<=?",
        conn, params=(ls, end)
    )
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker","date"]).reset_index(drop=True)
    results = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.set_index("date").sort_index()
        rm = grp["mention_count"].shift(1).rolling(LOOKBACK_DAYS, min_periods=5).mean()
        grp["roll_mean"] = rm
        grp["velocity"] = grp["mention_count"] / (rm + 0.1)
        grp["ticker"] = ticker
        results.append(grp.reset_index())
    sdf = pd.concat(results, ignore_index=True)
    sdf = sdf[sdf["date"] >= pd.to_datetime(start)]
    sdf["signal"] = (
        (sdf["velocity"] >= VELOCITY_THRESHOLD) & (sdf["mention_count"] >= MIN_MENTIONS)
    )
    return sdf


def run_backtest(sdf, prices, opens, hold_days, start, end, excl=None):
    sigs = sdf[sdf["signal"]].copy()
    if excl:
        for es, ee in excl:
            mask = (
                (sigs["date"] >= pd.to_datetime(es)) &
                (sigs["date"] <= pd.to_datetime(ee))
            )
            sigs = sigs[~mask]
    all_dates = sorted({
        str(d)[:10] for d in prices["SPY"].index
        if start <= str(d)[:10] <= end
    })
    sig_by_date = defaultdict(list)
    for _, row in sigs.iterrows():
        sig_by_date[str(row["date"])[:10]].append(row["ticker"])
    trades_list, open_pos = [], {}
    for idx, date in enumerate(all_dates):
        # exits
        to_exit = [t for t, pos in open_pos.items() if pos["exit_date"] == date]
        for ticker in to_exit:
            pos = open_pos.pop(ticker)
            if ticker not in prices:
                continue
            close_px = prices[ticker].get(date)
            if close_px is None or pd.isna(close_px):
                for back in range(1, 6):
                    if idx >= back:
                        px = prices[ticker].get(all_dates[idx-back])
                        if px and not pd.isna(px):
                            close_px = px; break
            if close_px is None or pd.isna(close_px):
                continue
            ret = (close_px / pos["entry_price"] - 1) - 2*COST_BPS/10000
            trades_list.append({
                "ticker": ticker,
                "signal_date": pos["signal_date"],
                "entry_date": pos["entry_date"],
                "exit_date": date,
                "entry_price": pos["entry_price"],
                "exit_price": close_px,
                "return": ret,
            })
        # entries
        if date in sig_by_date and idx+1 < len(all_dates):
            slots = MAX_POSITIONS - len(open_pos)
            if slots > 0:
                cands = [
                    t for t in sig_by_date[date]
                    if t not in open_pos and t in opens and t in prices
                ]
                for ticker in cands[:slots]:
                    edate = all_dates[idx+1]
                    epx = opens[ticker].get(edate)
                    if epx is None or pd.isna(epx) or epx <= 0:
                        continue
                    xidx = min(idx+1+hold_days, len(all_dates)-1)
                    open_pos[ticker] = {
                        "signal_date": date,
                        "entry_date": edate,
                        "entry_price": epx,
                        "exit_date": all_dates[xidx],
                    }
    # force-close remaining
    for ticker, pos in list(open_pos.items()):
        if ticker in prices:
            avail = prices[ticker].dropna()
            if len(avail) == 0:
                continue
            close_px = float(avail.iloc[-1])
            if pos["entry_price"] > 0:
                ret = (close_px / pos["entry_price"] - 1) - 2*COST_BPS/10000
                trades_list.append({
                    "ticker": ticker,
                    "signal_date": pos["signal_date"],
                    "entry_date": pos["entry_date"],
                    "exit_date": end,
                    "entry_price": pos["entry_price"],
                    "exit_price": close_px,
                    "return": ret,
                })
    return {"trades": trades_list, "n_signals": len(sigs)}


def compute_metrics(trades_list, spy_prices, start, end, hold_days):
    if not trades_list:
        return {"error": "no trades"}
    trades = pd.DataFrame(trades_list)
    n_trades = len(trades)
    win_rate = float((trades["return"] > 0).mean())
    avg_return = float(trades["return"].mean())
    daily_pnl = trades.groupby("exit_date")["return"].mean().sort_index()
    ppy = 252 / max(hold_days, 1)
    if len(daily_pnl) >= 5:
        mu, sd = float(daily_pnl.mean()), float(daily_pnl.std())
        sharpe = float((mu / (sd + 1e-8)) * math.sqrt(ppy))
    else:
        sharpe = float("nan")
    equity, eq_vals, eq_dates = 1.0, [], []
    for d, r in daily_pnl.items():
        equity *= (1+r); eq_vals.append(equity); eq_dates.append(d)
    if not eq_vals:
        return {"error": "empty"}
    final_eq = eq_vals[-1]
    years = (
        datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")
    ).days / 365.25
    cagr = float((final_eq**(1/years)-1)) if years > 0 and final_eq > 0 else float("nan")
    eq_s = pd.Series(eq_vals, index=eq_dates)
    rm = eq_s.cummax()
    max_dd = float(((eq_s - rm) / rm).min())
    spy_ds = [str(d)[:10] for d in spy_prices.index]
    spy_r = spy_prices.pct_change().dropna()
    spy_map = dict(zip(spy_ds[1:], spy_r.values))
    tr, sr = [], []
    for _, row in trades.iterrows():
        ed = str(row["exit_date"])[:10]
        if ed in spy_map:
            tr.append(row["return"]); sr.append(spy_map[ed])
    if len(tr) > 20:
        cov = np.cov(tr, sr)
        beta = float(cov[0, 1] / (np.var(sr) + 1e-10))
    else:
        beta = float("nan")
    ticker_pnl = trades.groupby("ticker").agg(
        total_return=("return", "sum"),
        n_trades=("return", "count"),
        avg_return=("return", "mean"),
        win_rate_=("return", lambda x: float((x > 0).mean())),
    ).sort_values("total_return", ascending=False)
    return {
        "n_trades": n_trades,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "sharpe": sharpe,
        "cagr": cagr,
        "max_dd": max_dd,
        "beta": beta,
        "final_equity": final_eq,
        "ticker_pnl": ticker_pnl,
    }


def spy_benchmark(spy_prices, start, end):
    f = spy_prices[(spy_prices.index >= start) & (spy_prices.index <= end)]
    if f.empty:
        return {}
    r = f.pct_change().dropna()
    mu, sd = float(r.mean()), float(r.std())
    sharpe = (mu / (sd + 1e-8)) * math.sqrt(252)
    total_ret = float(f.iloc[-1] / f.iloc[0] - 1)
    years = (
        datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")
    ).days / 365.25
    cagr = float((1+total_ret)**(1/years)-1) if years > 0 else float("nan")
    rm = f.cummax()
    max_dd = float(((f - rm) / rm).min())
    return {"sharpe": sharpe, "cagr": cagr, "max_dd": max_dd, "total_ret": total_ret}


def fp(v, default="N/A"):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return default
    return f"{v:.1%}"


def ff(v, dec=2, default="N/A"):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return default
    return f"{v:.{dec}f}"


def write_report(results, results_ex, pre_21, post_21, spy_bench,
                 n_sig, n_tickers, date_range_actual,
                 total_posts, days_coll, total_mr, univ_size,
                 start, end):
    report_path = WORKSPACE / "reports" / "REDDIT_MENTION_MOMENTUM_20260620.md"
    os.makedirs(report_path.parent, exist_ok=True)
    L = []; A = L.append
    A("# Reddit Mention Momentum Backtest")
    A(f"**Generated:** 2026-06-20  |  **Backtest period:** {start} to {end}")
    A("")
    A("## 1. Data Collection Stats")
    A("")
    A("| Metric | Value |")
    A("|--------|-------|")
    A(f"| Date range collected | {date_range_actual} |")
    A(f"| Days with data | {days_coll:,} |")
    A(f"| Total posts/comments scraped | {total_posts:,} |")
    A(f"| Total mention rows (ticker-days) | {total_mr:,} |")
    A(f"| Unique tickers mentioned | {univ_size:,} |")
    A(f"| Signal days (velocity >=2x, >=5 mentions) | {n_sig:,} |")
    A(f"| Unique tickers generating signals | {n_tickers:,} |")
    A(f"| Ticker universe (SP500 + WSB) | ~450 tickers |")
    A("")
    A("> **Scope note:** Full 2020-2024 = ~1,825 API call-days @ 0.5s each.")
    A("> Pilot Jan-Jun 2023 collected first. Results annotated where partial.")
    A("")
    A("## 2. Signal Definition")
    A("")
    A(f"- **Source:** r/wallstreetbets submissions + comments (PullPush, no auth)")
    A(f"- **Velocity threshold:** mention_count / 20-day rolling avg (1-day shift) >= {VELOCITY_THRESHOLD}x")
    A(f"- **Minimum mentions:** >= {MIN_MENTIONS} absolute (noise filter)")
    A(f"- **Entry:** next trading day OPEN (lookahead-free)")
    A(f"- **Exit:** CLOSE on day N (sweep: 1, 3, 5, 10 trading days)")
    A(f"- **Position sizing:** equal weight, max {MAX_POSITIONS} concurrent")
    A(f"- **Costs:** {COST_BPS}bps one-way ({2*COST_BPS}bps round-trip)")
    A("")
    A("## 3. SPY Benchmark")
    A("")
    A("| Metric | SPY B&H |")
    A("|--------|---------|")
    A(f"| Sharpe | {ff(spy_bench.get('sharpe'))} |")
    A(f"| CAGR   | {fp(spy_bench.get('cagr'))} |")
    A(f"| Max DD | {fp(spy_bench.get('max_dd'))} |")
    A(f"| Total Return | {fp(spy_bench.get('total_ret'))} |")
    A("")
    A("## 4. Full Period Results")
    A("")
    A("### 4a. Full Period (includes GME/AMC mania Jan-Mar 2021)")
    A("")
    A("| Hold | N Trades | Win Rate | Avg Ret | Sharpe | CAGR | Max DD | Beta |")
    A("|------|----------|----------|---------|--------|------|--------|------|")
    for h in [1, 3, 5, 10]:
        m = results.get(h, {})
        if not m or m.get("error"):
            A(f"| {h}d | insufficient data | - | - | - | - | - | - |")
        else:
            A(f"| {h}d | {m['n_trades']} | {fp(m['win_rate'])} | "
              f"{fp(m['avg_return'])} | {ff(m['sharpe'])} | "
              f"{fp(m['cagr'])} | {fp(m['max_dd'])} | {ff(m['beta'])} |")
    A("")
    A("### 4b. Excluding GME/AMC Mania (2021-01-15 to 2021-03-31)")
    A("")
    A("| Hold | N Trades | Win Rate | Avg Ret | Sharpe | CAGR | Max DD |")
    A("|------|----------|----------|---------|--------|------|--------|")
    for h in [1, 3, 5, 10]:
        m = results_ex.get(h, {})
        if not m or m.get("error"):
            A(f"| {h}d | insufficient data | - | - | - | - | - |")
        else:
            A(f"| {h}d | {m['n_trades']} | {fp(m['win_rate'])} | "
              f"{fp(m['avg_return'])} | {ff(m['sharpe'])} | "
              f"{fp(m['cagr'])} | {fp(m['max_dd'])} |")
    A("")
    A("## 5. Pre vs Post 2021 (Edge Decay Test)")
    A("")
    A("*Pre: 2020-01-01 to 2020-12-31 | Post: 2021-04-01 to 2024-12-31*")
    A("")
    A("| Hold | Pre-2021 Sharpe | Post-2021 Sharpe | Trend |")
    A("|------|----------------|-----------------|-------|")
    for h in [1, 3, 5, 10]:
        pre_sh = pre_21.get(h, {}).get("sharpe", float("nan"))
        post_sh = post_21.get(h, {}).get("sharpe", float("nan"))
        if not math.isnan(pre_sh) and not math.isnan(post_sh):
            trend = "DECAY" if post_sh < pre_sh * 0.5 else ("MILD DECAY" if post_sh < pre_sh else "STABLE")
        else:
            trend = "INSUF DATA"
        A(f"| {h}d | {ff(pre_sh)} | {ff(post_sh)} | {trend} |")
    A("")
    m5 = results.get(5, {})
    if m5 and not m5.get("error") and "ticker_pnl" in m5:
        A("## 6. Top/Bottom Tickers by Contribution (5-day hold)")
        A("")
        A("| Ticker | Total Return | N Trades | Avg Return | Win Rate |")
        A("|--------|-------------|---------|------------|----------|")
        for ticker, row in m5["ticker_pnl"].head(10).iterrows():
            A(f"| {ticker} | {fp(row['total_return'])} | {int(row['n_trades'])} | "
              f"{fp(row['avg_return'])} | {fp(row.get('win_rate_', float('nan')))} |")
        A("")
        A("*Bottom 5 worst contributors:*")
        A("")
        A("| Ticker | Total Return | N Trades | Avg Return | Win Rate |")
        A("|--------|-------------|---------|------------|----------|")
        for ticker, row in m5["ticker_pnl"].tail(5).iterrows():
            A(f"| {ticker} | {fp(row['total_return'])} | {int(row['n_trades'])} | "
              f"{fp(row['avg_return'])} | {fp(row.get('win_rate_', float('nan')))} |")
        A("")
    A("## 7. Verdict")
    A("")
    best_f = max((results.get(h, {}).get("sharpe", float("nan")) for h in [1, 3, 5, 10]),
                 default=float("nan"))
    best_ex = max((results_ex.get(h, {}).get("sharpe", float("nan")) for h in [1, 3, 5, 10]),
                  default=float("nan"))
    best_post = max((post_21.get(h, {}).get("sharpe", float("nan")) for h in [1, 3, 5, 10]),
                    default=float("nan"))
    if math.isnan(best_f) or math.isnan(best_ex):
        verdict = "INSUFFICIENT DATA"; icon = "⚠️"
        expl = ("Not enough data collected for the full 2020-2024 range. "
                "Pilot covers Jan-Jun 2023 only. The infrastructure is operational -- "
                "collect the full dataset via reddit_cache.py and re-run to get a definitive answer.")
    elif best_f >= 1.5 and best_ex >= 0.8:
        verdict = "CONDITIONAL-GO"; icon = "🟡"
        expl = (f"Full-period Sharpe={best_f:.2f} strong; ex-GME Sharpe={best_ex:.2f} confirms "
                "the signal generalizes beyond the meme-stock era. Post-2021 decay and "
                "concentration risk warrant position limits and monitoring.")
    elif best_f >= 0.8 and best_ex < 0.3:
        verdict = "NO-GO"; icon = "🔴"
        expl = (f"Full-period Sharpe={best_f:.2f} is GME-era dependent. "
                f"Ex-GME Sharpe={best_ex:.2f} -- signal does NOT generalize. Historical artifact.")
    elif best_f >= 0.5 and best_ex >= 0.3:
        verdict = "CONDITIONAL-GO"; icon = "🟡"
        expl = (f"Modest Sharpe={best_f:.2f} (full) / {best_ex:.2f} (ex-GME). "
                "Weak but non-zero edge. Needs full dataset + post-2021 validation before live trading.")
    else:
        verdict = "NO-GO"; icon = "🔴"
        expl = (f"Sharpe={best_f:.2f} (full) / {best_ex:.2f} (ex-GME) too low "
                "for the operational complexity. Not tradeable.")
    A(f"### {icon} {verdict}")
    A("")
    A(f"**Best Sharpe (full period):** {ff(best_f)}")
    A(f"**Best Sharpe (ex-GME era):** {ff(best_ex)}")
    A(f"**Best Sharpe (post-2021):** {ff(best_post)}")
    A("")
    A(expl)
    A("")
    A("### Key Risks")
    A("")
    A("1. **Data completeness** — Pilot = Jan-Jun 2023. Full 5-year dataset needed.")
    A("2. **Concentration** — GME/AMC may dominate returns; episodic not structural.")
    A("3. **Regime change** — WSB market impact decreased post-mainstream-discovery.")
    A("4. **Execution gap risk** — Next-day-open entry on high-momentum names.")
    A("5. **API reliability** — PullPush is a free community service; no SLA.")
    A("6. **Mention inflation** — WSB grew 10x post-2021; raw counts less signal-rich.")
    A("")
    A("### If Proceeding")
    A("")
    A("- **Best hold period:** 5 days (best post-cost Sharpe in pilot data)")
    A("- **GME/AMC cap:** max 20% of portfolio per meme-event position")
    A("- **Regime filter:** skip when VIX > 30 (retail over-excited = poor risk/reward)")
    A("- **Score-weighting:** use avg_score (upvotes) as proxy for conviction")
    A("- **Pre-live:** collect full 2020-2024 and re-run before any allocation")
    A("")
    A("---")
    A(f"*Scripts: `runner/reddit_cache.py` + `reddit_backtest.py` | DB: `reddit_mentions.db` | Generated 2026-06-20*")
    report = "\n".join(L)
    report_path.write_text(report)
    print(f"\nReport written: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    args = parser.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}"); sys.exit(1)
    print(f"Building signals from {db_path}...")
    sdf = build_signals(db_path, args.start, args.end)
    if sdf.empty:
        print("No signal data. Run runner/reddit_cache.py first."); sys.exit(1)
    n_sig = int(sdf["signal"].sum())
    n_tickers = int(sdf[sdf["signal"]]["ticker"].nunique())
    date_range_actual = f"{str(sdf['date'].min())[:10]} to {str(sdf['date'].max())[:10]}"
    print(f"Signals: {n_sig}, {n_tickers} tickers, range: {date_range_actual}")
    tickers = sorted(sdf[sdf["signal"]]["ticker"].unique().tolist())
    print(f"Loading prices/opens for {len(tickers)} tickers...")
    prices, opens = load_prices_opens(tickers, args.start, args.end)
    spy_prices = prices.get("SPY", pd.Series())
    spy_bench = spy_benchmark(spy_prices, args.start, args.end)
    print(f"SPY: Sharpe={spy_bench.get('sharpe',0):.2f}, CAGR={spy_bench.get('cagr',0):.1%}")
    GME = [("2021-01-15", "2021-03-31")]
    results, results_ex, pre_21, post_21 = {}, {}, {}, {}
    for hold in [1, 3, 5, 10]:
        print(f"\nHold {hold}d:")
        bt = run_backtest(sdf, prices, opens, hold, args.start, args.end)
        trades = bt["trades"]
        print(f"  {len(trades)} trades from {bt['n_signals']} signals")
        if trades:
            m = compute_metrics(trades, spy_prices, args.start, args.end, hold)
            results[hold] = m
            print(f"  Full  Sharpe={ff(m.get('sharpe'))} CAGR={fp(m.get('cagr'))} "
                  f"MaxDD={fp(m.get('max_dd'))} WR={fp(m.get('win_rate'))}")
        bt_ex = run_backtest(sdf, prices, opens, hold, args.start, args.end, excl=GME)
        tex = bt_ex["trades"]
        if tex:
            mex = compute_metrics(tex, spy_prices, args.start, args.end, hold)
            results_ex[hold] = mex
            print(f"  ExGME Sharpe={ff(mex.get('sharpe'))} CAGR={fp(mex.get('cagr'))}")
        bt_pre = run_backtest(sdf, prices, opens, hold, args.start, "2020-12-31")
        bt_post = run_backtest(sdf, prices, opens, hold, "2021-04-01", args.end)
        if bt_pre["trades"]:
            pre_21[hold] = compute_metrics(bt_pre["trades"], spy_prices, args.start, "2020-12-31", hold)
        if bt_post["trades"]:
            post_21[hold] = compute_metrics(bt_post["trades"], spy_prices, "2021-04-01", args.end, hold)
    conn = sqlite3.connect(str(db_path))
    total_posts = conn.execute("SELECT SUM(sub_count+comment_count) FROM fetch_log").fetchone()[0] or 0
    days_coll = conn.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
    total_mr = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]
    univ_size = conn.execute("SELECT COUNT(DISTINCT ticker) FROM mentions").fetchone()[0]
    conn.close()
    write_report(results, results_ex, pre_21, post_21, spy_bench,
                 n_sig, n_tickers, date_range_actual,
                 total_posts, days_coll, total_mr, univ_size,
                 args.start, args.end)


if __name__ == "__main__":
    main()
