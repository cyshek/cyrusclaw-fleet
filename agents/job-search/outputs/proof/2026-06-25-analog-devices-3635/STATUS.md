STATUS: PREP-READY-MANUAL
Generated: 2026-06-24T23:10:47+00:00

role_id: 3635
ats: workday (tenant: analogdevices)
company: Analog Devices
role: Sales Data & Analytics Product Manager

=====================================================================
APPLY HERE (MANUAL):

    https://analogdevices.wd1.myworkdayjobs.com/External/job/US-MA-Wilmington/Sales-Data---Analytics-Product-Manager_R262818/apply

=====================================================================

Packet contents:
  - JD.md                 (4982 chars of JD body)
  - Cyrus_Shekari_Resume_workday-analogdevices_R262818_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3635;
then re-run render_xlsx.py.
