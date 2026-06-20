# LEVERAGED-TREND FULL-HISTORY — Out-of-Sample Verdict

**Date:** 2026-06-09 (UTC) · **Author:** Tessera (parent-captured from subagent `lev_trend_fullhist` runId 6793271c, which built the code + produced the result JSON but context-died before writing this prose — verdict reconstructed by parent directly from the on-disk result files, NOT from agent prose).

**Mission bar:** BEAT SPX ON RAW RETURN (Cyrus directive). Gates suspended for explore; measured honestly.

**Candidate:** `strategies_candidates/leveraged_long_trend/` (PAPER, candidate-only, NOT live, NOT a `GATE_PASSING_PARENTS` member).

---

## TL;DR

**This is the FIRST lane in the project that genuinely beats SPX on raw return, out-of-sample, on a robust parameter plateau — full inception→2026 history, not just the post-2020 super-cycle.** It converts the prior single-window SOXL claim (`LEVERAGED_TREND_20260604`) into a real OOS result.

- **Headline (TQQQ / SMA-200 trend gate / VIX-off / 2bps-switch / T-bill cash), 2010-02→2026-06 (16.3 yr):**
  - Strategy **+10,121%** total · CAGR **32.9%** · maxDD **−56.0%** · Sharpe **0.846** · 84.6% in-market
  - SPX(^GSPC): +587% · CAGR 12.6% · maxDD −33.9% · Sharpe 0.773
  - Buy-hold-3x (no gate): +36,914% · CAGR 43.8% · maxDD **−81.7%** · Sharpe 0.904
- **Beats SPX raw: YES — in ALL 18 sweep cells** (3 sleeves × 3 gate modes × VIX on/off).
- **Frozen OOS (split 2018-01-01):** in-sample (2010-17) +641% vs SPX +148%; **out-of-sample (2018-26) +1,212% vs SPX +175%** — edge is *stronger* OOS, not a fitted-window artifact.
- **SMA-window robustness: 7/7 windows {100,120,150,180,200,220,250} beat SPX raw; 5/7 (150/180/200/220/250) also beat SPX Sharpe.** Broad plateau, not a lucky pick at 200.

**Honest asterisk (the whole reason this isn't a slam-dunk "promote"):** the raw-return win is largely a **leverage premium**, not risk-adjusted alpha. Best Sharpe (0.846) only marginally edges SPX (0.773); drawdowns are violent (−56% headline; stress windows 2018-Q4 −49%, 2022 −45%, 2011 −46%); the trend gate does NOT save you in fast V-shaped declines, only in slow grinds + the 2020 crash. A holder must stomach a >50% equity-curve drop to collect the raw-return premium. "Beats SPX raw" is TRUE and durable; "is alpha" is NOT the claim.

---

## Data (the unlock that made this possible)

Built `runner/daily_bars_cache.py` (Yahoo-v8 `adjclose`, split/div-adjusted, keyless, lookahead-safe as-of API; mirrors `cboe_cache`/`fred_cache` pattern) + `tests/test_daily_bars_cache.py` (15 tests, green). Cached to `data_cache/yahoo/`:
- TQQQ 2010-02-11 (4105 bars), UPRO 2009-06-25, SOXL 2010-03-11, QQQ, SPY, SOXX, ^GSPC — all `adjclose`.
- VIX/VIX3M from `cboe_cache`; 3M T-bill cash leg from `fred_cache`.

This is the deep-history extension the 06-08 pivot was reaching for: the prior SOXL result was capped at a **single post-2020 5.5yr Alpaca window** riding the semis super-cycle (+755% raw, flagged "unrepeatable / path-specific", no OOS). This run rides inception→2026 across 2011 / 2015-16 / 2018 / 2020 / 2022 — a real held-out test.

## No-lookahead contract (verified)
Signal for day D computed from bars with date ≤ D (underlying close + trailing SMA/TSMOM); position entered at D+1 OPEN, held over D+1 → position on any day uses strictly-earlier closes only. Per-switch cost charged each side. Cash leg earns prevailing 3M T-bill (annual/252). Confirmed in `backtest_daily.py` docstring + code.

---

## Winning-family sweep (full window, raw-return vs SPX)

| Config | totalRet% | CAGR% | maxDD% | Sharpe | %inMkt | beats SPX raw |
|---|---:|---:|---:|---:|---:|:--:|
| TQQQ/sma200/vix=0 | **10,121** | 32.9 | −56.0 | **0.846** | 84.6 | ✅ |
| TQQQ/both/vix=0 | 9,449 | 32.3 | −55.5 | 0.842 | 82.9 | ✅ |
| TQQQ/tsmom/vix=0 | 7,201 | 30.1 | −75.2 | 0.771 | 89.4 | ✅ |
| TQQQ/tsmom/vix=1 | 6,221 | 29.0 | −61.2 | 0.793 | 83.6 | ✅ |
| TQQQ/both/vix=1 | 4,635 | 26.7 | −58.3 | 0.776 | 79.1 | ✅ |
| TQQQ/sma200/vix=1 | 4,188 | 26.0 | −58.3 | 0.757 | 80.6 | ✅ |
| UPRO/sma200/vix=0 | 4,113 | 24.8 | −51.4 | 0.797 | 84.4 | ✅ |
| SOXL/sma200/vix=0 | 4,643 | 26.9 | **−84.3** | 0.695 | 76.5 | ✅ |
| *(…all 18 cells beat SPX raw; SOXL cells carry −84%…−89% DD — too violent)* | | | | | | |

**Reads:**
1. **TQQQ (3x Nasdaq-100) is the best sleeve** — UPRO (3x S&P) beats SPX but with less juice; SOXL (3x semis) has the highest raw upside in some cells but −84%…−89% drawdowns make it uninvestable.
2. **VIX-off > VIX-on for raw return.** The VIX/VIX3M term-structure overlay I built earlier (`VIX_REGIME_OVERLAY_20260608`) *reduces* raw return in nearly every cell while only marginally trimming DD on this sleeve. The earlier finding ("keep VIX as a risk-OFF gate for the leveraged sleeve") is **partially walked back**: on TQQQ the SMA-200 gate alone already does the heavy lifting; layering VIX on top mostly just sits you in cash during recoveries. VIX overlay stays a DRAWDOWN tool, not a raw-return enhancer here.
3. **SMA-200 ≥ TSMOM** as the gate; "both" ≈ sma200 (redundant).

## Frozen OOS (split 2018-01-01, TQQQ/sma200/vix=0)
| Segment | Strategy ret | SPX ret | Strat maxDD | %cash |
|---|---:|---:|---:|---:|
| In-sample 2010-02 … 2017-12 | +641% | +148% | −55.5% | 11.5% |
| **Out-sample 2018-01 … 2026-06** | **+1,212%** | +175% | −56.0% | 19.1% |

Edge persists (in fact amplifies) OOS. Not a window-fit.

## SMA-window robustness (TQQQ/vix=0, full window — is 200 special?)
| sma | totalRet% | Sharpe | beats SPX raw | beats SPX Sharpe |
|---:|---:|---:|:--:|:--:|
| 100 | 2,534 | 0.688 | ✅ | ❌ |
| 120 | 4,229 | 0.752 | ✅ | ❌ |
| 150 | **17,835** | **0.934** | ✅ | ✅ |
| 180 | 15,593 | 0.908 | ✅ | ✅ |
| 200 | 10,121 | 0.846 | ✅ | ✅ |
| 220 | 10,379 | 0.845 | ✅ | ✅ |
| 250 | 12,442 | 0.864 | ✅ | ✅ |

**7/7 beat SPX raw; 5/7 beat SPX Sharpe.** The peak at 150 (Sharpe 0.934) is the best risk-adjusted point but I do NOT cherry-pick it — 200 is the a-priori textbook choice and the plateau is what matters. A plateau this broad = structural trend-gate edge, not curve-fit.

## Stress windows (TQQQ/sma200/vix=1 — the headline gated config)
| Window | Strategy | SPX | BH-3x | Strat maxDD | %cash in window |
|---|---:|---:|---:|---:|---:|
| 2011 EU-debt chop | −46.2% | −7.6% | −26.0% | −46.7% | 43.5% |
| 2015-16 China devalue | −34.1% | −8.5% | −27.1% | −35.1% | 39.2% |
| 2018 Q4 selloff | −49.5% | −14.3% | −48.2% | −49.5% | 77.8% |
| **2020 COVID crash** | **−19.5%** | −13.6% | −39.2% | −29.6% | 82.7% |
| 2022 bear (full yr) | −45.0% | −20.0% | −79.7% | −45.0% | 92.8% |
| 2023-24 bull | **+160.0%** | +53.8% | +382.6% | −38.9% | 5.6% |

**The gate's real character:** it dramatically cuts the BH-3x bloodbath in slow bears (2022: −45% vs BH −80%; saved 35pp) and the COVID crash (−19% vs BH −39%), BUT it is whipsawed badly in **fast V-shaped reversals** (2011, 2018-Q4) where it sells low into the bounce and underperforms even unleveraged SPX. It is NOT a free hedge — it trades fat tails for raw upside. The 2023-24 bull (+160% vs SPX +54%) is where it earns its keep.

---

## Disposition

**KEEP as a strong candidate — the project's first real raw-return-beats-SPX result with OOS + robustness support — but do NOT promote to a live paper clock yet.** Reasons to hold:
1. **Risk-adjusted edge is marginal** (Sharpe 0.846 vs 0.773). The raw win is a leverage premium; under our SPY-relative IR gate (`spy_relative.py`) and the standard Sharpe-≥1.0 front door, this would **not clear** — exactly as the SOUL.md "12% at 2x risk is leverage not alpha" warning predicts. The mission bar (raw return) says ship; the risk discipline says size it tiny.
2. **−56% drawdowns** are beyond anything else on the bench. A live paper clock on a 3x sleeve needs explicit position-sizing + a real-money rail conversation with Cyrus before it's anything but paper.
3. **Single-instrument concentration** (TQQQ = 3x one index). Robust across sma-windows, but one sleeve, one index.

**Recommended next steps (research lane, my call to sequence):**
- (a) **Volatility-target the sleeve** instead of binary in/out: scale TQQQ exposure by inverse realized-vol so the −56% DD compresses toward SPX's −34% while keeping most of the raw upside — this is the honest path from "leverage premium" toward "risk-adjusted edge." If vol-targeting gets Sharpe clearly >1.0 AND keeps beating SPX raw, THAT is the promotable version.
- (b) **Synthetic pre-2010 extension** (the `daily_bars_cache` + daily-compounded-returns + FRED-drag builder, scoped 06-08) to test the gate across 2008-GFC — the one bear this run can't see (TQQQ inception is 2010). A NEGATIVE there (gate fails the GFC) is valuable and would cap conviction.
- (c) Report real-only vs synthetic separately; never blend.

**Bottom line:** earned conviction, with the asterisk stated plainly. This is the strongest lead the project has produced toward the actual mission. It is a *leverage-harvesting* strategy with a trend gate that tames (not eliminates) the tail — not alpha — and it should be advanced via vol-targeting before any live consideration. Logged; pile-discipline intact (candidate-only, protected md5s unchanged, suite green ex-known-flake).

---

### Reproducibility
- `python3 -m strategies_candidates.leveraged_long_trend.evaluate` → `evaluation_result.json`
- `python3 -m strategies_candidates.leveraged_long_trend.validate_oos` → `validation_oos_result.json`
- Protected md5s unchanged: backtest.py `9444ee5b…`, runner.py `4be185e4…`, risk.py `e4c227e0…`, backtest_xsec.py `2278a4c8…`, strategy_gen.py `a9d17ee4…`.
- Suite: 376 passed / 1 failed; the 1 failure (`test_dry_run_produces_report`) is the known in-process tournament-dry-run pollution flake — passes deterministically when run isolated (`15 passed` for `test_daily_bars_cache.py`; `1 passed` for the flake isolated). Live `strategies/` untouched; no killswitch.
