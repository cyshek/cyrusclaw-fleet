STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T21:03:41+00:00

role_id: 3514
ats: workday (tenant: ms)
company: Morgan Stanley
role: Program Manager - Parametric

=====================================================================
APPLY HERE (MANUAL):

    https://ms.wd5.myworkdayjobs.com/External/job/Seattle-Washington-United-States-of-America/Program-Manager---Parametric_PT-JR037957-1/apply

=====================================================================

Packet contents:
  - JD.md                 (8457 chars of JD body)
  - Cyrus_Shekari_Resume_workday-ms_Program-Manager-Parametric-PT-JR037957-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3514;
then re-run render_xlsx.py.
