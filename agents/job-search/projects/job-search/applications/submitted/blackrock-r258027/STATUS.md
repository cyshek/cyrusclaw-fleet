STATUS: PREP-READY-MANUAL
Generated: 2026-06-25T20:15:25+00:00

role_id: 3671
ats: workday (tenant: blackrock)
company: BlackRock
role: Oracle Fusion Solutions Architect

=====================================================================
APPLY HERE (MANUAL):

    https://blackrock.wd1.myworkdayjobs.com/BlackRock_Professional/job/Atlanta-GA/Associate--Financial-Consolidation-Architect--Oracle-FCCS-_R258027/apply

=====================================================================

Packet contents:
  - JD.md                 (7752 chars of JD body)
  - Cyrus_Shekari_Resume_workday-blackrock_R258027_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3671;
then re-run render_xlsx.py.
