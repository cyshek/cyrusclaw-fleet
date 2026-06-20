# Apple PREP-ONLY lane — STATUS

**Phase:** 1 — recon + arch decision
**Started:** 2026-06-08 ~21:13 PDT

## Goal
Build prep-only Apple lane in inline_submit.py (Apple = Apple-ID SSO + 2FA, NOT auto-submittable).
Run on 15 blocked Apple rows (ids: 34,37,52,68,83,85,964,1340,1634,1637,2216,2217,2218,2219,2220).
PREP-ONLY: tailored PDF + answer sheet to disk, prep_status='manual_ready'. NEVER applied_on/applied_by.

## Done
- Confirmed 15 rows status='blocked' block_reason='apple-sso-manual' in REAL db (projects/job-search/tracker.db, 2.8MB).
- Read prep_role_workday (L1456), detect_ats (L133), role-dict builder (L341+), run_bullet_rewriter (L832 — reads JD.md from APPS_DIR/{org}-{jid}/JD.md), run_cover_answers (L890), write_jd_files_workday (L1395), prep_role dispatch (L1891).
- Browser (openclaw, headless chrome) started: CDP http://127.0.0.1:18800.

## Next
- Test JD extraction on 1 Apple role via browser tool (confirm JS-render scrape works).
- Decide JD-fetch arch: standalone _apple_jd_fetch.py over CDP vs pre-write JD.md via browser tool.
- Implement detect_ats apple branch + role-dict apple branch + prep_role_apple + dispatch.
- Unit test + full regression.
- Run on 15 rows serially (reuse 1 tab).

## Blockers
- none yet
