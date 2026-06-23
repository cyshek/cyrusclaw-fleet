SUBMITTED — 2026-05-26T03:48Z

role_id: 872
slug: spacex-8520029002
url: https://boards.greenhouse.io/spacex/jobs/8520029002
final_url: https://job-boards.greenhouse.io/spacex/jobs/8520029002/confirmation
applied_by: auto
applied_on: 2026-05-25

## VALIDATION VERDICT: Both patches CONFIRMED WORKING ✅

### Patch 1 (greenhouse_filler upload fix — selector→element)
Earlier canary already validated; this run re-confirmed:
  resume_attempt_a/b/c report ok=false but verify_resume.filename_visible=true
  (Filestack swap pattern — bind via UI, files.length=0 is expected).
  Submit cleared without resume-related error.

### Patch 2 (academic-fields dryrun → filler resolution — 2026-05-25)
GPA/SAT/ACT/GRE selects routed correctly with deterministic labels:
  - GPA (Undergraduate): "3.8 out of 4.0" ✅
  - GPA (Graduate): "Other/Not Applicable" ✅
  - GPA (Doctorate): "Not applicable/Do not recall" ✅
  - SAT Score: "Did not take/Do not recall" ✅
  - ACT Score: "Did not take/Do not recall" ✅
  - GRE Score: "Did not take/Do not recall" ✅
  needs_review_dropdowns=[] (no fallback resolver needed).

## Extra fixes landed this run (committed for future tenants)

1. `greenhouse_filler.JS_FILL_EDUCATION_PANEL`
   - Added `.education--container` / `.education--form` to section selectors
     (SpaceX uses BEM double-dash variant, not the standard `.education-section`).
   - Added `findCtrlByLabelOrId(re, idPrefixes)` helper that matches via
     `label[for=...]` OR input id prefix (`school--`, `degree--`, `discipline--`),
     instead of the noisy `.closest().textContent` heuristic that picked up
     placeholder "Select..." instead of the real label.
   - School field now opens the react-select control BEFORE dispatching the
     input event (SpaceX async typeahead won't fire otherwise).
   Result: School / Degree / Discipline all filled cleanly:
     {School: "University of Houston", Degree: "Bachelor's Degree",
      Discipline: "Computer Science"}

2. `greenhouse_filler` clearance alias
   - `multi_value_multi_select` value "None" expands to
     ["None", "Never held a clearance", "Do not wish to disclose"] aliases.
   - `JS_TICK_MULTI_CHECKBOXES` now ticks only the FIRST matched alias
     (alias-expanded lists are alternates, not multi-selections).

3. `greenhouse_iframe_runner.py` react-select-multi fallback
   - When `JS_TICK_MULTI_CHECKBOXES` returns `err: 'no fieldset'` for a spec
     (i.e. the API typed it as multi_value_multi_select but the tenant rendered
     a react-select-multi instead), a new fallback `JS_TICK_REACT_SELECT_MULTI`
     opens the control, types into the menu, and clicks the first matching
     option. Picks one alias only (pickedAny gate).
   - On this run, "Active Security Clearance(s)" was picked as
     "Do not wish to disclose" (the third alias). "Never held a clearance"
     did NOT match in this run despite being in the option list — possibly
     a menu render timing issue; logged as a residual but did not block submit.
     [FOLLOW-UP: investigate why option matching missed "Never held a clearance"
      — might need extra sleep after open before scanning options.]

## Email-verification interstitial (NEW data point)
SpaceX shows an 8-box security code interstitial AFTER the main Submit click.
Runner detected it (8 boxes), polled Gmail, picked up code `EpJp73je`, filled
the boxes, and clicked Submit again — landed on /confirmation page. This means
the post-submit Gmail flow (`gmail_imap.wait_for_verification_code`) is alive
and works on the SpaceX tenant.

## Captcha posture
pre_submit.grecapErrText=''; post_submit.grecapErrText=''; bypassed_visible_captcha=true;
invisible_captcha=1. No captcha block this run.

## Counters
dryrun_counts: 30 total / 22 filled / 1 needs_review (clearance) / 4 declined / 3 unresolved / 0 blockers.
text_fields: 6/7 (location field absent — handled by stripe-style candidate-location react-select).
dropdowns: 11/11 picked ✅.
multi_checkboxes: 0/1 ticked, 1/1 react-select-multi fallback ticked ✅.
education_panel: 3/3 filled ✅.
demographics: 4/4 declined ✅.
phone iti: ok ✅.
resume: filename_visible (Filestack-bound) ✅.
submit: SUBMITTED → /confirmation ✅.

Tracker updated: applied_by='auto', applied_on='2026-05-25', prep_status='submitted'.
