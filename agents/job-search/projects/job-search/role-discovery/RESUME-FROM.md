# RESUME-FROM — Ashby Date-widget RUNNER fix

**STATUS: TASK COMPLETE. No follow-up required.** This file exists only so a future subagent knows the runner-side date fix is DONE and proven, not pending.

## What shipped (see `STATUS-ashby-date-runner.md` for full detail)
- `_ashby_runner.py`: `_SET_DATE_JS` (date-aware React `_valueTracker`-reset) + calendar-cell click fallback (`_DATE_CALENDAR_OPEN_JS`/`_DATE_CALENDAR_PICK_JS`) + `commit_ashby_date_fields()` + helpers `_resolve_date_dom_id`/`_date_fp_tail`. Wired into 3 spots: the `ashby.type_text_fields` step (skips keystrokes for date fids), the UPLOAD-LAST verify pass, and the FINAL pre-submit re-assert. Backup: `_ashby_runner.py.bak.ashby-date-runner-20260609-001139`.
- `test_ashby_date_runner.py`: 14 unit tests, green.
- Full suite: **901 passed, 48 subtests** (baseline 887 + 14 new). No regressions.
- Live `--no-submit` probe on OpenAI 2549: **PASS** — ISO `2026-06-23` committed to React (`el.value=="06/23/2026"` AND `_valueTracker=="06/23/2026"`, field not flagged missing). NO submit.

## If a NEW Ashby tenant's Date field still banks "Missing entry"
1. It will surface as `date-commit UNCOMMITTED <fid>` in the runner stderr log (not silent).
2. Reproduce with the standalone probe: `.venv/bin/python _ashby_date_probe.py` after editing its `URL` to the new tenant's `/application` URL and starting a CLEAN anonymous Chrome on port 19250 (NOT the resi-profile on 19223). It prints `commit_ashby_date_fields` result + `post_value._valueTracker` + `empty_required_scan`.
3. Most likely cause = a pure-calendar picker whose day-cell markup differs from react-datepicker's `.react-datepicker__day`/`role=gridcell`, or one needing month/year nav to reach the target month. Tweak `_DATE_CALENDAR_PICK_JS`'s cell selector / add month-nav; keep the JS programmatic-set path first.

## Known pre-existing nit (NOT introduced, flagged for a future cleanup)
`_SET_VALUE_JS` (line ~61) is a non-raw `"""..."""` with `\d` escapes → `DeprecationWarning: invalid escape sequence`. Will SyntaxError on a future Python. Fix = prefix `r"""`. Left untouched to keep this change surgical.
