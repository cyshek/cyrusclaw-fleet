STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T01:02:51+00:00

role_id: 3512
ats: workday (tenant: ms)
company: Morgan Stanley
role: Workplace Platforms Product Manager, Associate/AVP

=====================================================================
APPLY HERE (MANUAL):

    https://ms.wd5.myworkdayjobs.com/External/job/Purchase-New-York-United-States-of-America/Workplace-Platforms-Product-Manager--Associate-AVP_PT-JR035812/apply

=====================================================================

Packet contents:
  - JD.md                 (6773 chars of JD body)
  - Cyrus_Shekari_Resume_workday-ms_Workplace-Platforms-Product-Manager-Asso_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3512;
then re-run render_xlsx.py.
