# PEER_STATE.md

_Auto-generated digest of peer agents' latest daily memory + current BACKLOG.md._
_Generated: 2026-06-23 11:00 UTC_

---

## job-search

### Latest daily memory: `memory/2026-06-23.md`


## Management retry resolved — pipeline fix already completed
- Received delayed/stale 3pm management-check retry asking to fix prep-only `daily_apply.sh` after PID 299204 and run batch-200.
- Verified fix already landed: commit `9e284f0` wires `drain_prep_ready.py` into daily_apply.sh; commit `cab1c3a` adds killpg timeout for re-prep hangs.
- Verified drain log final: 51 submitted from 209 processed; XLSX rendered Open=540 Applied=818; DB `applied_by=auto` on 2026-06-22 = 51; total submitted=160.

## 02:10 UTC - Batch apply run (main directive)

**Trigger:** main agent directed "run batch apply, 200 rows, daily_apply.sh fix is live"

**What happened:**
- Found 263 PREP-READY packets on disk (208 stale/no-plan, 55 with valid plans)
- Ran drain_prep_ready.py in 2 passes
- Also ran parallel inline_submit prep (Ashby 154 roles + GH 101 roles) to generate new packets

**Results:**
- Pass 1 drain: 30 submitted, 23 failed (Ashby RECAPTCHA spam-flag datacenter IP)
- Pass 2 drain (GH only): 7 submitted (Anduril, Anthropic, Discord, Figma×3, IMC Trading)
- **Total submitted today: 33** (confirmed in DB, applied_by=auto)
- Pass 1 killed by SIGKILL at 197/263 (OOM likely)

**Submitted companies today (33 total):**
Alpaca, Anduril (2), Anthropic, Avoca, Bland AI, Decagon, Discord, Edia, ElevenLabs, Firecrawl, Figma (4), Fluidstack (2), Front, Granted, Handshake, Illumio, IMC Trading, Juicebox, Kikoff, Kodiak Robotics (2), Level, Modus, Momentus, OpenAI (IT Solutions), Piramidal, Scopely, Scout

**Tracker state:** 845 applied total, 529 open queue, 328 manual-apply

**Failure breakdown (36 total pass 1):**
- 23× Ashby RECAPTCHA_SCORE_BELOW_THRESHOLD (need residential proxy)
- 2× GH submit-clicked-no-confirmation (chime, courier-health)
- Rest: stale already-applied packets

**Ongoing:**
- drain3 loop running (every 10 min, GH only) — will catch new packets as prep processes finish
- Ashby prep process (154 roles) still running in background — generating more packets
- GH prep process (101 roles) still running in background

**New blockers discovered:**
- Ashby: Agave, Anyscale, Antithesis, Baseten, Bedrock Robotics, Bobyard, Cantina Labs, CharacterAI, Clera (x2), ElevenLabs-new, Fluidstack (3/4), H-Company, Hadrian → all RECAPTCHA residential needed
- Chime GH: uncertain status (re-check needed)
- Courier Health GH: uncertain status

## 02:25 — Residential drain complete (neat-nexus session)

Residential Ashby drain finished. 18 slugs attempted, 8 confirmed submitted (6 net-new to DB — Profound and Roboflow were already booked from Jun-21 session):

**Submitted via residential:**
- AirOps / PM, New Verticals ✅
- Antithesis / Forward Deployed Engineer ✅
- ElevenLabs / Talent Operations - Program Manager ✅
- Fluidstack / PM, Data Centers and Tooling ✅
- Handshake / Program Manager ✅
- Latent / Product Manager ✅
- Profound / FDE ✅ (was already booked Jun-21)
- Roboflow / FDE ✅ (was already booked Jun-21)

**Failed residential (RECAPTCHA_SCORE_BELOW_THRESHOLD — HARD cohort):**
- Bobyard ❌ (spam-flag, HARD)
- Cantina Labs ❌ (form validation: missing Country field — fixable bug)
- CharacterAI ❌ (HARD)
- Fluidstack-8fd64 / Logistics Systems PM ❌ (HARD, same org as successful one)
- Fluidstack-d6cb8 / PM Networking ❌ (HARD)
- H-Company ❌ (HARD)
- Hadrian ❌ (HARD)
- Plaud ❌ (HARD)
- Scaled Cognition ❌ (HARD)

**New insight:** Within same org (Fluidstack), some roles score above threshold, some don't. Score is per-session/IP timing, not per-tenant. 

**Actionable fix for Cantina Labs:** Country field not being set in location typeahead — plan needs to use "United States" not "United States Minor Outlying Islands". Need to fix `_ashby_runner.py` location picker country selection.

## Final session totals
- **39 submitted today** (33 GH/datacenter Ashby + 6 residential Ashby)
- **851 total applied** | **501 open queue** | **328 manual-apply**
- XLSX re-rendered
- Prep processes still running: Ashby (~154 remaining) and GH (~101 remaining)
- drain3 (young-ocean) still looping on GH queue

## 02:50 — Session 2 (inter-session cron trigger)

Continued from previous work. State at session start: 39 submitted today, 851 total applied, 22 PREP-READY packets staged.

_…(truncated; 465 total lines in source)_

### BACKLOG.md

# BACKLOG.md — job-search agent (workspace root)

**Last triaged:** 2026-06-23

## Tracker state (as of 2026-06-23 ~07:25 UTC)
- **Submitted: 236 total** | Applied: 646 | Open: 468 auto-submittable | Manual Apply: 266 | Blocked: 44
- **Today: 102 submitted** (biggest single-day count)
- companies.yaml: **1,528+ total**; Workday entries 72+
- XLSX: 4 sheets (Open → Applied → Manual Apply → Interviews)

## Schedule (crons)
- **Mon + Thu 7am PDT** — `weekly_run.sh` (full crawl ~1,336 companies + classify + auto-apply 200)
- **Tue-Sun 7am PDT** — `daily_crawl.sh` (top-tier 46-company delta + classify + discord ping)
- **12am PDT nightly** — `daily_apply.sh` (drain open queue up to 200 roles)

## 🔴 Blocked — need Cyrus action

- **Ashby HARD reCAPTCHA cohort** (Tavus 892, Moment 1213, Plaud, Decagon, Ramp, CharacterAI, H-Company, Hadrian, Scaled Cognition, Fluidstack-8fd64/d6cb8, Bobyard ~12 rows): residential proxy insufficient — need aged Google account + dedicated mobile IP. NOT auto-fixable.
- **Agave**: Seon bot-detection (different mechanism from reCAPTCHA — React hydration refused). NOT in reCAPTCHA-HARD cohort; separate blocker.
- **Lever hCaptcha** (Palantir 816-818 cluster, ~6 rows): nopecha API key or 2captcha workers needed. CapSolver does not support hCaptcha.
- **OpenAI 180d hold** (~23 rows, ~20 openai-applimit-180d): re-eligible late Aug/Sep 2026.
- **Deepgram** (6 rows): 60-day re-apply window, clears ~2026-07-30.
- **Google SSO** (~60 rows): Cyrus handles via Google account. VERDICT B unchanged.

## 🟡 Next engine targets

- **Workday "How Did You Hear" non-standard dropdown** (Cisco 2421 blocked). `pick_workday_source()` uses `input#source--source` — Cisco uses a different ID. Fix: detect source/referral dropdown by label-text fallback, try LinkedIn/Job Board/Other.
- **~11 Netflix Eightfold rows** flagged `applied` on 2026-06-14 but may never have been submitted (no prep_path; agent_notes say deferred). Now that `_eightfold_runner.py` self-ID checkbox is fixed, these are genuinely submittable — run a fresh batch.
- **Workday PREP-READY-MANUAL remaining** (Nordstrom 1456 already applied, Intel/Nvidia/Adobe 2026-06-20 done): any new Workday rows that land in manual_ready should be retried via `_workday_runner.py --url --tenant --resume` standalone.
- **iCIMS OTP runner** (built 2026-06-20, commit b5c1116): RealPage 2479 is the first live target. Re-probe to confirm OTP path before batch attempt.

## ✅ Recently shipped (2026-06-23, **102 submitted**)
- **Biggest single-day submit count**: 102 roles (auto + residential)
- Engine commits: `1acc9ab` (current_location_city resolver → NYC/LA/Chicago = No), `b5e4b89` (comp_seeking → $160k-200k), `5772826` (Ashby standalone Country combobox), `4ea271a` (SEL_PICK scopedMenu scope fix), `b2f3da6` (GH dryrun resolver fixes), stage_plans.py HARD_COHORT updated
- GH EMAIL-OTP DEBUNKED: `_gh_submit.py` already handles it via `gmail_imap.wait_for_verification_code()`. Proven: Labelbox 3401 submitted.
- GH Remix DEMO_SKIP_RE fixed: `identify.{0,10}as` pattern added → Chime unblocked
- GH Remix emptyRequired phantom blank-label filter: `real_empties` filter added
- Bedrock Robotics: cracked via residential on 2nd attempt (NOT hard cohort after all)
- Ashby passes 1–7 + GH passes 1–8 all completed; daily log has full per-pass details
- Lesson: datacenter Chrome = port 18800 (NOT 18900 = OpenClaw browser); residential = 19223
- Lesson: GH Remix end-date IDs vary (end-month--0 / end-year--0 text input on YipitData)
- Lesson: SEL_PICK global .select__menu grabs wrong control when multiple React-Selects present
- ⚠️ Nox Metals "Shift Supervisor" submitted — non-PM role; flag for Cyrus review

## ✅ Recently shipped (2026-06-22, major)

- **LinkedIn resolver**: 180 stranded rows → 57 resolved to real ATS (ashby 17/GH 17/lever 1 via brute probe; +22 via v2 brave-api). Root cause: `dynamic_ats_entry()` was dead code. Fixed commits 5f78846 + 7cf3b1f. 51 tests green.
- **Workday expansion**: companies.yaml Workday entries 40 → 72 (+32 verified live: Micron, CrowdStrike, Target, Comcast, T-Mobile, Warner Bros, Wells Fargo, Citi, Morgan Stanley, BlackRock, Nasdaq, PNC, Fiserv, FIS, Broadridge, Zendesk, Genesys, ServiceTitan, Hitachi, Pfizer, Gilead, Stryker, Abbott, Illumina, Amgen, KLA, Applied Materials, Marvell, Cadence, Autodesk, 3M). Commit b887556.
- **pick_batch bugs fixed** (3 root causes): YOE defaults wrong, stale aborted prep dirs blocking retries, 209 stale queued/ symlinks. pick_batch now works correctly.
- **DB reconciliation**: 77 phantom-applied rows backfilled, applied total corrected to 778.
- **Batch cap 200→500**: daily_apply.sh + weekly_run.sh drain full queue.
- **Workday pick_workday_source label-fallback** (Cisco 2421 unblocked).
- **no-adapter fix**: 4 new companies added (Confluent/Canva/Hugging Face/Wealthfront).
- **MAIN-AS-PROXY directive** active.

## ✅ Recently shipped (2026-06-20, major)
- YOE threshold 4→6 (commit dce5151); 267 rows recovered
- Staff/lead → ROLE_TYPE_BLOCKLIST with target-role carve-out (commit 350b494)
- FDE + SWE/ML/Data tracks fully UNBLOCKED; all role types open
- Discovery adapters: Remotive + RemoteOK (fb93bec), Himalayas (f0da363), SmartRecruiters + Workable + BambooHR (70a5710)
- YC Algolia batch-fetch: companies.yaml 1,011→1,336 (82e0b2f)
- High-comp sweep: Nuro, Motional, Wiz, Cerebras, Figure AI, Mistral AI added
- SWE/ML/data resume tracks added (commit 65ab3ea)
- Response tracker (Gmail IMAP → tracker.db): 78 interview requests found (commit 856c1e5)
- Brave stage-3a2 wired (commit 6c9bb92)
- Daily delta crawl cron Tue-Sun 14:00 UTC (commit 214a2b4)
- iCIMS runner built (commit b5c1116); dispatch wired into inline_submit.py
- Workday WE date re-verify belt-and-suspenders (commit 3659bd9)
- Eightfold self-ID checkbox fix: was the REAL Netflix blocker (not RESUMEWALL/residential)
- XLSX consolidated to 4 sheets: Open → Applied → Manual Apply → Interviews (commit b1f2dd3)
- 25 total submissions today: Anduril/Redwood/OneSchema/Skydio/Scopely/AppLovin/Securitize/Fireworks AI/Roblox/Netskope/Cresta/AiPrise/AirOps/Arini/Bobyard SE x2/Clera + Netflix 2853/2854/2860 + Adobe 2629/Nvidia 1935/Intel 2225 + Picogrid/Brellium/Thought Machine/Restate

---

## Doctrine (read FIRST every chain)

**ATTEMPT EVERY ROLE.** No cohort-level pre-skips. Manual queue is for ZERO-attempt rows only.

## Hygiene

- ONE browser-submit subagent at a time (shared OpenClaw browser instance — parallel workers clobber).
- `agent_notes` not `cyrus_notes` for agent-authored DB notes.
- `browser.upload` requires `ref=` or `element=`, never `selector=`. Check `files.length` after.
- Subprocess JSON output → parse with `json.loads`, not string slicing.
- Run `_backfill_drain_status.py` after EVERY residential drain.
- After any `applied_by='auto'`, run `render_xlsx.py` or sheet lags.

---

_Legacy backlog entries (pre-2026-06-20) archived in `memory/2026-06-08.md` and earlier daily logs._

Fully wired. 11+ Meta submissions already in `applications/submitted/meta-*/`. `companies.yaml` updated to "Meta Platforms" with brand aliases. Dispatch fully wired in `inline_submit.py`. Tracker inconsistencies for 2988/2995 fixed (applied_by=meta-runner).

Canonical backlog. Triage regularly. Move done items into `memory/YYYY-MM-DD.md` when they age out of "Recently shipped".

For deep design notes and adapter-level TODOs, see `projects/job-search/BACKLOG.md` (kept nested — too long for here).

---

## Role Discovery (added 2026-06-02, with Cyrus)

### 🅿️ [PARKED — do NOT work yet] Re-enable Google role discovery, recency-ordered (Cyrus via main, 2026-06-04) → ✅ DONE 2026-06-08
Partial reversal of the standing "Google opted-out" rule. **Resume discovering Google roles** under existing standing criteria (same YOE/role-type/geo filters), with ONE added requirement: in the sheet's **Google section, order most-recently-posted FIRST** (freshest at top). Rationale: Cyrus's resumes clear vendor/recruiter screens but stall at hiring-manager stage (ghosted / "pipeline full, can't schedule") — theory is fresher postings beat the pipeline fill-up.
- **✅ SHIPPED 2026-06-08** (subagent google_reenable, 22m25s, verified): Google removed from `COMPANY_BLOCKLIST` (MSFT/Amazon KEPT opted-out), historical Google rows un-skipped, recency sort (freshest-first) added to the Google sheet section. Recency re-verified 2026-06-08. No longer parked.
- MEMORY.md opt-out note updated 2026-06-04→2026-06-08 to reflect this (Google no longer a blanket opt-out; now re-enabled).

### ✅ 2026-06-03 — [DISCOVERY] li_company_slug_resolver SHIPPED: companies.yaml 828 → 967 (+139), +107 attemptable rows, +1 engine bug fixed
`li_company_slug_resolver.py` mines the 631 LinkedIn-source companies NOT yet in companies.yaml, probes them through the proven slug-resolver (staffing/megacap/aggregator/company-blocklist filtered) → **139 net-new employer boards merged** (76 gh / 50 ashby / 16 lever, ~11.5k open jobs). Crawled the new co's → **161 net-new tracker rows → 107 attemptable / 54 skip**. Notable: Verkada, FanDuel, Scopely, ClickHouse, Addepar, Samsara, Zoox, Lila Sciences. **BONUS: found + fixed an FDE-leak bug** — `decide_skip` only ran the FDE hard-block in the `jd_yoe is None` branch, so FDE roles with a sub-threshold parsed YOE leaked as keep (6 caught: Addepar/PubMatic/Actively AI/Charta Health/Console/Scaled Cognition). FDE check hoisted to unconditional Gate 0.5; regression test added; 6 rows flipped. Durable: every weekly crawl now hits 139 more real employers. Re-runnable as LinkedIn rows accrue.

**Current state — TWO discovery modes already running:**
- **Company-pinned crawl** — `run.py` iterates 381 yaml companies → their ATS board APIs (Greenhouse/Ashby/Workday/Lever). Deep coverage of known companies.
- **LinkedIn keyword-matrix adapter** — a companies.yaml entry (`adapter: linkedin`) crawls LinkedIn's guest jobs-search across a keyword × US-location matrix ("product manager", "TPM", "SE", etc.), surfacing NET-NEW companies by title. Actively running (476 new rows in June). This IS our breadth engine.

**Key correction (Cyrus, 2026-06-02):** most LinkedIn results are NOT Easy-Apply dead-ends. Of 132 open LinkedIn-URL rows, only ~8 are `linkedin-offsite-unresolved`; ~124 are tagged `manual-apply` = the LinkedIn Apply button routes to the COMPANY'S OWN SITE/ATS. So the bottleneck is **resolving the offsite link**, not an authwall. Across all 973 LinkedIn-source rows: only 85 resolved to a clean non-LinkedIn app_url, 888 still hold the LinkedIn URL → large untapped resolution pool.

**Options to ADD (priority order):**
1. **Keyword crawl on non-LinkedIn boards (P1, no infra)** — same keyword-matrix pattern against Wellfound/AngelList, YC Work-at-a-Startup, Indeed. Net-new companies, NOT IP-walled like LinkedIn. Best ROI. **✅ SHIPPED 2026-06-09 (`himalayas_discover.py` +13 tests, commit 6836eea/58a6649): Wellfound=DataDome-403 + YC-WaaS=login-walled from this IP, so pivoted to the open Himalayas jobs API (~105k jobs, no auth/captcha). Crawl→target-role keyword KEEP (live classifier)→US-filter→drop placeholder+staffing→dedup vs companies.yaml→verify a real GH/Ashby/Lever board exists→emit merge-ready YAML (`--apply`-gated). Live-validated (MEMX+Elation found on a 2920-job run). README: HIMALAYAS-DISCOVER-README.md. Reality: enterprise/iCIMS/Workday-skewed so ~5% verified-board hit-rate but REAL net-new; a complementary 3rd breadth source alongside yc_discover.**
2. **Improve LinkedIn offsite-link resolution (P1)** — 888 LinkedIn-source rows still hold the LinkedIn URL though most have a company-site Apply target. Better offsite-URL extraction (the `manual-apply` rows already point at company sites) converts discovered leads into submittable ATS links. Overlaps with proxy unblock for the authwalled subset. **✅ PARTIAL SHIPPED 2026-06-09 (`linkedin_db_crosslink_resolver.py` +14 tests, commit f30efb1): ZERO-HTTP tier — many stranded rows are for a company+role we ALREADY crawled directly from that company's ATS board (a separate non-LinkedIn row in the SAME tracker.db). Matches stranded↔direct by (norm_company,norm_title), resolves on an UNAMBIGUOUS single-URL match, rewrites app_url (preserves UNIQUE linkedin:<id> source_key), skips MS/Amazon. APPLIED: 79 rows resolved (stranded 851→772; 42 now auto-submittable: 22 Ashby/10 Lever/10 GH). Wired into weekly_run.sh as Step 3a0 (runs FIRST, before the HTTP resolvers — every crosslink is one fewer HTTP probe). The HTTP linkedin-fetch tactic stays dead anonymously (LINKEDIN-ATS-RESOLUTION-WALL.md); remaining ~772 need the careers/brute HTTP resolvers or the li_at authed path. P4 audit (P4-BLOCK-REASON-REDERIVE-REPORT.md) also found 8/20 `linkedin-stranded` blocked-row LABELS are stale/inaccurate + flagged a resolver "reject non-posting URL" guard candidate.**
3. **New ATS adapters (P2, build time)** — iCIMS, Eightfold (+ Oracle/Taleo, SuccessFactors, Phenom). Each opens that ATS's whole company universe, not one company.
4. **Enumerate Greenhouse/Ashby/Lever org directories (P2)** — programmatically discover org slugs posting US PM/TPM roles → auto-grow companies.yaml. Pure breadth, compounds every weekly crawl. **✅ li-resolve pass shipped 2026-06-03 (+139, see below).** ~~(Also fix the 25 `unknown`-ATS yaml entries.)~~ **CLOSED: the `adapter:None` entries are deliberate `skip:True` exclusions (proprietary/low-tier ATS like Confluent/Wealthfront, or VC firms a16z/Sequoia/BCG that don't hire our roles), NOT unresolved gaps. Premise was stale — don't re-chase.**

_…(truncated; 356 total lines in source)_

---

## openclaw-updates

### Latest daily memory: `memory/2026-06-23.md`

# 2026-06-23

- No activity today. Nightly distill cron fired; nothing to log or promote.

### BACKLOG.md

# BACKLOG.md — openclaw-updates

_Triage regularly. Move done items into the matching `memory/YYYY-MM-DD.md` once they age out._

Last reviewed: 2026-06-18

## Active

- **OCFR-001** (tracking, not building) — Runtime post-turn/session-end "memory-capture hook" so LOG-EVERY-INTERACTION is machine-guaranteed, not discipline-only. Filed 2026-06-08 per Cyrus via main. Full spec in `FEATURES.md`. Local-only until/unless escalated upstream.

## On hold (pending Cyrus)

- _(none — no open approval requests at the moment)_

## Pending (auto, no Cyrus action)

- **Harden kernel reboot flow** — recurring pattern: `unattended-upgrade` installs kernels outside our cron; reboot doesn't follow reliably. (Jun 16 install landed by Jun 19 via unknown path — possibly `unattended-reboot`, possibly manual.) TODO: add "reboot-required stale >24h" alert to `weekly-plugin-auth-check` and harden `weekly-system-updates` reboot step.

## Ideas

- Fill in `IDENTITY.md` next time it comes up organically (name/creature/vibe/emoji/avatar still placeholder).
- Consider a quarterly `du -sh` sweep of `~/.openclaw/sessions` if monthly hygiene starts flagging it.
- Maybe add a "security advisory" pre-check in the weekly cron — parse `apt-get upgrade -s` for `ubuntu-advantage` / USN markers and route those past Cyrus before auto-applying.

## Hygiene

- 2026-06-19: Confirmed kernel 6.17.0-1018-azure now running (reboot completed by Jun 19). No reboot-required flag. Quiet day.
- 2026-06-16: Ubuntu **24.04.4 LTS** (upgraded from 22.04); OpenClaw **2026.6.6**; kernel 6.8.0-1059-azure (running post-upgrade).
- 2026-06-07: apt fully current; openclaw 2026.5.22 (latest); no reboot required. Nothing pending.
- cloud-init 26.1 landed 2026-06-03 (see Recently shipped) — the old phased-rollout park is resolved.

## Recently shipped

- 2026-06-16 — **Ubuntu 22.04 → 24.04 upgrade** completed. VM now on 24.04.4 LTS (noble), kernel 6.8.0-1059-azure. OpenClaw bumped to **2026.6.6** in same window. Azure snapshot `openclaw-vm-pre-ubuntu24-20260615` retained as rollback.

- 2026-06-11 — **disk-cleanup-weekly cron** built + live. Script `/home/azureuser/.openclaw/bin/disk_cleanup.sh`; runs Wed 03:30 PT; prunes transcripts >30d (guards active <48h), vacuums systemd journal via `sudo`, clears stale cron backup files; posts to Discord only on ALERT (free <15%); first live run freed ~423 MB (69%→67% used). Cron id `92a9de12-3155-4ce7-913a-bc10c4d0077f`.

- 2026-06-08 — **OpenClaw 2026.5.22 → 2026.6.1** (resumed parked go/no-go under standing routine-maintenance approval). Also updated `@openclaw/discord` plugin 2026.5.6 → 2026.6.1. doctor Errors:0, no reboot. Hard-won recipe for npm-global update under a live systemd-user gateway captured in MEMORY.md (own-cgroup `systemd-run --user` + `sudo npm install`).
- 2026-06-06 — Weekly maintenance clean (apt 0 pkgs / openclaw 2026.5.22, both already current); no reboot. Discovered the elevated-vs-sudo gotcha (use plain `sudo` in this channel session).
- 2026-06-03 — cloud-init 25.3 → 26.1 upgrade (Cyrus-greenlit; previously parked phased item). Surveyed all 6 peers safe, ran with force-confold, exit 0, no reboot. Backlog cleared of parked items.
- 2026-05-29 — Adopted standing practice: daily `memory/YYYY-MM-DD.md` logs + this BACKLOG.md (per Cyrus directive via main).
- 2026-05-24 — Weekly handoff/distill cron is running clean (`lastRunStatus: ok`, delivered).
- 2026-05-22 — Bumped to OpenClaw 2026.5.22.

---

## travel

### Latest daily memory: `memory/2026-06-23.md`

# 2026-06-23

- No new activity today. Previous work (volleyball drop-in research) completed 2026-06-22.

### BACKLOG.md

# BACKLOG - travel agent

Triage regularly. Move done items into daily memory logs when they age out.

## Active

_(none — no active trip planning in flight)_

## On hold (pending Cyrus)

- **Travel plans themselves** — Cyrus confirmed 2026-06-09: he created me *ahead of* having trips. No plans right now; on hold. I'm a standby agent until a real trip lands. Don't re-ask scope/approvals/naming in the meantime — resolve specifics (airlines, seat, hotel tier, budget, loyalty, dates) *when* an actual trip arrives.

_Resolved 2026-06-09 (no longer open questions — answer is "plans on hold, nothing yet"): scope confirmation, standing approvals, upcoming-trips/preferences, naming. Will revisit each when a real trip materializes._

## Ideas

_(none yet — will populate as trip ideas come in)_

## Hygiene

- Fill out IDENTITY.md once naming question resolves
- Fill out USER.md with travel-specific Cyrus context as I learn it
- Periodic MEMORY.md distillation from daily logs (weekly Sunday cron handles HANDOFF; MEMORY is manual)

## Recently shipped

- 2026-05-24: Continuity protocol adopted, HANDOFF.md fleshed out from stub
- 2026-05-29: BACKLOG.md created, daily-log + backlog discipline adopted as standing practice
- 2026-06-22: Researched Seattle/Eastside indoor volleyball drop-in options; built `volleyball_dropins.html` with 3 sections (Seattle Parks 12 venues, Go Time Athletics, SBCC Bellevue); confirmed Bellevue Parks schedule from PDF (Crossroads CC + Hidden Valley Sports Park, $4R/$5NR)

---

## trading-bench

### Latest daily memory: `memory/2026-06-23.md`


## 2026-06-23 UTC — Post-Market Daily Review (5PM PT cron)

**Trades today (UTC 2026-06-23):** 0 trades — runners appear to have not fired yet or NYSE was quiet. Last trades were 2026-06-22 (8 total, all filled, no anomalies).

**Yesterday's (2026-06-22 UTC) trades recap (captured here for completeness):**
- 8 trades, all status=filled, zero non-filled anomalies
- Strategies active: breakout_xlk, sma_crossover_qqq, breakout_xlk_regime, sma_crossover_qqq_regime, tqqq_cot_combo, allocator_blend
- All buys (open positions being established)

**Leaderboard top 3 (as of review):**
1. `breakout_xlk__mut_c382b1` — $+44.05 realized, 3 trades, 100% win rate
2. `breakout_xlk_regime` — $+4.68 realized, 5 trades, 100% win rate
3. `breakout_xlk` — $+4.57 realized, 5 trades, 100% win rate
- Note: small sample sizes throughout; all 100% win-rate numbers are noise at n<10
- `backstop_test` still bottom at −$120 (known test artifact, 6 trades)
- `tqqq_cot_combo` unrealized −$6.67 (open position from today's buy)
- `leveraged_long_trend_paper` unrealized −$3.35 (open)

**Anomalies:** None. All trades filled. No MAX_TRADES_PER_DAY trips detected. No non-filled orders.

**PROMOTE candidates awaiting review:** None with a PROMOTE flag. Candidate dirs with active research:
- `leveraged_long_trend` — extensive backtest suite (voltarget, skew, breadth, vixterm all run), no PROMOTE file → still in research/evaluation
- `xsec_momentum_revival_b16` — CLOSED NEGATIVE (confirmed 2026-06-22 session)
- `overnight_drift`, `pead_smallmid`, `pead_neutral`, `pead_real`, `intraday_meanrev` — backtest results exist, no PROMOTE flags
- `macro_regime_allocator`, `allocator_blend_hardening`, `macro_regime_long`, `sma_crossover_qqq_macrogate`, `smallcap_momentum`, `credit_stress`, `pead_finnhub`, `regime_gated_xsec_momentum_xa_c87bbf`, `fx_lane` — in various states, no PROMOTE flags

**Research completed 2026-06-22:** SKEW overlay (❌ closed), VIX-term overlay (❌ closed), breadth-regime overlay (❌ closed), xsec_momentum_revival (❌ closed), load_xsec_strategy candidate-path infra (✅ shipped)

**No channel post warranted:** quiet day, no anomalies, no PROMOTE backlog.

## 🔬 edge_calibrator acceleration verdict (2026-06-23 ~5:45 PM PT) — main mgmt-check item 1
Q: "low-cost way to synthetically accelerate calibrator 19→30 trips without corrupting calibration?" → **NO. Documented + moved on.**
- The 30-trip gate counts REALIZED P&L of actual fills; training label = `1 if trip_pnl>0`. Synthetic trips = inventing fake P&L labels = poisoning the calibration. No "feed historical bars" path avoids this.
- **Empirical kicker:** of 19 counted trips, only **11 are live-12 book — and ALL 11 are WINS (0 losses).** A logistic regression on a one-class target is degenerate; forcing 30 while the book is all-wins yields a meaningless model. Gate is doing its job.
- **🐛 REAL FINDING (bonus): trip counter is POLLUTED.** `train_calibrator`/`_fifo_match_global` count EVERY strategy in tournament.db with no roster filter → 8 of the 19 are non-book: `backstop_test` (synthetic −$120 harness, 2 trips), `any` (2), `sma_crossover_btc` (4, dead crypto). When the gate opens at 30 it'll TRAIN on `backstop_test`'s synthetic losses + crypto noise. **Recommended a universe filter** (gate+train on live roster only) — but it's a PRODUCTION runner-module change → flagged to main, did NOT patch (candidate-only scope).
- Verdict memo: `reports/EDGE_CALIBRATOR_ACCELERATION_VERDICT_20260623.md`. Net: honest ETA to a *meaningful* calibration is further out than "30 trips" (need ≥30 live-book trips AND some losses so label isn't one-class) — and that's correct.

## 📋 Item 2 started (candidate disposition audit) — opus subagent `cand_disposition_audit`
Spawned read-only audit of all 16 candidate dirs → find any strategy w/ solid numbers but NO disposition on file. Deliverable: `reports/CANDIDATE_DISPOSITION_AUDIT_20260623.md`. Result pending (will log one-liner on return).

## ✅ Item 2 done — candidate disposition audit (opus subagent, verified on disk)
**BACKLOG IS CLEAN: 0 missing-verdict-but-solid candidates.** All 16 candidate dirs are PROMOTED, carry a verdict (file/MEMORY.md), or are correctly-closed clean negatives with a documented killer number.
- Buckets: PROMOTED/LIVE 2 (`leveraged_long_trend` = live voltarget sleeve, the ONLY dual-bar clearer: OOS Sharpe 0.855 vs SPX 0.722, full +2078.6%; `allocator_blend_hardening` robustness study) · DECIDED 7 (overnight_drift, macro_regime_allocator, credit_stress, fx_lane, xsec_momentum_revival_b16, sma_crossover_qqq_macrogate quarantine, regime_gated_xsec_xa_c87bbf) · CLOSE 7 (intraday_meanrev, smallcap_momentum, pead_real/neutral/smallmid/finnhub, macro_regime_long) · NEEDS-MORE-DATA 0.
- **Two tempting single-Sharpe numbers correctly DISQUALIFIED (I spot-checked both on disk):** pead_smallmid 0.757 = beta-0.876 levered-long artifact (hedged true-alpha 0.394; raw hold-5 actually 0.346, maxDD 71%); intraday_meanrev OOS 0.859 **collapses to 0.004 @ 4bps** w/ IS Sharpe **−2.877** (train lost money, PF 0.601) + all-2022 OOS fluke. Neither is un-decided — both are correct closes.
- Report: `reports/CANDIDATE_DISPOSITION_AUDIT_20260623.md`. Read-only confirmed (no code/promote/crontab touched). 
- **Takeaway:** no low-hanging promote sitting in the candidate pile. Next real improvement must be a NEW orthogonal signal class, not a re-dig of these.

## ✅ FIXED — edge_calibrator trip-counter pollution (universe filter shipped, 2026-06-23 evening)
Main greenlit the production-runner change (the fix I'd flagged this afternoon). Implemented + tested + verified live.
- **What:** added a universe filter to `runner/edge_calibrator.py` so the 30-trip gate AND the training set count LIVE-BOOK strategies only. Single choke point `_filter_trades(all_trades, universe)` applied in all 4 call sites (`train_calibrator`, `extract_training_rows`, `get_calibrated_kelly_fraction` prediction path, `calibration_report`).
- **Design (no rotting list):** explicit `universe=` from caller wins → else `LIVE_ROSTER` const (mirrors active `cron_tick.sh` 12-strategy line) → `EXCLUDE_STRATEGIES` (backstop_test/any/bp2 + 5 dead-crypto legs) stripped UNCONDITIONALLY even if passed in universe. New optional `universe` param threaded through all 4 public fns; runner's existing positional call works unchanged (LIVE_ROSTER default kicks in).
- **Verified live on tournament.db:** trip count **19→11** (drops sma_crossover_btc×4, any×2, backstop_test×2). Gate correctly STILL pass-through (11<30) — honest behavior preserved; `get_calibrated_kelly_fraction` returns raw unchanged so runner sizing untouched. Report now labeled "live-book only", backstop_test absent from breakdown. Confirmed all-wins one-class reality persists (so even at 30 it'd refuse a degenerate fit — correct).
- **Tests:** +8 new (`TestUniverseFilter`: excluded-dropped-from-count, not-in-roster-dropped, explicit-universe-override, excluded-stripped-even-with-explicit-universe, gate-counts-live-book-only, **training-labels-exclude-harness-losses**, report-says-live-book). Fixed pre-existing fixtures: `_make_multi_strategy_db` now emits LIVE_ROSTER names + swapped 16 `"strat_a"` placeholders→`"breakout_xlk"` (kept those tests on real trained-model paths). **Calibrator file: 42/42 green. Full suite: 675 passed, 1 skipped.**
- **1 unrelated pre-existing FAIL (NOT mine):** `test_fx_bars_cache::test_live_eurusd_cache_span_matches_lane_claim` — stale hardcoded bar-count assertion (expects 5843, cache now 5852; 9 newer trading days appended). FX lane is closed/decided. Left alone (out of scope). Flagging as a brittle-assertion cleanup item, not a regression.
- **Self-reviewed** (SOUL: code-review every mutation): empty-trades/None-universe/empty-set-universe/missing-strategy-key/bogus-universe all graceful, no crashes, pass-through preserved. `edge_calibrator.py` confirmed NOT in any md5-protected/frozen guard.
- **Net effect:** when the gate opens it will train on the 12-strategy live equity book ONLY — backstop_test's synthetic −$120 losses + crypto noise can never enter the labels. Honest ETA-to-train is now correctly LATER (paced by real live-book trips, not noise).

## 🔬 NEW LANE STARTED — FINRA daily short-volume signal (opus subagent finra_shortvol_lane, ~evening)
After shipping the calibrator fix, started a genuinely FRESH orthogonal signal class (self-report rule: obvious roadmap item → start in parallel, don't wait for main).
- **Why this one:** positioning-scout flagged FINRA daily short-vol 2026-06-05 as a top free pick but COT got built instead → never tested end-to-end. Distinct from COT (already a live tqqq_cot_combo component). Orthogonal to price/vol (measures short-sale flow, not price path).
- **Data verified live from this VM TODAY:** `https://cdn.finra.org/equity/regsho/daily/CNMSshvol<YYYYMMDD>.txt` (browser UA) → HTTP 200, pipe-delimited `Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market`, one file/day all symbols. **Archive starts 2019-01-02** (2018− = 403). Span ≈2019→2026 (covers 2020 crash + 2022 bear, NO 2008 — depth caveat). Core feature = ShortVolume/TotalVolume ratio (short-SALE flow proxy, NOT short interest — frame honestly).
- **Brief:** long/flat timing overlay on SPY+QQQ, test BOTH directions (H1 contrarian-capitulation high-ratio→long; H2 informed-flow high-ratio→flat), anti-lookahead (day-T file post-close → trade T+1 earliest), benchmark vs SPY B&H on traded path net of CostModel, FULL + OOS split, orthogonality corr vs SPY ret & vol (kill the secret-vol-relabel failure mode), report response surface (knife vs plateau). Candidate scope only — no live strategies/crontab/promote touch; cache to `data_cache/finra_shortvol/`.
- Deliverable: `reports/FINRA_SHORTVOL_LANE_<stamp>.md` + tight return summary. Awaiting completion event (push-based; not polling).

## ✅ FINRA SHORT-VOLUME LANE → CLOSE (clean robust negative) — subagent done, VERIFIED on disk
finra_shortvol_lane subagent finished (its CLI session died on a post-write compaction error, but ALL deliverables verified on disk — report 10.5KB, data cached SPY/QQQ/+12 syms, protected runners untouched, nothing promoted). Real result, not fabricated.
- **Thesis:** SVR = ShortVol/TotalVol (short-SALE flow ratio, NOT short interest) as long/flat timing overlay on SPY+QQQ, trailing-z for "extreme". BOTH signs tested (H1 contrarian-capitulation, H2 informed-flow). 1,877 days 2019→2026 (no 2008; covers COVID+2022). Pre-registered to disk BEFORE backtest. Strict 1-bar anti-lookahead (FINRA file post-close→trade T+1), repo 4bps-RT, identical cost footing.
- **Result — CLOSE:** honest OOS pick SPY +92.5% vs +103.5% B&H (Sharpe 1.373 vs 1.435); QQQ +111.5% vs +182.4%. Walk-forward 2/6 yrs each, compounded LOSES (SPY +75.4 vs +114.2; QQQ +95.8 vs +142.4). **KILLER DIAGNOSTIC: corr(exposure, excess ret) = +0.956 SPY / +0.971 QQQ; 0 of 160 configs beat bench with exposure <70-90%.** Pure closet-beta — zero timing edge, every step-to-cash removes more good days than bad. Configs that actually de-risk (<50% expo) underperform −90% to −158%.
- **Orthogonality (the valuable twist):** |corr(SVR, trailing ret/vol)| ≤ 0.19 → GENUINELY orthogonal, NOT a vol relabel (unlike every prior orthogonal reject here that died as a secret vol relabel). Real independent info that simply doesn't predict next-day index direction → makes it a CLEAN close, not a disguised dead lane.
- **Only un-pursued angle (flagged, weak prior):** cross-sectional single-name SVR ranking (academic prior weak for short-SALE-vol vs short-INTEREST). NOT worth pursuing now.
- Report: `reports/FINRA_SHORTVOL_LANE_20260623T012237Z.md` (+ prereg `_FINRA_SHORTVOL_PREREG.md`, engine `runner/finra_shortvol_backtest.py`, cache `runner/finra_shortvol_cache.py`). Reusable win: FINRA daily short-vol fetcher works from this VM (403=non-trading-day gotcha handled w/ consecutive-miss circuit breaker).
- ⚠️ note: sub mis-dated its own log to memory/2026-06-22.md; durable record is HERE (06-23) + MEMORY.md.

## 🔬 NEW LANE STARTED — 3rd-sleeve structural-edge scope (opus subagent third_sleeve_scope)
**Deliberate PIVOT** off timing-signal hunting (FINRA close crystallized it: every timing/regime overlay caps at closet-beta; the bench's only real wins — vol-target TQQQ, sector rotation, the 2-sleeve blend — are STRUCTURAL diversification/leverage, not signal-timing). So: test whether the validated allocator_blend gets a genuine lift from a 3rd low-correlation sleeve. Proposed to main→Cyrus as a strategy pivot; reversible research so started in parallel (autonomy + main-as-proxy; didn't wait for 👍).
- **What it extends:** 2-sleeve inv-vol(63d) risk-parity blend (TQQQ-voltarget + rotation top-2 of SPY/QQQ/GLD/TLT). Engine `_allocator_blend_tests.py::build_sleeves()/blend_portfolio()` (reused directly, no reimpl). Numbers to beat (2010-02→2026-06): full Sharpe 1.014 / OOS 1.147 / maxDD −23.9% / CAGR 15.9%.
- **Candidates (priority order):** (1) managed-futures/trend (CTA) — real ETFs DBMF(~2019)/KMLM(~2020) SHORT-history + a synthetic deep TSMOM proxy from DBC/GLD/TLT/UUP we already have; (2) fallback credit/curve sleeve via FRED BAA10Y/NFCI/T10Y2Y (fred_cache.py, key on disk). Test corr-to-each-leg FIRST (the gate — only works if genuinely low/neg-corr where blend hurts), then 3-sleeve-vs-2-sleeve-vs-SPX OOS net of cost.
- **Data trap flagged to sub:** Yahoo v8 is 429-throttling our IP RIGHT NOW (FINRA sub hammered it) → told sub to use query2 + 1.5-2s spacing + backoff + cache-once; SPY/QQQ/GLD/TLT/TQQQ/DBC already cached, only DBMF/KMLM/UUP/EFA are new fetches. Candidate/research scope only — no live strategies/crontab/promote/paper-clock.
- Deliverable: `reports/THIRD_SLEEVE_SCOPE_<stamp>.md` + tight summary (corr table, 3-vs-2-sleeve OOS raw-ret/Sharpe/maxDD, disposition). Awaiting completion event (push-based).

_…(truncated; 119 total lines in source)_

### BACKLOG.md

# BACKLOG.md — trading-bench

Single source of truth for what's next. Updated as items land or get re-prioritized.
Format: priority [P0 blocking / P1 next / P2 soon / P3 someday] · status [TODO / WIP / DONE / DROPPED] · brief.

- **✅ DONE 2026-06-21 · Paper-clock the ALLOCATOR BLEND out-of-band (Path A).** SHIPPED: `runner/allocator_paper_tracker.py` re-runs the validated blend engine daily (reuses `_allocator_blend_tests.build_sleeves`+`blend_portfolio` directly, zero sleeve reimplementation), logs idempotent daily snapshot to `allocator_paper.db` (`daily_snapshots` table), no live orders. Wired into `cron_tick.sh` (non-fatal, weekday crontab, idempotent per latest-trading-date). First snapshot 2026-06-18: w_tqqq=0.442 / w_rot=0.558 / rot_holds=[SPY,QQQ] / blend +1.89% vs SPX +1.08%, engine Sharpe 1.014 (matches report exactly). Report: `reports/ALLOCATOR_PAPER_TRACKER_LAUNCH_20260621.md`. Protected files md5-unchanged. Paper clock now accumulating forward. **The partial-trim runner primitive (next item) remains the path to FAITHFUL live paper.**
- **✅ DONE 2026-06-22 · P1 · Build the PARTIAL-TRIM runner primitive (the infra that's been implicitly blocking allocators).** SHIPPED: added a partial-sell-while-staying-long path to `runner/runner.py` (ONLY file changed). A `trim` action (and the now-safe legacy `sell`) resolves an exact share qty (from `action.qty` or `notional/price`), CLAMPS to attributed held qty (never oversell → no long→short flip), submits a QTY order, logs a `sell` row, and does NOT clear strategy state (stays long). Fail-safe ladder: flat→HOLD, unresolved→HOLD, full-sweep→degrade to CLOSE. Attribution correct BY CONSTRUCTION — emits exactly the `sell`-row shape `db.strategy_position` already subtracts (per-(strategy,symbol) keyed, own `min(q,qty)` clamp); zero new attribution code. Risk reuses the existing CLOSE-branch (daily-cap only) → **risk.py byte-unchanged**. 12 pinning tests written FIRST (`tests/test_runner_trim.py`), verified red-on-unchanged then green. Full suite **637 passed / 1 pre-existing-unrelated fail (EURUSD bar-count drift) / 1 skipped**. md5: runner.py CHANGED; risk.py/backtest.py/backtest_xsec.py UNCHANGED. Hard rails intact (paper-only guard + killswitch untouched). NOT wired to trade live (separate follow-up). Report: `reports/PARTIAL_TRIM_PRIMITIVE_20260622.md`. **Follow-up flagged:** `runner/runner_xsec.py` still has the old notional-sell path for basket `sell` legs (latent — xsec emits buy/close only today); port the same qty-clamp there before any basket strategy emits `sell`. → **✅ RESOLVED 2026-06-22, see next item.** NOTE: the 'inject non-traded underlying closes' gap was ALREADY RESOLVED (tqqq_cot_combo trades live with a working QQQ gate, trade id 56).
- **✅ DONE 2026-06-22 · P1 · Port the PARTIAL-TRIM primitive into the BASKET runner + write the live ALLOCATOR strategy.** SHIPPED two things (PAPER ONLY). **(1) `runner/runner_xsec.py` (ONLY engine file changed):** added the same partial-trim leg the single-symbol runner got — `action="trim"` + made legacy `sell` SAFE. Per leg: resolve sell qty (`action.qty` or notional/price), CLAMP to attributed held qty (never oversell → no long→short flip), submit QTY order, log a `sell` row so `db.strategy_position` subtracts exactly that qty, do NOT clear leg state (stays long); full-sweep degrades to CLOSE. Safety is STRUCTURAL: reuses the tested `db.strategy_position` reconstruction (zero new attribution code) + TWO independent clamp-to-held guards + md5-frozen `_clamp_basket` ignores `trim` entirely. Risk consulted close-semantics (de-risk, can't breach cap). 14 pinning tests FIRST (`tests/test_runner_xsec_trim.py`) incl the core BUY-two/TRIM-one/CLOSE-other multi-leg-attribution test — verified RED (10f/4p) then GREEN. **(2) `strategies/allocator_blend/strategy.py` (new) + `params.json` + 12-test smoke (`tests/test_allocator_blend_strategy.py`):** `decide_xsec()` REUSES `allocator_paper_tracker.compute_blend_state()` target-weight decomposition (zero sleeve-math reimpl, lookahead-safe by construction), maps target_w→per-leg buy/trim/hold/close with a 5% churn guard + fail-safes (engine error→whole-basket HOLD, missing price→hold leg, never panic-flatten). Live-smoked against the real tracker (target {TQQQ:0.13,SPY:0.28,QQQ:0.28} cash 0.31). Full suite **663 passed / 1 pre-existing-unrelated FX-cache fail / 1 skipped** (637 base +14 +12). md5: ONLY `runner_xsec.py` changed; runner.py/risk.py/backtest.py/backtest_xsec.py/broker_alpaca.py UNCHANGED. **Allocator strategy file written; SCHEDULING PENDING PARENT REVIEW** — deliberately NOT added to crontab/cron_tick.sh; pick the live paper notional + wire the schedule as a separate reviewed step. Report: `reports/ALLOCATOR_WIRING_20260622.md`.

When closing an item: move to "## Recently shipped" with a date, prune that section monthly.

---

## 📋 CONFIRMED BACKLOG — from Cyrus 2026-06-13 review session ("make sure we are not missing anything")

All items below were explicitly reviewed + confirmed by Cyrus 2026-06-13. Do them in priority order after the current detour. Sources: (A) = original parked-4 list; (V) = from Ray Fu prediction-markets video analysis.

### 🎯 P1 — Core engine work (do these first)

**[A] 1. Diversify mutation parents — DONE 2026-06-13** ✅
Mutation cron is mature on only 2 signals (SMA-cross-QQQ, breakout-XLK) wearing many costumes → promotions are window-luck, not new edge. Root-cause hygiene DONE (gate tightened, dedup, throttle, cull cron). The one remaining real lever: feed genuinely different archetypes into `tournament_loop.py` `GATE_PASSING_PARENTS`. Research problem — where edge actually comes from.

**[A+V] 2. Kelly sizing layer — DONE 2026-06-13** ✅
Three independent sources (YouTube-sprint, vol-target sleeve, Ray Fu Step 4) all converge: the missing piece is risk/sizing, not another entry signal. Concrete spec: replace flat $100-per-strategy sizing with Kelly fraction computed from the strategy's estimated edge + recent win/loss distribution. Fits inside the runner, no new data sources. Vol-target TQQQ sleeve = instance #1; this generalizes it to all strategies. See `reports/yt_research/SYNTHESIS`.

**[A] 3. FX lane — DONE 2026-06-13, LANE CLOSED** ❌ NO-GO
All 4 archetypes evaluated against existing `fx_lane_eval.json` (built 2026-06-09). Best: carry_proxy at 0.084 Sharpe / +2.0% OOS (+0.23%/yr CAGR). xsec_momentum: -20.5% OOS. None beat SPX raw. Consistent with prior MEMORY verdict. Staying in `strategies_candidates/` as a documented dead-end.

### 🎬 P1 — From the video (new items)

**[V] 4. Loss-triggered postmortem loop — DONE 2026-06-13** ✅
Current mutation cron runs on a schedule and doesn't learn from losses. Video's Step 5: after every loss, 5 agents run postmortem, figure out what went wrong, save it, update the system. Our version: when a strategy hits a losing threshold in the weekly tournament, spawn a diagnostic subagent that writes a structured "why did this lose" note (regime mismatch? cost blowout? signal decay?) → mutation step reads those notes before generating variants. Materially better feedback loop than blind scheduled mutation. Distinct from item #1 (that's about diversifying *what* we mutate; this is about making mutation *smarter*).

**[V] 5. Prediction markets lane — Polymarket scout — DONE 2026-06-13** ✅ CONDITIONAL-GO
Verdict: API accessible, 0% fees on geopolitics/macro markets, $100M+ volume, genuine edge thesis. ONE PREREQUISITE: Cyrus creates Polymarket.us account + KYC (~15 min). Report: `reports/POLYMARKET_SCOUT_20260613.md`.
Next: Cyrus signs up → then build `polymarket_scanner.py` (FRED/CME priors vs implied prob, flag >5% discrepancies) + prices-history adapter.

**[V] 6. Edge-calibration meta-model — SCAFFOLDED 2026-06-14; trip-counter FIXED 2026-06-23** ⏳ pass-through until 30 LIVE-BOOK round-trips
`runner/edge_calibrator.py` live + hooked into runner.py. Logistic regression on [n_round_trips, win_rate, avg_hold_bars, kelly_raw, recent_vs_all_winrate]. Calibration multiplier = 2*P(win)-1. **Universe filter shipped 2026-06-23** (main-greenlit): trip counter now counts LIVE-BOOK strategies only (LIVE_ROSTER const + EXCLUDE_STRATEGIES unconditional strip). Live trip count 11/30 (was 19, 8 were noise: backstop_test×2, any×2, sma_crossover_btc×4). All 11 current trips are WINS — one-class label means even at 30 trips the model will refuse a degenerate fit; honest. 675 tests passed/1 skipped. Auto-activates when gate crossed.

### 🔧 P2 — Infra / hygiene

**[A] 7. Runner fill-reconcile pass — DONE 2026-06-13** ✅
c382b1 order sat `pending_new` in DB despite filling — runner logged the initial ack and never polled back for terminal status. Add a reconcile pass: poll Alpaca for terminal status on `pending_new`/`accepted` orders → update DB row. Stops stale leaderboard/turnover. Small, self-contained fix.

---

## P0 — Blocking / urgent

- **DONE 2026-05-31 · main RULING 1 — DEMOTED `xsec_momentum_xa_38d2b2` to candidate.** Post-√252 Sharpe 1.04→0.87 (below 1.0 fast-track bar, clause a) + WF median 0.17 fitness fail. main: keeping it live on return-floor (clause f, 11.6%/yr) alone = retroactively justifying a promotion against a Sharpe criterion it no longer meets = goalpost-moving this audit prevents. Cron line removed (clock 1 tick old, ~free), live dir→`.trash/`, candidate preserved → re-promotes via front door only. Record: `reports/DEMOTE_xsec_momentum_xa_38d2b2_20260531T190924Z.md`. **No live xsec on cron now.**
- **DONE 2026-05-31 · main RULING 2 — GATE Bar A #5(b) re-bound on DEPLOYED-CAPITAL / instrument-level DD.** Was binding on idle-cash-diluted portfolio NAV (−50% leg → ~−5% vs $1000 NAV, invisible to the clause). Now `backtest_xsec.worst_instrument_dd_pct` (worst single-leg DD-from-entry, closed+open) + binding `walk_forward_xsec.passes_bar_a_5b()` (30% ceiling = candidate-stage MaxDD; Bar E stays 20%). Diluted NAV DD kept as secondary metric. Re-pin: `tests/test_backtest_xsec.py::TestDeployedCapitalDrawdown` (4 tests) proves −50% crash TRIPS #5(b) while diluted NAV would pass. Suite 233→237. GATE.md #5(b) text + History entry updated. Memo: `reports/HARNESS_INTEGRITY_AUDIT_20260531T190026Z.md`. **Single-stock xsec lane now UNBLOCKED — corrected ruler in place.**

- **DONE 2026-05-31 · Sharpe √252 fix shipped (correctness bug, mine).** `bars_per_year(timeframe, is_crypto)` in backtest.py (252 equities / 365 crypto for 1Day, intraday unchanged); applied in backtest.py + backtest_xsec.py. 7 pinning tests (tests/test_sharpe_annualization.py). Suite 226→233 green. Every historical equity daily Sharpe in the repo was inflated ~20%; all prior REJECTS stay rejected (more so). One live PROMOTION flagged (see P0 above).

## P0b — prior

- *(none — paper-trading clock started 2026-05-31)*

- **DONE 2026-05-31 · paper-trading clock STARTED for `xsec_momentum_xa_38d2b2`.** Cron line `5 14 * * 1-5` UTC (07:05 PT, 5min after NYSE open) added via `crontab -e`, routes `cron_tick.sh xsec_momentum_xa_38d2b2` → `tick.sh` → `runner.runner_xsec`. Cyrus green-lit self-add via main. Full path verified end-to-end (Sat → skip_market_closed, no post). First live tick Monday 07:05 PT; ≥4-week Bar B/C/E clock starts then. Channel msg 1510467169593594149. **Standing-orders update logged to MEMORY.md:** starting a paper clock on an approved promotion is NOT a separate ask going forward.

## P1 — Next up

- **✅ CLOSED 2026-06-22 · `breakout_xlk__mut_c382b1` anomalous-deployment audit RESOLVED (re-verified live on disk).** Original P0 (2026-06-13): deployed to `strategies/` 2026-06-12 05:08 UTC without code-review, `notional_usd: 1000.0` (10x), first $1000 XLK order stuck `pending_new`, double-listed in `strategies_candidates/`. **All four sub-items confirmed resolved 2026-06-22:** (1) audit done — root cause = mutation-cron artifact deployed without review (documented MEMORY); (2) code-review done — PASS, kept on live roster; (3) corrected — live `notional_usd: 100.0` (parity), AND no longer double-listed (`strategies_candidates/breakout_xlk__mut_c382b1` is GONE, only the live `strategies/` copy remains); (4) reconciled — the stuck $1000 order (trade id 43) is now `filled`, closing sells (ids 44/55) terminal; the lone $1000 trade is the historical pre-fix 06-12 one, everything since is $100-correct. Scheduled in crontab. **No residual anomaly. This P0 is closed; do not re-flag.**

- **✅ CLOSED 2026-06-21 · ADD FOREX — DEAD LANE, triple-confirmed.** 3 concordant negatives (FX_LANE_20260609 long/short basket, FX_TREND_FEASIBILITY_20260612 per-pair, FX_LANE_20260621 trend/carry/momentum). 0/5 series beat SPX raw, 0/5 Sharpe>0.8, best OOS 0.39. Costs NOT the killer (FX spreads negligible as predicted) — signal is weak/regime-dependent. No leverage-rescue. Only residual = weak diversifier sleeve IF allocator exists. Report: reports/FX_LANE_20260621.md.
[HISTORICAL] - **TODO 2026-06-09 · ADD FOREX as a real lane (Cyrus-prompted, my call — decided in-channel).** Cyrus asked why stocks not crypto/forex + noted FX *feels* predictable; FX had **never been evaluated** (grep-confirmed 0 prior work). Decision: ADD FX as a parallel lane (NOT a pivot off stocks, NOT a crypto revisit — crypto stays dead on the ~4% Alpaca round-trip cost). **Why FX is worth it:** spreads ~0.5–1bp = cheaper than crypto AND stocks, so edge that dies in crypto can clear in FX; clean trend-persistence; 24/5 no overnight gap. **The catch to test honestly:** near-efficient + low-vol (EURUSD <0.5%/day) → small per-trade edges that usually need leverage (rail-forbidden by default) + regime-shift risk (CB surprises, carry unwinds). **BUILD (next cycle):** (1) FX data adapter — free majors via Yahoo `EURUSD=X`/`GBPUSD=X`/`USDJPY=X` etc., verified ~2007+ in the crossasset scout; (2) FX cost realism (~1bp one-way, NOT the 400bp crypto model); (3) run 2–3 honest trend + carry strategies through the SAME walk_forward gate as everything else; negative result is acceptable + logged. Whether FX trend-persistence survives realistic-cost + no-leverage + walk-forward is the open question. Channel msgs 1513766589617672315 + 1513768801156730973; rationale in memory/2026-06-09.md.
- **🎯 BREAKTHROUGH 2026-06-09 · LEVERAGED-TREND BEATS SPX RAW, OOS, FULL HISTORY — the project's FIRST mission-bar clear. ✅ VOL-TARGET FOLLOW-ON DONE 2026-06-08 → now beats SPX on BOTH raw AND risk-adjusted.** Built `runner/daily_bars_cache.py` (Yahoo-v8 adjclose, keyless, lookahead-safe; +15 tests green). Candidate `strategies_candidates/leveraged_long_trend/` (PAPER, candidate-only, NOT live, NOT a GATE_PASSING_PARENT). **TQQQ / SMA-200 gate / VIX-off, 2010→2026: +10,121% vs SPX +587% raw · Sharpe 0.846 vs 0.773 · maxDD −56% vs −34%. ALL 18 sweep cells beat SPX raw. OOS (split 2018): +1,212% vs SPX +175% — amplifies OOS. 7/7 sma-windows beat SPX raw, 5/7 beat Sharpe (broad plateau, not curve-fit).** No-lookahead verified. Report `reports/LEVERAGED_TREND_FULLHIST_20260609.md`. **HONEST ASTERISK:** raw win is a LEVERAGE PREMIUM not alpha — Sharpe only marginally > SPX, DDs violent (2018-Q4 −49%, 2022 −45%); gate tames slow bears (2022 −45% vs BH-3x −80%) + COVID but whipsaws in fast V-reversals. Under SPY-relative-IR + Sharpe-≥1.0 it would NOT clear. **NOT promoted to a paper clock** (−56% on a 3x sleeve needs explicit sizing + real-money rail talk first). **OPEN follow-on (decided, next build): VOL-TARGET the sleeve** ✅ **DONE 2026-06-08** — `backtest_daily_voltarget.py` (new module, binary core untouched, backward-compat byte-exact): inverse-realized-vol sizing compressed −56%→−34.5% DD (target 0.25: +2,026% vs SPX +587%, maxDD −34.5% ≈ SPX −33.9%, Sharpe 0.859 > SPX 0.773; target 0.20: maxDD −27.8% BELOW SPX). ALL sweep cells beat SPX raw+Sharpe; frozen-OOS(2018) + vol-window-robustness(6/6) hold; 14 tests green incl. no-lookahead lock; suite 391/391. Report `reports/LEVERAGED_LONG_VOLTARGET_20260608.md`. **DD objection ANSWERED → legit promote-to-paper-clock candidate.** ✅ **SURVIVORSHIP CROSS-CHECK DONE 2026-06-08 (verdict B PARTIAL — `reports/LEVERAGED_LONG_SURVIVORSHIP_20260608.md`): re-ran the EXACT engine on UPRO/SPXL/SOXL. RAW-return SPX beat is STRUCTURAL (all 3 sleeves, every cell); broad-cap DD≤SPX holds (UPRO/SPXL) but NOT semis; BUT the Sharpe edge was LARGELY TQQQ-SPECIFIC (UPRO 0.746<SPX 0.802, SOXL 0.723<0.752) and "clean OOS" doesn't generalize (t0.20 FAILS OOS on broad-cap; only t0.25 holds, narrowly +186 vs +175). CORRECTED my TQQQ report (raw beat stands, Sharpe/OOS downgraded) — honest frame: a raw-return leverage-harvest, NOT risk-adjusted alpha. Reproduced UPRO t0.25 to the digit; md5s unchanged; suite 391/391.** REMAINING follow-ons (RE-PRIORITIZED): **#1 = REALISTIC EXECUTION-DRAG model** (off-TQQQ OOS margins thin enough that ~3000 rebal/yr could erase them — if broad-cap OOS beat dies under real costs the family is a WASH); then rolling walk-forward (UPRO 0.25), synthetic pre-2010 extension (test the 2008-GFC bear TQQQ can't see; negative there caps conviction; report real-vs-synthetic separately). This REVERSES the old "LEVERAGED-ETF TREND — REJECTED" (measured vs the now-suspended risk-adjusted bar). VIX-overlay-as-risk-OFF-gate PARTIALLY walked back: VIX-off > VIX-on for raw return on TQQQ (VIX is a DD tool, not a return enhancer here). Protected md5s unchanged; suite green ex known dry-run flake.

- **WIP/OPEN 2026-06-07 · Hourly mutation-cron is a redundant-dir factory — TIGHTEN-GATE + DEDUP-PURGE + THROTTLE + DIVERSIFY-PARENTS.** Triage subagent dissected the 48-dir `__mut_` pile (`reports/MUTATION_QUARANTINE_TRIAGE_20260607T040632Z.md`): "2 edges in 48 costumes" (only 2 signals behind 4 parents), promotions are window-luck (same code flips REJECT↔PROMOTE, medSharpe swings −1.4…+3.6 by split), 18 dirs provably redundant (md5-clones + inert-filter no-ops + parent-baseline dups). **Verdict: ship NONE to a paper clock; fix the process first.** PROGRESS: **(c) THROTTLE — DONE 2026-06-08** (cron 19d65b50 `20 * * * *`→`20 */4 * * *`, 4× fewer rounds). **(a) RISK-ADJUSTED/STABILITY GATE — DONE 2026-06-08** (the 3 stability constants in walk_forward.py were DEAD/never-called; now WIRED into `passes_mutation_gate`: 40-trade floor + 60% Sharpe-sign-consistency [both candidate-level, bind even orphan] + −0.10 parent-Sharpe-regression guard alongside the +0.10pp return delta; `TestMutationStabilityGuards` 5 tests pin it; full suite 325 green; protected md5s unchanged; strategies/ untouched). **(b) DEDUP in `evaluate()` — DONE 2026-06-08** (`REJECT_DUPLICATE` via normalized-code md5 `_find_code_clone` + inert-filter "≥X% of parent's closed trades changed or REJECT" guard; only suppresses bogus PROMOTEs, never touches `strategies/`; +12 tests; `strategy_gen.py` md5 `a9d17ee…` — guards re-verified live 2026-06-09). **(f) PURGE redundant dirs — DONE 2026-06-09** (main fleet-health nudge): culled the legacy pile **103→50** candidate dirs — moved all **53 `__mut_` costumes** of the 4 parent families to `.trash/candidate_cull_20260609T010308Z/` (recoverable, not `rm`); kept all **49 distinct research lanes** (xsec/pead/macro/credit/vol-regime/leveraged/overnight/connors/etc.); 156 `TOURNAMENT_ROUND_*.md` audit trail + live `strategies/` untouched; verified on disk (0 `__mut_` remain). **(g) RECURRING CULL CRON — DONE 2026-06-09**: weekly self-managing cull `7db57958` (Sat 8:30am PT) trashes future `__mut_` costumes, keeps distinct lanes — pile now self-manages, no longer relies on me noticing. **PILE RE-PILING ALREADY STOPPED before this cull** (the tightened gate + 4h throttle landed 06-08): only 1 candidate dir created 06-08, 0 on 06-09 — the "~100% PROMOTE" in nightly logs is the same recurring micro-mutants re-clearing + hash-dedup'd (no new dirs), not 12 new edges. **STILL OPEN (the only real remaining lever):** (d) diversify `tournament_loop.py` `GATE_PASSING_PARENTS` beyond the 2 signals (SMA-cross-QQQ / breakout-XLK) — feed genuinely different archetypes; (e) keep freezing promotions from the 4 mature families pending real new parents. This SUPERSEDES the old "15-PROMOTE-backlog awaiting Tessera review" framing (those were known overfit cousins — now trashed). **ROOT CAUSE CLOSED; remaining work is parent-diversity, a research lane, not a pile-hygiene problem.**

- **DONE 2026-06-05 · FREE-dataset scout sweep (6 orthogonal classes) → ranked map shipped.** 6 parallel scouts (options/IV, fundamentals, macro, alt-data, positioning, cross-asset) → consolidated `reports/SCOUT_SYNTHESIS_20260605.md`. Goal: orthogonal signal (corr <~0.3 to OHLCV) to break the ~0.5 SIGNAL ceiling, zero spend. Ranking filter = 2008-GFC coverage. TIER 1 (free, spans 2008): FRED credit/curve spreads (#1, both macro+crossasset scouts), CFTC COT, CBOE vol-index CSVs, GDELT, SEC EDGAR, Yahoo cross-asset ratios. DEAD: NAAIM/Pushshift (licensing). Full map promoted to MEMORY.md. SCOUTING ONLY — no ingest/backtest done.
- **DECISION-OPEN 2026-06-05 · Wire FIRST free Tier-1 source (recommend FRED credit spreads) into ingest + backtest.** Awaiting Cyrus/main go-ahead. Build order if green-lit: FRED HY−IG OAS + NFCI + T10Y2Y spreads → COT → CBOE. Access via keyed `api.stlouisfed.org` ONLY (fredgraph.csv is bot-walled + serves stale data from this VM — see MEMORY.md FRED trap). GATE unchanged at 1.0 FP-cont-Sharpe. Honest caveat held: orthogonal DATA ≠ EDGE; backtest decides.
  - **UPDATE 2026-06-09:** NOT blocked on a key — `FRED_API_KEY` is present + valid in the workspace `.env` (verified: `_api_key()` resolves, 32-char lowercase, live fetch works). The earlier "blocked on Cyrus for a key" note was FALSE. **The REAL blocker found 2026-06-09:** ICE BofA OAS series on free FRED were truncated to a rolling ~3yr window (BAMLH0A0HYM2 / BAMLC0A0CM / BAMLC0A4CBBB all now `observation_start=2023-06-12` — ICE licensing pullback), so the HY-IG-OAS-back-through-2008 scope is no longer buildable from free FRED. **SELF-UNBLOCK (no spend, no Cyrus dep):** swap ICE-OAS → **`BAA10Y`** (Moody's Baa−10yr credit spread, 1986, covers 2008+2020) + **`NFCI`** (1971) + **`T10Y2Y`** (1976) — all free, keyed-API-reachable now, span both crises. COT (Tier-1 #2) already done — see DONE item below.
  - **DONE 2026-06-09 · CREDIT-STRESS LANE built + walk-forwarded → NO beat-SPX-raw; real GFC-crisis-hedge value (candidate only).** Ingested BAA10Y+NFCI+T10Y2Y (keyed FRED, NFCI on a conservative 7d release-lag, ALFRED-PIT-cross-checked); 3 regime gates (spread / NFCI-conditions / combine), 12 OOS regime windows incl 2008+2020. **The JSON's "beats_spx_raw=True" is a BENCHMARK ARTIFACT** (vs ^GSPC PRICE-only); vs honest **buy-and-hold-SPY (total return)** every strategy in every config **LOSES** (beats SPY-BH 8–25% of windows). Apparent winner nfci_gate (+2747%) is 90%+ time-in-market @ corr 0.76–0.85 = closet-long equity. **REAL positive:** GFC-type crisis decoupling — combined_credit_macro **+8.1% in 2008 GFC while SPX −39.5% @ corr 0.05**; +5.0% in 2011 EZ-downgrade; crisis-composite +7.4% vs SPX −12.1%; cut maxDD to −29%. **TRADE-OFF that kills the full-cycle beat:** de-risking costs upside every bull/recovery; n=1 on the deep 2008 decoupling (2020 V-recovery punished cash; 2022 rates-bear got no help). **Disposition: candidate only, NOT a return engine** — a crisis-hedge/DD-control sleeve that only matters once a multi-strategy allocator exists (same shape as FX). Suite **446** (was 437, +9 incl NFCI-no-leak); 4 protected md5s unchanged; strategies/ untouched. Files under `strategies_candidates/credit_stress/`; report `reports/CREDIT_STRESS_20260609.md`. **3 workers died mid-build post-restart but left a complete lane that ran end-to-end; finished the report inline + verified all numbers from the JSON myself.** → beat-SPX-raw bar STILL UNMET (3 clean negatives now: leveraged-long wash, FX no-beat, credit-stress no-beat — each with a keep-able diversifier sliver).
- **DONE 2026-06-05 · COT positioning lane (Tier-1 #2) → REJECT (FP-cont +0.930 < 1.0 gate).** Built inline (2 subagents killed mid-run by gateway restarts; finished in-parent). CFTC TFF history 2010→2026 cached (no key, no spend) via `runner/cot_cache.py` (point-in-time `released_asof` + lookahead canary + 7 tests). Markets: ES→SPY, NQ→QQQ, ZN→10y. **The classic CONTRARIAN-positioning thesis FAILED** (best contrarian-lev ≈ +0.45); only real signal was leveraged-fund positioning **MOMENTUM** (+0.930, z104) + dealer-net contrarian (+0.869) — both sub-gate. **Orthogonality:** low corr to SPY trailing RETURN (−0.21..+0.24 ✓ not a price relabel) but meaningful corr to realized VOL (lev +0.53, dealer −0.44) → only PARTIALLY orthogonal, carries a vol-regime component. CAVEATS: small n (best 158 trades/8 windows), **no 2008/GFC** (TFF starts 2010 → only 2020+2022 bears). **Disposition:** REJECT standalone; candidate quarantined; **KEEP as a possible FEATURE/conditioning input for a later FRED+COT multi-factor COMBINE.** Suite 302→309, all protected md5 unchanged, strategies/ untouched. Report `reports/COT_POSITIONING_20260605T212415Z.md`.
- **DONE 2026-06-05 · Hourly mutation-cron real-gen fix (was silent dry-run every tick).** v2 inline-gen-then-finalize in one cron turn (v1 spawn+yield orphaned candidates). Root cause: `run_one_round()` in a `python3 -c` subprocess can't reach `sessions_spawn` → NotImplementedError → `--dry-run` fallback. Prompt-only fix, no runner/protected file touched, `delivery.mode=none` kept (earlier inline window leaked strategy.py to Discord). Verified LIVE: round 20260605T034734Z Mode=LIVE, real PROMOTE candidate `breakout_xlk_regime__mut_c382b1` quarantined. Technique promoted to MEMORY.md.

- **DONE 2026-06-04 (gate held, Cyrus FINAL) · High-vol / leveraged-INSTRUMENT archetype lane.** Ran SOXL/TQQQ/UPRO trend-follow (leverage inside instrument, exposure <= cash, no rail change). SOXL was the only one to clear the screen (~0.97) but FAILED Bar A (needs BH-crutch on 2 regime windows; cap is 1) → full-span FP 0.973 < 1.0. **Cyrus ruled the gate-hold FINAL 2026-06-04 — NOT graduated.** TQQQ marginal, UPRO reject (0.57). Reports: LEVERAGED_TREND_20260604T055554Z.md + SOXL_VALIDATION_20260604T060238Z.md. Boundary closed; do not reopen for this near-miss.

- **DONE 2026-06-04 · Add beat-SPY-risk-adjusted as a FIRST-CLASS gate metric.** Shipped runner/spy_relative.py (excess-return + tracking-error IR, bars_per_year-correct), wired additive-reporting into walk_forward.py + walk_forward_xsec.py, tests 289→302 green, protected md5s unchanged, IR independently hand-verified. Report reports/SPY_RELATIVE_GATE_BUILD_20260604T103622Z.md. NOT yet a binding gate (surfaced only) — making it binding = separate Cyrus/main call. ORIG: Cyrus directive: "aim to beat the S&P; if we only expect 8%/yr I may as well not do this." Bar = excess return over buy-and-hold SPY, RISK-ADJUSTED (not raw return). Implement: log SPY-relative excess return + information ratio (excess return / tracking-error vs SPY) alongside Sharpe on every walk-forward candidate output. A strategy making 12% at 2x SPY risk is leverage, NOT alpha — gate must catch that. Touches `runner/walk_forward.py` + `runner/walk_forward_xsec.py` reporting. Honest framing for Cyrus already delivered: beating SPX net-of-cost consistently is one of the hardest problems in finance; most candidates will fail this bar, and that's the point.

- **TODO 2026-05-31 · Revive single-stock cross-sectional universe (UNBLOCKED by $1000 paper bump).** Previously shelved purely for capacity ($100/10-names = $10/name noise). At $1000, ~$100/name baskets are runnable — this is where the published market-beating anomalies (Jegadeesh-Titman momentum, AHXZ low-vol) actually live. Wave-4 cross-asset was partly a $100 workaround; now go back to the universe the academic anomalies were written for. Spawn per-archetype backtest subagents (same Bar A discipline). Supersedes/closes the old P3 "$100 cap lift discussion" item.

- **DONE 2026-05-31 · Paper notional bumped $100 -> $1000.** `runner/risk.py` MAX_NOTIONAL/MAX_POSITION 100->1000 (PAPER ONLY; real-money start UNCHANGED at $100 max per GATE Bar E + per-request Cyrus approval). 6 clamp-test fallouts fixed by scaling request notionals 10x (assertions preserved, not weakened). 226/226 green. Live `xsec_momentum_xa_38d2b2` deliberately KEPT at approved $100 params (don't change an approved promotion's conditions the day before first tick); new xsec strategies use the bigger notional. See memory/2026-05-31.md.

- **DONE 2026-05-31 · Wave-5 low-vol IC + gate-robustness rulings actioned (main).** (1) **Bar A #5 clause (f) absolute-return floor added: ≥8.0%/yr net-of-cost on deployed notional**, co-primary guard with Sharpe ≥1.0. Calibration: momentum_xa 11.6%/yr PASS, lowvol barbell 7.5%/yr FAIL (highest Sharpe 1.23 — gaming signature), sector_rot 9.4%/yr (bound by (a)). **RATIFIED by main 2026-05-31** (8% overrode main's 3-5% suggestion — main: "this is when a peer SHOULD override main"). (2) **CRITICAL re-check: `xsec_momentum_xa_38d2b2` clears (f) at 11.6%/yr → promotion STANDS, Monday tick SAFE.** (3) **Low-vol barbell `xsec_lowvol_xa2_440761` NOT promoted** — filed defensive-sleeve-only never-alpha (`reports/DISPOSITION_xsec_lowvol_barbell_20260531T030000Z.md`). (4) **Cross-asset low-vol archetype CLOSED, no wave-6** — PATTERNS.md Pattern #5 (n=3 confirmed). 226/226 green, no code changed. GATE.md History entry added.

- **DONE 2026-05-31 · Wave-5 integrity rulings actioned (main's 3 findings).** (1) Promotion stands on corrected FP Sharpe **1.04** (real 2020-07-27→2026 span; the 1.13 was best-window 2025-Q3, the 2010 span was phantom — cache floor is 2020-07-27). (2) **Promotion-survival condition** written into `reports/PROMOTE_xsec_momentum_xa_38d2b2_*.md` before Monday's tick: two-tier (4wk liveness gate + ≥12wk significance gate: ≥15 round-trips & cost-aware Sharpe ≥0.80). Open Q pinged to main: ≥15-trade floor relocated 4wk→12wk because monthly cadence can't deliver it sooner. (3a) **`walk_forward_xsec` ZeroTradesError guard** — raises when 0 trades across all data windows (the warmup-starvation silent +0.00% trap), `--allow-zero-trades` opt-out, exits 3. (3b) **PATTERNS.md Pattern #4** (hard rule): FP-Sharpe claims must state real data span, never beyond cache floor. 226/226 tests, protected md5s unchanged. See `reports/PROMOTION_RECORD_CORRECTION_20260531T024500Z.md`.

- **DONE 2026-05-31 · `runner/runner_xsec.py` xsec live runner SHIPPED.** 454 LOC, parallel to `runner.py`, handles basket strategies (`decide_xsec`). `tick.sh` dispatches on `decide_xsec` presence. 9 new tests (`tests/test_runner_xsec.py`), suite 204 → 213. Protected files (`runner.py`/`backtest_xsec.py`/`risk.py`) md5-unchanged. Smoke rc=0 → `skip_market_closed`. Subagent died mid-debug on a test-isolation bug (regime test patched `sys.modules` not the package-bound attr); Tessera fixed with `mock.patch.object`. Only remaining step = cron line (see P0).
- **DONE 2026-05-31 · GATE.md Bar A bullet #5 fast-track AMENDMENT SHIPPED.** Cyrus explicit ack 01:42 UTC Discord msg 1510458328147558512. Option A (additive bullet) + V3 operationalization ((V1 OR V2) AND not-catastrophe) + clause-(d) bypass of bullets #1+#3 for #5 candidates. FP Sharpe ≥1.0, MaxDD ≤$200, catastrophe = (r ≤ -1.5% AND r < BH-basket). History entry added. `xsec_momentum_xa_38d2b2` PROMOTED to `strategies/` (candidate preserved in `strategies_candidates/` for audit). Promotion memo: `reports/PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`. `xsec_sector_rot_xa_257225` and `xsec_lowvol_xa_38a206` stay rejected.
- **DONE 2026-05-31 · Basket-aware `MAX_TRADES_PER_DAY` cap.** New helper `runner.risk.resolve_trades_per_day(params)` returns `max(MAX_TRADES_PER_DAY, 2*K)` when a strategy declares `xsec_basket_size: K` in params.json (1 ≤ K ≤ `MAX_XSEC_BASKET_SIZE=12`); otherwise returns legacy cap 4. Wired through `runner/runner.py` (live), `runner/backtest.py::_bt_check_trade` (single-symbol bt), and `runner/backtest_xsec.py::backtest_xsec` (xsec bt). 6 wave-3/wave-4 candidates backfilled with `xsec_basket_size`. Fixes the silent-truncation-at-trade-4 bug flagged by the multi-symbol harness subagent (a 6-leg cross-asset rebalance previously got 4 fills + 2 silent `skip_risk`, biasing backtests). 22 new tests (`tests/test_risk.py` 20 + `tests/test_backtest_xsec.py::TestBasketTradeCap` 2 covering both before/after behavior). Suite 182 → 204. Backward-compatible (any strategy without `xsec_basket_size` keeps cap=4 exactly).

- **DONE 2026-05-30 · PATTERNS.md created** (`reports/PATTERNS.md`). First two entries: Pattern #1 "SPY regime overlay strictly degrades sector-equity baskets" (3 confirmations: TSMOM, xsec momentum, sector rotation); Pattern #2 "Single-data-point class generalization trap" (process pattern, in-position-floor incident as canonical example). Per main's decision: PATTERNS.md is the positive institutional knowledge doc; GATE.md is the contractual floor; don't mix them.
- **DONE 2026-05-30 · Crypto retirement.** 6 strategies (`buy_and_hold_btc`, `sma_crossover_btc`, `rsi_mean_revert_eth`, `breakout_ltc`, `momentum_sol`, `trend_follow_doge`) moved to `strategies_retired/<name>/` with RETIREMENT.md per strategy (full trade history + P&L + reason + resurrection instructions). Cron lines removed. `runner/backtest.py` ALL_STRATEGIES cleaned. `tests/test_backtest.py` import flipped to `strategies_retired.sma_crossover_btc.strategy` (kept as harness test fixture). 182 tests stable.
- **DONE 2026-05-30 · Wave 4 cross-asset archetype backtests.** 3 subagents shipped: `xsec_momentum_xa_38d2b2` (FP Sharpe **1.13**), `xsec_lowvol_xa_38a206` (FP Sharpe 0.97 K=3 / 0.76 K=2-regime), `xsec_sector_rot_xa_257225` (FP Sharpe **0.98** N=150). **Universe-class hypothesis CONFIRMED 3/3**: same code, same harness, different universe (SPY/EFA/TLT/VNQ/DBC/GLD) → wave-3 sector-equity Sharpes 0.30/0.36/-0.09 jumped to 1.13/0.97/0.98. All 3 still REJECT under current GATE.md but for gate-architecture-mismatch reasons, not lack-of-edge. Triggered Pattern #1 expansion + Pattern #3 add in PATTERNS.md and the Bar A amendment proposal (currently in `reports/GATE_AMENDMENT_DRAFT_20260530T190000Z.md`, awaiting Cyrus sign-off; main pulled implicit-approval).
- **OPEN · P3 · $100 cap lift discussion.** Single-stock S&P xsec universes (textbook Jegadeesh-Titman / AHXZ) are unworkable under MAX_TRADES_PER_DAY=4 + $100 cap. Not blocking; cross-asset wave (above) covers near-term xsec exploration. File separately so it doesn't get lost: when bench has ≥1 strategy approaching Bar E or when cross-asset wave also REJECTs, this becomes the next gate to consider lifting. Don't lift unilaterally — affects all risk semantics.
- **DONE 2026-05-30 · Tier 3 design doc 5 main-tightenings applied + audit line** (`reports/TIER3_HARNESS_DESIGN_20260529T171740Z.md`).
- **DROPPED 2026-05-30 · F2 cache-key fix** — audit re-verified, finding was a false alarm. `_cache_path()` already includes `timeframe` as a first-class filename segment; `BTC-USD_1Hour_*.json` and `BTC-USD_1Day_*.json` coexist correctly. See `/tmp/F2_cache_key_audit_response.md`. Subagent flagged a separate, real concern (see P2 below).
- **DONE 2026-05-30 · Saturday weekly leaderboard cron fired at 9am PT; moratorium-lift trigger satisfied.** Leaderboard top 3 still tiny-sample (n=1 each).
- **DONE 2026-05-30 · Bar A bullet #7 smoke fix (`./tick.sh --candidate <name>`).** New `runner/candidate_smoke.py` (~170 LOC) imports from `strategies_candidates/`, calls decide() once with live market data, prints action, exits. Zero DB writes confirmed (tested tsmom/meanrev3d/overnight + negative). Standalone improvement; will be referenced in eventual GATE.md amendment write-up once Cyrus signs off cap=1.
- **WAITING · GATE.md Bar A bullet #1 amendment + bullet #7 update.** Main signed off on cap=1 variant 2026-05-30; awaiting Cyrus ack. Write-up plan in `memory/2026-05-30.md`.
- **TODO · Archetype triage shortlist** *(subagent in flight)*. Output: `reports/ARCHETYPE_TRIAGE_<ts>.md`.
- **DONE 2026-05-30 · Tier 2 regime classifier design doc** (`reports/TIER2_REGIME_CLASSIFIER_DESIGN_20260530T170702Z.md`, 350 lines, 23 sections). Once-daily LLM call, strict-JSON output, `regime_decisions` table for determinism, ~$0.14/mo cost, safe-fallback to `regime_uptrend()`. 8 open questions for main/Cyrus. Implementation deferred to P2.
- **DONE 2026-05-30 · Per-strategy P&L correlation analysis** (`runner/correlation.py` + `--correlation` flag, 9 new tests, 116/116 suite). Pure-Python Pearson (no pandas on box). Live run: only `sma_crossover_btc` × `backstop_test` produced a defined r=-0.568; everything else n/a until strategies accumulate closed trades.
- **DONE 2026-05-30 · Archetype triage** (`reports/ARCHETYPE_TRIAGE_20260530T170659Z.md`). 12 archetypes scored, **7 BACKTEST** (cross-sec momentum, vol-targeted trend, low-vol, short-horizon mean-reversion, PEAD, overnight drift, sector rotation), 4 DEFER, 1 SKIP. 8/12 VERIFIED with named academic citations (5 of those live-web-confirmed before captcha hit; 3 cited from training memory — spot-check before scheduling).
- **TODO · Fan out per-archetype backtest subagents (Bar A).** One subagent per recommended archetype (7 total). Isolated scratch dirs, single committer merges. Cap concurrency — likely 3-4 in parallel, queue rest.
  - **DONE 2026-05-30 · Wave 3 closed.** All three xsec archetypes shipped + REJECTED honestly: #1 momentum (Sharpe 0.30, floor-blocked), #3 low-vol (Sharpe 0.36, edge miss), #8 sector rotation (Sharpe -0.09, no edge). Reports + candidates on disk under `strategies_candidates/xsec_{momentum,lowvol,sector_rot}_*`. Zero promotions. Suite stays at 182. Honest verdict: at $100 / 11-sectors / 2021-2026, equity xsec anomalies don't have enough edge to clear. Need different universe or larger notional before retry.
  - 2026-05-30: Wave 2 results landing one-by-one:
    - **MeanRev3D QQQ:** 🔴 REJECT — 28 trades over 4 years, signal too rare in benign tape, asymmetric +1%/−5% ladder kills expectancy. Candidate preserved at `strategies_candidates/meanrev3d_qqq_cd3fbd/`. Report: `reports/BACKTEST_MEANREV3D_QQQ_20260530T171602Z.md`.
    - **Overnight SPY (filtered + unfiltered):** 🔴 REJECT both variants — cost drag (~67-121 trades/window) eats the entire +0.17%-0.34% gross signal per window. Reports: `reports/BACKTEST_OVERNIGHT_SPY_20260530T171621Z.md`.
    - **TSMOM SPY:** 🟡 REJECT-WITH-CAVEATS — full-period Sharpe 1.35, max DD -0.85%, beats BH-SPY in 6/8 named regime windows including both bears. Bar A bullet #1 fails on a technicality (bear-regime median -0.20% when BH-SPY was -1.27%; strategy LIMITED losses but gate counts it as a loss). Subagent raised a principled question: should Bar A allow "beats BH in regime" as alternative for defensive long-only strategies? Escalated to Cyrus + main. Candidate preserved at `strategies_candidates/tsmom_spy_2951d463/`. Report: `reports/BACKTEST_TSMOM_SPY_20260530T171711Z.md`.
    - **PEAD (8 mega-cap universe):** 🔴 REJECT, but the harness gap is the real story. 18 trades / +$32 on $900 deployed; only TSLA/NVDA/AMZN/JNJ produced any trades because mega-cap earnings reactions don't cross the +3% threshold (literature: PEAD is ~3x stronger in smallest size quintile). Bonus: subagent discovered SEC EDGAR Form 8-K Item 2.02 is a free, viable earnings-date source — reusable for any future event-driven strategy. Reports: `reports/BACKTEST_PEAD_DATA_FEASIBILITY_20260530T171453Z.md`, `reports/BACKTEST_PEAD_20260530T171825Z.md`.
    - PEAD — still in flight.

## P2 — Soon (after weekend sprint)

- **DONE 2026-05-30 · Cross-sectional walk-forward + first xsec archetype (#1 momentum) backtested.** `runner/walk_forward_xsec.py` (~440 LOC), `tests/test_walk_forward_xsec.py` (11 tests), extended `runner/candidate_smoke.py` for xsec candidates (+`tests/test_candidate_smoke.py`, 7 tests). Candidate: `strategies_candidates/xsec_momentum_236b86/` (11 SPDR sectors, K=3, monthly 12-1 rebalance). **Verdict: REJECT** — 5/8 windows fail Bar A #1, Sharpe 0.30 full-period, regime filter strictly worse (sectors all share SPY beta, double-gating). Report: `reports/BACKTEST_XSEC_MOMENTUM_20260530T174735Z.md`. Suite 182 passing. Smoke OK.
- **DONE 2026-05-31 · GATE.md Bar A bullet #5 fast-track amendment** (Cyrus explicit ack 01:42 UTC). Shipped V3 ((V1 OR V2) AND not-catastrophe) + clause-(d) bypass of #1/#3. Later hardened with clause (f) absolute-return floor ≥8%/yr-on-deployed (RATIFIED by Cyrus 2026-05-31 03:25). All open decision points (operationalization, threshold, clause-(d) ambiguity, denominator guard) RESOLVED. No open GATE.md items.
  - **UPDATE 2026-05-30 · sector-rotation backtest = third data point.** Faber GTAA N=200 sits at 22-24% in-position (misses by ≤3pp). N=150 cleanly clears at ~38% in-position. The floor is NOT fundamentally incompatible with xsec basket strategies — only with fixed-K rotators. Faber-style adaptive (0-to-11) basket sizes the strategy out of the floor problem naturally. **All 3 wave-3 archetypes REJECT, but for genuinely different reasons:** #1 momentum (floor + low Sharpe), #3 low-vol (Sharpe miss, NOT floor), #8 sector rotation (no Sharpe edge — not floor). The right reframe for main: **bench is rejecting these for lack of edge at $100/sectors/2021-2026, not for gate mis-calibration.** Two recurring xsec findings to bring: (a) $100 cap + 11-sector equity universe may be too constrained for any equity xsec anomaly to clear; consider raising notional OR adding cross-asset (bonds/REITs/commodities) before next xsec attempt; (b) SPY regime overlay is strictly degrading for sector-equity baskets — confirmed 3 times now (TSMOM, momentum, sector-rotation). Worth codifying as a no-go pattern.

_…(truncated; 232 total lines in source)_

---

## making-money

### Latest daily memory: `memory/2026-06-23.md`

## Nightly distill — 2026-06-23 02:20 PT
- No new Cyrus interaction or agent work today.
- Status unchanged: waiting on uncle Eddie's response to the agency pitch (sent ~2026-06-21).
- EXP-3 PagePeek still running (verdict ~2026-07-04); EXP-2 SiteLens fully paused.
- Pitch deck live at http://40.65.93.84:8080/agency-pitch.html (self-healing watchdog).
- MEMORY.md reviewed — no stale entries, no new durables to promote.

### BACKLOG.md

# BACKLOG.md — making-money

_Triage regularly. Keep this CURRENT-STATE and TIGHT — it is read on every autonomous tick, so verbose run-by-run changelog belongs in `memory/YYYY-MM-DD.md`, NOT here. (Compacted 2026-06-09: the old multi-hundred-KB Recently-shipped changelog was the #1 per-tick context bomb; full detail is preserved in the daily logs.)_

## Active
- **🎯 AI AUTOMATION AGENCY (current direction, Cyrus confirmed 2026-06-20).** Build and run AI automation agency for SMBs. I run: lead research, outreach, workflow builds. Cyrus runs: sales calls. Stack: n8n/Make.com + OpenAI APIs. Target: $5–15K/mo in 3–6 months. Zero capital. **Next: define service offering (workflow automation / AI chatbots / outreach automation), build prospect list (first 10 SMBs), draft outreach sequence.**
- **EXP-2 — SiteLens FULLY PAUSED (2026-06-21).** Cold outreach + follow-up cron both removed (bounce storm). 278+ emails sent; 0 replies. Not the active mission. Kept for verdict reference only: `node build/exp2-loop/report.mjs --json`.
- **EXP-3 — PagePeek Chrome extension LIVE (published 2026-06-20).** 14-day organic install window running; verdict due ~2026-07-04. Day-1 baseline: 0 installs. Check: `node build/exp3-chrome/install-log.mjs`. Reddit/HN posts drafted (`pagepeek-community-posts.md`) — Cyrus must post manually (datacenter IP blocked).
- **EXP-1 — pSEO READY-TO-FIRE.** `build/exp1-pseo/`; only needs domain (~$12) + `npm run go`. Not yet fired.

## On hold (pending Cyrus)
- **App Guardian — PARKED (not killed).** Honest EV ~$600–1,500/mo, tail to low-5-figs/mo, ~0% Base44 exit → below the $10k/mo floor. Revivable cheap floor. Assets: `research/app-wedge-candidates.md`, `research/slugs.txt` (21,301-slug Shopify index). Its audit-tool research now feeds EXP-2.
- **Live AI copilot (real-time conversation assistant)** — prototype `live-copilot/` + `research/live-copilot-mvp-scope.md` delivered. Parked behind the mission; revivable if a real-time-conversation vertical becomes the pick.
- **Carson Reed agency playbook** — operator build-out shipped (`research/carson-reed/` + `build/pillar{1,2,3}` + `build/phase0-aicaller-demo/`). Real local-lead-gen agency model; income claims asserted-not-shown. Superseded as the lead by the viral-swing pivot; kept as reference/fallback (Phase-0 AI-caller kit needs only a ~5-min Retell signup to revive).
- **Income-path lanes** — `income-path-research.md` + `playbooks/lane2-freelance-writing.md` (fast-cash fallback). Overtaken by the 06-08 direction but kept.
- **Algo trading arb, TikTok Shop, Micro-SaaS** — researched 2026-06-21 in opportunity scan (`research/opportunity-scan-2026.md`). All behind the agency path; revisit if agency stalls.
- **Open questions (let them surface naturally):** weekly time budget; starting capital; off-limits categories; existing leverageable assets.

## Ideas (unvetted, parking lot)
- Reusable mechanics from YouTube research (pre-call nurture drip; 3-pillar pitch frame; 3-day paid-ad test framework; opt-in→call→coaching funnel).
- AI-services arbitrage in non-saturated verticals.
- Productize Cyrus's own workflow (agent-ops / multi-agent coordination) — needs his blessing.
- Newsletter / build-in-public angle (no face-on-camera).

## Hygiene
- Weekly: review last 7 days of `memory/`, distill into MEMORY.md, refresh HANDOFF.md (one page).
- Keep THIS file tight + current-state. Detailed per-tick "what I shipped" goes in `memory/YYYY-MM-DD.md`, not here. When marking something shipped, collapse it to current-state — do not append a long narrative.

## Recently shipped
_(One-liners only; full detail lives in `memory/YYYY-MM-DD.md`. Older entries age out — don't accumulate changelog here.)_
- **2026-06-21** — Full opportunity scan completed (`research/opportunity-scan-2026.md`); AI Automation Agency confirmed as active direction by Cyrus.
- **2026-06-20** — EXP-3 PagePeek published live on Chrome Web Store. 200-email outreach batch3 sent (278 total). Follow-up cron installed. Community posts drafted for Cyrus to post manually. AI Automation Agency direction locked.
- **2026-06-18** — EXP-2 ignited: 89 personalized outreach emails sent (9 seed list + 15 Hunter.io + 65 batch-2 SMBs across 12 verticals). Reply-monitor cron running every 2h. K-factor measurement window open (2–4 wks). sitelume.app fixed (pm2 ESM bug → nohup + @reboot crontab). EXP-3 PagePeek submitted to Chrome Web Store 2026-06-17; review expected ~Jun 20.
- **2026-06-10** — 23 autonomous correctness/calibration ticks (all $0, no gates). Closed "static seeds partly parked" gate-day risk — pool refreshed to 222 DNS-verified seeds. EXP-1 made genuinely decisive. Per-tick detail in `memory/2026-06-10.md`.
- **2026-06-09** — EXP-2 hardened to ~1121 assertions across ~20 ticks; V3 ShopLens fire-ready; `preflight.mjs`/`decide.mjs` decision harnesses shipped.

