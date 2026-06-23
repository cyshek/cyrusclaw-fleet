STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T00:24:06+00:00

role_id: 3502
ats: workday (tenant: marvell)
company: Marvell
role: Engineering Program Manager / Project Manager

=====================================================================
APPLY HERE (MANUAL):

    https://marvell.wd1.myworkdayjobs.com/MarvellCareers/job/US-CA---Irvine/Engineering-Program-Manager---Project-Manager_2601773/apply

=====================================================================

Packet contents:
  - JD.md                 (5734 chars of JD body)
  - Cyrus_Shekari_Resume_workday-marvell_2601773_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3502;
then re-run render_xlsx.py.
