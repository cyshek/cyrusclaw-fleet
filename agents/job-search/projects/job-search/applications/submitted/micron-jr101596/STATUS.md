STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T00:29:29+00:00

role_id: 3487
ats: workday (tenant: micron)
company: Micron
role: New College Grad - SPMO Cost Program Manager

=====================================================================
APPLY HERE (MANUAL):

    https://micron.wd1.myworkdayjobs.com/External/job/Manassas-VA----Fab-6/F6-SPMO-Cost-Program-Manager_JR101596/apply

=====================================================================

Packet contents:
  - JD.md                 (5310 chars of JD body)
  - Cyrus_Shekari_Resume_workday-micron_JR101596_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3487;
then re-run render_xlsx.py.
