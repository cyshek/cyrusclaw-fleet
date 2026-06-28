STATUS: PREP-READY-MANUAL
Generated: 2026-06-28T08:36:38+00:00

role_id: 3670
ats: workday (tenant: blackrock)
company: BlackRock
role: AI Product Manager, Associate - Aladdin AI

=====================================================================
APPLY HERE (MANUAL):

    https://blackrock.wd1.myworkdayjobs.com/BlackRock_Professional/job/New-York-NY/AI-Product-Manager--Associate---Aladdin-AI_R263783/apply

=====================================================================

Packet contents:
  - JD.md                 (7774 chars of JD body)
  - Cyrus_Shekari_Resume_workday-blackrock_R263783_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3670;
then re-run render_xlsx.py.
