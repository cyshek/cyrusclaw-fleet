# GEICO 2021 — SUBMITTED ✅

**Role:** GEICO — Product Manager (R0062160)
**ATS:** Workday (tenant=geico)
**Apply URL:** https://geico.wd1.myworkdayjobs.com/External/job/Bethesda-MD/Product-Manager_R0062160/apply
**Location:** Bethesda, MD (2 Locations)
**Submitted:** 2026-06-10 ~22:16 PDT (2026-06-11 05:16 UTC) — hourly grind run5, EXIT 0
**Account:** existing FRESH alias cyshekari+wd-geico-202606110006@gmail.com (signin_fresh; already created+activated for GEICO 2358 earlier today)
**submitted_by:** auto
**resume_attached:** YES — `applications/submitted/geico-r0062160/Cyrus_Shekari_Resume_workday-geico_R0062160_v2.pdf` (tailored for R0062160 by inline_submit prep)

## CONFIRMATION
- **confirmation_text:** "thank you for applying" — matched in submit-confirmation page body by the runner's `verify_confirmation`.
- **confirmation_method:** Workday Review → `pageFooterNextButton` labeled "Submit" → confirmation body keyword verified → runner returned **EXIT 0 = "SUBMITTED - confirmation verified"**.
- **confirmation_screenshot:** `.workday-debug/geico-2021-after-submit.png` (copy of post-submit confirmation page; the success-prune kept this evidence shot, 11 step shots pruned).
- **confirmation_url:** Workday submit-confirmation page (post-submit; GEICO does not expose a stable public confirmation URL — proof is the screenshot + EXIT 0 + body-text match).
- **runner_log:** `.workday-debug/geico-2021-run5.log`

## ANSWERS GIVEN (Application Questions)
- Are you 18 years or older? → **Yes**
- Do you have a high school diploma or equivalent? → **Yes**
- Are you legally authorized to work in the United States? → **Yes** (US citizen)
- Will you now or in the future require any type of sponsorship? → **No**
- Do you currently hold / have you ever held a professional state-issued (legal) license? → **No** (factual)
- Do you have a familial, romantic, or extraprofessional relationship with a current GEICO employee? → **No** (factual)
- Have you worked previously as a GEICO associate? → **No** (factual)
- Are you a current or former contractor of GEICO? → **No** (factual)
- Do you understand in-person attendance at the assigned GEICO office may be required? → **Yes**
- "read and acknowledge" ack listbox → **"I have read and acknowledge"**
- "What is your desired salary?" (free text) → **160000** (maximize-advancing; within PM range)
- "List your reasons for leaving your last three positions." (free text) → professional growth-oriented answer (internships concluded as scheduled; pursuing full-time PM/TPM scope)
- Voluntary disclosures (ethnicity / gender / veteran) → declined; terms & conditions accepted.

## NOTES
- Followed the EXACT proven GEICO 2358 (R0061267) recipe via `_workday_runner.py` — same tenant, same fresh-alias sign-in, same `handle_ack_widget` + `fill_freetext_questions` + resume-upload + WE-fill-from-tailored-resume path.
- The documented `workday-fresh-we-block-uncommittable-on-nav` wall did NOT trigger: WE blocks filled from the tailored resume, converged (`total=3 empty=0`), and persisted across Next-nav. `STILL-REQUIRED-EMPTY: []`, POSTNEXT forensic clean (no errors/invalid/unanswered).
- One Microsoft WE end-date read-back failed but did not block (block converged empty=0 anyway; that field was non-required for that entry).

## tracker.db (committed by this worker)
```sql
UPDATE roles SET status='applied', applied_by='auto', applied_on='2026-06-10', block_reason=NULL,
  agent_notes=agent_notes||' | SUBMITTED 2026-06-10 (hourly grind run5): GEICO Workday R0062160 ... EXIT 0, "thank you for applying" verified ...'
WHERE id=2021;
```
Then re-ran `render_xlsx.py`.
