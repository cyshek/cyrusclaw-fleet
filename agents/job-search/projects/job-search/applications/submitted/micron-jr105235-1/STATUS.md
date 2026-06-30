STATUS: PREP-READY-MANUAL
Generated: 2026-06-29T14:55:01+00:00

role_id: 3904
ats: workday (tenant: micron)
company: Micron
role: IT Solution Architect

=====================================================================
APPLY HERE (MANUAL):

    https://micron.wd1.myworkdayjobs.com/External/job/Boise-ID---Main-Site/IT-Solution-Architect_JR105235-1/apply

=====================================================================

Packet contents:
  - JD.md                 (5934 chars of JD body)
  - Cyrus_Shekari_Resume_workday-micron_JR105235-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3904;
then re-run render_xlsx.py.
