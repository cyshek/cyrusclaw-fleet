STATUS: PREP-READY-MANUAL
Generated: 2026-06-28T08:15:57+00:00

role_id: 585
ats: workday (tenant: bakerhughes)
company: Baker Hughes
role: Solutions Architect- Production Solutions, Americas

=====================================================================
APPLY HERE (MANUAL):

    https://bakerhughes.wd5.myworkdayjobs.com/BakerHughes/job/US-TX-HOUSTON-575-N-DAIRY-ASHFORD-RD-ENERGY-CENTER-II-EC2/Solutions-Architect--Production-Solutions--Americas_R162747/apply

=====================================================================

Packet contents:
  - JD.md                 (7016 chars of JD body)
  - Cyrus_Shekari_Resume_workday-bakerhughes_R162747_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=585;
then re-run render_xlsx.py.
