STATUS: SUBMITTED (auto)
Generated: 2026-05-25T00:30:00+00:00
Submitted: 2026-05-24

role_id: 1130
ats: workday (tenant: salesforce) — FIRST VALIDATED SALESFORCE SUBMIT
company: Salesforce
role: Solution Engineer (Pre-Sales)- Small, Medium & Growth Business
job_req: JR318273

=====================================================================
CONFIRMATION
=====================================================================
Candidate Home (https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/userHome) shows:

  Job Title:           Solution Engineer (Pre-Sales)- Small, Medium & Growth Business
  Job Req:             JR318273
  My Application Status: In Consideration
  Date Submitted:      May 24, 2026

Driver `is_confirmation` returned True (review-page → Submit → post-submit URL matched
canonical Workday completion pattern; `ok: true` and empty blockers in driver result).

Account used: cyshekari+salesforce@gmail.com (Workday account created during this run;
account_created=true persisted to .workday-creds.json).

=====================================================================
PIPELINE NOTES (per-tenant gotchas — see WORKDAY-FULL-AUTO-PROGRESS.md 2026-05-24 section)
=====================================================================
1. source--source dropdown structure: Salesforce uses a `multiSelectContainer` widget. Clicking
   #source--source opens the menu correctly, BUT promptOption divs from previously-opened
   menus (e.g. phoneNumber--countryPhoneCode) remain `offsetParent`-visible in DOM and
   were being picked by fallback_first_sub. Driver now snapshots existing promptOption
   keys before opening and excludes them from "first new option" picks.

2. source path for Salesforce: [("Job Board", "External Career Site Sources"),
   ("LinkedIn", "Linkedin Jobs", ..., "LinkedIn Connection Post", "Glassdoor", "Indeed")].
   Driver picks "External Career Site Sources" → "Indeed".

3. Account flow: Create Account submitted, redirected to Sign In (account already existed
   from earlier failed probe). Driver's existing redirect-to-signin fallback handled it.

4. Application Questions added to driver keyword pool:
   - "government responsibilities" / "been responsible for matters" + "government" → No
   - "post-government employment restriction" / "no post-government" attestation → Yes
   - "debarred" / "proposed for debarment" / "declared ineligible for aw" → No
   - "preferred geographic location" → text fill with "San Francisco, CA"
   - "Regarding future positions at Salesforce" → opt-in (Yes, ...) via opt-discovery
     diagnostic (driver now opens the dropdown, logs options, picks first matching
     pattern). Picked "Yes, I would like to receive communications about Salesforce
     and future openings".

5. phoneNumber--countryPhoneCode is NOT required on Salesforce (form advanced cleanly
   despite Playwright `fill_text` retry-loop on a stale promptOption overlay).

=====================================================================
Files in this packet
=====================================================================
  - JD.md                 (Workday JD body)
  - Cyrus_Shekari_Resume_workday-salesforce_JR318273_v2.pdf  (uploaded successfully)
  - cover_answers.md      (not needed — driver handled all questions)
  - meta.json, prefill.json
  - confirmation screenshots in ../.workday-debug/salesforce-jr318273/002220-* and 002230-post-submit.png
