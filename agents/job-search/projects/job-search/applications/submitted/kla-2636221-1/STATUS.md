STATUS: PREP-READY-MANUAL
Generated: 2026-06-25T05:49:00+00:00

role_id: 3641
ats: workday (tenant: kla)
company: KLA
role: Forward Deployed Engineer

=====================================================================
APPLY HERE (MANUAL):

    https://kla.wd1.myworkdayjobs.com/Search/job/Ann-Arbor-MI/Forward-Deployed-Engineer_2636221-1/apply

=====================================================================

Packet contents:
  - JD.md                 (8585 chars of JD body)
  - Cyrus_Shekari_Resume_workday-kla_2636221-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3641;
then re-run render_xlsx.py.
