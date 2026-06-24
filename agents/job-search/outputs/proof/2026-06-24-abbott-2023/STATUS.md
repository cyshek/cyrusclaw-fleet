STATUS: PREP-READY-MANUAL
Generated: 2026-06-22T07:09:14+00:00

role_id: 2023
ats: workday (tenant: abbott)
company: Abbott
role: Product Manager

=====================================================================
APPLY HERE (MANUAL):

    https://abbott.wd5.myworkdayjobs.com/abbottcareers/job/Taiwan---Taipei/Product-Manager_31143425/apply

=====================================================================

Packet contents:
  - JD.md                 (1818 chars of JD body)
  - Cyrus_Shekari_Resume_workday-abbott_31143425_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2023;
then re-run render_xlsx.py.
