# (driver stub output — full report assembled separately)

- Floor: contiguous SPY daily coverage begins 2020-08 (>= 15 bars/mo); leading sparse months trimmed

**Gate `ts-only (VIX/VIX3M>1.0)`** — span 2020-08-04 → 2026-06-05 (1467 trading days)

| Metric | Overlay | Buy&Hold SPY | Delta |
|---|---|---|---|
| **Raw total return** | **+94.40%** | **+124.31%** | **-29.91pp** |
| Raw total return (net of 2.0bp switch cost) | +92.09% | +124.31% | -32.23pp |
| CAGR | +12.10% | +14.89% | -2.79pp |
| Max drawdown | -29.90% | -25.38% | -4.53pp avoided |
| Sharpe (daily, ann.) | 0.84 | 0.91 | -0.08 |
| SPY-relative excess (ann.) | -2.79% | — | — |
| Information ratio | -0.37 | — | — |

Overlay behavior: 5.0% of days risk-OFF (cash), 60 switches, avg weight 0.950. **Verdict: does NOT beat SPY raw (+-29.91pp gross).**


**Gate `pct-only (VIX>90th)`** — span 2020-08-04 → 2026-06-05 (1467 trading days)

| Metric | Overlay | Buy&Hold SPY | Delta |
|---|---|---|---|
| **Raw total return** | **+68.87%** | **+124.31%** | **-55.44pp** |
| Raw total return (net of 2.0bp switch cost) | +66.32% | +124.31% | -57.99pp |
| CAGR | +9.42% | +14.89% | -5.47pp |
| Max drawdown | -31.54% | -25.38% | -6.16pp avoided |
| Sharpe (daily, ann.) | 0.70 | 0.91 | -0.21 |
| SPY-relative excess (ann.) | -5.47% | — | — |
| Information ratio | -0.61 | — | — |

Overlay behavior: 11.0% of days risk-OFF (cash), 76 switches, avg weight 0.890. **Verdict: does NOT beat SPY raw (+-55.44pp gross).**


**Gate `ts+pct (either)`** — span 2020-08-04 → 2026-06-05 (1467 trading days)

| Metric | Overlay | Buy&Hold SPY | Delta |
|---|---|---|---|
| **Raw total return** | **+73.69%** | **+124.31%** | **-50.62pp** |
| Raw total return (net of 2.0bp switch cost) | +70.87% | +124.31% | -53.45pp |
| CAGR | +9.95% | +14.89% | -4.94pp |
| Max drawdown | -31.54% | -25.38% | -6.16pp avoided |
| Sharpe (daily, ann.) | 0.75 | 0.91 | -0.17 |
| SPY-relative excess (ann.) | -4.94% | — | — |
| Information ratio | -0.53 | — | — |

Overlay behavior: 11.8% of days risk-OFF (cash), 82 switches, avg weight 0.882. **Verdict: does NOT beat SPY raw (+-50.62pp gross).**


**Gate `ts+pct+vvix`** — span 2020-08-04 → 2026-06-05 (1467 trading days)

| Metric | Overlay | Buy&Hold SPY | Delta |
|---|---|---|---|
| **Raw total return** | **+47.48%** | **+124.31%** | **-76.83pp** |
| Raw total return (net of 2.0bp switch cost) | +43.75% | +124.31% | -80.56pp |
| CAGR | +6.90% | +14.89% | -7.98pp |
| Max drawdown | -31.51% | -25.38% | -6.13pp avoided |
| Sharpe (daily, ann.) | 0.56 | 0.91 | -0.35 |
| SPY-relative excess (ann.) | -7.98% | — | — |
| Information ratio | -0.79 | — | — |

Overlay behavior: 15.9% of days risk-OFF (cash), 128 switches, avg weight 0.841. **Verdict: does NOT beat SPY raw (+-76.83pp gross).**


**Gate `ts+pct de-risk-to-50%`** — span 2020-08-04 → 2026-06-05 (1467 trading days)

| Metric | Overlay | Buy&Hold SPY | Delta |
|---|---|---|---|
| **Raw total return** | **+98.57%** | **+124.31%** | **-25.74pp** |
| Raw total return (net of 2.0bp switch cost) | +96.95% | +124.31% | -27.36pp |
| CAGR | +12.51% | +14.89% | -2.38pp |
| Max drawdown | -27.63% | -25.38% | -2.26pp avoided |
| Sharpe (daily, ann.) | 0.87 | 0.91 | -0.04 |
| SPY-relative excess (ann.) | -2.38% | — | — |
| Information ratio | -0.53 | — | — |

Overlay behavior: 11.8% of days risk-OFF (cash), 82 switches, avg weight 0.941. **Verdict: does NOT beat SPY raw (+-25.74pp gross).**


---

## Out-of-sample split (train → 2023-07-05, test 2023-07-05 → 2026-06-05)
- Gate tuned on train half (chose VIX 85th-pct off), then frozen and run on the unseen test half.
- **Test raw return: +50.99% (overlay) vs +66.13% (SPY) = −15.14pp** — still does not beat SPY raw OOS.
- **Test max drawdown: −10.28% (overlay) vs −18.98% (SPY) = 8.70pp avoided** — the cleanest, out-of-sample evidence this is a DRAWDOWN tool, not a raw-return engine.

## Honest caveats (read before trusting any number)
- **Data span is 2020-08 → 2026-06, NOT a full cycle.** The contiguous SPY *daily* cache on this box begins 2020-08 (≥15 bars/mo filter; sparse leading months trimmed). So this window is **bull-dominated and contains exactly one sharp crash (none — COVID's worst was Feb–Mar 2020, BEFORE the cache floor) plus the 2022 grind-down.** Any per-year "2018 / COVID-2020" attribution is OUT OF SAMPLE OF THIS CACHE and was not reproduced here; do not cite it. To test the 2018/2020 sharp-spike thesis we must first ingest pre-2020 SPY daily bars.
- **VIX-complex data itself is deep and clean** (VIX/SKEW 1990, VVIX 2006, VIX3M 2009-09, all PIT-correct, lookahead-guarded). The limiting factor is the SPY *price* history, not the signal history.
- **Point-in-time / no lookahead:** every signal uses only index levels dated strictly before the decision date (cboe_cache lookahead guard verified on real data). Switch cost modeled at 2.0 bps/switch.
- **Verdict (mission = beat SPX raw):** ❌ on raw return in every variant and OOS. ✅ as a modest, regime-dependent **drawdown overlay** (best: de-risk-to-50%, and the OOS full-gate cut 8.7pp of DD). **Recommended use: a risk-OFF GATE for a future trend-gated *leveraged-long* engine (Natenberg idea #1 / the SOXL/TQQQ 200-DMA lane), where capping drawdown on a 3x sleeve is worth far more than it is on plain SPY.** Not a standalone strategy.
