STATUS: PREP-READY-MANUAL
Generated: 2026-06-27T00:42:34+00:00

role_id: 2021
ats: workday (tenant: geico)
company: GEICO
role: Product Manager

=====================================================================
APPLY HERE (MANUAL):

    https://geico.wd1.myworkdayjobs.com/External/job/Bethesda-MD/Product-Manager_R0062160/apply

=====================================================================

Packet contents:
  - JD.md                 (6316 chars of JD body)
  - Cyrus_Shekari_Resume_workday-geico_R0062160_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2021;
then re-run render_xlsx.py.
