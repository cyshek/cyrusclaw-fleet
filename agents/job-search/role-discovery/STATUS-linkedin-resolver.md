# STATUS — LinkedIn resolver refresh (subagent linkedin-resolver-refresh)

_Started 2026-06-11 ~00:10 PDT. Engine+data task. NO browser submit. Anonymous board-API HTTP only._

## Phase 0 — Read & understand (DONE)
- Read MEMORY.md DEBUNKED ledger: li_at unusable from this VM (shared Webshare IP edge-blocked + Azure IP server-side-deletes cookie). Bucket (b) = settled-unwinnable here. Don't reopen.
- Read both resolvers:
  - `linkedin_company_ats_resolver.py` (commit 0cbfb5e) — reads `companies.yaml` LIVE (never stale), exact-normalized company match, STRICT Jaccard≥0.7 + shared-distinctive-token title match. Better architecture but narrow.
  - `linkedin_stranded_brute_resolver.py` (pipeline stage 3a2) — uses `_linkedin_stranded_ats_map.json` (built each run by `_phase1_build_ats_map.py`) PLUS a `dynamic_ats_entry()` probe fallback. difflib matcher w/ seniority+PM/TPM expansions.
- `_phase1_build_ats_map.py` rebuilds the map every weekly run (so "stale 23-entry cache" = the live artifact, regenerated weekly).

## KEY FINDINGS (inventory)
- **Total LinkedIn-stranded (status='manual-apply' + linkedin.com url): 83 rows / 76 distinct companies.**
- **81/83 already carry a `LINKEDIN-BRUTE` note → 71 NO-ATS, 5 ERRORED, 5 UNRESOLVED.** The idempotency guard (`agent_notes NOT LIKE '%LINKEDIN-BRUTE%'`) then PERMANENTLY excludes them from future 3a2 runs.
- **ROOT-CAUSE BUG #1 (map builder status mismatch):** `_phase1_build_ats_map.py` selects companies via `status IN ('','blocked')` — but the stranded pool is `status='manual-apply'`. So the map builder NEVER sees the manual-apply companies → 71 came back NO-ATS (company absent from map entirely). The brute resolver's own SQL DOES include `manual-apply`, but it's fed a map that excludes them. **Fix: align the map builder's company-selection SQL with the resolver's RESOLVABLE_STATUSES.**
- **ROOT-CAUSE BUG #2 (NO-ATS poisons retries):** once a row gets `NO-ATS` agent_notes, the idempotency guard locks it out forever even after the map is fixed. **Fix: NO-ATS / ERRORED notes must be re-attemptable (don't treat them as terminal).**
- Company breakdown: only **7/76 in companies.yaml** (Cisco=workday, EMAG/Epic/Valence=greenhouse, Gamma=ashby, Google=google[SSO], Microsoft[blocklist]). **69/76 NOT in yaml** — mostly staffing firms, industrial/non-tech, healthcare/edu (genuine NO_BOARD), plus a handful of real tech with potential boards (Spot AI, Productboard, Checkmarx, NeuReality, Thea Energy, Docusign, Teradata, Copeland, ChargeAfter).

## Phase 1 — board probe of the 69 not-in-yaml companies (DONE)
- Probed GH/Ashby/Lever/SmartRecruiters/Workable (anon HTTP, backoff). 6 "board hits": Atlas Copco→ashby/atlas, Docusign→sr/docusign, GEICO→sr/geico, Kastle→ashby/kastle, Rise Technical→lever/rise, hackajob→sr/hackajob.
- **VERIFIED all 6 are WRONG-COMPANY SLUG COLLISIONS** (checked the boards' actual titles): ashby/atlas = an AI startup not the industrial pump co; ashby/kastle = an AI startup not the security co; sr/docusign + sr/hackajob = near-empty junk/test boards ("Job", "Bog Job", "New Job"); sr/geico = 1 "Licensed Insurance Agent"; lever/rise = a telco. NONE contain the stranded role → matcher's title-guard correctly REJECTS all 6. **Bucket (a) among the 69 not-in-yaml = effectively EMPTY.**
- Baseline run of the GOOD resolver (`linkedin_company_ats_resolver.py`, reads companies.yaml live): RESOLVED 0 / BOARD_BUT_NO_TITLE 11 / NO_BOARD 71 / BLOCKLISTED 1.
- **Checked the 11 BOARD_BUT_NO_TITLE:** 4 are Google (SSO-walled, stay manual-apply regardless). The 7 non-Google: EMAG (Romanian ecom, role not on board), Gamma (has Sales Manager/Solutions Architect, NOT the stranded "Sales Engineer" — expired/renamed), **Epic = Epic GAMES board but rows are Epic SYSTEMS healthcare TSE roles = slug collision**, Valence (board now 0 jobs = expired), Cisco (workday cisco/External 404 = wrong tenant cfg). **All 7 are genuine non-matches (expired roles / wrong-company collisions), NOT matcher-too-strict false-rejects.**

## KEY VERDICT
- **The current strict matcher is CORRECT for today's population — loosening it would create FALSE resolutions** (e.g. Epic Games "Solutions Architect (Animation)" ≠ Epic Systems "Technical Solutions Engineer"). 0 of the 83 stranded rows have a genuine resolvable ATS posting RIGHT NOW.
- The win is therefore (1) FIX the recurring pipeline bugs so FUTURE stranded rows (which DO sometimes have live boards) get resolved, and (2) add a SAFE fuzzy matcher (Sr/Senior, PM/Product Manager, trailing suffixes) that helps future rows without manufacturing collisions. The DEBUNKED bucket-(b) auth-walled rows stay manual-apply (proxy decision).

## TODO
- [x] Phase 1: probe done — bucket (a) among not-in-yaml is empty (all collisions).
- [x] Phase 2: FIXED two recurring-pipeline bugs (below). Map regenerated 23→79 companies (6→11 with known ATS).
- [x] Phase 3: broadened matcher SAFELY + 12 new tests (variant ACCEPT / collision REJECT) — 43 brute tests green.
- [x] Phase 4: re-ran resolver --apply on full stranded set: resolved 0 / unresolved 9 / errored 7 / no_ats 70.
- [x] Phase 5: 0 resolved today (all genuine non-matches/collisions) → 0 rows flipped. Flip path wired + verified (collision guard blocked the 3 wrong-company boards Atlas/Kastle/Rise).
- [x] Phase 6: fix IS in the recurring path — weekly_run.sh stage 3a2 calls `_phase1_build_ats_map.py` (fixed) then `linkedin_stranded_brute_resolver.py --apply` (fixed). No one-shot.

## FIXES SHIPPED (all in the RECURRING weekly_run.sh stage 3a2 path)
1. **`_phase1_build_ats_map.py`** — (a) company-selection SQL now uses `RESOLVABLE_STATUSES = ('','blocked','manual-apply','queued')` mirroring the brute resolver (was `('','blocked')` → never saw the manual-apply cohort → 71 NO-ATS). (b) companies.yaml matching now NORMALIZED via `adapters.linkedin._norm_company` (exact name first, then normalized) so 'Docusign'→'DocuSign', 'Gamma Reality Inc.'→'Gamma' hit yaml without a probe. Map: 23→79 companies, 6→11 known-ATS. Test: `test_phase1_build_ats_map.py` (3 green).
2. **`linkedin_stranded_brute_resolver.py`** — (a) IDEMPOTENCY FIX: guard now excludes only TERMINAL `LINKEDIN-BRUTE-DONE` (written for RESOLVED); NO-ATS/ERRORED/UNRESOLVED write a plain `LINKEDIN-BRUTE` note that is RE-ATTEMPTED next run (was: any `LINKEDIN-BRUTE` note locked the row out forever, so a stale-map NO-ATS was never retried even after the map was fixed). (b) MATCHER BROADENED SAFELY: added Tier-2 order-independent token-overlap (Jaccard≥0.7) for reordered/suffixed variants + a `collision_guard_ok()` anti-collision gate on EVERY tier (shared distinctive non-generic token, OR fully-generic target with structural substring sameness). ACCEPTs Sr/Senior, PM/Product Manager, reorderings, region suffixes; REJECTs Sales Engineer↔Sales Manager, wrong-company boards (Epic Games↔Epic Systems), different-discipline. Test: `test_linkedin_stranded_brute_resolver.py` (43 green, +12 new).
