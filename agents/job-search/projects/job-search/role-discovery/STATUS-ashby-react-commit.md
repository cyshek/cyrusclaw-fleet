# STATUS — ashby-react-commit hourly grind (2026-06-10)

## Phase: 3 of 3 (ENGINE FIX SHIPPED — validating on Curri/Knowtex)

## Done
- Residential browser UP: CDP=http://127.0.0.1:19223; egress=82.23.97.223.
- **Cartesia 1384 → SUBMITTED ✅** (residential cleared score-gate; datacenter spam-flagged). Committed.
- **RESOLVER KNOCKOUT FIX (ashby_dryrun.py, durable):** "authorized to work WITHOUT employer sponsorship?" was first-match-resolving to bare "sponsorship"->needs_sponsorship->"No" (a factual knockout — US citizen IS authorized w/o sponsorship). Added positive rules at TOP of _ASHBY_EXTRA_RULES -> work_authorized -> Yes. Verified: positive=Yes, "require sponsorship"=No (unchanged). .bak made.
- **Curri 2557 DIAGNOSTIC (residential):** captcha CLEARED (no spam-flag!), work-auth=Yes committed, Location committed. Submit banked `Missing entry: Full Name / Why-interested / Share-link`. Email/Phone/LinkedIn/GitHub/relocate-essay/plumber DID commit. => subset of text/essay fields resist the _valueTracker reset path; React controlled state reads empty at submit. THIS is the __reactProps$ onChange target.

## ENGINE FIX SHIPPED (_ashby_runner.py, chain_p13)
- Added reactOnChangeCommit() inside _REASSERT_TEXT_JS: after the native value-setter, find the input's React props bag (__reactProps$<hash>) on the element OR a wrapping ancestor (walks up 5 levels) and invoke onChange/onInput directly with a synthetic event carrying the value -> forces React controlled state to commit. Wired into forceSet (runs on EVERY reassert pass, incl. force=True pre-submit). Fully guarded/never-raises; no-op for non-React inputs.
- TEST: test_ashby_react_commit.py (6 tests incl. node-execution behavioral proof). FULL ashby suite GREEN: 133 passed, 6 skipped, 0 regressions.
- .bak: _ashby_runner.py.bak.react-commit-20260610-152858, ashby_dryrun.py.bak.react-commit-20260610-152858

## Next (IN PROGRESS)
- Re-run Curri 2557 on residential -> expect Full Name/Why/Share-link now commit -> FormSubmitSuccess.
- Then Knowtex 2593 (prep + run; single-select 2+yrs=Yes should commit via same fix).

## Blockers
- none; engine fix shipped + green.

## UPDATE (Curri SUBMITTED)
- **Curri 2557 → SUBMITTED ✅** server FormSubmitSuccess. Required full chain_p13 stack (fiber onChange + no-bounce Email + trusted-keystroke phone). Committed to DB + STATUS.md.
- Moving to Knowtex 2593 (prep + residential run, same engine).
