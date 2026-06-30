STATUS: PREP-READY-MANUAL
Generated: 2026-06-29T14:16:27+00:00

role_id: 3909
ats: workday (tenant: abbott)
company: Abbott
role: Global Product Manager – Coronary (Downstream Marketing)

=====================================================================
APPLY HERE (MANUAL):

    https://abbott.wd5.myworkdayjobs.com/abbottcareers/job/United-States---California---Santa-Clara/Global-Product-Manager_31149257-1/apply

=====================================================================

Packet contents:
  - JD.md                 (10197 chars of JD body)
  - Cyrus_Shekari_Resume_workday-abbott_31149257-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3909;
then re-run render_xlsx.py.
