# Lyft 1343 (PM Driver Earnings) — chain_007 attempt

**Outcome:** BLOCKED-FILESTACK-TOKEN-REQUIRED — NOT submitted.

## Live-verification of chain_006 sidecar (PRIMARY mission)

✅ **honest_verify_post_submit works.** Runner correctly reported
   `outcome=BLOCKED_FIELD_ERRORS` (not the chain_005 false-positive submit:ok).
   `honest_verify.downgraded=True`, submit step `result.ok` downgraded to False.

✅ **work_experience_block adapter works.** Detected=True, 5/5 fillable fields
   completed:
   - `current-role-0_1` checkbox clicked (current=True)
   - `company-name-0` = Microsoft
   - `title-0` = Technical Program Manager
   - `start-date-year-0` = 2024
   - `start-date-month-0` = March (via combobox — see fix below)
   - end-date-month/year correctly skipped because current=True

## Driver upgrades shipped (chain_007)

### 1. `greenhouse_iframe_runner.py` — careerpuck scroll-warmup

SPA wrappers (`app.careerpuck.com` for Lyft) lazy-load the GH iframe via
IntersectionObserver. Without a scroll, `iframe#grnhse_iframe` is never
injected, so the runner fell back to the direct embed URL (reCAPTCHA-gated).

After `page.goto(wrapper, wait_until="load")`, we now do:

```python
page.mouse.move(400, 400); page.mouse.move(640, 500)
page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(1.5)
page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
```

Verified: iframe now found ~1-2s after scroll on careerpuck/Lyft.

### 2. `greenhouse_filler.py` pickCombobox — listbox-leak fix

Old selector: `[role=option], [id^=react-select-]` — first match for "March"
was `react-select-start-date-month-0-listbox` (a DIV container, role=listbox,
textContent = "March" when filtered). Clicking the listbox is a no-op for
react-select; form state never updated. Runner reported `picked: "March"` but
post-submit error "Start date month is required".

Fixed:
```js
const strictOpts = [...document.querySelectorAll('[role=option]')];
let opt = strictOpts.find(o => textContent.startsWith(want)) || strictOpts.find(includes);
// fallback only if no role=option exists:
const looseOpts = [...document.querySelectorAll('[id^=react-select-][id*="-option-"]')];
```

Verified live: after fix, post-submit field errors went from
`['Resume/CV*', 'Resume/CV is required.', 'Start date month*', 'Start date month is required.']`
to `['Resume/CV*', 'Resume/CV is required.']` (start-date-month commit confirmed).

### 3. Tests

- `test_greenhouse_combobox_selector.py` (5 tests, all pass) — snapshot tests
  that the JS string has the strict selector + documented fix.
- All 27 chain_006/007 GH tests still pass.
- Broader suite: 89/91 pass (2 pre-existing Lever ImportErrors unrelated).

## Remaining blocker: Filestack-CDN-token (SAME as role 716)

This is the same blocker exhaustively diagnosed in chain_009 for Lyft 716:

- Lyft uses **Filestack** for resume upload (visible "Attach" button next to
  `#resume`).
- Filestack's adapter at submit-time looks for `resume_file_token` hidden
  form field (populated only by Filestack's XHR upload flow).
- `inp.files = DataTransfer.files` (our injection) populates `inp.files` but
  is NOT what Lyft's submit handler reads — so server rejects with
  "Resume/CV is required" even though `files_in_input=1, strict_bound=True`
  in our `verify_resume` check.
- Estimated fix: intercept Filestack XHR (`/filestack/upload` or similar) +
  set hidden token. ~3hr build per the role-716 agent_note.
- Out of the 60-min per-role budget.

## Reproduction

```
.venv/bin/python greenhouse_iframe_runner.py --slug lyft-8550252002 --dry-run  # full plan, no submit
.venv/bin/python greenhouse_iframe_runner.py --slug lyft-8550252002            # live attempt
```

Both produce `outcome=BLOCKED_FIELD_ERRORS` with `field_errors=['Resume/CV*',
'Resume/CV is required.']` post-fix.

## Prior STATUS history

- 2026-05-26 chain_005: BLOCKED-MISSING-FIELDTYPE (work-exp + Country missing).
  That diagnosis was correct re: work-exp (now fixed in chain_006/007), but
  the runner's submit:ok was actually a false-positive (NOW fixed by honest-verify).
- 2026-05-26 chain_007 (this file): BLOCKED-FILESTACK-TOKEN-REQUIRED.
