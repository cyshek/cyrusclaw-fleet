# PEER_STATE.md

_Auto-generated digest of peer agents' latest daily memory + current BACKLOG.md._
_Generated: 2026-06-20 11:00 UTC_

---

## job-search

### Latest daily memory: `memory/2026-06-20.md`

# 2026-06-20 Daily Log

## Nightly distill cron (12:25 AM PDT)
- No new activity on 2026-06-20. All work from the prior session is in 2026-06-19.md.
- Reviewed MEMORY.md + BACKLOG.md — both current, no stale entries found.
- DEBUNKED ledger in MEMORY.md already has the 2026-06-19 hCaptcha + Stripe fixes.
- No promotions needed tonight; yesterday's distill (2026-06-19 evening) was complete.
- bootstrap-guard trimmed job-search/MEMORY.md: 20773→19836 chars (backup kept)

### BACKLOG.md

# BACKLOG.md — job-search agent (workspace root)

**Last triaged:** 2026-06-19

## ✅ Meta auto-apply runner — DONE (2026-06-17/18)
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
5. **Fix dead web_search provider (P2)** — kimi key missing; enables search-driven "who's hiring PMs" discovery. (May already be working — verify.)

## Doctrine (read FIRST every chain)

**ATTEMPT EVERY ROLE.** No cohort-level pre-skips. Strict-Ashby / Lever-hCaptcha / Apple all get their 60-min per-role budget regardless of prior chain diagnoses. Cohort failures get logged per-role but never used to silently skip future rows. Manual queue is for ZERO-attempt rows only.

## Active (working on / next up)

### ✅ 2026-06-11 — [DISCOVERY, SHIPPED] JobRight.ai discovery-only adapter (commit `362029a`)
Built + wired `adapters/jobright.py` (406L) + test + fixture + companies.yaml SOURCE entry + tracker_merger.py (36 lines: `jobright:<jobId>` source_key, status='manual-apply', excluded from auto-submit queue — provably 0 rows enter burndown SQL). First live run: 331 fetched across 12 categories, 5 inserted, newest publishTime minutes-fresh. 12 pytest green. DB backed up `tracker.db.bak.20260611-205952-jobright-adapter`. Single-writer held. **Known limitation:** applyLink 100% wrapper URL (`jobright.ai/jobs/info/<id>`); raw ATS URL behind authed `/swan/*` (401 anon) — submission upgrade GATED on Cyrus session cookie + API test. Rows are freshness/discovery signal only.

### 🕐 2026-06-11 — [PENDING CYRUS] JobRight session cookie — one-time ATS URL test
Asked Cyrus to grab session cookie (Application→Cookies on jobright.ai OR Network header copy, DM only). One replay against `/swan/job/detail?jobId=<id>` answers the make-or-break: does the authed API expose the raw ATS URL? YES → upgrade adapter + M build submission path. NO (withheld by design) → keep as radar-only. No rush; don't chase biweekly cookie treadmill until this is confirmed first. **PENDING Cyrus reply.**

### 🕐 2026-06-11 — [PENDING CYRUS] Brave Tactic-3 → stage 3a2 wiring (LinkedIn NO_BOARD recovery)
`linkedin_ats_resolver_v2.py` Brave web-search fallback ("Company" careers <role> → real ATS link) is orphaned — NOT called by the live LinkedIn resolution chain (stages 3a0→3a→3a2). Already-paid `BRAVE_SEARCH_API_KEY` sits idle. Wiring it into stage 3a2 recovers a fraction of LinkedIn→company-site rows that fall through to NO_BOARD. Proper pipeline integration + tests (NOT a one-off). Offered to build; Cyrus pivoted to JobRight before approving. **PENDING go-ahead.**

### ✅ 2026-06-18 — [ENGINE BUG, FIXED] Ashby `final_clobber_guard` clobbers radio-picked state location (Thumbtack 2287) — FIXED commit b710f1d
FIXED. chain_035b: skip typeahead refill when a plan radio's field-path tail matches the location tail and has a checked DOM option. `_skip_loc_refill=True` → stability gate converges immediately → `location_ok=True`/`location_stable=True` forced. 167 tests green.

### 🟡 2026-06-11 — [ENGINE, IN-FLIGHT — top Workday unlock] Workday cross-nav WE-block fix (root cause CORRECTED: count-never-plateaus, NOT date-persistence)
**Designed + backed up, NOT yet landed/validated.** Builder subagent `we-persist-fix` ran a true create_fresh live probe (Nvidia 2829, EXIT-5 reproduced) and DEBUNKED the old "WE dates don't persist across Next-nav" theory — typed dates DO persist (DOM + React fiber + hidden inputs). Real cause = the WE-block COUNT never plateaus: (1) the resume PARSER manufactures a blank required 'add-another' block from the PDF each visit, (2) the 'successfully uploaded' marker vanishes on revisit → `file_present=False` → re-upload → parser re-runs → more blocks (cap didn't increment on the skip path) → total 4→5→6 → EXIT-5. **Fix design:** resume-cap-that-actually-holds (never re-upload after visit 1 on a fresh acct) + `harden_my_experience_before_next()` (delete every empty WE block, re-measure until 0-empty AND total stable ×2) + replace the lying `start_filled` single-source read. Backup `_workday_runner.py.bak.run4-wepersist` made. **NEXT WORKER:** finish landing behind the pytest gate (`test_workday_we_persist.py` + full `test_workday*.py` green), then re-run the 4-row cohort Nvidia 2829/Gates 2542/Boeing 2546/PayPal 2891, then the teed-up GEICO 2021 R0062160 end-to-end submit (already at app_url, prep_status=manual_ready). STATUS: `projects/job-search/role-discovery/STATUS-we-persist-fix.md`; full root cause in MEMORY.md DEBUNKED ledger (2026-06-11).

### ✅ 2026-06-08 (9:30 PM) — [ENGINE, durable cohort fix] `full_address` resolver closes the bare/"Home Address" LABEL_RULES gap — SHIPPED + unblocked Zuora 2755
**DONE.** A bare `Home Address`/`Address`/`Current Address`/`Your address`/`Candidate Address` single-line text field returned **None** from `greenhouse_dryrun.find_resolver` → no plan emitted → row banked blocked (`prep-blocker: Home address field no LABEL_RULES match`). The address rules only covered street/legal/mailing/residential/address-line. **Fix (`80064ce`):** added `r_full_address` (full one-line street+city+state+zip; degrades to city/state w/o street so it never blocks; defers to city_state on dropdowns) + needles `home/current/your/personal/candidate/full address` + a bare `address` catch placed **after** `address line N` and **after** `email` (33-label over-match probe = 0 mis-routes; `email address`→email, `street address`→street, `mailing address`→city_state all preserved). 3 regression tests; full suite **918 passed / 53 subtests / 0 regressions**. **DATA:** live `--no-submit` dryrun on Zuora CSE jid 7770757 (Remote-US) now **READY filled=16 unresolved=0** with `Home address` filled → flipped 2755 `blocked→queued`, cleared stale block_reason (backup `tracker.db.bak.zuora-addrfix-20260609-043713`, integrity ok before+after, 1 row, blocked 155→154). **Unblocks:** Zuora 2755 now auto-submittable + every future GH/Ashby board with a bare/Home address field fills instead of banking blocked. (See `memory/2026-06-09.md` ~21:30.)
- **Next phantom-audit target noticed:** 13 blocked rows still carry vague `OTHER`/`HARD-WALL`/`gh-blank-label-required`/`label-gap` reasons (Ambient 2563, Anara 2606, Antithesis 2781, Cartesia 1384, Curri 2557, Drata 2548, Knowtex 2593, Ready 2605, Snowflake 2527, Nintendo 2748, Paystand 2799, Pure Storage 2688). Re-derive each from a live dryrun — likely same label-less-required class or already-closed reqs. One-pass sweep would convert several to submittable/honest-closed + stop them resurfacing.

### ✅ 2026-06-08 (7:35 PM) — [HYGIENE, durable — ROOT CAUSE of "tick errored before commit → fix lost/redone"] Bulk git-track engine — SHIPPED
**DONE.** Was: only 32 tracked files (12 .py), 284 untracked .py, NO .gitignore → any tick editing an untracked engine file then erroring before its commit lost the fix. **Shipped (3 commits `af54e30`/`30f5ace`/`bef2447`):** new root `.gitignore` (excludes all secrets/`.linkedin-li-at`/`*creds.json`/`*.capsolver-key`/passwords/cookies, `tracker.db`+400 `.bak`, the 216M `.venv`, `-debug` dirs, `__pycache__`, the 2 probes — every secret path verified ignored via `git check-ignore`); new `role-discovery/pytest.ini` (`python_files=test_*.py` + `--ignore` probes → naive `pytest --collect-only` now 913 tests/0.74s/exit0, was hanging on the probes); bulk-added 265 role-discovery .py (adapters ×19, 76 `test_*.py`, runners/`_gh_submit`/`_icims_runner`/`capsolver_client`/`twocaptcha_client`) + 19 root project .py; `git rm --cached tracker.db` (file unchanged on disk, integrity ok). **Caught+redacted a live Webshare proxy cred hardcoded in `test_twocaptcha_client.py`** → RFC-5737 dummy (0 cred occurrences in final diff). Tracked tree 32→347 files (12→326 .py), zero secrets/DB/venv tracked. Full suite 913 passed, 0 regressions. **Loss-vector permanently closed.** (See `memory/2026-06-08.md` ~19:35.)

### ✅ 2026-06-11 — [DATA-INTEGRITY, SHIPPED] `_backfill_drain_status.py` promoted to idempotent post-drain RECONCILER (commit `2002f87`)
4 phantom-blocked rows recovered: Baseten 944/946/947 + Mercor 1237 were `status='blocked'` (stale label) but had real `FormSubmitSuccess` on disk from the 06-08 residential drain. Root cause: drain driver writes STATUS.md + `response_status='submitted-residential'` but NEVER flips tracker `status`/`applied_by`. Fix: `_backfill_drain_status.py` upgraded to an idempotent reconciler (run after every drain). Applied count now: DB status='applied'=546, sheet Applied=606. See `memory/2026-06-11.md`.

### ✅ 2026-06-08 (5:05 PM) — [DATA-INTEGRITY, SHIPPED] Relabeled 8 FALSE-applied score-gate rows applied→blocked
Autonomous tick found 8 rows marked `status='applied'` that were NEVER confirmed submitted — all hit the Ashby reCAPTCHA score-gate (warmed-profile/residential infra wall) and were mis-marked applied to stop re-grinding. `applied` lied to every "what needs applying?" query + dropped 8 real roles from the pipeline. Flipped applied→blocked (backup `tracker.db.bak.false-applied-relabel-20260609-001231`, integrity ok before+after, applied_by/applied_on cleared, RELABEL marker appended): **944/946/947 Baseten · 1237 Mercor · 2602 Modern Treasury · 2658 Benchling · 2664 Hudu · 2782 Antithesis**. They now sit in the blocked re-attempt queue for the next warmed-profile pass. (2727 EliseAI was left `applied` here, but the 8:00PM tick flipped it `applied→blocked` too — it was also false-applied (PREP-READY, never submitted) and its "field-gap" reason was a misdiagnosis; see the comp-cohort DEBUNKED item below.)

### ✅❌ 2026-06-08 (8:00 PM) — [ENGINE, Ashby cohort] "Field-walker drops compensation-expectations free-text" — DEBUNKED (premise was stale) + cohort genuinely closed
**This was a MISDIAGNOSIS, not a real gap.** The 5PM triage of 2727 EliseAI coined "required comp free-text is ABSENT from the dryrun plan" — but the cached dryrun (`applications/dryrun/eliseai-d400f45b-*.json`) shows the comp field **PRESENT, filled `Open to discuss`, ready_to_submit, blockers=0**. `ashby_dryrun.find_resolver`→`gh.find_resolver` already maps `compensation expectations`/`salary expectations`→`compensation` and `r_compensation` returns "Open to discuss"; reproduced on the venv against the exact EliseAI/Dash0 label + 9 variants = all resolve. **EliseAI 2727 + Dash0 2758 both reached PREP-READY; Dash0 2757 is already `submitted`.** The cohort never had a comp engine gap — the rows just never got a residential submit pass.
- **STILL did real engine work:** a coverage sweep found 2 phrasings the needles genuinely MISS — `expected total compensation`/bare `total compensation` (no "expectations" suffix) + abbreviated `comp expectations`/`comp range`. Added 4 needles to `greenhouse_dryrun.py` LABEL_RULES (+regression tests in `test_gh_label_rules_yc.py`; no over-match collisions). **Full suite 915 passed, 53 subtests, 0 regressions. Committed `89bffcb`.**
- **DATA:** 2727 EliseAI was false-applied (status=applied but response_status=NULL + STATUS.md still PREP-READY = never submitted) → flipped `applied→blocked`, cleared applied_by/on, corrected the misdiagnosed block_reason (backup `tracker.db.bak.eliseai-falseapplied-relabel-20260609-030510`, integrity ok before+after). Now in the residential re-attempt queue with 2758.
- **Remaining for 2727/2758 = a short residential submit pass** (Ashby score-gate = egress IP, crackable via `_residential_browser.sh`), NOT engine work. (See `memory/2026-06-09.md` ~20:00.)
- **Caution promoted:** stale auto-banked `block_reason` strings keep LYING (3rd false "batch4"/"field-discovery" reason this week). Re-probe from evidence (response_status + STATUS.md + cached dryrun) before "fixing" a banked reason.

### 🆕 2026-06-08 (4:00 PM) — [DATA, small] 9 Netflix `status=''` rows are UNCLASSIFIED → stranded out of queue AND skip
Found during the empty-status census (google-yoe-knockout tick). 9 Netflix rows have real `explore.jobs.netflix.net` ATS URLs but **no `llm_*` verdict** (crawled, never classified) so they sit `status=''` with no routing: 2870 PM Enterprise Dev Eng, 2874 TPM L6 Identity, 2875 Finance PgM, 2879 SA Total Rewards, 2880 HR PgM, 2882/2883 Support SE L5, 2885 SA L4 Workday, +1539 (SE L5, also `linkedin-offsite-unresolved`). FIX = run `jd_llm_classifier` over just these (or confirm the next scheduled classifier pass sweeps `company='Netflix' AND status=''`). Cheap, unblocks routing of a real megacap-adjacent ATS cohort. (Netflix is NOT on the blocklist — these are legit.)

### 🔴 2026-06-08 — [BLOCKED: datacenter-IP burns li_at in-browser] LinkedIn-stranded resolver — needs residential egress END-TO-END + pacing
**Two live runs 2026-06-08 (subagents) corrected the framing TWICE.** Run1 stopped on a stale cookie. Cyrus dropped a FRESH cookie (…vbPh), which tested HTTP-200 via curl (direct + proxy) at 04:34. Run2 then ran `--apply` in-browser and STILL got 0/26 — because the in-browser run from the bare Azure datacenter IP (resolver default CDP 18800) loaded ~26 authed `/jobs/view/` pages and **LinkedIn force-deleted the li_at server-side within ~2 min** (documented at resolver L811). Post-burn the cookie is dead even via residential proxy. DB was auto-restored (the run had wrongly flipped all 26 → `manual-apply`; that was authwall-disguised-as-no-ATS, NOT real Easy-Apply — reverted, app_url never touched, integrity ok).
- **Real stranded count = 26** (NOT ~105 — most historical rows already resolved; 61 already carry LINKEDIN-AUTHED notes). The old ~105/121 figures are stale.
- **REAL blocker = EGRESS-IP TRUST during the BROWSER run, NOT cookie freshness.** A fresh cookie passes curl-200 yet the in-browser datacenter-egress run BURNS it (LinkedIn kills li_at on browser `/jobs/view/` loads from the flagged Azure IP, then 429s). curl-200 ≠ in-browser-safe. So "refresh the cookie and re-run" does NOT work on its own — it just burns each new cookie for 0 resolves.
- **Verified working (once cookie is fresh):** residential relay (`_proxy_relay.py` → Webshare), Chrome v149 CDP binds IPv4 `127.0.0.1` when port uncontested, resolver default `http://127.0.0.1:18800` (managed browser), correct DB target (`projects/job-search/tracker.db`). No code fixes needed.
- **ACTION (infra, to actually unblock the 26):** (1) FRESH `li_at` in `projects/job-search/.linkedin-li-at`, AND (2) point the in-browser Chrome at a RESIDENTIAL-proxied egress END-TO-END for the whole run (`JOBSEARCH_CDP` → residential-proxied Chrome, NOT the default datacenter 18800), AND (3) PACE it — long delays + tiny batches so a burst of 26 authed loads doesn't trip the kill. All three together, or it re-burns. Until residential end-to-end egress is wired, this stays BLOCKED — do NOT keep re-running on fresh cookies (wastes them).


### ✅ 2026-06-03 — YC BREADTH SHIPPED: companies.yaml 384 → 735 (+354 net-new, ~doubled crawl surface)

`yc_discover.py` (7 tests green) pulls the public yc-oss directory (5,950 YC cos), filters Active+hiring+US (1,202), probes each through the proven ATS slug-resolver, dedups vs companies.yaml, emits merge-ready entries. **354 net-new verified employers merged** (252 ashby / 72 gh / 30 lever, 7,518 open jobs). Backup: `companies.yaml.bak.yc`. run.py `run_one` patched to exclude `note` from adapter opts. Re-runnable as YC adds hiring cos. **This is the durable fix for "submit queue runs dry" — more companies = more attemptable rows every weekly crawl.**

### 🌱 2026-06-03 — Discovery breadth WIDENED: companies.yaml 735 → 828 (+93)
`yc_discover.py --ignore-hiring-flag` (YC isHiring flag is stale; keep all Active, let live ATS probe filter). +93 verified employers (Salt Security, Inversion Space, SkydropX, Onebrief, Pyka, Formal…). Crawled 828-co list (794 OK, robustness fix held) → +9 tracker rows → 6 attemptable, all worked: **Anduril TPM 2656 + Formal SE 2663 SUBMITTED** (Formal came straight from the new cos — breadth feeds lands), Flip geo-knockout, 3 ACLU PRD-file-required. **Confirmed total 349.**

### ✅ 2026-06-08 (5:30 PM) — strict-Ashby score-gate cohort DRAINED: 21/24 SUBMITTED today + Date-widget engine fix CLOSED
The 24-row residential-egress drain is DONE for 21 rows (r3:4 + r4:12 + r5:5 — all FormSubmitSuccess, disk+DB verified; see `memory/2026-06-08.md`). Proven: Ashby reCAPTCHA score = form-POST egress IP, not profile warmth (21× confirmed via Webshare 82.23.97.223). **Remaining 3:**
- **2549 OpenAI** — Date-widget engine-edge is now FIXED end-to-end (dryrun `Date→input_date` ISO normalize + runner `commit_ashby_date_fields` `_valueTracker`-reset; live `--no-submit` probe on 2549 PASSED — `_valueTracker` holds 06/23/2026; 901 tests green, committed 2026-06-08 5:30PM). NOT score-gated, NOT applimit. **Only needs a short residential submit pass on JUST 2549 to LAND** (prep+commit proven, FormSubmitSuccess not yet recorded; left blocked/applied_by=NULL). OpenAI may re-clobber Email/text at submit → FINAL re-assert path should cover it.
- **1434 Klarity** — React-store radio, HARDEST engine-edge, still OWED. Residential passes the score-gate; real wall = required custom radios (sponsorship + SF-relocation) don't reach Ashby's submit serializer even after DOM checked=true + Playwright click + React onChange (30/30 isolated tests green, submit still banks Missing-entry). Needs deeper React-store fill or a true user-gesture.
- **891 Tavus** — GENUINE warmed-profile score-wall (A/B-proven on SAME IP/run: Tavus rejects while Firecrawl submits). LEAVE IT — don't re-grind on residential.
Drain mechanics proven; keep passes SHORT (≤5 rows) — long tails context-overflow but per-row STATUS.md always recovers.

### ✅✅ 2026-06-08 (LATE) — SUPERSEDES all "strict-Ashby = Cyrus-side / warmed-profile-required / IP-walled" notes below
**The strict-Ashby reCAPTCHA score-gate is AUTO-SUBMITTABLE NOW with existing infra — NOT Cyrus-side, NO warmed real profile, NO new spend.** A/B control (subagent `residential_egress_scope`, 2026-06-08): SAME plan/runner/session, only egress IP differs → Azure datacenter = `RECAPTCHA_SCORE_BELOW_THRESHOLD`/spam-flag, **residential IP (already-funded Webshare 82.23.97.223) = `FormSubmitSuccess`.** The 06-03..06-08 "needs warmed Google-engagement profile / fingerprint-stealth / Cyrus-side" framing (sections below, incl. the STATUS RECONCILE + NEXT LEVER notes) was WRONG — the differentiator was the server-weighted request IP all along; the 06-05 retest that "disproved" residential was masked by a stale Chrome-92 stealth UA (its own bot signal). Path: `_proxy_relay.py` (:18901) → Webshare → proxied Chrome (CDP 19223, Chrome-149 UA) → `_ashby_runner.py` via `JOBSEARCH_CDP`; launcher `role-discovery/_residential_browser.sh`. **~24 score-gate rows now drainable for ~$0.07 total.** Also fixed a `def patch_plan_default_empty_radios` NameError that had broken ALL Ashby submits since the 06-08 19:01 edit (ashby tests 7/7 green). Drain command + 24-row list: `memory/2026-06-08-residential-egress-scope.md`. (First 3 proof rows 2888/2899/2459 = DB-recorded, STATUS.md bookkeeping was skipped → re-confirm on the next drain pass.) Distinct walls residential does NOT fix: lever-hcaptcha-ENTERPRISE rqdata, eightfold Filestack upload, NYC DataDome solve-IP binding, openai-applimit-180d (time-gated).

### 📌 2026-06-08 STATUS RECONCILE — ✏️ UPDATED 2026-06-08 PM: strict-Ashby tail is NOW auto-submittable via residential egress (was wrongly "Cyrus-side")
**Census 2026-06-08 (verified in tracker.db) of blocked Ashby rows:** 33 OpenAI = `openai-applimit-180d` (hard 180-day apply cooldown, time-gated, NOT retryable, NOT a bug); ~24 = `ashby-score-gate*` (Baseten/Tavus/Mercor/Anrok/Klarity/Atticus/Lance/etc. — the reCAPTCHA score-gate); 4 = `proxy-ip-walled`; **39 = blocked with NO recorded reason** (triaged 2026-06-08, subagent `ashby_noreason_triage`); **128 already applied.** ✏️ **CORRECTION (2026-06-08 PM):** the ~24 score-gate rows are NO LONGER Cyrus-side — they are AUTO-SUBMITTABLE via the proven residential-egress path (`_residential_browser.sh`, A/B-proven, ~$0.07, no new spend). The earlier "these are CAPTCHA-SCORE-WALLED, the real unblock is Cyrus-side warmed-profile" takeaway is OVERTURNED: the score is driven by the form-POST EGRESS IP, not profile warmth. A drain subagent (`ashby_resi_drain`) is working the cohort. The engine fill/prep was already solid; the residential IP closes the last wall.

### ✅ 2026-06-03 — strict-Ashby score-gate CRACKED (Clipboard 350) + corrected diagnosis
**The gate is a BOT-FINGERPRINT score, not IP-trust** (disproves days-old "IP-walled" label). Wired residential browser egress (`_proxy_relay.py` → proxied Chrome `[::1]:18900`, `JOBSEARCH_CDP`) + native in-browser v3 token (`JOBSEARCH_INBROWSER_V3`) + **playwright-stealth (`JOBSEARCH_STEALTH=1`) = the actual lever** → Clipboard SUBMITTED. But threshold is **PER-TENANT**: 13-row sweep (`stealth_ashby_sweep.py`) cracked only Clipboard; Baseten/Mercor/Tessera/Anrok still gated (need warmed real-profile browser w/ Google engagement history). 2 form-validation rows = React-Select fill-commit races (Snowflake-2527 class). Full writeup in TOOLS.md. **Confirmed total 350.**

#### ✅ 🔭 NEXT LEVER for the strict tail — RESOLVED 2026-06-08 (residential egress, not warmed-profile)
**This was wrong.** The strict-Ashby tenants did NOT need a warmed real Chrome profile / Cyrus's Google session / manual submission. They needed **residential EGRESS IP during the form-POST** — the reCAPTCHA-v3 score is dominated by the server-side request IP (Azure datacenter = low score), not by profile engagement history. A/B-proven 2026-06-08 (see the ✅ STATUS RECONCILE above). The already-funded Webshare residential proxy + `_residential_browser.sh` is the lever; ~$0.07 to drain the whole cohort, no new spend, no Cyrus action. Stealth tooling is still built+reusable but the v3 token + Chrome-149 UA + residential IP is the actual working combo.

### ✅ 2026-06-03 — 5 net-new YC rows SUBMITTED (339→344) + 2 GH LABEL_RULES wins

Attain PM, Embrace SE, Robinhood Futures Risk PM, Alpaca PM ×2 — all GH /confirmation. Robinhood+Alpaca unblocked by LABEL_RULES (job-code, mailing-address, legal-birth-name, compensation).

### ✅ 2026-06-03 (12h-nonstop) — +3 more real (344→347) + 3 engine wins; fresh queue EXHAUSTED
**Submitted:** Anduril TPM (345), Last Call Media civic-tech PM (346, Workable POST 201), Speak PM (347, permissive Ashby).

_…(truncated; 263 total lines in source)_

---

## openclaw-updates

### Latest daily memory: `memory/2026-06-20.md`

# 2026-06-20

## Nightly Distill (01:00 PDT / 08:00 UTC)
- No interactive work today (Jun 20). Quiet Saturday.
- No kernel/apt/openclaw changes detected.
- No Cyrus requests or escalations.
- BACKLOG unchanged from Jun 19 — "Harden kernel reboot flow" still pending (auto, no Cyrus action needed).

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

### Latest daily memory: `memory/2026-06-21.md`

# 2026-06-21

- Memory watchdog nudge received from `main` (127h stale). Running nightly discipline pass.
- Status: standby agent. No active trips, no Cyrus interactions since 2026-06-16.
- Gap days (2026-06-17 through 2026-06-20): no activity logged — consistent with zero in-flight travel work.
- MEMORY.md reviewed; no new durable lessons to promote. Content current as of this pass.
- No open questions resolved; no new ones added.
- No BACKLOG changes — still waiting on Cyrus for scope/mandate/preferences confirmation.

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

---

## trading-bench

### Latest daily memory: `memory/2026-06-20.md`

# 2026-06-20 (UTC)

## Nightly distill — 2026-06-20 09:00 UTC (2:00 AM PT)

- No interactive work today (Saturday). All substantive activity was logged yesterday (2026-06-19):
  - PEAD v2, PEAD market-neutral (both REJECT)
  - TQQQ stress test (robust, 2022 DD is universal binding constraint)
  - Intraday data spike (Alpaca SIP confirmed free; path unblocked for future use)
  - Intraday mean-reversion backtest (REJECT — edge = cost, structurally backwards in bull markets)
  - Bear-regime complement backtest (GLD only viable; no combo passes PROMOTE gate; C3-TQQQ+GLD best risk-adjusted at Sharpe 1.081, MaxDD -15%)
  - Cache purge: data_cache/yahoo/ cleared (4.1G)
  - Nightly post-market reviews (0 trades both days, leaderboard unchanged)
- MEMORY.md: no new durable lessons to promote today
- BACKLOG.md: no changes needed; `leveraged_long_trend` still pending formal gate write-up; all others resolved
- State: quiet weekend, no anomalies, no runners fired

### BACKLOG.md

# BACKLOG.md — trading-bench

Single source of truth for what's next. Updated as items land or get re-prioritized.
Format: priority [P0 blocking / P1 next / P2 soon / P3 someday] · status [TODO / WIP / DONE / DROPPED] · brief.

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

**[V] 6. Edge-calibration meta-model — SCAFFOLDED 2026-06-14** ⏳ pass-through until 30 round-trips
`runner/edge_calibrator.py` live + hooked into runner.py. Logistic regression on [n_round_trips, win_rate, avg_hold_bars, kelly_raw, recent_vs_all_winrate]. Calibration multiplier = 2*P(win)-1. Currently 14/30 trips — auto-activates when gate crossed, no manual intervention needed.

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

- **P0 2026-06-13 · ANOMALOUS DEPLOYMENT — `breakout_xlk__mut_c382b1` LIVE AT 10x NOTIONAL, UNREVIEWED.** Deployed to `strategies/` at 2026-06-12 05:08 UTC WITHOUT Tessera code-review (daily log said "pending review"). params.json has `notional_usd: 1000.0` (10x roster parity). First live order ($1000 XLK buy, order 702733c2) stuck at `pending_new` — never confirmed filled. ALSO still in `strategies_candidates/` (cp not mv). **MUST RESOLVE NEXT SESSION:** (1) audit how it got deployed; (2) do actual code-review; (3) correct/remove if notional or code is anomalous; (4) reconcile pending order with Alpaca paper API.

- **TODO 2026-06-09 · ADD FOREX as a real lane (Cyrus-prompted, my call — decided in-channel).** Cyrus asked why stocks not crypto/forex + noted FX *feels* predictable; FX had **never been evaluated** (grep-confirmed 0 prior work). Decision: ADD FX as a parallel lane (NOT a pivot off stocks, NOT a crypto revisit — crypto stays dead on the ~4% Alpaca round-trip cost). **Why FX is worth it:** spreads ~0.5–1bp = cheaper than crypto AND stocks, so edge that dies in crypto can clear in FX; clean trend-persistence; 24/5 no overnight gap. **The catch to test honestly:** near-efficient + low-vol (EURUSD <0.5%/day) → small per-trade edges that usually need leverage (rail-forbidden by default) + regime-shift risk (CB surprises, carry unwinds). **BUILD (next cycle):** (1) FX data adapter — free majors via Yahoo `EURUSD=X`/`GBPUSD=X`/`USDJPY=X` etc., verified ~2007+ in the crossasset scout; (2) FX cost realism (~1bp one-way, NOT the 400bp crypto model); (3) run 2–3 honest trend + carry strategies through the SAME walk_forward gate as everything else; negative result is acceptable + logged. Whether FX trend-persistence survives realistic-cost + no-leverage + walk-forward is the open question. Channel msgs 1513766589617672315 + 1513768801156730973; rationale in memory/2026-06-09.md.
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
- **OPEN · P2 · `load_xsec_strategy` candidate-path cleanup.** Currently `strategies/`-only; xsec candidates have to bypass via `importlib.util.spec_from_file_location` (subagent did this in `_run_xsec_momentum_wf.py`). Trivial. Lift to support `strategies_candidates/` like `load_strategy` does.
- **DONE 2026-05-30 · Tier 2 regime classifier infra shipped.** `runner/regime_classifier.py` (707 LOC) + frozen prompt + schema + 29 unit tests. Two new DB tables (`llm_decisions` Bar-C.3 audit, `regime_decisions` hot-path). Opt-in `regime_gate` integrated into `runner/runner.py`; crypto bypasses; LLM failure NEVER crashes a tick (safe-fallback to `regime_uptrend(SPY, 50)`). Model: gpt-4o-mini (~$0.005/mo, 3+ OOM under Bar C.2 cap). Manual CLI verified end-to-end against paper Alpaca: no-key fallback path, bogus-key 401 fallback path, idempotent re-run. Report: `reports/TIER2_REGIME_CLASSIFIER_IMPL_20260530T174332Z.md`. **Deferred (intentional):** cron wiring, first Tier 2 trading strategy that flips `regime_gate: true`, `runner/regime_backtest.py` for Bar C eval. None are blockers.
- **DONE 2026-05-30 · Multi-symbol / cross-sectional harness extension.** New `runner/backtest_xsec.py` (660 LOC) + `tests/test_backtest_xsec.py` (15 tests, suite 120→135). Design (A): wrapper-of-singletons + synced bar clock. Shared-cap risk enforcement via `_clamp_basket(...)` (proportional scaling, closes first). Unblocks archetypes #1 cross-sec momentum, #3 low-vol, #8 sector rotation. `runner/backtest.py` + `runner/runner.py` unchanged (mtime-verified). Report: `reports/MULTI_SYMBOL_HARNESS_20260530T173605Z.md`. Subagent flagged `walk_forward_xsec` follow-up (~80 LOC) + `MAX_TRADES_PER_DAY=4` shared-cap bite for >4-leg rebalances.
- **DONE 2026-05-30 · Fix `_iso_date()` intraday-truncation in bars cache.** Non-midnight `end_dt` now serializes full timestamp (`YYYY-MM-DDTHHMMSSZ`); midnight-UTC still emits short form to preserve daily-cache layout. 4 new unit tests in `tests/test_bars_cache.py` (suite 120/120).
- **DONE 2026-05-30 · Multi-symbol / cross-sectional harness shipped.** `runner/backtest_xsec.py` (660 LOC, design A: wrapper-of-singletons + synced bar clock + `_clamp_basket` shared risk cap) + `runner/walk_forward_xsec.py` (440 LOC) + xsec extension to `runner/candidate_smoke.py`. Used by 5+ subagents (3 wave-3 + 3 wave-4); proven by use, not shelf infra.

_…(truncated; 216 total lines in source)_

---

## making-money

### Latest daily memory: `memory/2026-06-20.md`

# 2026-06-20 — making-money daily log

## No new activity today

Nightly distill ran ~2:20am PT. No Cyrus interaction, no new work initiated.

## Key watch items
- **EXP-3 PagePeek Chrome review** — expected ~Jun 20 (1–3 business days from Jun 17 submission). Check Chrome dev console tomorrow if Cyrus hasn't heard.
- **EXP-2 K-factor window** — 89 emails sent Jun 18; 2–4 week measurement window running. Reply-monitor cron active (job b2ac77a9, every 2h).
- **Hunter.io usage:** ~16/25 monthly searches used.

### BACKLOG.md

# BACKLOG.md — making-money

_Triage regularly. Keep this CURRENT-STATE and TIGHT — it is read on every autonomous tick, so verbose run-by-run changelog belongs in `memory/YYYY-MM-DD.md`, NOT here. (Compacted 2026-06-09: the old multi-hundred-KB Recently-shipped changelog was the #1 per-tick context bomb; full detail is preserved in the daily logs.)_

## Active
- **🎯 THE MISSION (locked 2026-06-08): find/build a $10k/mo-floor, magnitude-optimized business an agent team can run with no founder audience.** Research CLOSED — converged answer in `research/TRACK-C-SYNTHESIS.md` (+ `distribution-machine-2026.md`, `product-categories-10k.md`, `SELECTION-RUBRIC.md`). Reach = pay / loop / ranked-index only; agents CAN build product-led loops (send-to-a-non-user) + marketplace store-rank + (later) paid; agents CANNOT do automated organic broadcast or thin AI-pSEO; the real wall is IGNITION, not the channel. **Winning shape = product-led LOOP on a MARKETPLACE foundation + a DATA-MOAT leg = the BARBELL.** Now in the **EMPIRICAL-EXPERIMENT phase** (<$50, prove the thesis before any long build).
- **EXP-2 — product-loop K-factor test [BUILT + HEAVILY HARDENED + PROFILE-ABSTRACTED; awaits ignition gate].** `build/exp2-loop/` (SiteLens): smallest send-to-a-non-user AI deliverable (keyless on-page SEO + perf audit → shareable report → "⚡ run your own" loop-back), fully instrumented to compute K. THE thesis-critical experiment.
  - State: decisive-or-silent K measurement (sample-size gate ≥15 seeds/≥20 views + 95% Wilson CI; cohort windowing); `report.mjs` PASS/FAIL harness. Engine PROFILE-ABSTRACTED (`src/profiles.js`) — a swing = add a profile, not fork. **V1 SiteLens (web) + V2 LocalLens + V3 ShopLens (e-com) all built as profiles, end-to-end IGNITABLE + message-fire-ready** (targeting + outreach speak each vertical's language). V4 AI-Proposal = next queued profile.
  - One-command ignition: `node ignite.mjs --vertical {local|trades|pro|realestate|food|ecom|shopify} --base <domain> --sender "<name>"` chains source→clean→audit+rank→draft in-process (now routing the correct profile per vertical: local presets→LocalLens, ecom presets→ShopLens, else→SiteLens — so the headline path actually fires V1/V2/V3) + a decisive front-preflight → GO/GO_DRY/NO_GO/NO_SEEDS packet (with seed-QUALITY tier). Offline-verified via `--from-fixture`/unit (note: per-host audit fetches are live, so a true offline end-to-end run isn't possible from this IP).
  - Test posture: ~1270 deterministic assertions (`npm test`) covering K-math, the per-check **classification thresholds** inside `runChecks` AND the broken-links/images finding's two pure pieces — `collectInternalResources` (same-origin selection: who gets blamed) + `brokenResourcesCheck` (the recipient's verdict sentence) — plus **report.mjs CLI itself** (raw-verdict JSON ↔ decide.mjs contract + human PASS-WEAK→INCONCLUSIVE headline collapse), the live event ROUTES, score, OG card (SVG+PNG), report/home HTML, fixes, per-vertical calibration (incl. the V4 ProposalLens `proposal` benchmark namespace: own prior + "landing pages" share-hook noun). Static seed floor guarded by `test/seeds.mjs` (CI count/shape + verify-seeds' pure go/no-go aggregator) + `verify-seeds.mjs` (live DNS at gate-time; also `preflight.mjs --check-seeds`).
  - **Remaining = Cyrus one-time gates only:** free GCP PSI key (perf ring), domain (~$12), and the **ignition seed** (send ~20–50 real audits to real SMBs) to measure REAL K over 2–4 wks. **(Static seed pool is now STRONG — 222 DNS-verified seeds, 26–29/vertical, ≥18–20 strong each; a `--source static` ignition no longer needs a Common-Crawl top-up. “seeds parked” risk = CLOSED 2026-06-10.)**
- **EXP-1 — pSEO indexation + intent probe [READY-TO-FIRE; `npm run go`].** `build/exp1-pseo/` (data-moat leg): gen-pages+sitemap, indexation poller (classifier hardened against the `site:` query-echo false-positive), intent log, decisiveness-gated PASS/FAIL (`DECISION_MIN_URLS=8`). ~228 assertions. The qualified-signup classifier is allowlist-bound (`CONVERSION_ACTIONS` + pure `isQualifiedSignup`) so a bare organic `pageview`/`visit` can't false-PASS the single-signup gate — and the intent-log PRODUCER (`parseArgs`/`buildRow`) is now pinned too, so a missing/empty `--action` can't silently emit a phantom qualified `signup` from the write side. One-command gate-day runner refuses on a placeholder domain AND now refuses a config that would generate fewer than the decisiveness floor (example ships 9 topics → 10 URLs, clears it) — so a default fire is *decisive*, not doomed to INCONCLUSIVE. Remaining = domain (~$12).
- **EXP-3 — marketplace cold-start install probe [READY-TO-FIRE; `npm run go`].** `build/exp3-chrome/` (marketplace foundation): real MV3 extension "PagePeek" (on-page SEO + share-preview check, score now in **byte-parity with the SiteLens engine** — same 85/70/55/40 grade bands + warn-partial-credit, so the popup→report `?ref=ext` handoff shows ONE number) + install-tracker + decisiveness-gated PASS/FAIL (≥14 real calendar days AND ≥5 distinct measurement days; window now robust to omitted-`--day` logging — see 06-10) + pure-Node packager + paste-ready listing. ~139 assertions (producer-side `install-log` day-marker/window contract now pinned end-to-end through `computeVerdict`). Remaining = Chrome dev acct ($5).
- **Decision harnesses (both ONE-COMMAND):** `build/preflight.mjs` (pre-fire: are all 3 kits ready + which ONE gate to open first → recommends DOMAIN first; ~78 assertions) and `build/decide.mjs` (post-fire: reads all 3 `report.mjs --json` verdicts → the single next mission move per selection-doc §5; ~188 assertions incl. headline↔stance drift guard, the real producer↔consumer contract for ALL THREE experiments [EXP-2 PASS-WEAK can't mis-bank as a commit; EXP-1/EXP-3 verdict-field drift can't silently degrade a leg to PENDING], and the danger-combo escalation for BOTH weak-loop stances [reach-FAIL *and* borderline] + marketplace-FAIL → RECONSIDER_SHAPE). These bracket the experiment phase deterministically so gate-day can't drift from the locked answer.
- **Vertical deliverable PRE-SELECTED (`research/VERTICAL-DELIVERABLE-SELECTION.md`):** winner = V1 SiteLens (web/SEO/perf, marketing-freelancer/SMB ICP), Chrome-marketplace-native = the EXP-2 build itself → a K-PASS converts to real v1 with ~zero pivot, and its benchmark `scores.jsonl` seeds the data-moat leg. Queue V1→V2→V3→V4; KILLED on loop-leakage = contractor/restaurant/resume audits. EXP-2 still empirically GATES the commit.
- **Open (non-blocking, Cyrus may override): barbell vs all-in data-moat.** Proceeding on default = barbell.

## On hold (pending Cyrus)
- **App Guardian — PARKED (not killed).** Honest EV ~$600–1,500/mo, tail to low-5-figs/mo, ~0% Base44 exit → below the $10k/mo floor. Revivable cheap floor. Assets: `research/app-wedge-candidates.md`, `research/slugs.txt` (21,301-slug Shopify index). Its audit-tool research now feeds EXP-2.
- **Live AI copilot (real-time conversation assistant)** — prototype `live-copilot/` + `research/live-copilot-mvp-scope.md` delivered. Parked behind the mission; revivable if a real-time-conversation vertical becomes the pick.
- **Carson Reed agency playbook** — operator build-out shipped (`research/carson-reed/` + `build/pillar{1,2,3}` + `build/phase0-aicaller-demo/`). Real local-lead-gen agency model; income claims asserted-not-shown. Superseded as the lead by the viral-swing pivot; kept as reference/fallback (Phase-0 AI-caller kit needs only a ~5-min Retell signup to revive).
- **Income-path lanes** — `income-path-research.md` + `playbooks/lane2-freelance-writing.md` (fast-cash fallback). Overtaken by the 06-08 direction but kept.
- **YouTube research follow-up** — `research/REPORT.md` delivered 2026-05-26; awaiting Cyrus's next ask.
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
- **2026-06-18** — EXP-2 ignited: 89 personalized outreach emails sent (9 seed list + 15 Hunter.io + 65 batch-2 SMBs across 12 verticals). Reply-monitor cron running every 2h. K-factor measurement window open (2–4 wks). sitelume.app fixed (pm2 ESM bug → nohup + @reboot crontab). EXP-3 PagePeek submitted to Chrome Web Store 2026-06-17; review expected ~Jun 20.
- **2026-06-10** — 23 autonomous correctness/calibration ticks (all $0, no gates), each logged in the daily. Highlights: closed the perennial **"static seeds partly parked"** gate-day risk — pool refreshed to **222 DNS-verified seeds, 26–29/vertical** (≥18–20 strong each), CI-guarded → a `--source static` ignition hits a real K-cohort with no CC dependency; fixed an EXP-2 engine accuracy bug (inline `<script>`/`<style>` counted as prose → non-mutating `readableText` clone-strip); pinned the untested PRODUCER halves of EXP-1 intent-log + EXP-3 install-log (false-PASS / window-collapse footguns regression-locked); tested `report.mjs`/`verify-seeds.mjs` CLIs; closed a `decide.mjs` danger-combo escalation gap; severity-gated the outreach hook chooser. EXP-2 `npm test` green end-to-end. Per-tick detail in `memory/2026-06-10.md`.
- **2026-06-10** — EXP-1 made genuinely decisive: `config.example.json` was under-provisioned (3 topics → 4 URLs) below `report.mjs DECISION_MIN_URLS=8`, so a gate-day fire would deploy + burn the ~4-wk window reading INCONCLUSIVE forever. Expanded example to 9 real topics (10 URLs, clears floor) + added a `go.mjs validateConfig` guard that refuses sub-floor configs pre-deploy (floor imported from report.mjs). `go` suite 37→45, green. EXP-1 remaining = domain ($12) only.
- **2026-06-09** — EXP-2 hardened to ~1121 assertions across ~20 ticks: every figure/verdict/conversion-bearing surface now tested (K math + live event routes + score + OG card SVG/PNG + report/home HTML + actionable fixes + per-vertical percentile calibration); V3 ShopLens e-com made genuinely fire-ready + one-command offline-verified; static seed floor refreshed to 184 real DNS-verified seeds + CI/DNS guards; `preflight.mjs`/`decide.mjs` decision harnesses shipped. (See daily logs for per-tick detail.)

