# STATUS-brute.md — LinkedIn-stranded brute-force resolver

**Subagent:** linkedin-stranded-brute-resolver
**Started:** 2026-05-27 23:15 UTC
**Completed:** 2026-05-27 23:35 UTC

## Phase progress
- [x] Phase 0 — context reading
- [x] Phase 1 — company→ATS mapping (`_linkedin_stranded_ats_map.json`)
- [x] Phase 2 — `linkedin_stranded_brute_resolver.py`
- [x] Phase 3 — `test_linkedin_stranded_brute_resolver.py` (30/30 green)
- [x] Phase 4 — dry-run validated (16 resolved, 14 unresolved, 91 NO-ATS)
- [x] Phase 5 — `--apply` committed (same numbers, real DB write)
- [x] Phase 6 — 25 new companies appended to `companies.yaml` (354→379)
- [x] Phase 7 — TOOLS.md, memory/2026-05-27.md, HANDOFF.md, weekly_run.sh Step 3a2

## Final counts
- Stranded LinkedIn rows pre-sweep: 121
- Stranded LinkedIn rows post-sweep: 105 (16 rewritten to real ATS URLs)
- Resolved: 16 (9 Ashby + 6 Greenhouse + 1 Lever)
- Unresolved (board reachable but no title match this week): 14
- NO-ATS (custom-ATS giants / staffing firms / Workday auth-walled): 91
- Errored: 0
- New yaml entries: 25
- Tests: 30/30 green
- Backup: `tracker.db.bak.20260527-232414-linkedin-brute-resolver`
