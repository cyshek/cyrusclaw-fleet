# STATUS-ashby-date-runner.md

**Task:** RUNNER-side half of the Ashby Date-widget cohort fix (dryrun half was already shipped + tested by the parent).
**Date:** 2026-06-09 (UTC) / 2026-06-08 PDT
**Outcome:** ✅ COMPLETE — runner commits an ISO date into the Ashby Date widget so it persists to React/serializer state. **Live --no-submit probe on OpenAI 2549 PASSED.** Full suite green. NO submit performed, NO DB writes, NO cookie/proxy/secret touched, gateway not restarted, resi-profile Chrome (port 19223) untouched.

---

## Files changed

1. **`_ashby_runner.py`** (backup: `_ashby_runner.py.bak.ashby-date-runner-20260609-001139`; +337 lines, all additive/surgical)
   - **`_SET_DATE_JS`** — date-aware React `_valueTracker`-reset transition (mirrors the proven `_SET_VALUE_JS`). Probes `el.type`: sends ISO `YYYY-MM-DD` for a native `<input type=date>`, and the localized `MM/DD/YYYY` (then ISO) for a masked/react-datepicker text input. Resolves nameless+idless inputs by `data-field-path` container tail (the OpenAI 2549 class) or a `label[for]` fallback. Bounces through `''` + resets `_valueTracker` so React registers a genuine transition, fires `input`+`change`+`blur`, and returns a `committed` signal (value retained AND contains the requested y/m/d digits).
   - **`_DATE_CALENDAR_OPEN_JS` / `_DATE_CALENDAR_PICK_JS`** + Python orchestrator **`commit_ashby_date_fields(page, date_specs)`** — programmatic set FIRST; if it doesn't stick (rare masked pickers that only accept a real calendar gesture), open the picker (trusted `page.mouse.click` on the input) → find the day-cell matching the target day (react-datepicker `.react-datepicker__day` / `role=gridcell` fallbacks) → trusted-click it → re-verify. Best-effort, never raises. Returns `[{fid, committed, method, final, ...}]`.
   - Helpers **`_resolve_date_dom_id`** (uuid-tail / `__systemfield_` / single-underscore fallbacks, same as the text path) and **`_date_fp_tail`** (uuid or `question_<id>` tail).
   - **Wired into 3 spots**, all keyed on the EXISTING plan plumbing (`ashby.type_text_fields` step's `date_field_ids` arg × the ISO value already in `text_fields` — no plan/emit changes needed):
     1. `ashby.type_text_fields` step handler: pre-seeds the date fids into `done` so the keystroke loops SKIP them (keystrokes are exactly what r4 proved don't commit), then drives the date path and records `date_results`.
     2. UPLOAD-LAST verify pass: re-commits dates after the resume-autofill parse settles (the autofill can clobber a date like it clobbers Email/Location).
     3. FINAL pre-submit re-assert: re-commits dates as the last write before submit (covers BOTH the legacy and upload-last code paths).
   - Added `import re` inside `commit_ashby_date_fields` (the module has no top-level `re`; matches the file's local-import convention).

2. **`test_ashby_date_runner.py`** (NEW, 14 tests) — pure/unit, no browser. A `FakePage` mimics the `_SET_DATE_JS` / calendar `page.evaluate` contract. Covers: `_resolve_date_dom_id` (concrete id, uuid-tail fallback, nameless→None), `_date_fp_tail`, `commit_ashby_date_fields` (passes ISO-shaped value, reports committed, SKIPS a non-ISO value without driving the widget, calendar-cell fallback path when the programmatic set fails, nameless field driven by fp tail, empty/None specs), and END-TO-END plan routing (`ashby_filler.build_plan` routes Date→`date_fields`+`text_fields`; the emitted `ashby.type_text_fields` step carries `date_field_ids`; the runner's `date_specs = date_field_ids × text_fields` mapping yields ISO values and excludes non-date text fields).

3. **`_ashby_date_probe.py`** (NEW, standalone --no-submit live probe; kept for reproducibility) + **`ashby_date_probe.png`** (screenshot evidence, no submit).

---

## Test counts

- **New file `test_ashby_date_runner.py`: 14 passed.**
- **FULL real suite (`python -m pytest test_*.py -q -p no:cacheprovider`, excludes ad-hoc `_*_test.py` browser probes): 901 passed, 48 subtests passed in ~39s.**
  - Parent baseline was 887 passed + 48 subtests. 901 = 887 + 14 new date-runner tests. **No regressions.**

---

## LIVE PROBE PROOF (OpenAI 2549, `--no-submit`)

Connected a CLEAN anonymous headless Chrome 149 on a dedicated debug port (19250, fresh temp profile — NOT the resi-profile on 19223), loaded
`https://jobs.ashbyhq.com/openai/1778fbc9-b9c5-4ea5-a1d3-aa7bea0be272/application`, located the Date field, drove it through the NEW `commit_ashby_date_fields`, read back state, and STOPPED before submit.

**Target field:** "When can you start a new role?" — a **nameless, idless** `type:"text"` masked react-datepicker input, scoped only by `data-field-path="3f4e05d4-dd62-48ef-96ca-d9f293ae18d4"`. (Exactly the r4-diagnosed field: keystrokes here did not commit.)

| signal | before | after `commit_ashby_date_fields` |
|---|---|---|
| `el.value` | `""` (empty) | **`"06/23/2026"`** (masked picker reformatted ISO `2026-06-23` → its MM/DD/YYYY display) |
| `el._valueTracker.getValue()` | — | **`"06/23/2026"`** ← React's controlled-state tracker holds it (the decisive commit signal, NOT just DOM `.value`) |
| empty-required scan `flaggedMissing` | — | **`false`** |
| commit result | — | `method=set_value_js, committed=true` |

> Note: today (2026-06-09 UTC) + 14d = `2026-06-23`, so the probe used the EXACT ISO value the dryrun normalization produces at runtime, not a placeholder.

**→ DID THE ISO DATE COMMIT TO REACT STATE? YES.** Evidence: `_valueTracker.getValue()` == the date (React controlled state, not just the DOM attribute) AND the input value reflects the date AND the field is no longer empty/flagged-missing. The programmatic `_valueTracker`-reset transition was sufficient for this masked text picker; the calendar-cell click fallback was not needed here (it remains for stricter pickers and is unit-tested).

---

## HONEST VERDICT

- **No over-claim.** On the OpenAI 2549 form (a masked react-datepicker text input — the canonical Ashby Date class and the exact r4 failure), the programmatic JS path commits cleanly and is proven by the React `_valueTracker`, not just by `el.value`. This unblocks the Ashby Date-field cohort (OpenAI 2549 + any future Ashby tenant with a date question) without per-row `--answers`.
- **Where the JS path could still be insufficient (documented, with a safety net):** a tenant whose Date widget is a *pure* calendar control that rejects ALL programmatic value sets and only accepts a real day-cell pointer gesture. For that, `commit_ashby_date_fields` already includes the calendar-cell trusted-click fallback (open picker → match day cell → `page.mouse.click` → re-verify). That fallback path is unit-tested against a simulated picker, but it was NOT exercised on a live tenant in this task because OpenAI's picker committed via the JS path. If a future live tenant trips the fallback and its calendar markup differs from react-datepicker's `.react-datepicker__day` / `role=gridcell` (e.g. a custom grid, or one that needs month/year navigation to reach the target month), the day-cell selector may need a tenant-specific tweak — but the field would surface as `date-commit UNCOMMITTED` in the runner log rather than silently banking, so it's diagnosable.

## NEW ISSUE SPOTTED (pre-existing, not introduced)
- `_SET_VALUE_JS` (the older sibling, line ~61) is a plain `"""..."""` string containing `\d` regex escapes, which emits a `DeprecationWarning: invalid escape sequence '\d'` at import. Harmless today but will become a SyntaxError on a future Python. Trivial fix = prefix it `r"""..."""` (my `_SET_DATE_JS` already uses `r"""`). Left untouched to keep this change surgical; flagging for a future cleanup pass.
