STATUS: PREP-READY-MANUAL
Generated: 2026-06-09T06:58:54+00:00

role_id: 2891
ats: workday (tenant: paypal)
company: PayPal
role: Product Manager 2 - Technical

=====================================================================
APPLY HERE (MANUAL):

    https://wd1.myworkdaysite.com/recruiting/paypal/jobs/job/San-Jose-California-United-States-of-America/Product-Manager-2---Technical_R0136890/apply

=====================================================================

Packet contents:
  - JD.md                 (8512 chars of JD body)
  - Cyrus_Shekari_Resume_workday-paypal_R0136890_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2891;
then re-run render_xlsx.py.

---
## 2026-06-10 SUBMIT ATTEMPT — BLOCKED (EXIT 5, loop-cap)
- runner: _workday_runner.py (fresh account cyshekari+wd-paypal-202606101106@gmail.com, no email-verify)
- My Information: OK (source=Indeed committed). Resume uploaded OK.
- My Experience: BLOCKED — Workday regenerates a NEW empty work-experience block each visit
  (workExperience-165 -> -290 -> -417), each carrying required jobTitle*/companyName*.
  prefill-guard fills the empty block and converges (empty 1->0) each pass, but a fresh empty
  block reappears on the next step-visit, so the step never clears -> revisited >3x -> loop-cap EXIT 5.
  Runner also misclassifies its own filled blocks as "unexpected prefilled WE on a fresh account".
- confirmation_observed: NO. submitted_by: (none — NOT submitted). resume_attached: yes (upload succeeded but app not submitted).
- status committed: blocked / block_reason=workday-experience-loop-cap
