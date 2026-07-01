STATUS: PREP-READY-MANUAL
Generated: 2026-07-01T03:02:55+00:00

role_id: 3976
ats: workday (tenant: amfam)
company: American Family Insurance
role: Commercial Product Management - Product Manger Work Comp

=====================================================================
APPLY HERE (MANUAL):

    https://amfam.wd1.myworkdayjobs.com/Careers/job/Remote-Work/Product-Manager---Workers-Compensation--Hybrid-_R38809-1/apply

=====================================================================

Packet contents:
  - JD.md                 (6096 chars of JD body)
  - Cyrus_Shekari_Resume_workday-amfam_R38809-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3976;
then re-run render_xlsx.py.
