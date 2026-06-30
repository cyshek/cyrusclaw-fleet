STATUS: PREP-READY-MANUAL
Generated: 2026-06-29T14:38:07+00:00

role_id: 3820
ats: workday (tenant: snapchat)
company: Snap
role: Technical Program Manager, Level 4

=====================================================================
APPLY HERE (MANUAL):

    https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/Los-Angeles-California/Technical-Program-Manager--Level-4_R0045980/apply

=====================================================================

Packet contents:
  - JD.md                 (8839 chars of JD body)
  - Cyrus_Shekari_Resume_workday-snapchat_R0045980_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3820;
then re-run render_xlsx.py.
