STATUS: PREP-READY-MANUAL
Generated: 2026-06-27T22:09:30+00:00

role_id: 3811
ats: workday (tenant: homedepot)
company: The Home Depot
role: Product Manager - Finance

=====================================================================
APPLY HERE (MANUAL):

    https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/CUMBERLAND-PKWY-OFFICE---1147/Product-Manager---Finance_Req183417-1/apply

=====================================================================

Packet contents:
  - JD.md                 (7126 chars of JD body)
  - Cyrus_Shekari_Resume_workday-homedepot_Req183417-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3811;
then re-run render_xlsx.py.
