STATUS: PREP-READY-MANUAL
Generated: 2026-05-30T18:25:47+00:00

role_id: 1456
ats: workday (tenant: nordstrom)
company: Nordstrom
role: Product Manager 2 - Payments Experience (Hybrid - Seattle)

=====================================================================
APPLY HERE (MANUAL):

    https://nordstrom.wd501.myworkdayjobs.com/nordstrom_careers/job/San-Jose-CA/Seasonal-Restaurant-Front-of-House---Bazille---Valley-Fair_R-844548/apply

=====================================================================

Packet contents:
  - JD.md                 (3512 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nordstrom_Seasonal-Restaurant-Front-of-House-Bazil_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=1456;
then re-run render_xlsx.py.
