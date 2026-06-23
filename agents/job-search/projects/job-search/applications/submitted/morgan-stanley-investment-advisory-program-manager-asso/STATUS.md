STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T00:58:00+00:00

role_id: 3511
ats: workday (tenant: ms)
company: Morgan Stanley
role: Investment Advisory Program Manager, Associate

=====================================================================
APPLY HERE (MANUAL):

    https://ms.wd5.myworkdayjobs.com/External/job/Purchase-New-York-United-States-of-America/Investment-Advisory-Program-Manager--Associate_PT-JR036790/apply

=====================================================================

Packet contents:
  - JD.md                 (6160 chars of JD body)
  - Cyrus_Shekari_Resume_workday-ms_Investment-Advisory-Program-Manager-Asso_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3511;
then re-run render_xlsx.py.
