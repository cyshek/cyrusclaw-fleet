# STATUS — OVERNIGHT BACKLOG-BUILD (non-submit)

**Started:** 2026-06-09 06:33 UTC / 2026-06-08 23:33 PDT
**Subagent:** overnight backlog-build (non-browser-submit). Survived ≥2 platform drops/compactions; resumed each time.
**Updated:** 2026-06-09 08:10 UTC

## Phase: P2 DONE+validated · P3 DONE+wired+applied · P4 DONE (read-only triage report) — all backlog items complete

## Done
- **P1 (Netflix 9 rows) — DONE.** All 9 classified+routed. 8 already attempted→blocked on the known Eightfold/Filestack resume wall (`need-runner-eightfold-RESUMEWALL`); 1539 (KEEP target role, exact dup of 2882) classified + marked same wall so it won't re-fail in the queue. DB integrity ok.
- **P2 (discovery breadth) — DONE + COMMITTED.** `himalayas_discover.py` + `test_himalayas_discover.py`.
  - Source selection: Wellfound=DataDome-403, YC WaaS=login-wall, YC Algolia key=dead (all HTTP-dead from this IP). **Himalayas API = OPEN JSON, ~105k jobs**, exposes companyName/companySlug/title/seniority/locationRestrictions. WINNER. (Brief named Wellfound/YC WaaS but both walled; Himalayas satisfies the "net-new, not IP-walled" intent.)
  - Pipeline mirrors `yc_discover.py`: fetch (offset-walk, 20/page) → keyword-filter via LIVE classifier KEEP gate (`title_has_target_role`+`extract_title_skip`) → US filter → dedup vs companies.yaml → probe net-new cos via `bulk_discover_slugs.probe()` (GH/Ashby/Lever) → emit merge-ready. `--apply` gated, backs up yaml, NO blind merge.
  - WAF gotcha found+fixed: detailed Chrome UA → 403, bare `Mozilla/5.0` → 200.
  - **My contribution this round (commit `8266e62`):** added 429 backoff/retry (5 tries, cap 30s) so big crawls don't truncate at the first 429 (~2920 jobs); politer 0.5s page sleep; +2 tests. (Predecessor committed the base `8e8f813`.)
  - Live-proven: 2920 jobs → 44 target-role cos → 42 net-new → **2 verified GH boards: MEMX, Elation Health**. 12 himalayas tests green; FULL SUITE **928 passed**, no regressions.
  - Reality note: Himalayas skews enterprise/healthcare/consulting remote (Workday/iCIMS/SAP) → GH/Ashby/Lever hit-rate ~5% but REAL. Complementary 3rd breadth source alongside yc_discover + LinkedIn-matrix.
  - **Fresh-session round (commit `6836eea`):** END-TO-END re-validated against LIVE API (totalCount=105264; fetch/paginate/cache/probe all work on 400+1600-job fresh crawls). Found+fixed 2 real discovery-quality bugs: (1) Himalayas leaks literal `"name"` placeholder as companyName on ~10% of rows → now dropped; (2) staffing/recruiter middlemen now dropped via the SHARED `staffing_blocklist.is_staffing_firm` (same list LinkedIn pipeline uses). 26→23 clean target-role cos on the sample (3 junk removed). +1 regression test (13 himalayas green). Wrote `HIMALAYAS-DISCOVER-README.md` review doc. FULL SUITE **931 passed**, 0 regressions. Left `--apply`-gated for Cyrus review (hits → output/himalayas_discover_hits.json).

## Next (P3)
- **P3 (LinkedIn offsite-link resolution) — DONE + COMMITTED + WIRED.** Commit `f30efb1`.
  - Diagnosed the 851 stranded LinkedIn rows (app_url still linkedin.com). The HTTP `linkedin_fetch` tactic is dead anonymously (LINKEDIN-ATS-RESOLUTION-WALL.md). But found a ZERO-cost win: **83 (→79 after policy) stranded rows are for a company+role we ALREADY crawled directly** from that company's public ATS board (a separate non-LinkedIn row in the SAME tracker.db).
  - Built `linkedin_db_crosslink_resolver.py` (+`test_...`, 14 tests): matches stranded LinkedIn row → direct-ATS row by (norm_company, norm_title) using the SAME normalization as the weekly pipeline; resolves ONLY on an UNAMBIGUOUS single-URL match; copies the real app_url; PRESERVES the UNIQUE `linkedin:<id>` source_key (roles.source_key is UNIQUE — copying the direct key collides; caught this on first apply, fixed); skips Microsoft/Amazon/AWS via `company_is_blocked` (Google kept — un-blocked 2026-06-08, discovery-only).
  - **Applied to live DB: 79 rows resolved** (851→772 stranded). DB backed up (`tracker.db.bak.crosslink-20260609-065832`) + integrity ok before+after. 42 are now directly auto-submittable (22 Ashby + 10 Lever + 10 Greenhouse); 20 Google get the correct careers URL; rest custom-ATS (Netflix/TikTok/Roblox/etc). render_xlsx regenerated.
  - **Wired into `weekly_run.sh` as Step 3a0** (runs FIRST, before the HTTP resolvers 3a/3a2 — every row it resolves is one fewer HTTP probe; cannot be rate-limited). Idempotent (re-run resolves 0). [weekly_run.sh is untracked in git by repo convention; live edit is what cron runs.]
  - FULL SUITE **945 passed**, 0 regressions.

## Done (P3 detail above)

## Blockers
- None.

## Coordination
- Submit subagent STATUS files present (STATUS.md=ashby-date DONE, STATUS-netnew-pm-submit DONE, STATUS-nord2049, STATUS-apple-prep). I will NOT grab any row those work; my P4 (if reached) is dryrun-only.
