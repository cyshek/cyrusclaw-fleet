# PORT-PLAN — chain_006 sidecar (Greenhouse work-exp + iframe honest-verify)

Subagent: NON-BROWSER sidecar. Two gaps from chain_005. Files identified, fixtures saved.

## Gap 1 — GH work-experience repeater block

### Findings
- The boards-api spec (`boards-api.greenhouse.io/v1/boards/lyft/jobs/8550252002?questions=true`) does NOT expose `company-name-0 / title-0 / start-date-* / end-date-* / country`. Only the rendered `/embed/job_app` HTML does.
- Saved fixture: `projects/job-search/role-discovery/tests/fixtures/lyft-8550252002-embed.html` (93 KB).
- Element types confirmed via grep:
  - `company-name-0`, `title-0` → plain `<input type=text>` (native setter works)
  - `start-date-year-0`, `end-date-year-0` → plain `<input type=text>` maxlength=4
  - `start-date-month-0`, `end-date-month-0` → `<input role=combobox aria-autocomplete=list>` (react-select typeahead)
  - `country` → same combobox shape (typeahead). Already partially handled in `greenhouse_iframe_runner.py` `country_select` block — keep, but add fallback for the work-experience-block case.
- `personal-info.json` has `experience_summary` (single current job dict) but no `work_experience` array. Per task: add the array as single source of truth.

### Approach
1. **personal-info.json:** add `work_experience: [{company,title,start_month,start_year,end_month,end_year,current,country}]`. Single entry = current Microsoft TPM. `current=true` so `end_*` left blank / "Currently work here" checkbox ticked if present (Lyft form does NOT show a current-employer checkbox in this fixture — handle the empty-end-date case explicitly).
2. **greenhouse_iframe_runner.py:** runtime fill step (best location since boards-api can't see these). New function `fill_work_experience_block(frame, work_exp)`:
   - Detect by `document.querySelectorAll('input[id^="company-name-"]')`. If empty → no-op.
   - For each index N, set company-name-N, title-N, start/end-date-year-N via native setter.
   - For month combobox: focus + type 3-letter month name + Enter (or click first option). Same pattern as country.
3. **greenhouse_dryrun.py:** add `_detect_work_experience_block(html) -> bool` flag in spec (informational; allows tracker/STATUS to expose it). Add an optional cached HTML scan that emits a synthetic `work_experience_block: true` plus required indices. **Decision (LEAN):** only emit a flag + count; runtime fill is the source of truth (driver already has live DOM). Skip the dryrun-side filler emission — the runner handles it natively.
4. **greenhouse_filler.py build_plan:** propagate `work_experience: [...]` from personal-info into plan (for runner to consume). Add `JS_FILL_WORK_EXPERIENCE_BLOCK` constant.

Tests:
- Unit (mock HTML): detect work-experience block in Lyft fixture → returns True + count=1.
- Unit (mock HTML on Asana fixture or fabricated GH HTML with NO repeater) → False.
- Unit: `build_plan` given a personal-info with `work_experience` propagates to plan key.
- Unit: JS string contains expected selectors (snapshot-style).

## Gap 2 — iframe runner honest-verify

### Findings
Current outcome chain in `greenhouse_iframe_runner.run()` 30-second poll loop:
- Sets `outcome="CAPTCHA_GATE"` on `.grecaptcha-error`
- Sets `outcome="SUBMITTED"` on body-text/URL `conf` match
- Otherwise `outcome="TIMEOUT"` with `post_submit` showing fieldErrs

Problem: the JS_SUBMIT `step:submit, result:{ok:true}` in the events stream is read by humans as "submit succeeded". The runner does NOT honestly downgrade when post_submit.fieldErrs is non-empty AND there's no confirmation.

### Approach
1. After the polling loop ends without confirmation, inspect `last["fieldErrs"]`. If non-empty:
   - Set `outcome="BLOCKED_FIELD_ERRORS"`.
   - Walk back through `report["events"]` and rewrite the `submit` step's `result.ok=true` to `result.ok=false, result.downgraded_from_clicked=true, result.field_errors=[...]`.
   - Emit `report["honest_verify"] = {field_errors: [...], reason: "post_submit fieldErrs non-empty"}`.
2. Same downgrade if `files_in_input` in `verify_resume` was > 0 but post-submit shows resume error.

Tests:
- Unit: `_honest_verify_post_submit(report, last)` — given a fake report with `events=[{step:submit,result:{ok:true}}]` and `last={fieldErrs:["Resume required"],conf:false}`, returns the report with submit step downgraded + outcome=BLOCKED_FIELD_ERRORS.
- Unit: same fn with `last={conf:true, fieldErrs:[]}` does not mutate.

## File touch list

| File | Change |
|---|---|
| `projects/job-search/personal-info.json` | Add `work_experience` array (1 entry, Microsoft TPM current) |
| `projects/job-search/role-discovery/greenhouse_filler.py` | Pull work_experience into build_plan; add `JS_FILL_WORK_EXPERIENCE_BLOCK` constant |
| `projects/job-search/role-discovery/greenhouse_dryrun.py` | (Optional/LEAN) flag `_work_experience_block_detected` from cached HTML; informational only |
| `projects/job-search/role-discovery/greenhouse_iframe_runner.py` | Add fill_work_experience_block runtime step + honest-verify post-submit downgrade |
| `projects/job-search/role-discovery/test_greenhouse_work_experience.py` | NEW — unit tests for detection, plan propagation, JS-string sanity |
| `projects/job-search/role-discovery/test_greenhouse_iframe_honest_verify.py` | NEW — unit tests for the honest-verify downgrade |
| `projects/job-search/role-discovery/tests/fixtures/lyft-8550252002-embed.html` | NEW — saved fixture for detection tests |

## Out of scope (deferred to chain_007 browser verify)
- Live re-run of Lyft 1343 with the new work-experience filler — requires the browser chain.
- `inline_submit.py --role-id 1343 --dry-run` Part 3 "live verify" — `inline_submit` for `greenhouse_iframe` tenants short-circuits with manual instructions; it doesn't invoke the iframe runner. Marking this as documented limitation, not blocker.

## Risk-cards
- **Risk: work-experience month combobox could be a non-typeahead native `<select>` on other tenants.** Mitigation: detect element shape (`role=combobox` vs `<select>`) and branch.
- **Risk: multi-row repeater (N>0) not encountered in fixture.** Mitigation: implementation iterates all `[id^="company-name-"]` so it supports any N, but only chain_007 live can verify a multi-row tenant.
- **Risk: country handler already exists upstream; new work-experience handler must not double-fire.** Mitigation: work-experience step inspects `#country` separately and only fills if blank (idempotent).
