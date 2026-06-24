STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T21:08:51+00:00

role_id: 3515
ats: workday (tenant: servicetitan)
company: ServiceTitan
role: Solutions Engineer, Enterprise

=====================================================================
APPLY HERE (MANUAL):

    https://servicetitan.wd1.myworkdayjobs.com/ServiceTitan/job/US-Remote/Solutions-Engineer--Enterprise_JR113481/apply

=====================================================================

Packet contents:
  - JD.md                 (6129 chars of JD body)
  - Cyrus_Shekari_Resume_workday-servicetitan_JR113481_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3515;
then re-run render_xlsx.py.
