## 2026-05-25 06:02 UTC — role 1295 think-cell Solution Engineer

SKIPPED 2026-05-25: location-mismatch | Denver in-office 3d/wk required, candidate not in commute zone | LLM-classifier missed `loc: Denver, CO` despite fit=92 score

- URL: https://job-boards.eu.greenhouse.io/thinkcellsoftware/jobs/4872202101
- dryrun blockers: 2 unmapped questions, one of which is the hard in-office gate ("willing to come into the office 3 days a week, commutable distance from downtown Denver?")
- Decision: not pushing through. Answering "Yes" = lie (Cyrus is Toronto-remote). Answering "No" = guaranteed gate-reject. Better to skip cleanly.
- Action: tracker.roles[id=1295] → status='skip', flags+='location-mismatch'. Did NOT submit.
- Classifier follow-up: LLM gave fit=92 ignoring Denver constraint. Worth a backlog item to weight US in-office locations against remote-only preference in the fit prompt — but this is a 30-min lean-mode run, NOT my job to fix that here.
- Elapsed: ~3min. No browser launched, no LLM credits burned beyond initial classify.

## 2026-05-24 23:30 PDT — SUBMIT role 1244 Bear Robotics PM (Breezy)
- Status: ✅ SUBMITTED auto, end-to-end
- ATS: Breezy HR — **first successful Breezy submit** (new ATS validated)
- Apply URL: https://bear-robotics.breezy.hr/p/46767ea95411-product-manager/apply → /submitted
- Form: plain Angular form. Required = resume + name + email + phone + race + gender. Decline-to-answer available for both EEO. No captcha. No account required.
- Driver: ad-hoc Playwright CDP (`/tmp/breezy_fill_submit.py`) — NOT a permanent adapter yet.
- **Important finding:** OpenClaw `browser` tool's `upload` action does NOT fire AngularJS `ng-file-select` handler — file ends up with `inp.files.length=0` immediately after. Playwright `set_input_files` over CDP works fine. The browser tool's CDP upload may dispatch only `input` event, not `change`, or fires before Angular wraps the input. Reproduced 3 times; documented.
- **Permanent pipeline note:** Bear Robotics + any other Breezy tenants in the queue will need a `breezy_playwright.py` driver OR a fix to the `browser` tool's upload action. Recommend builder follow-up: add `adapters/breezy.py` (discovery already exists?) and a `breezy_playwright.py` submit driver mirroring `workday_playwright.py`.
- Time: ~30min (most spent fighting browser upload, then 5 min via Playwright direct).

## 2026-05-25 — role 848 Sentry Solutions Engineer (Ashby, fit=92, $178K target)

**Outcome: BLOCKED (captcha-hard, score-gate)**

- Prepped via `inline_submit.py --role-id 848` → OK (25.2s, 13/14 fields filled).
- Submit attempts: 2 (cookies + storage cleared between attempts via CDP `Network.clearBrowserCookies` + `Storage.clearDataForOrigin`).
- Both rejected by Ashby anti-spam score-gate: *"Your application submission was flagged as possible spam."* — no visible widget, no challenge to solve; pure fingerprint/IP gate.
- Logged to `tracker.roles[848].agent_notes`: `BLOCKED 2026-05-25: captcha-hard | Sentry Ashby score-gate, 2 attempts | CapSolver Enterprise`.
- STATUS.md = BLOCKED-CAPTCHA-HARD at `applications/submitted/sentry-9889cf59-cd32-4aff-bff7-645bb1be4e14/STATUS.md`.

**Pipeline bugs surfaced (worth fixing before next Ashby attempt):**
1. `ashby_dryrun.py` mapped "First and Last Name" → `identity.last_name` only (got "Shekari"). Should map to `full_name`.
2. Location combobox skipped as `_ashby_type=Location unknown`. Needs a resolver that types into the combobox and picks the first option matching identity.location.
3. EEO fields (`_systemfield_eeoc_gender/race/veteran_status`) not in dryrun spec at all. Should auto-emit "Decline to self-identify" defaults.

Without these fixes, future Ashby attempts will fail validation even if the captcha is solved. Worth fixing in one pass.

## 2026-05-25 15:15 PDT — SUBMIT role 1378 HeyGen FDE Strategic Accounts ✅
- ATS: Greenhouse iframe (job-boards.greenhouse.io/heygen)
- Result: SUBMITTED. confirmation_url=https://job-boards.greenhouse.io/heygen/jobs/5113581007/confirmation
- Captcha: invisible reCAPTCHA v3 — passed clean, no challenge.
- Unexpected gate: **8-char email verification** (similar to Anthropic). Code `LuZ7K9YV` fetched via `gmail_imap.py`, filled into `security-input-0..7`, second Submit landed `/confirmation`.
- Two custom essay prompts (LLM-shipped thing; largest enterprise deployment).
- Pipeline fixes shipped (will benefit future roles):
  - `greenhouse_dryrun.py` LABEL_RULES: added 2 HeyGen essay routes → `why_company_essay`.
  - `cover_answer_generator.py` OPEN_QUESTION_HINTS: added `point us|point me|show us|show me` so directive-style essays without `?` get tailored answers (previously fell through to the generic why-company template, which is wrong shape).
- Tracker updated (applied_by=auto, applied_on=2026-05-25), xlsx regenerated (Applied: 132, Open: 299, Manual Ready: 7).
- Elapsed: ~10 min.

---

## 2026-05-25 ~15:24 UTC — role 1154 SUBMITTED ✅ (Box · Enterprise Solutions Engineer · $252K · Greenhouse)

- URL: https://job-boards.greenhouse.io/boxinc/jobs/7558067 (modern GH host, invisible reCAPTCHA — passable).
- Initial dryrun aborted on 2 unmapped labels:
  - "Have you ever been employed at Box, including working as a contractor, intern, grad, or full-time employee?" — Yes/No
  - "Consent To Process" — single-option "I Agree" tickbox
- Pipeline fix → added 2 LABEL_RULES to `greenhouse_dryrun.py` (commit-worthy, benefits all future GH boards):
  - `("ever been employed at", "worked_at_company_before")` + `("been employed at", "worked_at_company_before")`
  - `("consent to process", "acknowledge_yes")`
- Re-ran inline_submit → OK, 0 blockers, plan emitted.
- Browser plan executed cleanly (16/16 text+dropdown fields, demographics all "I don't wish to answer", GDPR consent box ticked, resume uploaded + attached).
- Three plan gaps required ad-hoc dropdown picks during the run (NOT in plan):
  - `country` ("United States") — Box's schema didn't surface this in dryrun spec
  - `candidate-location` typeahead ("Kirkland, Washington, United States") — typeahead, plan didn't include it
  - `question_64244151` Privacy Notice ("I Acknowledge") — was in needs_review_dropdowns
- First Submit → bounced to email-verification step (8-char code sent to cyshekari@gmail.com).
- Fetched code via `fetch_company_code.py "Box"` → `v9nw1z9X` → entered → resubmit → **confirmation page** (`/confirmation`, "Thank you for applying. Your application has been received.").
- Screenshot captured.
- Tracker: applied_by='auto', applied_on='2026-05-25', prep_status='submitted'.
- xlsx regenerated: Open 298, Applied 133, Manual Ready 7.
- Elapsed: ~11 min (mostly plan-gap recovery + email-code wait).

**Recurring-pipeline followup candidates (NOT yet fixed; flag for main agent):**
1. Greenhouse plan emitter (`greenhouse_filler.py:emit_steps`) misses some required dropdowns when the dryrun spec doesn't enumerate them (saw `country` + `candidate-location` missing on Box). Worth a probe — if other modern GH boards do the same, the runner should fall back to scanning the live DOM for empty required selects and prompting alternates.
2. Box (and presumably other GH tenants) gates submit on email verification. We have `fetch_company_code.py` working — could be wired into the runner instead of needing manual intervention.

## 2026-05-25 15:30 UTC — role 862 Skydio Aviation Regulatory PgM (Ashby tenant probe)

**Result:** BLOCKED — captcha-hard (Ashby spam score-gate)

- Prep OK via inline_submit.py (26s, 6/7 fields filled, 1 unresolved = Websites).
- Browser run #1: fresh openclaw profile, filled all 4 text fields via `evaluate` + setNativeValue + input/change/blur events, clicked "No" on Prior US Government Employment via custom yesno button group, uploaded resume via `browser.upload ref=e11` (the actual Resume "Upload File" button — `e35` from aria-snapshot was the autofill uploader, the real form button only appears in `snapshotFormat=ai`). EEOC voluntary radios left blank. Clicked Submit → page returned: *"We couldn't submit your application. Your application submission was flagged as possible spam."*
- Cookie clear: `browser:stop`, wiped Default/{Session Storage, Local Storage, IndexedDB, Cache, Code Cache, Sessions, SharedStorage, WebStorage}, `browser:start`.
- Browser run #2: identical flow, fresh chrome session. Same spam-flag error.
- Per brief: 2 attempts → BLOCKED. Tagged 862 with `captcha-hard, 2 attempts` note; tagged siblings 863/864/865 with cluster note (same tenant, no point probing each).
- Submitted button enabled both times, no visible captcha widget — Skydio uses invisible Ashby scoring, likely device fingerprint + headless detection. CapSolver Enterprise needed to bypass (per brief, this is the standing recommendation).

**Notes for next probe (when CapSolver lands):**
- Ashby form uses custom yes/no button group (`._yesno_17tft_149`), not `<input type=radio>` — the planner's radio code path looked at `input[type=radio]` and missed it (resolved manually here). Should patch `ashby_filler.py` to detect both DOM patterns. Skipped fields: `dc901517-...` (Websites) — optional, no impact.
- Resume upload needs `snapshotFormat="ai"` to get the right button ref; `snapshotFormat="aria"` only exposed the autofill button and Submit, hiding all form fields.

**Plan:** main agent should not queue 863/864/865 separately — they share the tenant gate. Wait for CapSolver Enterprise integration, then re-probe 862; if it submits, batch all four.

**Time:** ~9 minutes wall.

## 2026-05-25 15:38 UTC — role 1370 Wiz Partner Solutions Architect (gh-iframe via wiz.io wrapper)

**Result:** SUBMITTED ✅

- New iframe-wrapper host added: `wiz.io` → GH slug `wizinc` in `adapters/greenhouse_iframe.HOST_TO_GH_SLUG` (permanent pipeline fix — Wiz will keep posting roles weekly).
- Pre-submit dryrun surfaced 4 unknown custom Wiz screener questions (data-retention 12mo consent + Alphabet/Google employment history triplet). Added LABEL_RULES for all four (label substrings cover GH tenants reusing the same template language).
- First submit attempt FAILED (outcome=TIMEOUT) on two server-side validation errors:
  - Wiz's state dropdown uses full names (Washington, etc) but `r_state` returned 'WA' → fixed with abbrev→fullname map inside `r_state`.
  - "Have you ever worked for the local, state, or federal government?" matched generic `state` rule and got 'WA' → fixed by adding higher-priority govt rule (`worked for the local, state, or federal government → answer_no`) before the generic state line.
- Also generalized `r_answer_yes` / `r_answer_no` to match options whose label STARTS WITH 'Yes'/'No' (Wiz consent uses "Yes, I consent to the retention of my data." multi-word option). Helps any GH tenant with verbose option phrasing.
- Second submit: filled=17, review=0, declined=4, unresolved=0, blockers=0. Runner submitted via direct embed fallback (wrapper iframe wasn't injected into the wiz.io Next.js page, runner fell through to `https://job-boards.greenhouse.io/embed/job_app?for=wizinc&token=4683486006`). Email verification gate auto-handled (code `Pmr2x7MV` via gmail_imap).
- Confirmation URL: `https://job-boards.greenhouse.io/embed/job_app/confirmation?for=wizinc&token=4683486006`.
- Tracker: applied_by='auto', applied_on='2026-05-25', prep_status='submitted'. Backup `tracker.db.bak.20260525-role1370`.
- xlsx regenerated: Open 301, Applied 134, Manual Ready 7.
- Elapsed: ~9 min wall (most spent on dryrun rule fixes + double submit).

**Permanent pipeline fixes shipped (recurring-bleeding stopped):**
1. `adapters/greenhouse_iframe.py` — `wiz.io` host map entry.
2. `greenhouse_dryrun.py` — `r_state` abbrev→fullname mapping when options demand full names. Benefits ANY GH tenant with full-state-name dropdowns.
3. `greenhouse_dryrun.py` — `r_answer_yes`/`r_answer_no` fallback to startswith 'Yes'/'No' option matching. Benefits ANY GH tenant with verbose consent/agreement option phrasing.
4. `greenhouse_dryrun.py` — LABEL_RULES additions for 'federal government', talent-pool retention consent, Alphabet/Google employment history (Wiz's template is a copy-paste from a Google template — the rules will fire on any other tenant inheriting the same language).

**One-off vs recurring checklist (per AGENTS.md):**
- (1) Source of bad data: greenhouse_iframe adapter didn't know wiz.io. (2) Recurrence: YES, Wiz will keep posting. (3) Permanent home: `HOST_TO_GH_SLUG` map ✓. (4) Migration: no backfill needed; new wrapper detection is forward-looking only.
- (1) Source of state-abbrev bug: `r_state` resolver. (2) Recurrence: YES, any GH tenant with full-state-name dropdowns hits this. (3) Permanent home: `r_state` resolver itself ✓.
- (1) Source of govt-question bug: missing LABEL_RULE + generic `state` rule too greedy. (2) Recurrence: YES, generic-state-word collisions are a known footgun (already 3 HIGH-PRIORITY phrase rules guarding this). (3) Permanent home: more specific rules added before generic ✓.

**Note for future audit:** The runner submitted on the FIRST attempt with `filled_needs_review` values silently (no abort). That's a runtime safety gap — `filled_needs_review` items SHOULD probably block submit unless explicitly waived. Flagging here, not fixing in this subagent (scope creep).

## 2026-05-25 15:50 UTC — role 1342 Chime PgM Performance Effectiveness — SUBMITTED
- ATS: Greenhouse (legacy boards.greenhouse.io → job-boards.greenhouse.io/chime/jobs/8535236002)
- Confirmation: https://job-boards.greenhouse.io/chime/jobs/8535236002/confirmation
- Plan ran cleanly (text/dropdowns/phone-iti/decline-demographics/GDPR/resume) — 0 errors.
- 2 gaps vs emitted plan, fixed inline:
  - Country dropdown (required, label `Country*`, react-select with "United States +1") was not in plan.dropdowns. Set manually.
  - Demographic `4024621002` ("I identify as:*") emitted as `demographic_question_4024621002` but real id had no prefix. Set manually to "I don't wish to answer". (Catch-all step 7 didn't pick it because the bare label "I identify as" doesn't match the gender|race|ethnic|… regex.)
- New gotcha: **Chime Greenhouse ships an 8-char email security code gate** (`#security-input-0..7`, "A verification code was sent to cyshekari@gmail.com"). Submit button stays `disabled` until all 8 boxes are filled. Fetched via `fetch_company_code.py "chime" <since>` (code `qVcfmm8b`, subject "Security code for your application to Chime Financial, Inc"). Same pattern as Anthropic gate — playbook's JS_DETECT_VERIFICATION should already cover this, but standalone steps would benefit from a `security-input-*` check pre-submit.
- Lean-mode time: ~12 min wall (single role, manual step execution from emitted plan).

---

## 2026-05-25 — role 893 Tesla PM Customer Support Operations ($221K, fit=92)

**Result: BLOCKED 2026-05-25: ats-no-driver | Tesla custom ATS | needs Tesla-specific Playwright driver**

- Source URL was LinkedIn (`/jobs/view/...-4399834590`). `inline_submit.py --role-id 893` → `ValueError: unsupported ATS URL` (no LinkedIn auto-resolve in current code path).
- Resolved manually via web_search: `https://www.tesla.com/careers/search/job/product-manager-customer-support-operations-266962`.
- Updated `tracker.roles.app_url` + `jd_url` to the Tesla careers URL; `agent_notes` annotated.
- `inline_submit.py` only dispatches greenhouse / ashby / lever / workday. Tesla runs a custom in-house ATS on `tesla.com/careers/search/job/<slug>-<id>` (likely with internal account flow). No driver in repo.
- `web_fetch` of the Tesla page returned **403 Access Denied** (Akamai edge) — Tesla blocks server-side fetchers, so even JD scraping needs a real browser.
- Captcha policy not exercised (never reached an apply UI).
- Did NOT prep an account on cyshekari+tesla@gmail.com; deferred until/unless a Tesla driver is built.
- Lean-mode time: ~4 min wall (URL resolve + tracker update + log).

**Recurrence flag:** If Tesla rolls more PM roles into the queue, every one will hit this same wall. Permanent fix = either (a) build a Tesla custom-ATS Playwright driver (account login + form prep, similar shape to Workday), or (b) downgrade Tesla to prep-only manual STATUS=MANUAL_READY with a stub packet folder so they show up on the "Manual Ready" xlsx sheet for Cyrus. Recommend (b) as the short-term unblock; (a) only if Tesla volume justifies the build.

---

## 2026-05-25 — role 829 Rivian TPM Manufacturing Engineering (Atlanta) — BLOCKED

**Status:** BLOCKED (no submit, no prep packet). Tracker row updated with flag + agent_notes.

**What happened:**
- Brief assumed Rivian = Workday tenant (`rivian.wd5.myworkdayjobs.com`). **Wrong.**
- Rivian actually uses **iCIMS** (`us-careers-rivian.icims.com`). Confirmed via `https://careers.rivian.com/careers-home/` → search iframe points at iCIMS.
- Pipeline's `inline_submit.py` only routes greenhouse / greenhouse_iframe / ashby / lever / workday. No iCIMS adapter exists.
- LinkedIn URL (`/jobs/view/4407094249`) is guest-blocked for the offsite Apply link — needs a logged-in session or browser automation to resolve to the iCIMS posting URL.
- iCIMS search page returns a stub iframe shell to curl; the inner search results page returns 143 bytes (likely needs JS/cookies). Couldn't grab the job slug without a real browser.
- Google search via curl also returned no usable iCIMS deep link.

**Decisions (lean mode, ~12 min):**
- Did NOT update `app_url` — would have polluted the tracker with a guess. Left LinkedIn URL in place.
- Did NOT run `inline_submit.py` — would have produced an `unknown` ATS error and burned no useful packet.
- Did NOT spin up Playwright to resolve via authenticated LinkedIn (out of scope for LEAN, also no LinkedIn cookies wired here).
- Logged BLOCKED in tracker: `flags += 'submit-blocked 2026-05-25 (Rivian uses iCIMS, no adapter; LinkedIn URL only)'` and full diagnostic in `agent_notes`.

**Recurrence flag (one-off vs pipeline):**
This will recur for every Rivian role (and any other iCIMS company in the queue). Three permanent options:
  (a) Build an iCIMS Playwright driver (account create + form prep) — only worth it if iCIMS volume is meaningful. Currently 1 Rivian role.
  (b) Add an iCIMS prep-only path that emits a `MANUAL_READY` stub packet so the role surfaces on the "Manual Ready" xlsx sheet for Cyrus's manual apply (mirrors the Workday-unvalidated pattern). Cheap.
  (c) Build a LinkedIn-→-direct-apply-URL resolver (browser w/ session cookies) and feed the resolved URL back through the existing routers. Most leverage long-term — fixes every LinkedIn-only row.
Recommend (b) as the immediate unblock + (c) as the higher-leverage follow-up. Filed as a finding, not actioning here.

**Captcha policy:** not exercised — never reached an apply UI.

## 2026-05-25 16:09 UTC — Role 1368 Smartsheet PM II Growth → SUBMITTED ✅

- **ATS**: Greenhouse (NEW job-boards.greenhouse.io variant — different from legacy boards.greenhouse.io)
- **Confirmation**: `/confirmation` URL + "Thank you for your interest in Smartsheet! Your application has been received."
- **Duration**: ~10 min agent time
- **Captcha**: reCAPTCHA Enterprise v3 (invisible badge) — passed silently
- **Email verification**: 8-char code (`mR6tReVN`) prompt after first Submit click; fetched via `fetch_company_code.py smartsheet`, filled 8 separate `security-input-{0..7}` inputs, re-submitted.
- **Pipeline impact**: 282 open, 136 applied (was 135), 7 manual ready.

### Pipeline gaps surfaced (job-boards.greenhouse.io vs legacy)

The dryrun spec + step plan that `inline_submit.py` generates assumed the **legacy** Greenhouse boards form. On this variant:

1. **No "Apply" reveal button** — form is inline on page load.
2. **Comboboxes need real click (browser.act:click via ref)** to open, not synthetic mousedown/mouseup. After listbox opens, options work via synthetic clicks. Driver should fall back to ref-click if synthetic mousedown leaves `aria-expanded=false`.
3. **File upload requires `ref` of visible Attach button**, not `selector=input#resume`. The hidden input accepts files via setter but the form doesn't pick them up (the visible button handler is the real path).
4. **Location combobox uses async remote search** (Google Places) — needs real typing (slowly:true), then ~1.5s wait, then click react-select option.
5. **Demographic decline label**: include `"I don't wish to answer"` (straight apostrophe) AND `"I don\u2019t wish to answer"` (curly) — different Greenhouse tenants render differently. Smartsheet uses straight.
6. **Privacy-notice questions**: "Yes" answer rarely exists; usually it's a verbose "I acknowledge receipt of the X Privacy Notice." — driver should fuzzy-match on `acknowledge` keyword.
7. **8-char security code post-submit**: Greenhouse on this variant gates Submit with email verification. Worth adding to `inline_submit.py` as a standard post-submit step (poll for `Security code` label, run `fetch_company_code.py <company>`, fill 8 `security-input-{0..7}` inputs, re-click Submit).

### Recurrence risk

Likely recurs on every job-boards.greenhouse.io role (Smartsheet, and any other tenant on this new template). Worth a pipeline update before next batch. NOT touching `inline_submit.py` from this subagent — flagging only.

## 2026-05-25 16:07 UTC — role 1269 Peterson Cat Sales Engineer
- ATS: workday (tenant: petersonholding, non-Adobe)
- Result: PREP-READY-MANUAL (expected)
- prep_status='manual_ready', prep_path set
- Packet: applications/submitted/peterson-cat-sales-engineer-req-2023-1770/
- Apply URL: https://petersonholding.wd1.myworkdayjobs.com/PetersonJobs/job/San-Leandro-CA/Sales-Engineer_REQ-2023-1770/apply
- Elapsed: 25.9s
[2026-05-25T16:11:19Z] role 1267 Curtiss-Wright SE → PREP-READY-MANUAL (Workday non-Adobe, 27.1s, prep_status=manual_ready)
[2026-05-25T16:12:30Z] role 1286 Stark Tech SE-HVAC → BLOCKED: ats-no-driver | Phenom People ATS (careers.starktech.com is a Phenom site — phenompeople.com CDN, widgetApiEndpoint=/widgets, phApp namespace, refNum=STNSTLUS) | needs new Phenom People driver (no existing adapter/submitter). Tracker app_url left unchanged; role left in open/unapplied state.

## 2026-05-25 ~16:55 UTC — role 1095 Afresh SE — BLOCKED (browser instability)

**Approach:** New-GH-template (job-boards.greenhouse.io). Inline form, no Apply reveal. Form structure confirmed: text inputs work, file upload via `browser.upload ref` works (uploaded resume successfully on first session).

**Failure mode:** Browser tab dies repeatedly during/after combobox interaction.
- Attempt 1: Text fields + resume upload OK. First combo click (work-auth, e24) → listbox opened, picked "Yes" OK. Second combo click (sponsorship Yes/No) hit `PortInUseError: Port 18800 is already in use`. Retried OK. Third click (gender, e28) returned but `targetId` silently rerouted to HackerRank tab — Afresh tab disappeared.
- Attempt 2 (per instructions: ONE retry cookie-cleared): `browser.stop` → `rm -rf user-data` → `browser.start` → reopen Afresh. Refilled text + resume. Started combos. After first evaluate the Afresh tab disappeared again, eval silently rerouted to HackerRank.

**Confirmed combo structure (for future Afresh attempts):** Native `<input role="combobox">` typeahead, NOT react-select. IDs: `question_17743590004` (work-auth), `question_17743591004` (sponsorship), `gender`, `hispanic_ethnicity`, `veteran_status`, `disability_status`, plus `country`. No standalone "Hispanic/Latino" question in dryrun JSON — present in actual form (one more declined demographic).

**Root cause hypothesis:** Afresh page has reCAPTCHA Enterprise (`6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0`) loaded eagerly. Headless Chrome (no-sandbox) appears to be crashing or losing the Afresh tab specifically — possibly the captcha challenge fires on combobox interaction and the headless browser kills the page. **HackerRank tab persists across browser restarts**, hinting that's where things settle.

**Per task spec: 1 retry done, captcha-suspected → BLOCKED.**

**Tracker / status:** Did NOT mutate tracker. STATUS.md still = PREP-READY (set by inline_submit). Resume staged at `/tmp/openclaw/uploads/Cyrus_Shekari_Resume_afresh_5986020004_v2.pdf` if Cyrus wants to drive manually.

**Time spent:** ~12min.


---
## 2026-05-25 ~16:46-17:05 UTC — role-id 1357 HackerRank FDE (GH new-template) — BLOCKED

**Result:** BLOCKED on Chrome tab crash, not captcha challenge.

**What happened:**
1. `inline_submit.py --role-id 1357` → CSP-blocklist skip (HackerRank tenant is on `greenhouse_csp_blocklist.yaml` — reCAPTCHA Enterprise).
2. `inline_submit.py --role-id 1357 --ignore-csp-block` → OK in 50.5s, plan generated (17/17 fields filled), PDF + cover ready.
3. Browser open `https://job-boards.greenhouse.io/hackerrank/jobs/7482134` → form loaded inline (new GH template, no Apply reveal — confirmed Smartsheet/Hume pattern).
4. **Tab ghost issue:** A leftover Afresh tab from session-restore (`Tabs_*` files) kept stealing focus from `act:evaluate` calls. Driver picked the most-recently-active tab regardless of explicit `targetId`. Fixed by `browser stop` → `pkill -9 chrome` → delete `Sessions/Tabs_*` + `Current/Last Tabs/Session` + `Cookies*` → restart (also satisfied "ONE cookie-clear retry on captcha" budget).
5. Reopened HackerRank cleanly. Text fields (8/8) filled via native setter. Upload via `ref=e63` (Attach button, per quirk — NOT `input#resume`) succeeded after staging PDF to `/tmp/openclaw/uploads/`. All 6 question dropdowns set via react-select pattern: dispatch `mousedown`/`mouseup`/`click` on `.select__control` → wait → click matching `[role="option"]`. All 6 reported `ok:true` with correct displayed value.
6. Next `act:evaluate` (re-filling text in case page reset) → `tab not found`. Page crashed to about:blank. Headless Chrome dies on this page reliably (probably the reCAPTCHA Enterprise + Google API content iframes — same root cause that put HackerRank on the CSP blocklist in the first place).

**Not done:**
- Location field (Google Places, type slowly) — never reached.
- Submit click + confirmation observation — never reached.
- Post-submit 8-char email code (`fetch_company_code.py hackerrank` → `security-input-{0..7}`) — never reached.

**Time burn:** ~20 min.

**Recommendation:**
- HackerRank is correctly on `greenhouse_csp_blocklist.yaml`. The `--ignore-csp-block` override produces a fillable form but headless Chrome can't sustain the page long enough to submit. Manual submission required.
- STATUS.md left as PREP-READY-MANUAL (prep is good — fields validated against real form; resume + cover answers in workdir; user can copy from `cover_answers.md` and submit manually in ~3 min).
- No tracker mutation. No `applied_by`/`applied_on` set.
- Cookie-clear retry budget consumed.


## 2026-05-25T16:58 UTC — role 1375 Anduril Program Manager - SkillBridge — BLOCKED
- ATS: legacy boards.greenhouse.io (redirects to job-boards.greenhouse.io)
- Slug: anduril-5142847007
- Result: **BLOCKED disqualifier** | SkillBridge requires active-military status | manual-skip or hide-program-roles
- Detail: required dropdown `question_12083811007` = "Are you currently a US transitioning service member that is eligible and interested in a SkillBridge Fellowship?*" — civilian = forced "No" = self-disqualifying for a SkillBridge-only role.
- Form-fill worked end-to-end (text fields + 5 react-select dropdowns picked cleanly), resume NOT uploaded, Submit NOT clicked.
- Tracker: status='skip', flags+='skillbridge-only'. No applied_by/applied_on mutation.
- STATUS.md: applications/submitted/anduril-5142847007/STATUS.md
- Recommendation: add a SkillBridge/Fellowship filter to role-discovery, or have the LLM classifier flag titles containing "SkillBridge" as `non-eligible` (skip gate).
- Elapsed: ~6 min.

## 2026-05-25 17:13 UTC — SUBMIT 1374 Anduril Mission Ops PM Group 5

- ✅ **SUBMITTED** | role_id=1374 | slug=anduril-5141963007 | fit=45
- Confirmation: https://job-boards.greenhouse.io/andurilindustries/jobs/5141963007/confirmation
- Verification code: H50figGg (8-char, gmail_imap fetched in 1st poll)
- Elapsed: ~14 min wall, well under 18-min cap
- **Findings worth surfacing to MEMORY.md / playbook:**
  1. Anduril (boards.greenhouse.io/andurilindustries) DOES use the 8-char post-submit verification code. Brief said "No 8-char post-submit code" for legacy `boards.greenhouse.io` — INCORRECT for this tenant. The code is mailed by `no-reply@us.greenhouse-mail.io`, subject `Security code for your application to Anduril Industries`. Form renders 8 `security-input-N` slots after first Submit. Plain native setter + InputEvent works; submit auto-enables when all 8 filled.
  2. Anduril's PhoneInput widget includes a SEPARATE Greenhouse react-select labeled "Country" (`#country`) that is REQUIRED but NOT exposed by the boards-api dryrun. It's the phone country code selector (United States = "+1") and its display value is shown as ONLY the dialing code (e.g. "+1"), which is confusing. The dryrun-emitted plan therefore tries to submit without it and fails the first time with "Select a country". Fix: pick "United States +1" option via standard mousedown/mouseup/click on the react-select control.
  3. The role variant 5141963007 had NO US-citizen / ITAR / SkillBridge dropdowns. So no disqualifier path triggered.
- No retries needed, no captcha challenge (reCAPTCHA v3 invisible passed silently from VM).

---

## Role 1542 — Asana, Solutions Engineer (gh_iframe via asana.com)
- **Subagent label:** SUBMIT role-id 1542 Asana SE (GH iframe via asana.com wrapper)
- **Started:** 2026-05-25 17:08 UTC. **Submitted:** 17:14 UTC. ~6 min wall clock.
- **Outcome:** SUBMITTED. Tracker: applied_by=auto, applied_on=2026-05-25, status=applied, prep_status=submitted.
- **ATS path:** `asana.com/jobs/apply/<jid>?gh_jid=<jid>` → embeds `job-boards.greenhouse.io/embed/job_app?for=asana&token=<jid>` (NEW template — strict validityToken-gated). First attempt blocked at dryrun (LABEL_RULES misses), second attempt blocked at server-side validation (sex demographic missing), third attempt cleared all gates + 8-char security code.
- **Pipeline tweaks landed (permanent — kept):**
  1. `adapters/greenhouse_iframe.py` HOST_TO_GH_SLUG: added `asana.com → asana`.
  2. `greenhouse_dryrun.py` LABEL_RULES + resolver:
     - Two new "otherwise engaged" rules → `worked_at_company_before` for Asana's "Have you been employed, or otherwise engaged, by an Asana entity in the past?" (the `, or otherwise engaged,` interjection blocks the existing `been employed by` rule).
     - Four new "U.S. government entity" / "type 'N/A'" rules → new `literal_na` resolver (`r_literal_na` returns `"N/A"`) for the follow-up free-text gate.
  3. `greenhouse_filler.py` DEMO_LABEL_RE: added `\bsex\b` so "Please identify your sex" routes to the demographic decline path rather than the multi_checkboxes (US/USA) branch. Word-boundary guard prevents matches inside `essex`, `unisex`, etc.
  4. `greenhouse_iframe_runner.py` outcome detector: also returns `conf=true` when `location.href` contains `/job_app/confirmation` (the new-template confirmation page renders no "thank you" copy on first paint, so previous body-text-only detector timed out even on successful submits).
- **Verification signal:** Email security-code interstitial fired AFTER first Submit (8x `security-input-N` boxes), runner auto-pulled `XBaGqE81` from Gmail (`gmail_imap.wait_for_verification_code`), filled + resubmitted, server redirected to `/embed/job_app/confirmation`. Server-side validation passed (`fieldErrs: []`, `grecapErrText: ''`).
- **Findings worth surfacing to MEMORY.md / playbook:**
  1. Asana uses the Anduril-style 8-char post-submit verification code (not previously documented for asana.com wrapper). Same `wait_for_verification_code` + `JS_SUBMIT_VERIFICATION_CODE` flow handles it transparently.
  2. New-template Greenhouse iframes (`job-boards.greenhouse.io/embed/job_app`) render the confirmation page at `/embed/job_app/confirmation?for=<slug>&token=<jid>` with NO "thank you" copy on first paint. Body-text-only success detectors will time out and report TIMEOUT on real successes. URL-based detection is now the canonical signal.
  3. `Please identify your sex` is a `multi_value_multi_select` (with "I don't wish to answer" option) but Greenhouse renders it as react-select in the new template, NOT as a `<fieldset>` of checkboxes. The plan-builder needs to route it through `declined_demo_multi` so the `JS_DECLINE_DEMOGRAPHICS` react-select fallback can pick it up.
  4. The wrapper-host pattern (asana.com Netlify Next.js page that iframes a strict-template GH board) is a NEW iframe-wrapper class — the existing 18 wrappers we had were almost all legacy-template-friendly. Worth scouting for other companies on Netlify/Vercel with `boards-api.greenhouse.io/v1/boards/<slug>` JSON behind a custom URL.
- No captcha challenge (invisible reCAPTCHA Enterprise passed silently from the VM). No retry was needed beyond the planned three iterations (one for adapter routing, one for label rules, one to fix the sex routing).
