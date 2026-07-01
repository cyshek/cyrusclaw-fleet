# RETURN STACKING — CONFIRM-OR-KILL VERDICT

**Stamp:** 20260630T204227Z · **Author:** trading-bench subagent (Return Stacking confirm-or-kill)
**Script (reproducible):** `_return_stacking_confirm.py` · **Raw JSON:** `reports/_return_stacking_result.json`
**Data:** free only — Yahoo daily (via `runner/daily_bars_cache`) + FRED `DGS3MO` (via `runner/fred_cache`, keyed API). No paid feeds.

---

## VERDICT: **KILL** (as a Sharpe/risk-improvement) · **GO-with-caveat** only as a *pure return-amplifier* if a higher-vol, higher-drawdown mandate is explicitly wanted.

**Return stacking a financed TQQQ-voltarget diversifier on top of the rotation core does NOT reach a risk/return point the sum-to-1 inv-vol blend cannot.** It reaches a *higher-raw-return* point (mechanically — a sum-to-1 blend physically can't produce 22–30%/yr from these two sleeves), but at **strictly worse Sharpe and strictly worse drawdown**, both full-period and OOS (2020+), even though financing was historically cheap (avg 3M T-bill **1.51%/yr** over 2010–2026). The financing drag is real but small (**~100 bps/yr @0.5, ~201 bps/yr @1.0** gross borrow cost on the stacked notional); it is **not** the primary killer here — the killer is that **levering a 0.82-Sharpe diversifier and adding it on top of the core dilutes the portfolio Sharpe toward the diversifier's**, while the unlevered inv-vol blend *raises* Sharpe by tilting INTO the calmer, higher-Sharpe sleeve mix. Stacking adds beta; inv-vol blending adds risk-efficiency. They are not the same trade, and for our objective (risk-adjusted return) blending wins cleanly.

The **+1-bar canary** on the diversifier signal confirms the (small, negative-vs-blend) result is **not** a one-bar-lookahead artifact — lagged numbers are within noise of unlagged.

---

## THE KILLER NUMBERS

### Monthly metrics (published-formula basis; Sharpe = monthly × √12)
Common window **2010-02-12 → 2026-06-30**, 197 months. IS = through 2019, OOS = 2020+.

| Series | FULL Sharpe | FULL ann ret | FULL maxDD | OOS Sharpe | OOS ann ret | OOS maxDD |
|---|---|---|---|---|---|---|
| Core alone (rotation top-2) | 1.018 | 12.9% | −26.2% | 0.967 | 13.5% | −26.2% |
| Diversifier alone (TQQQ voltarget) | 0.821 | 17.8% | −29.6% | 0.993 | 20.9% | −16.3% |
| SPX (^GSPC) benchmark | 0.894 | 12.5% | −24.8% | 0.844 | 13.8% | −24.8% |
| **Inv-vol blend (sum-to-1, NO financing) — best current point** | **1.100** | **15.5%** | **−17.6%** | **1.216** | **18.3%** | **−16.6%** |
| Stacked @0.5 (financed) | 1.014 | 21.1% | −32.1% | 1.032 | 22.3% | −32.1% |
| Stacked @1.0 (financed) | 0.947 | 28.3% | −39.9% | 1.003 | 30.4% | −38.3% |
| Stacked @0.5 — **canary (div signal lagged +1 bar)** | 1.016 | 21.2% | −32.9% | 1.038 | 22.4% | −32.9% |
| Stacked @1.0 — **canary (div signal lagged +1 bar)** | 0.943 | 28.2% | −39.2% | 1.003 | 30.4% | −39.2% |

### Daily-annualized cross-reference (Sharpe = daily × √252; comparable to the bench's reported sleeve/blend Sharpes)

| Series | Sharpe | ann ret | maxDD | ann vol | SPY corr |
|---|---|---|---|---|---|
| Core alone | 0.925 | 12.9% | −29.0% | 14.2% | 0.46 |
| **Inv-vol blend (ref)** | **1.037** | 15.6% | **−20.3%** | 15.1% | 0.59 |
| Stacked @0.5 | 0.959 | 21.1% | −36.5% | 22.7% | 0.58 |
| Stacked @1.0 | 0.919 | 28.1% | −43.7% | 32.9% | 0.60 |
| — OOS 2020+ — | | | | | |
| Core alone (OOS) | 0.859 | 13.6% | −29.0% | 16.4% | 0.52 |
| **Inv-vol blend (OOS)** | **1.097** | 18.4% | **−20.0%** | 16.7% | 0.57 |
| Stacked @0.5 (OOS) | 0.931 | 22.2% | −36.5% | 24.9% | 0.58 |
| Stacked @1.0 (OOS) | 0.922 | 29.8% | −43.4% | 35.1% | 0.59 |

---

## THE HONEST ANSWER TO "DOES THIS REACH A POINT INV-VOL CANNOT?"

**On RAW RETURN: yes, trivially** — stacking @1.0 delivers ~30%/yr OOS vs the blend's ~18%, which a sum-to-1 combination of these two sleeves can never reach (you can't allocate >100%). **If the only goal were maximal compounding and the mandate tolerated ~35% annual vol and ~44% drawdowns, stacking @1.0 is the highest-return point on the menu.**

**On RISK-ADJUSTED RETURN (Sharpe) and on DRAWDOWN: no.** Every stacked variant is **below** the inv-vol blend's Sharpe (OOS: 1.03 / 1.00 stacked vs **1.22** blend monthly; 0.93 / 0.92 vs **1.10** blend daily) and has **roughly 2× the drawdown** (−36% to −44% stacked vs **−20%** blend). The blend reaches a point stacking cannot: **higher Sharpe AND lower drawdown simultaneously.** Stacking and inv-vol blending move in *orthogonal* directions on the risk/return plane — stacking pushes out the return axis at a worse slope; inv-vol blending rotates the whole frontier up (better slope). For a risk-adjusted objective, the sum-to-1 blend is not just adequate — it is **strictly superior**, and financing makes stacking worse, not better.

## FINANCING DRAG (quantified)

- **avg 3M T-bill (DGS3MO) over window: 1.508%/yr** (units verified: FRED DGS3MO is in percent → monthly = v/100/12).
- **Gross borrow cost on the stacked notional** = StackSize × (avg T-bill + 50bp spread):
  - @0.5 → **~100.4 bps/yr** (of which 25 bps is the pure 50bp-spread half-weighted).
  - @1.0 → **~200.8 bps/yr** (of which 50 bps is the pure spread).
- This is the gross hurdle the diversifier leg must out-earn *before* it adds anything. The diversifier (TQQQ voltarget) earned ~18–21%/yr, so it *clears* the hurdle on return — which is exactly why stacked raw return is high. But clearing the hurdle on *return* does not buy *Sharpe*: the leg's own Sharpe (0.82 full / 0.99 OOS) is **below** the blend's, so stacking it on top drags the composite Sharpe down regardless of how cheap the borrow is. **Financing is the falsifiable killer the task warned about, and it is logged truthfully: it is a real ~100–200 bps/yr drag, but even at zero financing the Sharpe ranking would not flip (stacked@1.0 zero-fin Sharpe would gain only the ~2 pp/yr return back, nowhere near closing a ~0.2 Sharpe gap).**

## CANARY (mandatory, diversifier daily signal)

Lagging the TQQQ-voltarget daily return stream **+1 trading bar** (acting one day late on its gate/vol-size signal) and re-aggregating to months changes the stacked Sharpe by **< 0.005** at both stack sizes (@0.5: 1.014→1.016 full, 1.032→1.038 OOS; @1.0: 0.947→0.943 full, 1.003→1.003 OOS). **No timing artifact.** The (negative-vs-blend) conclusion is robust to one-bar execution slippage on the diversifier.

---

## METHOD NOTES / INTEGRITY

- **Mechanism:** exact ReturnStacked.com published monthly formula `R_stacked = R_core + S·(R_div − Fee/12 − (R_TBill_month + Financing/12))`, Fee=0, Financing=0.50%/yr, R_TBill_month = annual_rate/12. Also computed a daily analogue (financing/252) purely to produce a daily-√252 Sharpe directly comparable to the bench's existing sleeve/blend Sharpes; economically identical overlay.
- **Core** = `_sigimprove_tests.run_sector_rotation(["SPY","QQQ","GLD","TLT"], hold_top=2, lookback_months=3, cost_bps=2, start=2005-01-01)` — the validated rotation sleeve.
- **Diversifier** = `run_backtest_voltarget(VolTargetParams(target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0, vix_gate=False, switch_cost_bps=2.0, breadth_windows=[30,90,180]))` — the EXACT config `_allocator_blend_tests.build_sleeves` uses for the live `leveraged_long_trend_paper`.
- **Reference blend** = sum-to-1, monthly-rebalanced, drift-between, **inv-vol(63d)** weighting of `[voltarget, rotation]`, reproduced byte-for-byte from `_allocator_blend_tests` (same sleeve ordering, same 2bps inter-sleeve cost), NO financing. This is the best risk/return point a sum-to-1 blend reaches.
- **Sharpe** computed via the canonical primitive `runner.fp_sharpe.sharpe_from_returns` (excess=0, matching bench convention) — monthly series → bpy=12, daily series → bpy=252. (Note: `fp_sharpe.fp_continuous_sharpe` operates on walk-forward *window objects*; for a single continuous return series the continuous-span Sharpe IS `sharpe_from_returns(series, bpy)` directly, which is what was used.)
- **Common calendar** = intersection of both sleeves' + SPX daily dates = TQQQ-inception-bounded (2010-02-12 → 2026-06-30). T-bill forward-filled to every market date; monthly T-bill leg = month-average annual rate.
- **No-lookahead:** both sleeve engines are individually lookahead-safe; the overlay uses only contemporaneous monthly returns + a financing rate known at month start; canary stresses one-bar execution lag on the diversifier.
- **Hard rails honored:** 6 protected files MD5-unchanged (verified pre/post — runner.py 0f763975, risk.py e303317e, backtest.py 717c36e6, backtest_xsec.py d8927364, walk_forward_xsec.py 8c3df32c, safety_backstop.py bccefaba). No crontab/.db/paper-tracker/strategies edits. Read-only use of `_allocator_blend_tests.py` / `_sigimprove_tests.py` configs. Relevant regression subset **80 passed / 0 failed** (suite baseline 907/3 preserved — no harness added to `runner/`).

## BOTTOM LINE FOR THE ROADMAP

Do **not** promote return-stacking as a Sharpe/risk improvement — the inv-vol blend already dominates it on the dimension we optimize. The only scenario where stacking earns a slot is an *explicit* high-octane "max compounding, accept 35% vol / 44% DD" sleeve, which is a different product than what the validated blend targets. **KILL for the stated objective; logged truthfully with financing drag exposed.**
