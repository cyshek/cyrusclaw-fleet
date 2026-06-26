STATUS: PREP-READY-MANUAL
Generated: 2026-06-25T18:26:41+00:00

role_id: 3625
ats: workday (tenant: bestbuycanada)
company: Best Buy Canada
role: Product Manager (2 Openings: Reverse Logistics OR Mobile Activation)

=====================================================================
APPLY HERE (MANUAL):

    https://bestbuycanada.wd3.myworkdayjobs.com/BestBuyCA_Career/job/00000-Canadian-Headquarters/Product-Manager-x2_R-50994/apply

=====================================================================

Packet contents:
  - JD.md                 (5214 chars of JD body)
  - Cyrus_Shekari_Resume_workday-bestbuycanada_Product-Manager-x2-R-50994_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3625;
then re-run render_xlsx.py.
