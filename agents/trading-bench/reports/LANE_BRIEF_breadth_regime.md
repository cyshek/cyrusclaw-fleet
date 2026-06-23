# LANE BRIEF (ready-to-run, NOT yet spawned) — Breadth-Divergence Regime Signal on the Allocator

**Drafted:** 2026-06-22. **Status:** framed + data-gated, parked pending go/no-go. **Bar set by main:** crisp falsifiable mechanism first, prototype only if it's that clean.

---

## The mechanism hypothesis (falsifiable, non-price-momentum, orthogonal to all closed lanes)

**Claim:** Equity-market *breadth* — the fraction of a universe trading above its own 200-day SMA — captures **internal deterioration before it shows up in the cap-weighted index price or in realized vol.** A cap-weighted index (SPX/QQQ) can keep rising on a handful of mega-caps while the median stock is already rolling over; that internal divergence has historically preceded index drawdowns. Mechanism: distribution/topping shows up in the *cross-section* (fewer names participating) earlier than in the *index level* (still held up by leaders) or in *index realized vol* (still low because leaders are calm).

**Why it's genuinely new here:** every signal class the bench has examined is trend/vol/price-derived (TQQQ trend, sector momentum, VIX-term, NFCI macro) or earnings (PEAD, closed). Breadth is a **market-internals** signal — a distinct class, not price-momentum, not a macro overlay. It is the one un-examined axis main flagged.

**Falsifiable prediction (the test that decides it):** When breadth diverges *bearishly* from the index (index flat/up while % > 200d-SMA falls below a threshold), forward allocator drawdowns are larger than baseline, AND a breadth-gated de-risk overlay cuts those drawdowns **AND** preserves raw return net of cost + 1-day lag. If breadth de-risking only fires *coincident with* (not before) the SMA-200 gate, the hypothesis is FALSE — it's redundant, like VIX-term.

**The specific trap to test against (pre-registered):** This must beat the LIVE allocator (OOS Sharpe 1.142, ret +276%), not SPX. The allocator already has SMA-200 + inverse-vol regime capture. The decisive question — identical to what killed VIX-term and downgraded NFCI — is **does breadth fire EARLIER than the price gate?** Episode test: in 2018-Q4 and 2022, does breadth deteriorate *before* QQQ breaks its 200d SMA? If timing is coincident → CLOSE-REDUNDANT. If breadth leads by weeks → potential real edge.

---

## Data path (survivorship-clean, free — gated FIRST)

Breadth needs a universe. Survivorship bias is the killer (computing breadth over *today's* survivors back to 2010 overstates historical breadth). Two free, survivorship-clean options from this VM's working Yahoo v8 path:

1. **Sector-ETF breadth (immediate, coarse):** % of the 11 SPDR sector ETFs (XLK/XLF/XLE/XLV/XLI/XLY/XLP/XLU/XLB/XLRE/XLC) above their own 200d SMA. Survivorship-clean (ETFs don't drop out), computable today, spans 2010+ (XLRE from 2015, XLC from 2018 — handle the ramp). Coarse (11 names) but a legitimate breadth proxy. **Start here.**
2. **Fixed mega-cap universe breadth (escalation, finer):** a frozen list of ~40–60 large-caps that existed in 2010 (AAPL/MSFT/JNJ/XOM/JPM/PG/KO/...), % above 200d-SMA. Still mildly survivorship-flavored (picks 2010-survivors) but far better than today's-constituents; finer-grained. Escalate to this ONLY if the sector-ETF proxy shows life.
3. PIT S&P 500 constituents (the gold standard) is NOT trivially free — do NOT block on it. If both proxies are dead, the lane closes; if one shows life, that's enough to justify the cost of sourcing real constituents later.

**Breakeven-bps gate (bench law, apply FIRST):** breadth flips slowly (it's a 200d-SMA-of-a-universe), so turnover should be LOW — this is favorable (unlike overnight-drift which died on turnover). Still compute the de-risk switch count + breakeven cost before believing any net number.

---

## Why this is PARKED, not spawned (the honest EV call)

Main's lean was "wait for Saturday," and I agree the binding constraint is the **paper-clock gate** (4wk/100+trips/realized-Sharpe), which no backtest clears. The breadth lane is crisply framed (clears main's bar to exist) BUT its honest prior is LOW expected value: it would modulate the *same allocator* that already has SMA-200 + inverse-vol, so the base-rate outcome is CLOSE-REDUNDANT or TAIL-HEDGE-ONLY (the fate of the last two overlays). Spawning it now = likely opus-token spend to reconfirm a redundancy.

**Decision:** brief is ready; go/no-go is a one-word call. Run it only if (a) main wants it run despite the redundancy prior, or (b) idle time with nothing higher-value persists and a disciplined negative is still worth banking. Otherwise the highest-value action is to let the paper fills accumulate to Saturday's checkpoint.

---

## If spawned — the deliverables (same discipline as macro lane)

- `strategies_candidates/breadth_regime_allocator/breadth_overlay.py` — sector-ETF-breadth (+ optional fixed-mega-cap) computed survivorship-clean, applied as a de-risk overlay on the validated blend (reuse `_allocator_blend_tests.py`); reproduce the baseline anchor first.
- `reports/BREADTH_REGIME_VERDICT_<date>.md` — hypothesis, breadth construction + exact lag, overlay-vs-live-blend table (IS+OOS, net@2bps), the **2018-Q4/2022 lead-vs-coincident episode test** (the decisive one), 1-day-lag robustness, threshold neighbors, switch count, VERDICT (CLEARS-BAR / TAIL-HEDGE-ONLY / CLOSE-REDUNDANT).
- Protected files off-limits; flag-don't-apply any actionable result; verify-don't-trust on return.
