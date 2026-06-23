# GO-LIVE DECISION PACKET — allocator_blend + TQQQ vol-target sleeve

**Status:** living document. Compiled 2026-06-22 after the pre-real-money parameter-robustness checklist completed.
**Purpose:** when Cyrus decides whether to move either live paper strategy to real money, this is the single page that holds (a) what's validated, (b) the optional config nudges discovered during hardening (each with its cost/benefit + my recommendation), and (c) the hard gates that still must be cleared. Nothing here is applied to live config — these are decisions for the go-live moment.

---

## 1. What is LIVE on paper right now (validated, hardened)

| Strategy | What it is | Headline (full / OOS) | maxDD | Status |
|---|---|---|---|---|
| **leveraged_long_trend** (TQQQ vol-target sleeve, standalone) | Hold TQQQ sized inverse-realized-vol to 25% ann-vol, only when QQQ>200d-SMA (else T-bill cash), w≤1.0 | Sharpe 0.863 / OOS ~0.86 | −34.5% | LIVE paper, hardened ✅ |
| **allocator_blend** (multi-sleeve) | Inverse-vol (63d) blend of the TQQQ sleeve (A) + sector rotation (B: monthly 3mo-mom top-2 of SPY/QQQ/GLD/TLT) | Sharpe 1.009 / OOS 1.142 | −23.9% | LIVE paper, hardened ✅ |

Both beat SPX on raw return AND Sharpe, net of 2bps, OOS (frozen-2018 split). The allocator is the stronger risk-adjusted vehicle (the blend cuts the sleeve's −34.5% DD to −23.9% and lifts Sharpe to ~1.0); the standalone sleeve has higher raw CAGR (~20%) but deeper drawdowns.

**Hardening completed (2026-06-22):**
- Allocator 63d lookback: ROBUST (flat plateau 42→126d; walk-forward ≈ static; haven-break costs return not safety — maxDD stays −23.1% even with GLD/TLT→cash). Report: `ALLOCATOR_HARDENING_20260622.md`.
- TQQQ sleeve params: NOT over-tuned (SMA-200 + vol-20 both robust; 25% target is a pure risk dial; WF re-tuning *underperforms* static-live). Report: `TQQQ_SLEEVE_HARDENING_20260622.md`.

---

## 2. The 3 PARKED optional config nudges (discovered in hardening; NOT applied)

Each was found by stress-testing the live params. None is applied to live config — they're cost/benefit decisions for the go-live moment. **Default recommendation for all three: keep live config as-is unless the stated trade-off is explicitly wanted.**

| # | Option | What it does | Cost / caveat | My recommendation |
|---|---|---|---|---|
| 1 | **Allocator lookback 63→84/126d** | +~0.02 full Sharpe; walk-forward mildly prefers 126d | ~Nil (same risk profile); it's noise on a flat plateau | **Leave at 63d.** 0.02 Sharpe is within plateau noise; main concurred "leave it." Only revisit if reopening the allocator for other reasons at go-live. |
| 2 | **Sleeve trend-gate 200→175d** | +64pp OOS return, better OOS Sharpe (0.918 vs 0.855), shallower DD; a *true* plateau (neighbor floor ≥ live) | Survivorship risk — it's one 2010–2026 path; walk-forward evidence says 200d is the more out-of-distribution-robust textbook default | **Keep 200d live; bank 175 as an optional nudge.** The measured edge is real but the WF tell argues against chasing it. A reasonable "if Cyrus wants a touch more aggression at go-live" lever. |
| 3 | **NFCI macro tail-hedge overlay** | Cuts the allocator's worst drawdowns (2022: −19.6%→−6.1%DD, ~+13pp; lifts OOS Sharpe to ~1.23) | Costs ~18pp OOS return at realistic execution lag (return parity is lag-fragile); benefit concentrates in just 2 stress episodes (2020, 2022); does NOT fire earlier than SMA-200 in 2018-Q4 | **Do NOT apply for a raw-return mandate.** It's a *drawdown hedge that costs return*, not a return improver. Apply ONLY if tail-protection becomes the explicit priority over raw return at go-live. Report: `MACRO_REGIME_VERDICT_20260622.md`. |

**Reading of the three together:** options 1 and 2 are "free-ish raw-return upgrades" (1 is noise, 2 is a real-but-survivorship-flavored nudge); option 3 is a different axis entirely (give up return to buy drawdown insurance). Under the current mission bar (**beat SPX on RAW RETURN**), none is a clear must-apply: 1 is noise, 2 is optional aggression, 3 actively costs return. The honest default is **ship the validated live config unchanged** and treat all three as levers available at the go-live conversation.

---

## 3. Hard gates that STILL must be cleared before real money (NOT suspended)

The research-side promotion gates are suspended under the current explore-first mission, BUT the real-money go-live rails are NOT. Per MEMORY/GATE:

- [ ] **Cyrus's explicit per-request approval** — real-money go-live is his call, not a standing approval, not main's to greenlight.
- [ ] **≥4 weeks of paper track** + **100+ round-trips** + **realized paper Sharpe > 1** + **realized maxDD < 20%** + **OOS confirmation** (GATE graduation criteria).
- [ ] **Live cost ≤ 2× modeled** (the 2bps assumption holds in real fills) — verify against actual paper fills before trusting backtested net numbers.
- [ ] **Paper-clock data sufficiency** — allocator_paper.db + tournament.db need ~20–40 trading days of fills before P&L is even readable (first real checkpoint: Saturday leaderboard).
- [ ] Physical rails intact at go-live: paper→live broker-URL flip, killswitch (`STOP_TRADING`) honored, risk caps in the runner (not strategy code).

**Bottom line:** the engine is validated and hardened, but the *track record* gate (4wk / 100+ trips / realized Sharpe>1) is the binding constraint right now — and it can only be satisfied by letting the live paper fills accumulate. **No amount of additional backtesting substitutes for the paper clock running.**

---

## 4. What this means for "what to do next"

The validated-and-hardened state is a natural pause point. The highest-value next thing is **not** another research lane — it's **letting the paper fills breathe** until there's real out-of-sample paper data to read (Saturday is the first checkpoint). The two obvious "new lane" candidates are both substantially closed in prior work (see §5), so re-running them without a genuinely new angle would burn effort to reconfirm a known negative.

---

## 5. Why the "obvious" next research lanes are already closed (don't re-derive)

- **Single-stock price-based cross-sectional momentum** → CLOSED (memory, 2026-06-01/02): all variants cost-strangled or overfit; "the signal class is the problem." Re-running vanilla price-momentum xsec at $1000 notional just re-derives this. Would need a genuinely *new* signal axis (not price) to be worth opening.
- **Earnings/event-driven (PEAD)** → CLOSED (memory, 2026-06-13): best OOS 0.657, fails the 0.7 gate; unfillable in microcaps, beta-hedged loses the edge. DB `earnings.db` retained.
- **A genuinely new lane would need:** an orthogonal, non-price, free-data signal class not yet tried — e.g. a cross-asset *carry/term-structure* angle, or a *breadth/dispersion* regime signal — and even then, the bar is now "beat the allocator," which is hard (4 signal classes examined, none cleared it). Worth doing only with a specific mechanism hypothesis, not a generic sweep.

---

*Compiled by Tessera. Update this file whenever a parked nudge is applied, a gate is cleared, or the go-live decision is made.*
