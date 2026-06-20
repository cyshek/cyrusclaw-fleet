> ⚠️ **SUPERSEDED by [`ROADMAP-2026-06.md`](./ROADMAP-2026-06.md) (2026-06-04).** Most of this plan (all 3 fillers, discovery breadth, remix-GH recovery, Gmail tracker) has SHIPPED. Kept for history only — do not plan from this file.

# ROADMAP — Job-Search Pipeline Expansion (May 2026)

_Written 2026-05-13. Planning doc, not code. Read in 5 min and approve / edit._

## Where we are today

- **Discovery:** 9 adapters (`greenhouse`, `ashby`, `lever`, `workday`, `smartrecruiters`, `apple`, `google`, `meta`, `microsoft`). 949 roles in tracker.db across ~150 companies. ~67% are Apple (542) — heavy concentration.
- **Submit:** Greenhouse end-to-end works (`inline_submit.py` + `greenhouse_filler.py` + `greenhouse_dryrun.py`). 13 auto-submitted today. Daily target 10–15.
- **Open backlog (208 roles):** by ATS — Ashby 55, Greenhouse 41, LinkedIn 27, Apple 25, Workday 12, Lever 7, custom-careers ~30.
- **Big gaps:**
  - We index 67 Ashby roles but **can't auto-apply to any of them** (the highest-leverage AI labs: OpenAI, Cursor, Linear, Notion, Modal, Perplexity, Mistral, Cohere, Anthropic-via-some-roles).
  - Lever ~9 roles (Palantir, Spotify, Netflix) — same story, no filler.
  - Workday 71 roles — no filler, and Workday's the gateway to most F500.
  - Microsoft / Google / Meta / Amazon: scan-blocked (and Cyrus opted out of MSFT/Google/Meta/Amazon anyway, so this gap mostly doesn't matter — just Apple).

---

## Section 1 — Discovery expansion

### 1a. ATS adapter gaps (build new adapters)

| ATS | New companies (est.) | Effort (h) | Effort breakdown | ROI | Notes |
|---|---|---|---|---|---|
| **Ashby** | Already built ✅ — but **expand list**: ~30–50 more high-fit AI/dev-tool startups (Magic, World Labs, Poolside, Sakana, Reka, Tavus, Bland, Cresta-style, Decagon, Sierra-style + the next batch from YC/Forbes AI50) | 2 | All slug discovery via `bulk_discover_slugs.py`. No code change. | **HIGH** | Cheapest win. Run `bulk_discover_slugs.py` with a curated list of ~80 candidates this week. |
| **Lever** | Discord (no — they're GH), Reddit (no — GH), Plaid (no — Ashby), Brex (no — GH). Real Lever-only catches: **Palantir (have), Shield AI, Outreach, Front (now Ashby)**. Lever is on its way out. | 1 | Just add slugs. | **LOW** | Adapter exists; just add a few names. Don't over-invest. |
| **Workday** | F500 expansion: ~40 more tenants (Boeing, Lockheed-already-have, Northrop, Raytheon, Coca-Cola, P&G, Pfizer, Comcast, Verizon, T-Mobile, AT&T, Walmart, Target, Costco, Home Depot, Wells, BoA, Citi, etc.) | 4 | 1h candidate list, 2h tenant/site discovery (probe via `wd5.myworkdayjobs.com` patterns), 1h smoke test | **MED** | F500 PMs typically 5–10 YOE — most will fail YOE filter. Worth it for the 10–20% that do, and for SE/SA roles. |
| **iCIMS** | Major users: Cisco-some, ServiceNow-some, Verizon, Comcast, Best Buy, AT&T, Marriott. ~10–20 new companies. | 6 | 2h API recon (iCIMS exposes `careers-{tenant}.icims.com` w/ JSON `?in_iframe=1`), 3h adapter, 1h test | **LOW-MED** | Mostly enterprise / non-tech. Skip for now unless a specific company is target. |
| **SmartRecruiters** | HashiCorp, Bosch, Visa-some, Square-some. ~5–10 new. | 2 | Adapter exists ✅, just add slugs. | **LOW** | Already built. Just curate. |
| **Custom careers pages** | Coinbase, Hugging Face, Sourcegraph, Replicate, Groq, Confluent, Wealthfront, Canva, Citadel-Sec, Snap, EA, TikTok | per-co 4–8 | Each is a snowflake; needs HTML parse or browser-driven scrape | **LOW per-company** | Only do for top 3 most-wanted. **Coinbase + Hugging Face** are the only must-haves. |
| **LinkedIn job search** | Catch-all fallback for everything we miss | 8 | LinkedIn auth required (Cyrus's account); use existing browser session. Build query → result-page scraper. Then de-dupe against tracker. | **MED-HIGH** | Big upside but fragile (LinkedIn breaks scrapers regularly). Use as **discovery-only**, not apply. |
| **HN "Who's Hiring"** | Monthly thread on news.ycombinator.com, has ~500 posts/month, ~10–20% relevant | 4 | Fetch monthly thread + LLM tag (PM/SE/AI/US/YOE). Store as roles with source="hn". | **MED** | Surfaces stuff we'd never find. JD often has apply-email or one-off URL → can't auto-apply, just queue for manual. |
| **YC jobs board** (`workatastartup.com`) | ~2000 active YC postings, ~5% high-fit | 6 | Login required (Cyrus's YC account). Browser scrape + LLM-tag. | **MED-LOW** | YC startups often pay <market for Cyrus's level. Worth a one-shot crawl + then quarterly. |

**Recommended discovery work (ranked):**
1. ✨ **Bulk-add Ashby slugs** — 2h, ~30 new high-fit companies
2. ✨ **HN Who's Hiring monthly crawl** — 4h, surfaces hidden gems
3. **Workday F500 expansion** — 4h, builds breadth (gated by Workday filler being built first)
4. LinkedIn discovery scraper — 8h, but only worth it if we hit a wall on the above

### 1b. Scan-blocked companies (Apple, MSFT, Google, Meta)

| Company | Cyrus's interest | Open roles likely | Block | Recommended | Effort |
|---|---|---|---|---|---|
| **Apple** | YES | ~25–50 PM/TPM/SE at any time | Listing endpoint 404'd; current adapter scrapes search-page HTML + per-role JD fetch (works) | **Already working ✅** — just fragile. Add Playwright fallback if HTML fails. | 0–4h |
| Microsoft | NO (employer) | n/a | n/a | Skip permanently | 0 |
| Google | NO (Cyrus opted out) | n/a | n/a | Skip | 0 |
| Meta | NO (Cyrus opted out) | n/a | n/a | Skip | 0 |
| Amazon | NO (Cyrus opted out) | n/a (Twitch covered separately) | n/a | Skip | 0 |

**Verdict:** the "scan-blocked big tech" problem is actually just Apple, and Apple already works. **No browser-driven scrape work needed in 2026 Q2.** If Cyrus changes his mind on Google/Meta later, Playwright + stealth is the right tool (~12h per company).

---

## Section 2 — Auto-apply expansion (fillers)

| ATS | Companies unlocked (open roles) | Form complexity | Effort (h) | Pattern | Gotchas |
|---|---|---|---|---|---|
| **Ashby** ⭐ | OpenAI, Cursor, Linear, Notion, Modal, Perplexity, Mistral, Cohere, Anyscale, Plaid, Ramp, Retool, Vanta, Replit, Supabase, Snyk, Sentry, Glean, ElevenLabs, Harvey, Sierra, Deel, Crusoe, Cognition, Writer, Character.AI, Lambda, Baseten, Skydio (~67 open roles) | **Single-page**, GraphQL-backed. Form schema fully discoverable: `POST jobs.ashbyhq.com/api/non-user-graphql` query `applicationForm{...}` — confirmed 2026-05-13 returns `FormRender`. | **8–12h** | Same shape as `greenhouse_filler.py` + `greenhouse_dryrun.py`: write `ashby_dryrun.py` (GraphQL query → JSON spec) + `ashby_filler.py` (drives browser). | (1) GraphQL schema introspection needed once to enumerate field types. (2) Ashby uses custom React form components — likely need same `setNative` + dispatch trick. (3) Resume upload likely direct `<input type=file>`, simpler than Filestack. (4) Some Ashby boards have private posting APIs (Hippocratic AI, EvenUp, Ironclad) — those return 404 and need browser scrape instead. |
| **Lever** ⭐ | Palantir, Spotify, Netflix, Shield AI, Outreach (~9 open roles, more if we expand) | **Single-page server-rendered HTML.** Form fields have stable `name` attributes (`name`, `email`, `phone`, `urls[LinkedIn]`, `cards[uuid][field0]`, `resume` file input). Confirmed via Palantir 2026-05-13. | **6–8h** | Simpler than Greenhouse. Write `lever_dryrun.py` (parse `/apply` HTML → field list) + `lever_filler.py` (mostly native form fills, no React). | (1) Card-based custom questions use `cards[uuid][fieldN]` naming — stable per posting but unique per question. (2) Location autocomplete is a Google Places widget. (3) Honeypot field `_t` exists — leave blank. |
| **Workday** | 71 open roles across ~30 F500 tenants | **Multi-page** (4–6 steps: My Info, My Experience, Application Questions, Voluntary Disclosures, Self-ID, Review). **Auth required** — must create + persist account per tenant. Profile import from PDF reduces work. | **20–30h** | Same shape but bigger: `workday_dryrun.py` + `workday_filler.py` + `workday_session_manager.py` (handles login, password reset, MFA detection). | (1) Each tenant is its own account; need credential vault keyed on `host`. (2) Workday session cookies expire; need re-auth flow. (3) "Quick Apply" with resume parsing helps but never gets demographics right. (4) Forms vary per tenant config — generic step labels but custom Q's. (5) MFA: many tenants use email codes — wire up gmail_imap. |
| **iCIMS** | ~10 enterprise tenants if we add them | Single-page, mostly. Auth often required. | 12h | Standard pattern. | iCIMS uses captchas more aggressively. May need vision-LLM solve or skip captcha-required tenants. |
| **SmartRecruiters** | HashiCorp + ~5 others | Single-page, public API exists. | 6h | Standard. | Public API even has POST /candidate endpoint — could submit purely API-side, no browser. **Highest-automation potential** but small surface area. |
| **Generic LLM-driven fallback** | Every one-off ATS we'll never write a dedicated filler for | Variable | **20–30h to build, then 0 per ATS** | Vision model + DOM dump → "for each visible field, what value from personal-info.json fits?" → emit step list → run through existing browser tool. | (1) Slow (~5 LLM calls per form). (2) Bigger error surface. (3) Best for ATSes we'll see <5 times (Phenom, Workable, custom). (4) Replaces per-ATS fillers eventually but not immediately — start by building it as a **fallback** that triggers on unrecognized URLs. |

**Recommended filler work (ranked by ROI):**
1. ⭐⭐⭐ **Ashby filler** — 8–12h, unlocks 67+ open roles at the highest-fit companies (OpenAI, Cursor, Linear, Modal, Perplexity, Mistral, Cohere). **This is the single highest-value piece of work in the next 3 months.**
2. ⭐⭐ **Lever filler** — 6–8h, smaller surface but Palantir alone is worth it
3. ⭐ **Workday filler** — 20–30h, gates 71+ roles but high effort; wait until #1 and #2 are done
4. **Generic LLM filler** — 20–30h, longer-term play; build after Ashby + Lever to handle the long tail

---

## Section 3 — Cross-cutting infrastructure

| Feature | Effort | Impact | Priority |
|---|---|---|---|
| **Application response tracker (Gmail IMAP)** | 12h | Closes the loop. Auto-tag tracker.db rows as `responded`/`rejected`/`next-round`. Massively improves Cyrus's signal on what's actually working. | ⭐⭐⭐ HIGH |
| **Resume A/B tracking** | 4h | Each `applications/submitted/<slug>/` already has tailored resume — add a `variant_hash` column, correlate with response rates. Useful only after we have ≥50 responses. | MED (later) |
| **Daily metrics dashboard** | 4h | Generate `daily-metrics.md` per cron run: submitted today, in queue, by ATS, response rate. Send to Discord. | MED |
| **Recruiter outreach drafter** | 16h | Extract recruiter name from JD / LinkedIn → draft cold message → optional auto-send via LinkedIn (risky, manual-approve) | LOW (defer 6mo) |
| **LLM-driven form fill** | see Section 2 (generic fallback) | High but heavy | already covered |
| **Submit-side reliability hardening** | 6h | The current Greenhouse pipeline has 0 systematic retry. Add per-step retry + structured error bucketing. | MED |
| **Tracker schema migration: per-source `external_id`** | 2h | Currently we infer ATS from URL; explicit column makes everything else easier. | HIGH (do it before fillers) |

---

## Section 4 — Recommended sequencing (3 months)

**Optimization target:** maximize quality applications submitted per week, with reasonable build effort. Don't build what we won't use.

### Week 1–2 (now → 2026-05-27): "Unlock Ashby"
- ✅ Continue Greenhouse drain (cron, autonomous)
- 🛠 **Add `external_id` + `ats_kind` columns to tracker.db** (2h) — clean foundation
- 🛠 **Build `ashby_dryrun.py` + `ashby_filler.py`** (10h) — highest-ROI single piece of work
- 🛠 Bulk-add ~30 Ashby slugs to companies.yaml + run discovery (2h)

**End of week 2 expectation:** Auto-applying to OpenAI, Cursor, Linear, Modal, Perplexity, Mistral, Cohere, ~10 more. Submission volume jumps from ~13/day to ~25/day with no loss in quality.

### Week 3–4 (2026-05-27 → 2026-06-10): "Close the loop"
- 🛠 **Gmail IMAP response tracker** (12h) — without this we're flying blind on what's working
- 🛠 **Lever filler** (8h) — Palantir + Shield AI + a few others
- 🛠 Daily metrics → Discord (4h)

**End of month 1 expectation:** ~30–35 apps/day going out. Response visibility. Lever covered.

### Month 2 (2026-06-10 → 2026-07-10): "Workday + breadth"
- 🛠 **Workday filler** (25h, multi-page, auth) — slowest piece but unlocks 71+ roles and counting
- 🛠 Workday F500 tenant expansion (4h)
- 🛠 HN Who's Hiring monthly crawl (4h)
- 🛠 Submit-side retry/error hardening (6h)

**End of month 2:** Workday auto-apply working on ≥3 tenants. Total daily volume 40–50.

### Month 3 (2026-07-10 → 2026-08-10): "Long tail + intelligence"
- 🛠 **Generic LLM filler** (25h) — handles the long tail (Coinbase, Hugging Face, custom careers pages)
- 🛠 Resume A/B variant tracking (4h, by now we have data)
- 🛠 LinkedIn discovery scraper (8h, only if existing pipeline is full)
- 📊 First quarterly retro: which companies actually responded? Re-rank companies.yaml.

**End of month 3:** Pipeline covers 90%+ of relevant US AI/infra/dev-tools roles for Cyrus's profile. Daily volume 50+. Response data drives next quarter's priorities.

---

## Anti-roadmap (things explicitly NOT to build)

- ❌ Custom adapter / filler for any single company that's not in Cyrus's top-30 most-wanted (use generic LLM filler instead, eventually)
- ❌ Browser-driven scrape for Microsoft/Google/Meta/Amazon (Cyrus opted out)
- ❌ Recruiter cold outreach automation (low ROI, high reputational risk — defer ≥6mo)
- ❌ Captcha-solving infrastructure (current decline rate is acceptable; skip captcha'd tenants)
- ❌ Re-architecting the inline submit pipeline — it works, leave it alone
- ❌ Slack/X/Twitter notification posting — Discord is the channel, keep it there

---

## Open questions for Cyrus

1. **Confirm AI-disclosure stance for Ashby applications** — same as Greenhouse (always "No")? Likely yes, but worth a sanity check.
2. **Workday: are you OK with creating accounts at ~30 F500 tenants** under your real email? Each one will spam you with "your application is being reviewed" emails.
3. **HN Who's Hiring**: the "apply by emailing X" pattern — should I draft cold-application emails for these (manual-approve queue) or just surface them to your tracker as `requires_manual` and let you handle?
4. **Lever's Palantir form has card-based custom questions** like "Which Palantir products excite you?" — these need answer-generation per-role. OK to use the same `cover_answer_generator.py` pattern (LLM-drafted, no AI disclosure)?
