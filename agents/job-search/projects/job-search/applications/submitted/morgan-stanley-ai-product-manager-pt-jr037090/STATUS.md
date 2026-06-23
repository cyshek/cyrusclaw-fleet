STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T08:20:50+00:00

role_id: 2033
ats: workday (tenant: ms)
company: Morgan Stanley
role: AI Product Manager

=====================================================================
APPLY HERE (MANUAL):

    https://ms.wd5.myworkdayjobs.com/External/job/New-York-New-York-United-States-of-America/AI-Product-Manager_PT-JR037090/apply

=====================================================================

Packet contents:
  - JD.md                 (7069 chars of JD body)
  - Cyrus_Shekari_Resume_workday-ms_AI-Product-Manager-PT-JR037090_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2033;
then re-run render_xlsx.py.
