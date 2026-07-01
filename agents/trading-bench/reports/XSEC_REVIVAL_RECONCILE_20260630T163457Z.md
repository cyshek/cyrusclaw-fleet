# Single-Stock XSEC Revival — Reconciliation + Free PIT-Membership Spine

**Run:** 20260630T163457Z · **Agent:** trading-bench · **Assignment:** main-cron P1 "Single-stock cross-sectional universe revival (Jegadeesh-Titman momentum + AHXZ low-vol on S&P 500)" · **Model:** opus
**Mode:** read-only recon + free-data infra build. No crontab, no live orders, no paid signups. All 6 protected md5s unchanged. Suite 882 passed/3 skip (+10 new).

---

## TL;DR (the honest verdict)

**I did NOT spawn the J-T-momentum / AHXZ-low-vol backtest subagents as literally specified, because my own closed-lane ledger + a dedicated scout already prove that exact run is a known dead end on our free data — and running it would manufacture a survivorship-beta mirage, not an edge.** Instead I (a) reconciled the assignment against the evidence, (b) built + tested the one piece that genuinely advances the lane at $0 (the PIT membership spine), and (c) surface the single real unblock: a ~$20/mo delisted-price feed, which is Cyrus's call.

This is the "decide and execute, come back with answers not questions, don't fake a winner" path — the assignment quoted a **stale backlog note (dated 2026-05-31)** that a later finding (2026-06-23) superseded.

---

## Why the literal assignment is a known dead end

The assignment cites BACKLOG line 111 (2026-05-31): *"at $1000, ~$100/name baskets are runnable — this is where Jegadeesh-Titman momentum, AHXZ low-vol actually live."* That note predates the binding-constraint discovery.

**1. Both anomalies are already CLOSED as survivorship mirages (2026-06-23).**
- AHXZ low-vol ≡ **BAB** → `reports/BAB_KILLTEST_20260623T191225Z.md`: OOS Sharpe −0.245, survivorship mirage #2.
- Jegadeesh-Titman ≡ **XSEC momentum** → `reports/XSEC_MOMENTUM_20260623T203942Z.md` + sector-neutral variant: EW-of-same-universe control beats it, survivorship mirage #3. (Also rejected in Wave-3, 2026-05-30, at the smaller notional.)
- Same day, PIT-value (mirage #1) and PEAD (mirage #4) closed on the identical root cause.

**2. The binding constraint is the UNIVERSE, not capital.** MEMORY.md standing rule (mandatory): *"every constituent-ranking signal on our fixed modern-survivor universe is killed by EW-same-universe control. Next genuinely-new lane must bring a survivorship-clean universe OR be path-dependent/allocator/regime."* The $1000 bump changes basket *affordability* ($100/name vs $10/name noise) — it does **nothing** to the survivorship problem, which is orthogonal to capital.

**3. A $0 PoC is self-deceiving (the scout's word).** `reports/SURVIVORSHIP_UNIVERSE_SCOUT_20260623T213215Z.md` checked every free source from this box: Yahoo **purges delisted tickers**, and no free feed serves delisting-adjusted prices for dead names. So a momentum/low-vol backtest on free data silently drops every name that went to zero = the exact survivorship bias we're trying to kill. Running it would likely show a long-only "beat" that is **pure survivorship beta** (negative L/S spread), and risk a false PASS.

**Spawning 3-4 subagents to re-run this on free data would burn cycles rediscovering a 2026-06-23 negative.** SOUL.md: "skeptical of your own outputs… don't fake a winner."

---

## What actually unblocks it (the one real decision → Cyrus)

Per the scout, the cheapest *honest* fix is **one paid EOD feed with delisted prices**:
- **EODHD "All-In-One" $19.99/mo** (delisted EOD + adjusted_close, 30+yr, API-native, **verified reachable from this datacenter IP** — DEMO key returned full AAPL history). Cancel anytime. Downside: $20 + ~2 eng-days.
- Sharadar (Nasdaq Data Link SEP+SF1, ~$100/mo combined) is cleaner-shaped but pricier; CRSP is gold-standard but institution-gated (no individual tier); Norgate is Windows-only (infeasible on this Linux box).

**This is a paid-data sign-off = explicit Cyrus call** (my hard constraint: "Paid = explicit Cyrus sign-off"). It is NOT a reversible decision I make autonomously. One feed resurrects **all four** closed lanes (momentum, low-vol/BAB, PIT-value, PEAD) at once — the scout calls it "the highest-leverage ~$20–100/mo we could spend on this project."

---

## What I built at $0 (so the spend is pre-de-risked)

To not come back empty-handed — and because nothing on disk did this yet — I built + validated the **free membership half** of the survivorship-clean universe:

**`runner/sp500_pit_membership.py`** (new, non-protected) — reconstructs point-in-time S&P 500 membership by replaying Wikipedia's dated add/remove change-log backward from today's snapshot.
- `build_membership_table(current, changes)` — pure transform (no network).
- `members_asof(table, date)` — PIT set on any date; backward-undoes changes dated after `as_of`. Convention: a change dated D takes effect at the OPEN of D.
- `_parse_change_date` — handles "January 10, 2024" and ISO.
- `load_live_membership_table()` — live Wikipedia fetch + scrape.

**`tests/test_sp500_pit_membership.py`** (new, 10 tests, tests-first) — pins parse + as-of semantics against a synthetic change-log (no network): added-name appears on/after its date, reversed the day before, multi-step backward walk, far-past reverses all adds while preserving only-later-removed names, today==current. **All 10 green.**

**Live smoke** (`reports/_sp500_pit_live_smoke.py`, not in unit suite) against real Wikipedia:
```
current constituents scraped: 516
dated change rows parsed:     402   (span 1976-07-01 -> 2026-06-30)
members_asof 2010-06-30: 514 | 2015: 509 | 2018: 509 | 2020: 511 | 2022: 510 | 2024: 513
today == current snapshot: OK    AAPL in index 2015-06-30: True
```
Reconstruction stays near ~500 at every point (correct for a 500-member index) and round-trips to today.

### Honest caveats on the spine (not buried)
- **This is NECESSARY-BUT-NOT-SUFFICIENT.** It tells you *who* was in the index on date D; it does **not** price the names that later died. Running a cross-sec anomaly on this membership + Yahoo prices alone STILL reintroduces survivorship bias (dead names vanish) — do not do that. The spine only becomes a survivorship-clean universe once joined to a delisted-price feed.
- Scrape is approximate: current=516 (a few extra linked symbols from secondary tables vs the true ~503) and 402 parsed change-rows vs 681 raw date-strings on the page (row parser is stricter). Good enough to prove the mechanism; would be tightened (exact symbol-column scoping) when the lane goes live. Neither affects the verdict.

---

## Recommendation to main / Cyrus

1. **Hold the J-T / low-vol backtests** until a delisted-price feed exists — running them now on free data is a known survivorship mirage, not a Bar-A test.
2. **Decision for Cyrus:** approve **EODHD $19.99/mo** (one month, cancel anytime). On approval I wire `runner/eodhd_cache.py` (mirrors `cboe_cache.py`), join it to this membership spine → `build_pit_universe.py` emitting `(date, ticker, in_universe, mktcap_rank, delist_date, delist_return)`, then re-run momentum + low-vol with **dead names scored to their delisting return** and the **mandatory L/S-spread + EW-same-universe controls**. That's the first honest PoC. ~2 eng-days after the feed lands.
3. If Cyrus declines the spend: this lane stays closed (correctly), and the membership spine is on the shelf for whenever a feed is approved for any of the four lanes.

**Files:** `runner/sp500_pit_membership.py`, `tests/test_sp500_pit_membership.py`, `reports/_sp500_pit_live_smoke.py`, `reports/_wiki_sp500_probe.py`. Protected md5s unchanged; no crontab/live touches.
