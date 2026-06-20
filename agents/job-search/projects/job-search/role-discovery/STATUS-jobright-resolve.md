# STATUS: jobright_resolve_apply.py build — COMPLETE

phase: DONE
started: 2026-06-11 22:23 PDT
finished: 2026-06-11 22:xx PDT

## Done
- [x] Studied existing jobright adapter, tracker_merger, inline_submit detect_ats pattern
- [x] Confirmed DB rows 2913-2917 are live test targets
- [x] Wrote jobright_resolve_apply.py (resolve_apply_url + classify_ats + strip_utm_params + run_batch + CLI)
- [x] Wrote test_jobright_resolve_apply.py (61 tests, all passing)
- [x] Added .jobright-session to .gitignore (line 110, covered by **/.jobright-session)
- [x] Ran full test suite: 73 passed (61 resolve + 12 adapter)
- [x] Verified dry-run with no cookie: clean exit, helpful instructions
- [x] Committed: only jobright_resolve_apply.py + test_jobright_resolve_apply.py + .gitignore
  - Commit hash: a5925b6
  - No hardcoded secrets
  - Other-worker dirty files NOT touched/staged

## Blockers
None — no cookie needed for build; live resolve runs when Cyrus pastes JOBRIGHT_SESSION_ID.

## Live run CLI (once cookie exists)
  cd projects/job-search/role-discovery
  export JOBRIGHT_SESSION_ID='<value-from-DevTools>'
  # dry-run first
  .venv/bin/python jobright_resolve_apply.py --dry-run
  # then commit
  .venv/bin/python jobright_resolve_apply.py
