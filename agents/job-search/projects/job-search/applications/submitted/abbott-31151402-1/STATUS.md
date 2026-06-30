STATUS: PREP-READY-MANUAL
Generated: 2026-06-29T14:22:08+00:00

role_id: 3910
ats: workday (tenant: abbott)
company: Abbott
role: Program Manager, R&D

=====================================================================
APPLY HERE (MANUAL):

    https://abbott.wd5.myworkdayjobs.com/abbottcareers/job/United-States---Minnesota---Plymouth/Program-Manager_31151402-1/apply

=====================================================================

Packet contents:
  - JD.md                 (6972 chars of JD body)
  - Cyrus_Shekari_Resume_workday-abbott_31151402-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3910;
then re-run render_xlsx.py.
