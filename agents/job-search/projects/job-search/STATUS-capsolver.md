# CapSolver scaffolding — STATUS (FINAL)

**Owner subagent:** f423fd48-3cbe-4327-b586-f72e5b02e79b
**Started:** 2026-05-27 12:20 PDT
**Completed:** 2026-05-27 12:55 PDT
**Mission:** Build CapSolver scaffolding so strict-Ashby cohort unlocks on env-var flip. No real spend.

## Status: ✅ COMPLETE

## Deliverables
- `role-discovery/capsolver_client.py` — thin façade, env-only key gate, 60s timeout, exponential 429 backoff
- `role-discovery/captcha_presubmit.py` — runner-side detect+solve+inject helper, hard-gated on `ENABLE_CAPSOLVER=1`
- `role-discovery/greenhouse_iframe_runner.py` — wired in (pre-`JS_SUBMIT` hook, defensive try/except)
- `role-discovery/ashby_filler.py` — FIX 5 step upgraded with executable `driver_exec` spec
- `role-discovery/test_capsolver_scaffold.py` — 36 unit tests, all mocked, all green
- `TOOLS.md` — updated with new module info + to-enable instructions
- `projects/job-search/CAPTCHA-SOLVER-DECISION.md` — "scaffolding shipped, awaiting funding" note prepended

## Tests
- 36 new tests in `test_capsolver_scaffold.py`: all pass
- 0 regressions across `test_ashby_filler_chain005`, `test_greenhouse_iframe_honest_verify`

## To-enable (Cyrus)
```bash
export CAPSOLVER_API_KEY='<paste-key-here>'
export ENABLE_CAPSOLVER=1
```
That's it. No config files. No other knobs. Runners are no-ops until both vars set.

## Estimated cost
~$0.16 to sweep all 53 strict-Ashby rows ($2.99/1000 v3 solves × 53 = $0.158).

## Phases
- 12:20 — read brief, scanned codebase
- 12:30 — discovered captcha_solver.py + captcha_inject.py already existed; scoped down to additive surface
- 12:35 — built capsolver_client.py (env-only key gate, 4 solver methods, exp backoff)
- 12:45 — built captcha_presubmit.py (detect/solve/inject helper)
- 12:50 — wired into greenhouse_iframe_runner.py + ashby_filler.py
- 12:55 — wrote 36-test suite, all green; updated TOOLS.md + CAPTCHA-SOLVER-DECISION.md

## Blockers
None.
