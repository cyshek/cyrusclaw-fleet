# Workday Full-Auto — DONE 2026-05-16 (Adobe)

**Status:** ✅ **WORKING END-TO-END** for Adobe Workday tenant. Two submits confirmed live.

## Submits

| Role ID | Role | Job Application ID | Submitted |
|---|---|---|---|
| 9 | Engineering PM R163295 | `688ddd4f2bc490002b74f725a3910000` | 2026-05-16 20:27:21 UTC |
| 8 | Group Product Manager R165611-1 | `7d7f107a296b90002b6649dc68b40000` | 2026-05-16 20:29:53 UTC |

Confirmation URLs: `https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced?Job_Application_ID=<id>`

## Architecture

Single driver: **`role-discovery/workday_playwright.py`**. Flow loop (`run_workday_apply`):

1. Open apply URL, click "Apply Manually" (anonymous flow — no account creation needed for Adobe).
2. Detect step via progress-bar label (`detect_step` → `classify_step` → `info|exp|questions|voluntary|selfid|review|...`).
3. Dispatch to per-step handler.
4. Click Next; wait for transition; allow 1 retry if step doesn't advance (Self Identify needs 2 Next clicks).
5. On Review: click Submit. Confirm via `?Job_Application_ID=` in URL.

## Per-step Handlers (all in workday_playwright.py)

### `fill_my_information` (already working pre-session)
- Stable IDs: `name--legalName--firstName`, `address--addressLine1`, `address--city`, `address--postalCode`, `emailAddress--emailAddress`, `phoneNumber--phoneNumber`, `country--country`, `address--countryRegion`, `source--source`
- Radio: `input[name=candidateIsPreviousWorker]` (name+value selector, IDs are unstable)

### `fill_my_experience`
- Resume: `input[type=file]` → set_input_files(resume_path) → wait for "successfully uploaded" toast
- Work experience seeded by Workday as row index 5+; education at row 6+. Iterate via JS:
  ```js
  Array.from(document.querySelectorAll('[id^="workExperience-"][id$="--jobTitle"]')).map(el => el.id.match(/^workExperience-(\d+)/)[1])
  ```
- **DATE FIELDS = spinbuttons** (NOT text inputs). IDs:
  - `workExperience-{N}--startDate-dateSectionMonth-input`
  - `workExperience-{N}--startDate-dateSectionYear-input`  
  - `workExperience-{N}--endDate-dateSectionMonth-input`
  - `education-{N}--firstYearAttended-dateSectionYear-input` (year-only)
  - `education-{N}--lastYearAttended-dateSectionYear-input`
- Spinbutton fill pattern: `loc.evaluate("el=>el.focus()")` → Control+A → Delete → `keyboard.type(value)` → blur. Fallback: native `value` setter + input/change/blur events. (Playwright .click() fails with "outside viewport" — use JS focus.)
- Degree dropdown value for Adobe: "Bachelors" (not "Bachelor of Science").

### `fill_application_questions` (NEW this session)
- Walks DOM, extracts each `button[id^="primaryQuestionnaire--"][aria-haspopup=listbox]` and its closest `<fieldset>` → `<legend>` for the question text.
- Also detects checkbox-group questions (e.g. Adobe's "Have you ever worked at Adobe in the following capacity").
- Keyword-based answers (visa→No, legal-age→Yes, background-check→Yes, etc.).
- AI disclosure questions: always "No" per policy.

### `fill_voluntary_disclosures` (NEW this session)
- 3 listbox dropdowns: `personalInfoUS--ethnicity`, `personalInfoUS--veteranStatus`, `personalInfoUS--gender`
- Decline answers via `select_dropdown_by_text`:
  - ethnicity → "Declined to State (United States of America)"
  - veteran → "I DO NOT WISH TO SELF-IDENTIFY"
  - **gender → "Male"** — Adobe tenant silently rejects "Not declared" (UI option exists but server sees missing-value). Fall back to "Male" per personal-info.json policy.
- T&C checkbox: `input[type=checkbox][id*=acceptTermsAndAgreements]`

### `fill_self_identify` (NEW this session)
- Disability status uses **checkboxes** (not radios). IDs end `-disabilityStatus`.
- Decline: tick "I do not want to answer".
- Name signature: `[id="selfIdentifiedDisabilityData--name"]` → full name.
- Date: `selfIdentifiedDisabilityData--dateSignedOn-dateSection{Month,Day,Year}-input` (spinbuttons). Auto-filled with today.
- **Quirk:** Page needs 2 Next clicks (first submits the form server-side, second advances). Driver handles via stuck-step retry (allows 1 same-step retry).

### Review/Submit
- Click `button:has-text("Submit"):not(:has-text("Save"))`. 
- Workday redirects to `/en-US/external_experienced?Job_Application_ID=<id>`. That URL pattern IS the confirmation (no "Thank you" text — page just renders the job-search listing again).

## Confirmation Detection (NEW)

`is_confirmation(page)` now also returns True if `Job_Application_ID=` is in the URL. Text-only confirmation was insufficient because Adobe redirects to the generic job-search page after submit.

## Reusable Helpers Added

- `fill_spinbutton(page, selector, value, label)` — for Workday date spinbuttons
- `fill_workday_date(page, prefix, month, year, label)` — convenience wrapper
- `select_dropdown_by_text(page, button_id, candidates, label)` — opens a listbox, picks first matching option

## Known Constraints / Gotchas

- **Headless only** (no xvfb). All work in `headless=True`.
- **No image model** for screenshot OCR. Verified pages via URL + body-text inspection.
- **Browser data wiped between runs** during dev (`rm -rf .workday-browser-data/adobe`). For prod the persistent context is harmless to keep.
- Workday sometimes needs **2 clicks of Next** to advance (Self Identify on Adobe). Driver retries once.
- `select_dropdown_by_text` uses `[role=option]` query — picks the FIRST match across the page. If multiple dropdowns are open simultaneously this could misfire. In practice handlers open one at a time and Escape before next, so it's fine.

## Next-tenant Considerations (not validated this session)

- Other Workday tenants may use radios instead of checkboxes for disability status (driver has a radio fallback).
- Some tenants require account creation before apply (different submit path). Adobe accepts anonymous "Apply Manually" — easiest case. NVIDIA, Intel, HPE, BakerHughes: TBD.
- Application Questions vary tenant-by-tenant. The keyword-based `pick_option` covers common questions; for unknown questions the driver records a blocker and aborts (no fake answers per policy).

## Files Changed This Session

- `role-discovery/workday_playwright.py` — added `fill_spinbutton`, `fill_workday_date`, `select_dropdown_by_text`, `fill_application_questions`, `fill_voluntary_disclosures`, `fill_self_identify`; updated `is_confirmation`; relaxed stuck-step detection to allow 1 retry.
- `applications/submitted/adobe-r163295/STATUS.md` + `confirmation.png` (role 9)
- `applications/submitted/adobe-r165611/STATUS.md` + `confirmation.png` (role 8)
- `tracker.db`: roles 8, 9 set `applied_by='auto', applied_on='2026-05-16', prep_status='submitted'`
- `Cyrus_Job_Tracker.xlsx` re-rendered (Applied: 76)

Helper scripts (can be deleted or kept for debug): `dump_exp.py`, `dump_step.py`, `inspect_exp.py`, `probe_state.py`, `probe_vol_opts.py`.

---

## 2026-05-17 PM — Multi-tenant expansion attempt

**Status:** ❌ Infrastructure improvements landed; no new tenants fully validated end-to-end.

### Infrastructure changes to `workday_playwright.py`

1. **`load_creds()` rewritten** to support the nested `{shared_email, shared_password, tenants: {<t>: {email, ...}}}` shape in `.workday-creds.json`. Per-tenant email overrides shared_email; password always falls back to shared_password.
2. **`handle_account_prompt()` overhauled:**
   - Dismisses cookies banner first.
   - Detects create-vs-signin mode (`verifyPassword` input → create).
   - Clicks the `[data-automation-id="click_filter"][aria-label="<label>"]` overlay div (the real click target — `createAccountSubmitButton` is intercepted by the overlay sibling in modern Workday).
   - Strategy chain: click_filter overlay → JS click → force click.
   - Returns explicit `none` / `created` / `signed_in` / `failed:<reason>`.
   - Auto-recurses into sign-in if Create Account redirects to Sign In page (handles "account already exists" path).
   - Caller in `run_workday_apply` now uses `_account_attempted` flag to avoid infinite re-submit loops.
3. **`maybe_handle_email_verification()` added:** detects Workday's `verifyAccountCodeInput` and other code-style inputs; polls `gmail_imap.wait_for_verification_code` (90s budget) and submits the code. Link-based verification flows are NOT yet supported (would need to GET the link via `requests` and re-attach cookies).
4. **`gmail_imap.py` SENDER/SUBJECT/BODY hints extended** to match Workday verification emails (`workday`, `myworkdayjobs`, `workdaysite`, `verify your account`, `account verification`).
5. Hardcoded `EXPERIENCE_DATA` / `EDUCATION_DATA` audited — values are honest (Microsoft TPM 2024-present + UH BS CS 2024 match `personal-info.json.experience_summary`). The Amazon 2023-05→2024-02 row in `EXPERIENCE_DATA[1]` is loaded but only used if Workday seeds 2+ work-experience rows; for Adobe runs only row 0 was filled.

### Per-tenant probe results

| Tenant | URL probe result | Entry-point flow | Tested submit? | Blocker |
|---|---|---|---|---|
| **Salesforce** | URL OK; anonymous `applyManually` available | Adobe-style (no upfront sign-in) | ❌ no qualifying roles | Sole non-overreach role (834, exp:5+yrs) caught by JD-level overreach guard (`yoe:10>=8`). 0 qualifying. |
| **PayPal** | URL OK; anonymous `applyManually` available | Mid-flow create-account modal | ❌ stuck on My Information | Account creation now works (plus-aliased email `cyshekari+paypal@gmail.com`). Driver advances to step 1 (My Information) but then stuck — handler fills name/address/email/phone but doesn't fill PayPal-specific required fields: `Phone Device Type` dropdown and `How Did You Hear About Us?` is a multi-select moniker (not the single-pick path our handler uses). `source--source` moniker option "LinkedIn" not found at first level → only "Job Board" path. Need PayPal-specific source path AND Phone Device Type select handler. |
| **Mastercard** | URL OK (after adding `CorporateCareers` site segment); anonymous `applyManually` available | Adobe-style | ❌ not attempted | Same expected blockers as PayPal — tenant-specific My Information fields. |
| **Intel** | URL OK (after adding `External` site segment); anonymous `applyManually` available | Adobe-style | ❌ not attempted | Only 1 qualifying role (700); already had prep-only packet. |
| **Nvidia** | Some URLs in tracker missing `NVIDIAExternalCareerSite` site segment → resolve to `community.workday.com/invalid-url` (stale). Working URLs require **upfront sign-in** (no anonymous applyManually button on JD pages). | Sign-in-first (deeper deviation from Adobe) | ❌ not attempted | Driver currently expects anonymous applyManually as entry. Would need a new "sign-in-from-JD" entry handler. Several tracker URLs also need slug_sweep — first 3 Nvidia URLs probed all redirected to invalid-url. |
| **HPE** | Same as Nvidia: sign-in-first | Sign-in-first | ❌ not attempted | Same as Nvidia. |
| **Baker Hughes** | per Cyrus directive: SKIPPED entirely | — | — | — |

### What WORKS now that didn't before

- Generic tenant entry via `--tenant <name>` (was already there, but creds-loading was broken — fixed).
- Workday account creation for tenants that show a mid-flow modal (PayPal verified; Salesforce, Mastercard, Intel expected to use same modal).
- Sign-in fallback if Create Account redirects to Sign In (handles `email already exists`).
- Email verification scaffolding (code-input pattern) — UNVALIDATED end-to-end since PayPal didn't require verification before letting the apply proceed.

### What DOESN'T work yet

1. **`fill_my_information` is Adobe-tuned.** Other tenants have additional required fields (Phone Device Type select, multi-select source). Needs per-tenant overrides or a generic "scan-required-and-fill" pass.
2. **Sign-in-first JD entry flow** (Nvidia, HPE). Driver assumes JD page → click "Apply" → applyManually visible.
3. **Link-based email verification** (alternative to code-input). Not implemented; tenants that send a click-to-verify link will abort.
4. **PayPal+ aliased emails** — UNCERTAIN whether every Workday tenant accepts `+` in email. PayPal does; others untested.

### Recommended next steps

- Write a "scan unfilled required fields" helper that walks every `[aria-required=true]:not([aria-invalid=false])` and either fills via heuristics or aborts with a precise blocker (e.g. "Phone Device Type — no default in personal-info.json"). Per-tenant field maps in a YAML.
- Add a sign-in-first entry handler for Nvidia / HPE / other tenants where JD only shows "Sign In" (no Apply button).
- Run `slug_sweep.py` for Nvidia, Intel, Mastercard before any further attempt — several tracker URLs are stale (redirect to community.workday.com/invalid-url).
- Probe ONE Salesforce / Mastercard / Intel role before adding the per-tenant field handlers to make sure the gaps are real (PayPal might be unique).

---

## 2026-05-19 — Nvidia tenant VALIDATED (4 submits)

**Status:** ✅ **Nvidia full-auto WORKING end-to-end**. 4 live submits confirmed.

### Submits

| Role ID | Role | Job Req | Submitted (UTC) |
|---|---|---|---|
| 763 | Software Program Manager, NPI | JR2014827 | 2026-05-19 10:19:02 |
| 1224 | Technical Program Manager – VLSI | JR2015102 | 2026-05-19 10:25:22 |
| 1225 | Technical Program Manager, Dataset Operations | JR2018252 | 2026-05-19 10:28:08 |
| 1226 | Product Program Manager, System LPU | JR2012702 | 2026-05-19 10:30:54 |

All landed at `…/jobTasks/completed/application` with "Application Received May 19, 2026" in Candidate Home.

### Key differences vs Adobe (now in driver)

1. **JD-page entry**: Nvidia JD pages do NOT show "Apply Manually" directly. The Apply button is `[data-automation-id="adventureButton"]` (an `<a>` link to `…/apply`). Driver now clicks `adventureButton` first if present, before looking for `applyManually`. Adobe URLs land directly on the apply flow so `adventureButton` is absent — safe no-op.

2. **Sign-in-method chooser**: After `applyManually` click, Nvidia (and HPE) shows a chooser page with `[data-automation-id="GoogleSignInButton"]` + `[data-automation-id="SignInWithEmailButton"]`. The latter leads to a Sign In form with a `[data-automation-id="createAccountLink"]` to switch to Create Account. New helper: **`handle_signin_choice(page, slug, prefer="create"|"signin")`** drives this; called at the top of `handle_account_prompt`. Adobe/PayPal have no chooser → safe no-op.

3. **`click_filter` overlay aria-label varies per tenant**: Adobe uses `aria-label="Sign In"` / `aria-label="Create Account"` on the overlay div. Nvidia uses `aria-label="Submit"` on the sign-in submit overlay. `handle_account_prompt` now tries both labels per action.

4. **Per-tenant account state**: New top-level `mark_account_created(tenant)` writes `tenants.<tenant>.account_created=true` into `.workday-creds.json` on first successful Create Account. Subsequent runs read this flag and call `handle_account_prompt(..., prefer_signin=True)` so we go straight to Sign In and skip the Create Account link. Detection of "account already exists" widened to include `aria-invalid="true"` on the email field after Create Account submit.

5. **`source--source` moniker level-2 label varies**: Adobe = `"LinkedIn"`. Nvidia = `"Linkedin Jobs"`. `select_moniker_promptoption` now accepts tuples of alternates at any path level: `["Job Board", ("LinkedIn", "Linkedin Jobs", "LinkedIn Jobs", "Indeed")]`. Function also rewritten to always close the menu (Escape + body click) at end, preventing pointer-events interception of subsequent field clicks.

6. **Phone country code (required on Nvidia)**: New field `#phoneNumber--countryPhoneCode` is a Workday `selectinput` widget with `promptOption` entries like "United States of America (+1)". Treated as a moniker pick. Adobe doesn't render this field.

7. **Phone device type (required on Nvidia)**: New `#phoneNumber--phoneType` listbox. Driver tries "Mobile", "Cell", "Cell Phone", "Mobile Phone", "Home" in order. On role 763's run the dropdown wasn't visible (overlay intercept) but the form advanced anyway — Nvidia seems to accept missing phoneType in some flows. Will revisit if it ever blocks.

8. **Application Questions: sponsorship as checkbox group**: Adobe used dropdowns. Nvidia renders Yes/No checkbox-groups for both authorization and sponsorship questions. Extended `fill_application_questions` so the `checkboxGroup` branch falls back to `pick_option(qtext)` and ticks the Yes/No checkbox whose label matches the keyword answer (was previously only looking for "I have not worked" / "None of the above"). Added sponsorship keyword variants: `"work permit"`, `"employer support to obtain"`, `"require employer support"`.

9. **"Something went wrong" recovery**: When re-entering an in-progress Workday application (one that previously left My Information mid-fill), the apply URL renders a "Something went wrong / Please refresh the page" panel. Driver now detects this body text in the main loop and calls `page.reload()` once per step kind. Reload restores the form AND preserves any data already saved (e.g. source pick). This recovered role 1224 cleanly after an earlier broken run.

### Files touched

- `role-discovery/workday_playwright.py` — all of the above. Specific functions added/modified:
  - new `mark_account_created(tenant)`
  - new `handle_signin_choice(page, slug, prefer)`
  - rewrote `select_moniker_promptoption` (alternates + reliable close)
  - extended `handle_account_prompt(page, ..., tenant, prefer_signin)` (signin chooser, label variants, account_created persistence)
  - extended `fill_my_information` (phone country code via moniker, phone device type)
  - extended `fill_application_questions` (checkboxGroup yes/no fallback, expanded sponsorship keywords)
  - extended `run_workday_apply` (adventureButton entry click, SWR-reload recovery)
- `.workday-creds.json` — nvidia tenant now has `account_created: true`
- `tracker.db` — roles 763, 1224, 1225, 1226 marked `applied_by='auto', applied_on='2026-05-19', prep_status='submitted'`
- `applications/submitted/nvidia-jr{2014827,2015102,2018252,2012702}/STATUS.md + confirmation.png`

### Known caveat

- Role 764 (System Products Memory Solutions Engineer, JR1981294) is stuck in Cyrus's Candidate Home as "Not Submitted" — early failed run left it in a partial state. Driver's SWR-reload doesn't help here because that role was poisoned BEFORE the recovery logic was added. Could be resumed manually by Cyrus or via a future helper that picks up from Candidate Home. Not a blocker; other roles work clean.

### Not yet validated

- HPE / Mastercard / PayPal / Intel / Salesforce tenants. The Nvidia changes are generic enough that HPE (also sign-in-first) should "just work" if the field IDs line up. Recommend probe-one before batching.

---

## 2026-05-22 PM — PayPal tenant VALIDATED + Manual Ready queue drained

**Status:** ✅ **PayPal full-auto WORKING end-to-end.** Manual Ready queue: 0.

### Outcomes for the 6 Workday Manual Ready packets

| Role ID | Company | Slug | Result |
|---|---|---|---|
| 579 | Baker Hughes | baker-hughes-r163493 | ✅ Submitted (earlier today, auto) |
| 699 | Intel | intel-jr0280825 | ✅ Submitted (earlier today, auto) |
| 951 | Intel | intel-jr0283865-1 | ✅ Submitted (earlier today, auto) |
| 819 | PayPal | paypal-r0134500-1 | ✅ Submitted (this run, auto). First PayPal tenant submit. |
| 959 | Adobe | adobe-r164954 | ⛔ Posting removed (404). Tracker → `status='closed', prep_status='skipped'`. |
| 675 | HPE | hpe-1201238-2 | ⛔ Posting removed ("The page you are looking for doesn't exist."). Tracker → `status='closed', prep_status='skipped'`. |

**Net new submits this run: 1 (PayPal).** Other 3 had already drained today via prior tenant work.

### PayPal-specific driver changes

1. **PEP (Politically Exposed Person) questions** — Yes/No dropdowns specific to PayPal. Added keyword matches to `pick_option`:
   - `"politically exposed person"`, `"pep"`, `"associated with a politically"`, `"close relationship"` → `"no"`
2. **Acknowledgement DATE question** inside Application Questions step. Previously the question-scanner only extracted dropdowns / checkboxGroups / text inputs. New branch: detect `[data-automation-id="dateInputWrapper"]` whose month-input id begins with `primaryQuestionnaire--`, expose as `type:"date"` with `id=<prefix>`. New handler fills MM/DD/YYYY with today's date via existing `fill_workday_date` / `fill_spinbutton`.
3. **Diagnostic dump on stuck-step** — added a one-time DOM diagnostic (`fieldsets`, `aria-required` controls, alert errors) when a step retries twice without advancing. Pure observability; no behavioral change.
4. **Submit confirmation pattern (PayPal)** — Driver returned `post-submit errors` because PayPal redirects back to `/apply` after Submit, NOT to `/jobTasks/completed/application`. Verified via Candidate Home (`/userHome`) that the application IS recorded as "Resume Submitted, May 22, 2026" with the correct req id. `is_confirmation` should be extended to also poll `/userHome` for the new application row when the post-submit URL doesn't match the standard completion pattern (or accept a 6/6 progress bar + clean submit click as success).

### Per-tenant pattern (PayPal)

- **Entry flow:** anonymous `applyManually` works on JD page (after `adventureButton` click). No upfront sign-in required, but mid-flow it switches to account-create / sign-in.
- **Account creation:** `cyshekari+paypal@gmail.com` accepted (plus-aliased Gmail). Stored in `.workday-creds.json`. No email verification step encountered.
- **Page count:** 6 pages (My Information → My Experience → Application Questions → Voluntary Disclosures → Self Identify → Review).
- **Required fields not in personal-info.json yet:**
  - `source--source` is multi-level moniker (Job Board → Indeed). Worked with existing alternates list.
  - `phoneNumber--countryPhoneCode` (`United States of America (+1)`).
  - Phone device type field NOT rendered on this PayPal page — earlier 2026-05-17 PM note about PayPal needing Phone Device Type was wrong or has since changed.
- **Date-field widget:** spinbutton trio (Month / Day / Year) — same as Adobe. (Application-question dates also use spinbutton.)
- **Self Identify page:** standard "I do not want to answer" checkbox; needs 2 Next clicks (driver already handles via stuck-step retry).
- **Confirmation pattern:** Driver should check `/recruiting/<tenant>/jobs/userHome` after Submit; an application row with status "Resume Submitted" and date today is the canonical confirmation.

### What a generic `workday_playwright.py` would need (gap items remaining)

- **`is_confirmation`** should additionally accept "post-Submit + 6/6 + no errors + click did fire" as success when URL doesn't match any standard pattern. Today the run returned `ok=false` despite a valid submit; without manual verification it would have been re-run and double-applied. **HIGH PRIORITY** to add userHome cross-check before any auto-retry.
- **Date-type Application Questions** are now handled (PayPal acknowledgement). Likely seen on other tenants too.
- **Posting-removed detection** — Both Adobe-959 and HPE-675 returned "page does not exist" on the JD URL. Driver should detect this in iter 0 and return a clear `posting-removed` blocker (instead of "no Next button at iter 0 unknown").

### Files touched

- `role-discovery/workday_playwright.py` — added date-type question scanner + handler, PayPal PEP keyword matches, submit overlay fallback, post-submit diagnostic dump.
- `.workday-creds.json` — `tenants.paypal.account_created = true`.
- `tracker.db` — role 819 set `applied_by='auto', applied_on='2026-05-22', prep_status='submitted'`. Roles 675, 959 set `status='closed', prep_status='skipped'`.
- `Cyrus_Job_Tracker.xlsx` re-rendered (Applied: 98, Manual Ready: 0).
- `applications/submitted/{paypal-r0134500-1, hpe-1201238-2}/STATUS.md` updated.

---

## 2026-05-23 — HPE tenant VALIDATED (1 submit) + Salesforce/Chevron probed

**Status:** ✅ **HPE full-auto WORKING end-to-end.** 1 live submit confirmed. Salesforce-1222 posting removed. Chevron-1223 blocked on source--source moniker structure difference (documented).

### Submits

| Role ID | Role | Job Req | Submitted (UTC) |
|---|---|---|---|
| 1228 | Engineering Program Manager – HPC/AI Platform Engineering - Early Career | 1206918 | 2026-05-23 03:04:59 |

Confirmation via two signals:
1. Post-Submit URL = `https://hpe.wd5.myworkdayjobs.com/en-US/Jobsathpe/jobTasks/completed/application` (HPE's canonical completion URL, same pattern as Nvidia).
2. Re-navigating to the JD with the candidate signed in shows banner: *"You applied for this job on May 22, 2026. View Application"*.

**Important quirk for HPE:** Workday userHome's "My Applications" list shows the row as `In Progress` after submit (not `Submitted`). This is a stale-cache / display lag on Workday's part — the JD-revisit banner is the authoritative signal. Do NOT use userHome cell-status as a confirmation oracle for HPE; the cross-check should hit the JD URL.

### HPE-specific change to driver

Single line: `personalInfoUS--ethnicity` decline-list extended to include `"Not Specified"` and `"Prefer not to"`. HPE's ethnicity dropdown does NOT offer `"Declined to State"` (the Adobe / Baker Hughes label) — just race buckets + `"Not Specified (United States of America)"`. The Voluntary Disclosures page also renders a separate `personalInfoUS--hispanicOrLatino` dropdown which the existing Baker-Hughes branch already handled ("No" / "I do not wish to answer"). No other code paths needed changes — HPE re-uses Nvidia's sign-in-first entry handler (`adventureButton` → `applyManually` → sign-in chooser), Adobe's My Information layout, and Nvidia's Application Questions checkbox-group fallback.

### Driver changes this session

- `fill_voluntary_disclosures`: ethnicity decline-list now `["Declined to State", "Decline to self-identify", "Decline to State", "Do not wish", "Not Specified", "Prefer not to"]`. **One-line addition; backward-compatible.**
- `.workday-creds.json`: added `chevron` tenant entry (`cyshekari+chevron@gmail.com`). Account was created during probe but no submit landed.

### Salesforce JR336914-1 — posting removed

Probed role 1222 (Product Manager, Pricing & Product Operations, JR336914-1). Driver immediately detected `posting-removed` (body text: *"The page you are looking for doesn't exist."*). Tracker row updated to `status='closed', prep_status='skipped'`. **No Salesforce tenant validation possible this session** — zero qualifying live roles in queue. Recommend re-attempt after next discovery crawl surfaces a fresh Salesforce role.

### Chevron R000071280 — blocked on source--source dropdown structure

Probed role 1223 (Workforce Management Solution Architect, Houston). Driver got past entry + account-create + sign-in cleanly and reached My Information. Blocker:

- `source--source` is the standard Workday id but Chevron's dropdown structure differs from Adobe/Nvidia/HPE.
- `select_moniker_promptoption` opens the field via `getElementById('source--source').click()` but no menu actually appears (or no `promptOption` becomes visible). The `fallback_first_sub` path then picks up phantom `promptOption` entries (`"United States of America (+1)"`) that appear to be leaking from a different widget. Picked option does NOT stick.
- Result: form fails validation with `"Error-How Did You Hear About Us? The field How Did You Hear About Us? is required and must have a value."`

**Hypothesis:** Chevron renders the source field as an `<input>` with a sibling button-shell rather than the inline-clickable button container used elsewhere. The current `select_moniker_promptoption` heuristic doesn't traverse to the click-target button. Needs a tenant-specific opener (click the `<button aria-haspopup="listbox">` sibling) or a generic refactor that walks to the nearest haspopup ancestor before clicking.

**Not pursued further this session** — Chevron has only 1 qualifying live role in the queue. The fix is non-trivial DOM-archaeology that's better done when there's a queue of ≥3 Chevron roles to justify the investment. Documented as a follow-up.

### What works now that didn't before

- HPE tenant added to validated list. Sign-in-first entry path (`adventureButton` → `applyManually` → sign-in chooser → Sign In existing account) verified.
- Ethnicity "Not Specified" decline-equivalent unlocks any tenant whose dropdown drops the "Declined" option (likely true for several enterprise tenants).

### Validated tenants after this session

**Adobe, Nvidia, Intel, Baker Hughes, PayPal, HPE.** 6 tenants total.

### Files touched

- `role-discovery/workday_playwright.py` — one line in `fill_voluntary_disclosures` (extended ethnicity decline list).
- `.workday-creds.json` — added `chevron` entry, `tenants.chevron.account_created = true`.
- `tracker.db` — role 1228 set `applied_by='auto', applied_on='2026-05-23', prep_status='submitted'`. Role 1222 set `status='closed', prep_status='skipped'` (Salesforce posting-removed).
- `Cyrus_Job_Tracker.xlsx` re-rendered (Applied: 99, Manual Ready: 0).
- `applications/submitted/hpe-1206918-2/STATUS.md` + `confirmation.png` created.

### Next-tenant follow-ups

1. **Chevron** (when queue has ≥3 roles): teach `select_moniker_promptoption` to walk to the nearest `[aria-haspopup="listbox"]` button before clicking. Probe one Chevron source-dropdown DOM dump first to confirm the structural difference.
2. **Salesforce** (when a live JR appears): probe-one before batching. Mid-flow account modal expected; tenant-specific My Information fields unknown.
3. **Mastercard** (when queue has any roles — currently 0 in-queue): probe-one.



---

## 2026-05-24 — Salesforce tenant VALIDATED (1 submit)

**Status:** ✅ **Salesforce full-auto WORKING end-to-end.** 1 live submit confirmed via Candidate Home.

### Submits

| Role ID | Role | Job Req | Submitted (date) |
|---|---|---|---|
| 1130 | Solution Engineer (Pre-Sales) - SMB & Growth Business | JR318273 | 2026-05-24 |

Confirmation: Candidate Home (`https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/userHome`) → "My Applications / Active (1)" → JR318273 / `In Consideration` / May 24, 2026.

### Salesforce-specific gotchas (now in driver — all generalizable)

1. **`source--source` is a `multiSelectContainer` widget**, not the inline-button container used by Adobe/Nvidia/HPE. Clicking `#source--source` via JS DOES open the menu — but the fallback_first_sub logic was picking phantom `promptOption` entries left in the DOM by *previously-closed* menus (specifically `phoneNumber--countryPhoneCode`'s "United States of America (+1)" option remained `offsetParent`-visible). **Fix:** `select_moniker_promptoption` now snapshots existing visible promptOption keys (label+id) **before** opening and excludes them from both the explicit-candidate match and the `fallback_first_sub` pick. After a pick succeeds the snapshot is refreshed for the next level. **One-time DOM-archaeology issue — generally useful for all future tenants.**

2. **Salesforce source path:** Top-level options are `['Current or Former Employee', 'External Career Site Sources', 'Referral']` (not `'Job Board'`). Driver now uses tuple-alternates at level 1: `("Job Board", "External Career Site Sources")`. Level 2 (External Career Site Sources): no "LinkedIn" plain — uses `"LinkedIn Connection Post"`, `"Indeed"`, `"Glassdoor"`, `"Salesforce Careers Website"`, etc. Added these to the level-2 alternates tuple. Picked "Indeed" on this run.

3. **`phoneNumber--countryPhoneCode` is NOT required on Salesforce** (Workday returns a "United States of America (+1)" promptOption when clicked, but the field tolerates being unfilled — form advanced). The `fill_text` fallback for this field's failure still produces noisy Playwright retry logs but doesn't block submission.

4. **New Application Questions answered (driver keyword extensions):**
   - `"government responsibilities" + "responsible for matters" + "government"` → No
   - `"post-government employment restriction"` / `"no post-government"` (attestation) → Yes (I attest I have no restrictions)
   - `"debarred"` / `"proposed for debarment"` / `"declared ineligible for aw"` → No
   - Text field: `"preferred geographic location"` → "San Francisco, CA"
   - Dropdown: `"Regarding future positions at Salesforce, please select one of the following options"` → 3 options: `["Select One", "Yes, I would like to receive communications about Salesforce and future openings", "No, please do not contact me about Salesforce and future openings"]`. Driver picks the first `Yes, ...` option (opt-in is benign).

5. **NEW driver feature — `DROPDOWN unanswered options` diagnostic:** When `pick_option` returns empty for a dropdown question, the driver now opens the dropdown briefly, logs all `[role=option]` text contents, then either runs a tenant-specific handler (currently only "regarding future positions at") or bails with a precise blocker. **This is now the standard discovery pattern for tenants:** run once, read the `DROPDOWN unanswered options` log lines, add a keyword rule + Yes/No mapping or extend the future-positions-style handler.

6. **Sign-in chooser:** Salesforce does NOT show the Nvidia/HPE-style sign-in-method chooser (`SignInWithEmailButton` etc.). Drops straight to a Create Account form with a `signInLink` to switch. The existing `handle_account_prompt` Create→redirect-to-Sign-In fallback handled it on this run (the Salesforce account already existed from a 00:15 UTC probe attempt).

### My Experience step quirk

- Workday on Salesforce did NOT pre-seed any work-experience or education rows. Driver's `exp_rows: []` finding meant nothing was filled — resume PDF upload alone was accepted. Application advanced cleanly. Salesforce parses the uploaded resume server-side; no manual row backfill needed. (Compare Adobe/Nvidia which seed empty rows the driver fills.)

### Validated tenants after this session

**Adobe, Nvidia, Intel, Baker Hughes, PayPal, HPE, Salesforce.** 7 tenants total.

### Files touched

- `role-discovery/workday_playwright.py`:
  - `select_moniker_promptoption`: pre-snapshot existing promptOption keys; explicit candidates AND fallback_first_sub now exclude pre-existing leftovers; snapshot refreshed between path levels.
  - `fill_my_information`: source path level-1 now `("Job Board", "External Career Site Sources")`; level-2 adds `"LinkedIn Connection Post"`, `"Glassdoor"`.
  - `pick_option`: added government-responsibilities, post-government attestation, and debarred keyword rules.
  - Application Questions text branch: added `"preferred geographic location"` → "San Francisco, CA".
  - Application Questions dropdown branch: new `DROPDOWN unanswered options` diagnostic + Salesforce future-positions opt-in handler.
- `.workday-creds.json` — `tenants.salesforce.account_created = true`.
- `tracker.db` — role 1130 set `applied_by='auto', applied_on='2026-05-24', prep_status='submitted'`. Backup at `tracker.db.bak.20260524-r1130`.
- `applications/submitted/salesforce-jr318273/STATUS.md` + `confirmation.png` updated.

### Probe scripts (kept for future reference, deletable)

- `role-discovery/probe_sf_source.py` — DOM dump of source--source widget structure
- `role-discovery/probe_sf_future.py` — was for diagnosing the future-positions dropdown
- `role-discovery/verify_sf_submit.py` — userHome verification helper (signs in, dumps "My Applications" table)
