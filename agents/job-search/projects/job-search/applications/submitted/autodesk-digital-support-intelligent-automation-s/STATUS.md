STATUS: PREP-READY-MANUAL
Generated: 2026-06-27T22:08:28+00:00

role_id: 3746
ats: workday (tenant: autodesk)
company: Autodesk
role: Digital Support Intelligent Automation Solutions Engineer

=====================================================================
APPLY HERE (MANUAL):

    https://autodesk.wd1.myworkdayjobs.com/Ext/job/Massachusetts-USA---Remote/Digital-Support-Intelligent-Automation-Solutions-Engineer_26WD99564-1/apply

=====================================================================

Packet contents:
  - JD.md                 (7433 chars of JD body)
  - Cyrus_Shekari_Resume_workday-autodesk_Digital-Support-Intelligent-Automation-S_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=3746;
then re-run render_xlsx.py.
