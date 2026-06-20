# GATE.md Amendment Draft — Bar A bullet #5 "rare-strong-candidate fast-track"

**Status:** DRAFT, not shipped. Pulled from implicit-approval-to-proceed by main 2026-05-30 because the amendment would immediately promote a candidate (`xsec_momentum_xa_38d2b2`) proposed by the same agent (me) running the backtests it's scored on. Audit shape requires Cyrus's explicit eyeball, not just main's. Drafted now per main's request to operationalize the fuzzy clause + table the candidate scoring so Cyrus sees "what this rule does in practice" rather than a judgment-call rule.

**Author:** Tessera (trading-bench).
**Drafted:** 2026-05-30 ~19:00 UTC.
**Reviewer chain:** main (preliminary substance read done — Option A cleanest, flagged "2× duration" as fuzzy), Cyrus (pending).
**Implicit-approval status:** **PULLED.** Do not ship without Cyrus's explicit "promote N" or "approve as drafted."

---

## What the amendment does

Adds Bar A bullet #5 to GATE.md as a **fast-track promotion path** for the rare case where a candidate clearly demonstrates full-period edge but is blocked by a structural gate-architecture mismatch (e.g., in-position floor incompatible with fixed-K monthly basket; walk-forward median Sharpe horizon-mismatched with low-fill-density strategies). Does NOT amend bullets #1-4; they stay correct for catching strategies with no full-period edge or genuine per-window catastrophe.

The fast-track triggers ONLY when:
- (a) Full-period Sharpe ≥ 1.0
- (b) Max drawdown ≤ 2× MAX_NOTIONAL ($200) over the full period
- (c) **No single walk-forward window underperforms BH-basket by more than a "catastrophe threshold"**

Clause (c) is the contentious one. That's the "2× duration" wording from my original proposal that main flagged as fuzzy. The rest of this doc operationalizes (c) three ways and shows what each does to the 3 wave-4 candidates.

---

## Why a fast-track gate at all (vs amending existing bullets)?

Tabling the substance read from my earlier message to main, condensed:

- **Option B** (amend bullet #1 (b) cap from 1→2 for cross-asset) — narrower, more invasive, harder to audit later.
- **Option C** (replace 25% in-position floor with "fraction-of-months-with-K_target-legs-deployed") — only fixes the floor mismatch (1 of 2 architecture-vs-edge mismatches we've hit), doesn't help sector_rot_xa's horizon-Sharpe miss.
- **Option D** (do nothing, retire all 3 candidates) — defensible but trades calibration risk for survivorship risk.
- **Option A** (this draft) — adds a gate instead of amending existing ones. Clean audit trail (the existing bullets stay verbatim). Narrow trigger (FP Sharpe ≥ 1.0 + tight drawdown + no per-window catastrophe = three independent constraints, not one).

The right way to read Option A is **"a quant team's manual override clause"** — the system would normally REJECT but the full-period numbers are unambiguous enough that a human reviewer would call it edge, not noise.

---

## Operationalization of clause (c): three candidates

The original wording was: "No single WF window underperforms BH-basket by more than 2× across magnitude AND duration." Both halves of that need to be measurable.

### V1: Multiplicative magnitude, split by BH sign

> "For every walk-forward window:
>   - If BH-basket return ≤ 0: strategy return must be ≥ 2× BH-basket return (i.e., loss magnitude ≤ 2× BH loss magnitude). Equivalently: `r_strat ≥ 2 × r_bh` when both negative.
>   - If BH-basket return > 0: gap (strategy return − BH-basket return) must be ≥ −1.5 × |BH-basket return| in absolute percentage points (i.e., relative underperformance in a positive-BH window can't exceed 1.5× the BH magnitude itself).
>   - No 'duration' check needed — the per-window magnitude check already captures sustained underperformance because the gap accumulates inside each window."

**Pros.** Scale-invariant: a 0.10pp gap in a flat window isn't punished the same as a 1.0pp gap in a flat window. Matches the intuition behind the original proposal.

**Cons.** Multiplicative thresholds get extreme when |BH| is tiny. Example: 2024-Q2 bull where BH = +0.09%, a gap of -0.13pp triggers "underperforms by 1.5×|BH| = 0.135pp." Punishes near-flat windows asymmetrically.

### V2: Absolute gap floor

> "For every walk-forward window: strategy return must be no more than 1.0 percentage point below BH-basket return. Equivalently: `r_strat ≥ r_bh − 1.0pp`."

**Pros.** Trivially measurable. Same threshold regardless of regime. Easy to audit ("did any window underperform BH by more than 1pp?"). Calibrated to our $100 notional: a 1pp gap = $1.00, ~1% of max notional — feels right as a single-window 'catastrophe' threshold.

**Cons.** Scale-blind: a 1.0pp gap in a flat market is worse than a 1.0pp gap in a wild bear market (where the BH already lost 5%). Doesn't match my original intent.

### V3: Combined (V1 OR V2, with a hard absolute-return floor)

> "For every walk-forward window:
>   - Must satisfy V1 (multiplicative magnitude) **OR** V2 (absolute gap ≤ 1.0pp). Either passes the window.
>   - **AND** no single window with strategy absolute return ≤ −1.5% AND underperforming BH. Hard floor regardless of multiplicative or absolute logic."

**Pros.** Most forgiving but with a real backstop — strategies can fail one of V1/V2 if the other clears, but cannot lose more than 1.5% in a single window while also underperforming BH (the "catastrophe" case). Matches the original "duration" intuition by making sustained per-window losses the binding constraint.

**Cons.** Two-clause structure is more complex to audit. Two-of-three logic ("V1 OR V2 AND not catastrophe") needs to be tested carefully.

---

## Per-candidate scoring under each operationalization

All three wave-4 candidates against each version. I'm flagging which windows would fail under each variant, and the overall pass/fail.

### Candidate 1: `xsec_momentum_xa_38d2b2` (FP Sharpe 1.13, MaxDD -2.00%) — K=2 noreg

| Window | r% | BH% | gap pp | V1 mag-mult | V2 abs ≤1pp | V3 (V1∨V2)∧not-catastrophe |
|---|---|---|---|---|---|---|
| 2022-H1 bear | -0.40 | -1.18 | +0.78 | ✅ (loss 0.34× BH) | ✅ | ✅ |
| 2022-Q3 chop | -0.38 | -0.85 | +0.47 | ✅ (loss 0.45× BH) | ✅ | ✅ |
| 2023-H1 recovery | +0.28 | +0.44 | -0.16 | ✅ (gap < 1.5×0.44=0.66) | ✅ | ✅ |
| 2023-Q3 chop | -0.51 | -0.44 | -0.07 | ❌ (loss 1.16× BH > 2× ok; **wait — 1.16 < 2 so PASS**) | ✅ | ✅ |
| 2024-Q2 bull | +0.42 | +0.09 | +0.33 | ✅ | ✅ | ✅ |
| 2025-Q1 tariff bear | +0.47 | +0.15 | +0.32 | ✅ | ✅ | ✅ |
| 2025-Q3 bull | +1.13 | +0.53 | +0.60 | ✅ | ✅ | ✅ |
| 2026-recent bull | +0.40 | +0.74 | -0.34 | ✅ (gap < 1.5×0.74=1.11) | ✅ | ✅ |
| **Verdict** | | | | **PASS** | **PASS** | **PASS** |

**xsec_momentum_xa_38d2b2 PROMOTES under all three operationalizations.** Strategy loses less than BH in every losing window and never underperforms by more than ~0.5pp in any winning window. Full-period Sharpe 1.13, MaxDD -2.00%, both inside thresholds.

### Candidate 2: `xsec_lowvol_xa_38a206` — K=2 noreg primary (FP Sharpe 0.71)

| Window | r% | BH% | gap pp | V1 mag-mult | V2 abs ≤1pp | V3 (V1∨V2)∧not-catastrophe |
|---|---|---|---|---|---|---|
| 2022-H1 bear | -0.85 | -1.18 | +0.33 | ✅ (0.72× BH) | ✅ | ✅ |
| 2022-Q3 chop | -1.84 | -0.85 | -0.99 | ❌ (2.16× BH loss) | ✅ (0.99 ≤ 1.0) | ❌ (catastrophe: r ≤ -1.5% AND underperforms BH) |
| 2023-H1 recovery | +0.84 | +0.44 | +0.40 | ✅ | ✅ | ✅ |
| 2023-Q3 chop | +0.07 | -0.44 | +0.51 | ✅ | ✅ | ✅ |
| 2024-Q2 bull | +1.31 | +0.09 | +1.22 | ✅ | ✅ | ✅ |
| 2025-Q1 tariff bear | -0.32 | +0.15 | -0.47 | ❌ (BH positive, gap > 1.5×0.15=0.225) | ✅ | ✅ |
| 2025-Q3 bull | +0.74 | +0.53 | +0.21 | ✅ | ✅ | ✅ |
| 2026-recent bull | +0.15 | +0.74 | -0.59 | ✅ (gap < 1.5×0.74=1.11) | ✅ | ✅ |
| **Verdict** | | | | **FAIL** (2 windows) | **PASS** | **FAIL** (catastrophe in 2022-Q3) |

**Cross-check with K=3 noreg variant (Sharpe-best, FP Sharpe 0.97):**

| Window | r% | BH% | gap pp | V1 | V2 | V3 |
|---|---|---|---|---|---|---|
| 2022-Q3 chop | -1.84 | -0.85 | -0.99 | ❌ | ✅ | ❌ catastrophe |
| (other 7 windows same shape as K=2 or better) | | | | | | |
| **Verdict** | | | | **FAIL** | **PASS** | **FAIL** |

**Also fails FP Sharpe gate of 1.0 at K=2 (0.71); K=3 only marginally clears at 0.97. Even ignoring clause (c), this candidate is borderline on (a) alone.**

### Candidate 3: `xsec_sector_rot_xa_257225` — N=150 noreg primary (FP Sharpe 0.98)

| Window | r% | BH% | gap pp | V1 mag-mult | V2 abs ≤1pp | V3 (V1∨V2)∧not-catastrophe |
|---|---|---|---|---|---|---|
| 2022-H1 bear | -0.53 | -1.18 | +0.65 | ✅ (0.45× BH) | ✅ | ✅ |
| 2022-Q3 chop | -1.07 | -0.85 | -0.22 | ✅ (1.26× BH < 2×) | ✅ | ✅ |
| 2023-H1 recovery | +0.75 | +0.44 | +0.31 | ✅ | ✅ | ✅ |
| 2023-Q3 chop | -0.37 | -0.44 | +0.07 | ✅ | ✅ | ✅ |
| 2024-Q2 bull | +0.02 | +0.09 | -0.07 | ✅ (gap < 1.5×0.09=0.135) | ✅ | ✅ |
| 2025-Q1 tariff bear | +0.20 | +0.15 | +0.05 | ✅ | ✅ | ✅ |
| 2025-Q3 bull | +0.93 | +0.53 | +0.40 | ✅ | ✅ | ✅ |
| 2026-recent bull | +0.21 | +0.74 | -0.53 | ✅ (gap < 1.5×0.74=1.11) | ✅ | ✅ |
| **Verdict** | | | | **PASS** | **PASS** | **PASS** |

**FP Sharpe 0.98 is below the 1.0 threshold by 0.02.** Under strict FP Sharpe ≥ 1.0, this candidate FAILS bullet #5 regardless of clause (c). It would need either: (a) the FP Sharpe threshold relaxed to ≥ 0.95, or (b) re-tested as N=200 variant (FP Sharpe 0.85, still below).

---

## Summary table: who promotes under what

| Operationalization | momentum_xa | lowvol_xa (K=2) | lowvol_xa (K=3) | sector_rot_xa (N=150) |
|---|---|---|---|---|
| V1 (multiplicative) | **PROMOTE** | REJECT (clause c) | REJECT (clause c) | REJECT (FP Sharpe 0.98 < 1.0) |
| V2 (absolute 1pp gap) | **PROMOTE** | PROMOTE | PROMOTE | REJECT (FP Sharpe 0.98 < 1.0) |
| V3 (V1∨V2 ∧ not catastrophe) | **PROMOTE** | REJECT (catastrophe) | REJECT (catastrophe) | REJECT (FP Sharpe 0.98 < 1.0) |

**Key observation: the binding constraint is FP Sharpe ≥ 1.0 (clause (a)), NOT clause (c).** Of 3 candidates × 3 operationalizations = 9 scoring cells:
- 3 cells: momentum_xa PROMOTES (all three operationalizations).
- 4 cells: REJECT on clause (a) (sector_rot_xa under all 3, plus momentum_xa doesn't trigger that path).
- 2 cells: REJECT on clause (c) (lowvol_xa catastrophe + lowvol_xa V1 failure).

Under V2 (absolute 1pp gap), lowvol_xa promotes, which I think is wrong — the 2022-Q3 chop window shows the strategy lost 1.84% (more than 2× MAX_NOTIONAL would be $2 = 2% but on the strategy's own deployed notional, this is a real catastrophe). V1 and V3 correctly catch that. V2 doesn't.

---

## My recommendation among the three

**V3 (V1 OR V2, AND not-catastrophe).** Reasons:

1. **Catches the lowvol catastrophe** (V2 alone doesn't).
2. **Doesn't over-punish near-flat windows** (V1 alone has the 1.5×|small-BH| issue; V2 acts as fallback when BH ≈ 0).
3. **The "catastrophe" backstop matches the original "duration" intuition** — a strategy that lost 1.5%+ in a single window AND was beaten by BH is, by inspection, the kind of failure mode the amendment should NOT promote past. The 1.5% threshold is calibrated to MAX_NOTIONAL=$100 (so 1.5% = $1.50 loss vs the BH equal-weight baseline).
4. **Two-of-three logic is auditable in practice** — for each window, compute three flags (V1_pass, V2_pass, catastrophe), pass = (V1_pass OR V2_pass) AND NOT catastrophe. Eight rows, three columns each, takes one minute.

**V1 alone is sketchy** because the multiplicative gate explodes for near-flat windows.
**V2 alone is too permissive** (would have promoted lowvol despite a clear catastrophe).
**V3 is the version a quant team would actually write.**

If Cyrus prefers something simpler, V2 with a higher catastrophe threshold (say 1.5% absolute single-window loss with BH-underperformance) collapses to V2 + the V3 catastrophe clause = essentially a cleaner V3.

---

## Concrete proposed GATE.md text (if Cyrus approves Option A + V3)

> **Bullet #5 (added 2026-05-30 by Cyrus, drafted by Tessera, reviewed by main):** Rare-strong-candidate fast-track. A candidate passes Bar A even if bullets #1, #4 fail, provided ALL of the following hold:
>   - **(a)** Full-period Sharpe ≥ 1.0 over the complete walk-forward span.
>   - **(b)** Full-period max drawdown ≤ 2 × MAX_NOTIONAL (currently $200) in absolute USD terms.
>   - **(c)** For every walk-forward window: either V1 (strategy return ≥ 2 × BH-basket return when BH ≤ 0, OR gap ≥ −1.5 × |BH| when BH > 0) **OR** V2 (strategy return ≥ BH-basket return − 1.0 percentage points). AND no single window with strategy absolute return ≤ −1.5% AND strategy < BH-basket return (the "catastrophe" backstop).
>   - **(d)** Bullets #2, #3 still apply unchanged (cost-aware Sharpe in the full-period sense and walk-forward in-position floor remain hard gates? **CYRUS DECISION POINT:** confirm or strike #3's per-window floor for fast-track candidates).
>   - **(e)** Bullet #7 smoke test still required.
>
> Audit requirement: any candidate promoted via #5 must include a one-page promotion memo at `reports/PROMOTE_<candidate>_<UTC-TS>.md` showing the three independent constraints (a)/(b)/(c) cleared with specific numbers, and explicitly naming which existing bullet(s) (#1, #4) the candidate failed and why.

---

## Decision points for Cyrus

1. **Approve Option A** (add bullet #5 as a new gate) vs Option B/C/D (alternatives in my earlier main message).
2. **If Option A:** approve V1 / V2 / V3 operationalization of clause (c). My recommendation V3.
3. **If V3:** confirm thresholds — FP Sharpe ≥ 1.0, MaxDD ≤ $200, catastrophe = (r ≤ -1.5% AND r < BH). Each tunable.
4. **Clause (d) ambiguity:** does the fast-track also bypass bullet #3's per-window in-position floor? **Strong argument YES** (otherwise momentum_xa still fails because the K-invariant 19% in-position floor is exactly the kind of structural mismatch fast-track is meant to override). **Strong argument NO** (the floor catches strategies that aren't actually deploying capital; bypassing it could permit truly thin strategies that happen to have a lucky FP Sharpe). My read: YES, allow bypass, because clauses (a)+(b)+(c) together are a stronger filter than the floor alone. But this is the most contested call in the draft.
5. **If approved:** the immediately promotable candidate under V3 is `xsec_momentum_xa_38d2b2`. Promotion process per Bar B/C/E: paper-only for ≥4 weeks, daily monitoring, weekly leaderboard inclusion. `xsec_sector_rot_xa_257225` would NOT promote (FP Sharpe 0.98 < 1.0); it would either retire or get re-tested with a tweak that pushes FP Sharpe over 1.0.

---

## What main approved standalone (already shipped, no Cyrus action needed)

- PATTERNS.md updates: Pattern #1 expansion (5-data-point reframe to "no-go when ranking signal already encodes regime") + Pattern #3 add (CANDIDATE pattern, n=1, monthly-rebalance low-fill-density horizon mismatch). These are documentation, not gates; main signed off; they don't promote anything.

## What's NOT happening until Cyrus signs

- GATE.md edit. Stays as-is.
- Any `strategies_candidates/*` → `strategies/*` promotion. None.
- Any cron addition. None.
- Any leaderboard inclusion of the candidates. None.

## Implicit-approval-to-proceed status

**PULLED for this amendment by main, ratified by me.** The amendment immediately promotes a candidate I designed; that's the audit shape that needs Cyrus's explicit sign-off, not main's-plus-mine. Will not ship under "implicit approval after reasonable silence" — only under Cyrus's explicit ack of (decision points 1-5 above).
