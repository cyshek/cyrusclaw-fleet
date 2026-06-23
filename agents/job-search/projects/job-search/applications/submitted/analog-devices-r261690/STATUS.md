STATUS: PREP-READY-MANUAL
Generated: 2026-06-22T18:20:14+00:00

role_id: 3498
ats: workday (tenant: analogdevices)
company: Analog Devices
role: Program Manager, Data Governance and Stewardship

=====================================================================
APPLY HERE (MANUAL):

    https://analogdevices.wd1.myworkdayjobs.com/External/job/US-MA-Wilmington/Program-Manager--Data-Governance-and-Stewardship_R261690/apply

=====================================================================

Packet contents:
  - JD.md                 (5910 chars of JD body)
  - Cyrus_Shekari_Resume_workday-analogdevices_R261690_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3498;
then re-run render_xlsx.py.
