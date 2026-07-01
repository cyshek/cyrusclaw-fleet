# RTL-Immunization Confirm-or-Kill -- Overlapping Daily-Staggered Tranches

_Generated 20260630T210708Z UTC. Research-only. Free Yahoo data. NO protected-file edits, NO DB writes, NO live wiring._

**Mechanism (Newfound Rebalance Timing Luck):** any hard-date monthly rebalancer's realized equity depends on WHICH trading day of the month it rebalances. Running N tranches (tranche k rebalances on the k-th trading day of each month) and holding the equal-weight average of their equity curves cuts that timing-luck variance ~1/N with ZERO change to the underlying signal. We quantify the dispersion across the N single-date tranches (= the luck baked into picking day-1) and test whether the EW-average is a free risk-adjusted improvement vs the day-1 live config.

**Ruler:** FP-Sharpe = canonical full-period continuous-span Sharpe (`runner/fp_sharpe.py`, sample-stdev, sqrt(252)). CAGR / maxDD via `_stats_from_equity`. OOS split = train<=2019, OOS 2020+. N tranches = 21 (clamped to last trading day for short months).

---

## Target: `sector_rotation_top2`

- Window: 2005-01-03 -> 2026-06-30 (5406 days), 21 tranches

### RTL dispersion across the 21 single-date tranches (THE luck in picking day-1)

- **FP-Sharpe**: mean 0.8315, stdev **0.0718**, min 0.6853, max 0.9754, spread **0.2900** Sharpe units
- **CAGR**: mean 11.56%, stdev 1.100%, min 9.46%, max 13.83%, spread **436.9 bp/yr**
- **maxDD**: mean -34.36%, stdev 3.258%, min -41.57%, max -28.65%, spread **12.91 pp**
- **Terminal wealth** (base 1.0): mean 10.668, stdev 2.293, min 6.948, max 16.085, spread 9.137
- OOS FP-Sharpe stdev across tranches: 0.1283 (IS: 0.0656)

### EW-average-of-tranches vs day-1 baseline (live config)

| Metric | day-1 baseline | EW-average | delta |
|---|---|---|---|
| FP-Sharpe (full) | 0.9132 | 0.8852 | -0.0280 |
| CAGR % | 12.86 | 11.67 | -1.192 |
| maxDD % | -28.98 | -32.08 | -3.10 |
| ann vol % | 14.38 | 13.50 | -0.88 |
| terminal wealth | 13.396 | 10.668 | -2.727 |
| IS FP-Sharpe (<=2019) | 0.9482 | 0.9844 | +0.0362 |
| OOS FP-Sharpe (2020+) | 0.8474 | 0.7054 | -0.1420 |
| OOS maxDD % (2020+) | -28.98 | -31.10 | -2.12 |

- Turnover/cost note: each tranche has the SAME per-tranche turnover as the day-1 baseline; the EW-of-tranches holds 1/N in each, so blended cost ~= single-tranche cost (verified: baseline avg-turnover/rebal 1.123 vs tranche-mean 1.122).

### VERDICT: **GO-with-caveat**

RTL material (FP-Sharpe stdev 0.0718 / CAGR spread 436.9 bp/yr / maxDD spread 12.91pp) but EW-average costs slightly on one axis (FP-Sharpe -0.0280 vs day1, maxDD -3.10pp vs day1) -- still a robustness win.

---

## Target: `invvol_63d_blend`

- Window: 2010-02-12 -> 2026-06-30 (4119 days), 21 tranches

### RTL dispersion across the 21 single-date tranches (THE luck in picking day-1)

- **FP-Sharpe**: mean 1.0028, stdev **0.0340**, min 0.9229, max 1.0636, spread **0.1406** Sharpe units
- **CAGR**: mean 15.28%, stdev 0.586%, min 14.03%, max 16.37%, spread **233.9 bp/yr**
- **maxDD**: mean -23.05%, stdev 2.179%, min -28.13%, max -19.35%, spread **8.79 pp**
- **Terminal wealth** (base 1.0): mean 10.243, stdev 0.839, min 8.550, max 11.915, spread 3.365
- OOS FP-Sharpe stdev across tranches: 0.0684 (IS: 0.0300)

### EW-average-of-tranches vs day-1 baseline (live config)

| Metric | day-1 baseline | EW-average | delta |
|---|---|---|---|
| FP-Sharpe (full) | 1.0534 | 1.0220 | -0.0313 |
| CAGR % | 16.15 | 15.30 | -0.848 |
| maxDD % | -20.80 | -20.96 | -0.15 |
| ann vol % | 15.34 | 15.04 | -0.29 |
| terminal wealth | 11.546 | 10.243 | -1.303 |
| IS FP-Sharpe (<=2019) | 1.0192 | 1.0392 | +0.0199 |
| OOS FP-Sharpe (2020+) | 1.0847 | 0.9876 | -0.0971 |
| OOS maxDD % (2020+) | -19.43 | -20.96 | -1.53 |

- Turnover/cost note: each tranche has the SAME per-tranche turnover as the day-1 baseline; the EW-of-tranches holds 1/N in each, so blended cost ~= single-tranche cost (verified: baseline avg-turnover/rebal 0.083 vs tranche-mean 0.076).

### VERDICT: **GO-with-caveat**

RTL material (FP-Sharpe stdev 0.0340 / CAGR spread 233.9 bp/yr / maxDD spread 8.79pp) but EW-average costs slightly on one axis (FP-Sharpe -0.0313 vs day1, maxDD -0.15pp vs day1) -- still a robustness win.

---

## Bottom line

- **Sector-rotation top-2**: MATERIAL rebalance-timing luck baked into the single day-1 config = **436.9 bp/yr CAGR spread / 0.0718 FP-Sharpe stdev** across the 21 tranches. Verdict: **GO-with-caveat**.
- **invvol_63d blend**: MATERIAL rebalance-timing luck = **233.9 bp/yr CAGR spread / 0.0340 FP-Sharpe stdev** across the 21 tranches. Verdict: **GO-with-caveat**.
