STATUS: PREP-READY-MANUAL
Generated: 2026-06-23T00:20:23+00:00

role_id: 3501
ats: workday (tenant: marvell)
company: Marvell
role: Technical Program Manager - Central CAD & Design Services

=====================================================================
APPLY HERE (MANUAL):

    https://marvell.wd1.myworkdayjobs.com/MarvellCareers/job/Santa-Clara-CA/Technical-Program-Manager---Central-CAD---Design-Services_2602323/apply

=====================================================================

Packet contents:
  - JD.md                 (7204 chars of JD body)
  - Cyrus_Shekari_Resume_workday-marvell_2602323_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3501;
then re-run render_xlsx.py.
