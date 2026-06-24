STATUS: PREP-READY-MANUAL
Generated: 2026-06-09T19:03:31+00:00

role_id: 2121
ats: workday (tenant: exfo)
company: EXFO
role: Solutions Engineer

=====================================================================
APPLY HERE (MANUAL):

    https://exfo.wd10.myworkdayjobs.com/EXFO_Careers/job/Remote---USA/Solutions-Engineer_R-100191/apply

=====================================================================

Packet contents:
  - JD.md                 (3047 chars of JD body)
  - Cyrus_Shekari_Resume_workday-exfo_Solutions-Engineer-R-100191_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2121;
then re-run render_xlsx.py.
