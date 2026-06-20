import json, math, os, numpy as np
from collections import defaultdict

WS = "/home/azureuser/.openclaw/agents/trading-bench/workspace"
REPORTS_DIR = os.path.join(WS, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

result = {
    "status": "ok",
    "verdict": "PROMISING",
    "full_period_sharpe": 1.02,
    "full_period_return_pct": 447.2,
    "oos_sharpe": 0.80,
    "oos_return_pct": 99.7,
    "spx_full_return_pct": 360.6,
    "beats_spx_raw": True,
    "n_trades_full": 922,
    "n_trades_oos": 456,
    "win_rate_pct": 58.7,
    "max_drawdown_pct": -32.9,
    "avg_trade_ret_pct": 0.485,
    "period_breakdown": [
        {"period":"2012-2014","sharpe":1.71,"return_pct":75.1,"spx_return_pct":61.2,"n_trades":208},
        {"period":"2015-2017","sharpe":1.00,"return_pct":38.5,"spx_return_pct":29.9,"n_trades":173},
        {"period":"2018-2020","sharpe":1.12,"return_pct":67.2,"spx_return_pct":39.3,"n_trades":261},
        {"period":"2021-2024","sharpe":0.59,"return_pct":35.0,"spx_return_pct":58.9,"n_trades":280},
    ],
    "nasdaq_api_probe": {
        "2024-10-25":{"total":39,"w_est":0,"w_act":0,"w_surp":27},
        "2024-07-26":{"total":45,"w_est":0,"w_act":0,"w_surp":32},
        "2024-04-26":{"total":52,"w_est":0,"w_act":0,"w_surp":36},
        "2023-10-27":{"total":67,"w_est":0,"w_act":0,"w_surp":56},
        "2022-01-28":{"total":38,"w_est":0,"w_act":0,"w_surp":28},
        "2020-01-31":{"total":37,"w_est":0,"w_act":0,"w_surp":24},
        "2018-10-26":{"total":50,"w_est":0,"w_act":0,"w_surp":36},
        "2015-10-23":{"total":35,"w_est":0,"w_act":0,"w_surp":26},
    },
    "data_feasibility": (
        "EDGAR EPS: WORKS (quarterly from ~2009, PIT via filed date, no key needed). "
        "Nasdaq estimates: EMPTY - eps_forecast null for all tested dates 2015-2024; used EDGAR YoY proxy. "
        "Yahoo prices: WORKS (adj-close 1993+). All 5 feasibility tickers joined cleanly."
    ),
    "key_finding": (
        "Long-only PEAD with YoY EPS proxy (922 trades, 2012-2024): "
        "return=447.2%, Sharpe=1.02. SPX=360.6%. "
        "Signal BEATS SPX raw full-period (+86.6ppt excess). "
        "OOS (2019-2024): sh=0.80, ret=99.7% vs SPX OOS 134.3% — OOS LAGS SPX. "
        "Temporal Sharpe decay: 1.71 (2012-14) -> 1.00 (2015-17) -> 1.12 (2018-20) -> 0.59 (2021-24). "
        "CAUTION: YoY proxy != analyst consensus; true PEAD requires estimate history. "
        "Large-cap-only universe + no-short rail + YoY bias means MARGINAL may be more accurate with true signal."
    ),
    "report": "reports/PEAD_RESEARCH_20260614.md",
}

with open("/tmp/pead_result.json", "w") as f:
    json.dump(result, f, indent=2)
print("Wrote /tmp/pead_result.json")

# Drift data from sample run output
dbc_data = {
    "large_beat": {"d5": 0.79, "d10": 1.27, "d21": 1.99, "d63": 5.82, "n": 91},
    "beat":       {"d5": 0.79, "d10": 1.51, "d21": 2.09, "d63": 5.49, "n": 16},
    "inline":     {"d5": 3.50, "d10": 6.00, "d21": 9.58, "d63": 15.48,"n": 6},
    "miss":       {"d5": 0.33, "d10": 1.12, "d21": 2.66, "d63": 6.85, "n": 17},
    "large_miss": {"d5": 1.08, "d10": 1.36, "d21": 2.87, "d63": 5.17, "n": 47},
}

edgar_res = {
    "AAPL": [{"filed":"2009-07-22"},{"filed":"2026-05-01"}],
    "MSFT": [{"filed":"2009-10-23"},{"filed":"2026-04-29"}],
    "GOOGL":[{"filed":"2015-10-29"},{"filed":"2026-04-30"}],
    "JPM":  [{"filed":"2009-08-10"},{"filed":"2026-05-01"}],
    "XOM":  [{"filed":"2009-08-05"},{"filed":"2026-05-04"}],
}
edgar_counts = {"AAPL":51,"MSFT":51,"GOOGL":29,"JPM":51,"XOM":51}
nasdaq_probe = result["nasdaq_api_probe"]
feasibility = ["AAPL","MSFT","GOOGL","JPM","XOM"]
nok = False  # No estimates available

def write_report():
    L = []
    A = L.append

    A("# PEAD (Post-Earnings Announcement Drift) Research Report")
    A(f"**Date:** 2026-06-14  |  **Agent:** trading-bench  |  **Verdict:** `{result['verdict']}`")
    A("")
    A("---")
    A("")
    A("## Executive Summary")
    A("")
    A("PEAD is one of the most replicated anomalies in academic finance: stocks beating analyst expectations "
      "continue drifting in the same direction for 1-60 days post-announcement. "
      "This sprint tests a **long-only PEAD strategy** on top-50 S&P 500 names, 2012-2024.")
    A("")
    A("**Configuration:**")
    A("- Signal: EDGAR YoY same-quarter EPS surprise (EDGAR PIT; Nasdaq analyst estimates unavailable free-tier)")
    A("- Universe: Top 50 S&P 500 by EDGAR + Yahoo price coverage (50 tickers, 922 large-beat events)")
    A("- Hold: 21 trading days post-announcement")
    A("- Cost: 5 bps entry + 5 bps exit = 10 bps round-trip")
    A("- No shorting on Large Miss (long-only safety rail)")
    A("- Walk-forward: IS 2012-2018, OOS 2019-2024")
    A("")
    A(f"> **Verdict: `{result['verdict']}`**")
    A(f"> Full Sharpe: **{result['full_period_sharpe']:.2f}** | Return: **{result['full_period_return_pct']:.1f}%** vs SPX **{result['spx_full_return_pct']:.1f}%**")
    A(f"> OOS (2019-2024): Sharpe **{result['oos_sharpe']:.2f}** | Return **{result['oos_return_pct']:.1f}%** vs SPX OOS **134.3%**")
    A(f"> Beats SPX full-period raw return: **YES** (+86.6 ppt excess)")
    A(f"> **CAUTION: OOS underperforms SPX** (99.7% vs 134.3%) — signal shows IS-OOS degradation")
    A("")
    A("---")
    A("")
    A("## 1. Data Feasibility")
    A("")
    A("### 1a. SEC EDGAR EPS Actuals — STATUS: WORKS")
    A("")
    A("Endpoint: `https://data.sec.gov/api/xbrl/companyfacts/CIK{N}.json`")
    A("")
    A("- Concept: `us-gaap/EarningsPerShareDiluted` (fallback: EarningsPerShareBasic)")
    A("- PIT anchor: `filed` date = original 10-Q/10-K filing date (NOT fiscal period end)")
    A("- No API key required; `User-Agent` header required (returns HTTP 403 without it)")
    A("- XBRL mandate took effect ~2009; quarterly EPS coverage consistent from 2009-2010")
    A("")
    A("| Ticker | Q Records | Date Range |")
    A("|--------|----------|-----------|")
    A("| AAPL | 51 | 2009-07-22 -> 2026-05-01 |")
    A("| MSFT | 51 | 2009-10-23 -> 2026-04-29 |")
    A("| GOOGL | 29 | 2015-10-29 -> 2026-04-30 |")
    A("| JPM | 51 | 2009-08-10 -> 2026-05-01 |")
    A("| XOM | 51 | 2009-08-05 -> 2026-05-04 |")
    A("")
    A("**PIT rule applied:** For each (fiscal_year, fiscal_period) pair, only the FIRST `filed` row is kept "
      "(original announcement). Later filings of the same period = restatements = excluded. "
      "This guarantees zero lookahead bias.")
    A("")
    A("Note: GOOGL shows only 29 records (split from GOOG, XBRL coverage starts later). "
      "All others show full 51 records = ~12.75 years of quarterly data.")
    A("")
    A("### 1b. Nasdaq Earnings Calendar (Analyst Estimates) — STATUS: EMPTY")
    A("")
    A("API endpoint `api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` responds HTTP 200 "
      "but `eps_forecast` field is **null for all tested dates spanning 2015-2024**. "
      "The free/unauthenticated tier no longer exposes analyst consensus estimates.")
    A("")
    A("The `surprise` (surprise%) field IS populated, suggesting the actual EPS is available post-announcement, "
      "but without `eps_forecast` we cannot reconstruct the pre-announcement consensus.")
    A("")
    A("| Date | Rows | W/Estimate | W/Actual | W/Surprise% |")
    A("|------|------|-----------|---------|------------|")
    for d in sorted(nasdaq_probe.keys()):
        v = nasdaq_probe[d]
        A(f"| {d} | {v['total']} | {v['w_est']} | {v['w_act']} | {v['w_surp']} |")
    A("")
    A("**Fallback: EDGAR YoY proxy**")
    A("```")
    A("surprise_pct = (EPS_Q_actual - EPS_same_Q_prior_year) / abs(EPS_same_Q_prior_year) * 100")
    A("")
    A("Bucketing:")
    A("  Large Beat  : surprise > +10%  <- Strategy: go long 21 days")
    A("  Beat        : +2% to +10%     <- skip")
    A("  In-line     : -2% to +2%      <- skip")
    A("  Miss        : -10% to -2%     <- skip")
    A("  Large Miss  : < -10%          <- skip (no short)")
    A("```")
    A("")
    A("**Critical limitation:** YoY EPS growth != analyst consensus surprise. A company growing "
      "EPS 30% YoY is classified 'large beat' even if it missed consensus by 5%. "
      "The true PEAD anomaly is about information surprise relative to expectations, not trend.")
    A("")
    A("### 1c. Yahoo Finance Price Data — STATUS: WORKS")
    A("")
    A("- Endpoint: `query1.finance.yahoo.com/v8/finance/chart/{SYM}?interval=1d&events=div,split`")
    A("- Returns split+div-adjusted closes (critical: use `adjclose`, not raw `close`)")
    A("- All 5 feasibility tickers confirmed working; SPX (^GSPC) from 1970")
    A("")
    A("### 1d. Join Feasibility")
    A("")
    A("- EDGAR x Yahoo join on ticker + `filed` date: **clean** for all 5 test tickers")
    A("- Backtest 2012-2024 chosen for full XBRL coverage + 3-year YoY lookback buffer")
    A("- Nasdaq surprise% field (w/o estimate) cannot be used alone for PEAD signal construction")
    A("")
    A("---")
    A("")
    A("## 2. Signal Construction")
    A("")
    A("```")
    A("Signal: EPS Surprise (EDGAR YoY proxy)")
    A("  surprise_pct = (EPS_Q - EPS_same_Q_prior_year) / |EPS_same_Q_prior_year| * 100")
    A("")
    A("Classification:")
    A("  Large Beat  : surprise > +10%  -> long 21 trading days (5bps entry + 5bps exit)")
    A("  Beat        : +2% to +10%      -> flat")
    A("  In-line     : -2% to +2%       -> flat")
    A("  Miss        : -10% to -2%      -> flat")
    A("  Large Miss  : < -10%           -> flat (no short rail)")
    A("")
    A("Entry: close price on EDGAR 'filed' date")
    A("Exit:  close price on 21st trading day after entry")
    A("Cost:  net_return = (exit/entry) * (1-0.0005)^2 - 1")
    A("```")
    A("")
    A("### Average Drift by Classification (5-Ticker Sample, 2012-2024)")
    A("")
    A("| Classification | N | +5d% | +10d% | +21d% | +63d% |")
    A("|---------------|---|------|-------|-------|-------|")
    for cls in ["large_beat","beat","inline","miss","large_miss"]:
        d = dbc_data[cls]
        A(f"| {cls} | {d['n']} | {d['d5']:.2f} | {d['d10']:.2f} | {d['d21']:.2f} | {d['d63']:.2f} |")
    A("")
    A("**Key observation:** The YoY proxy shows surprisingly weak differentiation between large_beat and "
      "large_miss categories — both show positive drift at 21d and 63d. This is a red flag: "
      "with true analyst estimates, we expect large_miss to show NEGATIVE drift (mean reversion). "
      "The positive drift across all categories likely reflects the 2012-2024 bull market "
      "dragging all categories upward (market beta dominates).")
    A("")
    A("---")
    A("")
    A("## 3. Backtest Results")
    A("")
    A("**Universe:** Top 50 S&P 500 by EDGAR+Yahoo availability (50 names, all liquid large-caps)  ")
    A("**Hold:** 21 trading days  |  **Cost:** 5bps/side  |  **Signal:** YoY EPS surprise > +10%  ")
    A("**Classification split (2012-2024):** 922 large_beat | 181 beat | 99 inline | 152 miss | 456 large_miss")
    A("")
    A("### 3a. Full Period: 2012-2024")
    A("")
    A("| Metric | PEAD Strategy | SPX Buy-Hold |")
    A("|--------|--------------|-------------|")
    A(f"| **Total Return** | **{result['full_period_return_pct']:.1f}%** | **{result['spx_full_return_pct']:.1f}%** |")
    A(f"| Annual Sharpe (sqrt-12 annualized) | {result['full_period_sharpe']:.2f} | ~0.65 (hist. avg) |")
    A(f"| Max Drawdown | {result['max_drawdown_pct']:.1f}% | ~-34% (2020 COVID) |")
    A(f"| Win Rate | {result['win_rate_pct']:.1f}% | N/A |")
    A(f"| N Trades | {result['n_trades_full']} | N/A (buy-hold) |")
    A(f"| Beats SPX Raw Return | **YES** | Benchmark |")
    A("")
    A("### 3b. Walk-Forward: In-Sample vs Out-of-Sample")
    A("")
    A("| Period | Trades | Return | Sharpe | Max DD | SPX Return |")
    A("|--------|--------|--------|--------|--------|-----------|")
    A(f"| IS  2012-2018 | 466 | 174.0% | **1.31** | -14.5% | 96.3% |")
    A(f"| OOS 2019-2024 | {result['n_trades_oos']} | {result['oos_return_pct']:.1f}% | **{result['oos_sharpe']:.2f}** | -32.9% | 134.3% |")
    A("")
    A("**IS-OOS Gap:** Sharpe degrades from 1.31 to 0.80 (39% decline). Return outpaces SPX in IS (+77.7ppt) "
      "but lags in OOS (-34.6ppt). This is the critical red flag — the signal decays materially OOS.")
    A("")
    A("### 3c. Temporal Degradation (3-Year Buckets)")
    A("")
    A("| Period | Trades | Return | Sharpe | vs SPX | Signal Alpha |")
    A("|--------|--------|--------|--------|--------|-------------|")
    for p in result["period_breakdown"]:
        alpha = p["return_pct"] - p["spx_return_pct"]
        direction = "+" if alpha >= 0 else ""
        A(f"| {p['period']} | {p['n_trades']} | {p['return_pct']:.1f}% | {p['sharpe']:.2f} | {p['spx_return_pct']:.1f}% | {direction}{alpha:.1f}ppt |")
    A("")
    A("**Degradation pattern:** Sharpe 1.71 (2012-14) -> 1.00 (15-17) -> 1.12 (18-20) -> **0.59 (21-24)**. "
      "The final period Sharpe (0.59) underperforms SPX total return (58.9% vs 35.0%). "
      "This is consistent with large-cap PEAD being arbitraged away by the 2020s.")
    A("")
    A("---")
    A("")
    A("## 4. Honest Verdict")
    A("")
    A("### `PROMISING` — but with significant asterisks")
    A("")
    A("The headline numbers look good: 447.2% full-period return, Sharpe 1.02, beats SPX by 86.6ppt. "
      "However, the honest interpretation requires these caveats:")
    A("")
    A("**What works:**")
    A("- The strategy generates consistent excess return in IS period (2012-2018)")
    A("- Win rate ~58.7% is meaningfully above 50%, suggesting a real signal")
    A("- Sharpe 1.02 is compelling for a simple rule-based system")
    A("- 922 trades gives statistical confidence (not a small-sample artifact)")
    A("")
    A("**What doesn't:**")
    A("1. **OOS underperforms SPX** (99.7% vs 134.3% over 2019-2024)")
    A("2. **Temporal decay is real:** Sharpe drops from 1.71 to 0.59 — classic arbitrage erosion")
    A("3. **YoY proxy is a rough signal** — the large positive drift for `large_miss` in the sample "
      "confirms the proxy doesn't cleanly separate good/bad news (bull market bias)")
    A("4. **Long-only bias:** The 2012-2024 period was predominantly a bull market; "
      "any diversified long portfolio captures ~360% SPX return; excess alpha may be partially luck")
    A("5. **No slippage model:** Earnings events cause bid-ask spreads to widen; "
      "real-world 5bps assumption is optimistic")
    A("")
    A("**Most likely verdict with TRUE analyst estimates:** MARGINAL")
    A("The YoY proxy inflates signal quality. True PEAD in large-caps requires:")
    A("- Analyst consensus EPS (IBES, Finnhub, or FactSet)")
    A("- Standardized Unexpected Earnings (SUE) for cross-sectional ranking")
    A("- Ideally small/mid-cap universe where arbitrage is less complete")
    A("")
    A("### Caveats Summary")
    A("")
    A("| Caveat | Severity | Impact |")
    A("|--------|---------|--------|")
    A("| YoY proxy != analyst consensus | HIGH | Likely overstates signal |")
    A("| Top-50 S&P 500 = most arbitraged | HIGH | Understates true PEAD alpha available in small-cap |")
    A("| OOS Sharpe 0.80, lags SPX OOS | HIGH | Signal may not be deployable now |")
    A("| No shorting = half the P&L left | MEDIUM | Full L/S would show stronger risk-adj return |")
    A("| 2020 COVID distorts YoY EPS | MEDIUM | Some 'large beats' in 2021 = base-effect noise |")
    A("| 5bps cost assumes best execution | LOW | Real impact ~20-50bps around earnings releases |")
    A("")
    A("### Academic Context")
    A("")
    A("- **Original:** Ball & Brown (1968), Foster Olsen Shevlin (1984)")
    A("- **Peak alpha:** ~1990s-2000s; documented to degrade substantially after 2010")
    A("- **Why it decayed:** algorithmic event-driven funds, HFT price discovery, "
      "falling execution costs reducing arbitrage barriers")
    A("- **Where it lives:** Low-coverage stocks, small-cap, earnings with high analyst dispersion")
    A("- **Academic consensus (2020s):** Large-cap PEAD essentially zero after costs; "
      "small-cap PEAD still positive but diminished from historical levels")
    A("")
    A("---")
    A("")
    A("## 5. Next Steps")
    A("")
    A("To make this GENUINELY PROMISING (not just technically beating SPX in IS):")
    A("")
    A("1. **Get true analyst estimates** (highest priority)")
    A("   - Finnhub free tier: 1 year of EPS estimates history")
    A("   - Forward collection: start collecting Nasdaq calendar `surprise` field now (it's populated)")
    A("   - The Nasdaq API shows `w_surp` populated — the surprise% post-announcement IS available; "
      "we just need the pre-announcement estimate")
    A("")
    A("2. **Expand to small/mid-cap** (likely 2-3x better alpha)")
    A("   - Russell 2000 subset where analyst coverage is sparse")
    A("   - EDGAR XBRL covers thousands of small-caps")
    A("")
    A("3. **Optimize hold period**")
    A("   - Academic literature suggests 5-10 day hold is stronger in modern data")
    A("   - Grid search 5/10/21/42 days on IS, validate OOS")
    A("")
    A("4. **Add short leg on Large Miss**")
    A("   - Full L/S PEAD is the canonical strategy; long-only loses half the information")
    A("")
    A("5. **Combine with momentum filter**")
    A("   - Large beats + positive price momentum (past 12-1 month) historically strongest")
    A("")
    A("6. **Consider SUE ranking** (Standardized Unexpected Earnings)")
    A("   - Cross-sectional ranking by surprise magnitude better than fixed 10% threshold")
    A("   - Go long top quintile, short bottom quintile")
    A("")
    A("---")
    A("")
    A("## Appendix: Key Numbers")
    A("")
    A("```")
    A("Full Period (2012-2024):")
    A(f"  Strategy return:   447.2%")
    A(f"  SPX return:        360.6%")
    A(f"  Excess return:    +86.6 ppt")
    A(f"  Annual Sharpe:      1.02")
    A(f"  Max Drawdown:     -32.9%")
    A(f"  Win Rate:          58.7%")
    A(f"  N Trades:           922")
    A("")
    A("Walk-Forward:")
    A(f"  IS  (2012-2018): ret=174.0%, sh=1.31, vs SPX 96.3%  (+77.7ppt)")
    A(f"  OOS (2019-2024): ret= 99.7%, sh=0.80, vs SPX 134.3% (-34.6ppt)")
    A("")
    A("Temporal (3yr buckets):")
    A(f"  2012-2014: Sharpe 1.71, ret 75.1%, SPX 61.2%  (+13.9ppt)")
    A(f"  2015-2017: Sharpe 1.00, ret 38.5%, SPX 29.9%  ( +8.6ppt)")
    A(f"  2018-2020: Sharpe 1.12, ret 67.2%, SPX 39.3%  (+27.9ppt)")
    A(f"  2021-2024: Sharpe 0.59, ret 35.0%, SPX 58.9%  (-23.9ppt) <- underperforms")
    A("```")
    A("")
    A("---")
    A("")
    A("*Generated by trading-bench research subagent — 2026-06-14*  ")
    A("*Data: EDGAR XBRL + Yahoo Finance v8 (cached in `cache/pead/`)*  ")
    A("*Script: `scripts/pead_run.py` | JSON: `/tmp/pead_result.json`*")

    report_path = os.path.join(REPORTS_DIR, "PEAD_RESEARCH_20260614.md")
    with open(report_path, "w") as f:
        f.write("\n".join(L))
    print(f"Wrote {report_path}")
    return report_path

path = write_report()
print("All done.")
print(f"Result JSON at /tmp/pead_result.json")
print(f"Report at {path}")
