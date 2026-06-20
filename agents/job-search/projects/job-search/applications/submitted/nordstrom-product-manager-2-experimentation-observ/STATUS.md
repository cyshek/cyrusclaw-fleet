STATUS: PREP-READY-MANUAL
Generated: 2026-06-09T05:10:33+00:00

role_id: 2049
ats: workday (tenant: nordstrom)
company: Nordstrom
role: Product Manager 2 - Experimentation, Observability & Platform Infrastructure (Hybrid - Seattle)

=====================================================================
APPLY HERE (MANUAL):

    https://nordstrom.wd501.myworkdayjobs.com/nordstrom_careers/job/Seattle-WA/Product-Manager-2---Experimentation--Observability---Platform-Infrastructure--Hybrid---Seattle-_R-837009/apply

=====================================================================

Packet contents:
  - JD.md                 (6695 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nordstrom_Product-Manager-2-Experimentation-Observ_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2049;
then re-run render_xlsx.py.
