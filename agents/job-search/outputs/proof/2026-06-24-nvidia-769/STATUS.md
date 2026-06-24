STATUS: PREP-READY-MANUAL
Generated: 2026-06-07T21:00:41+00:00

role_id: 2829
ats: workday (tenant: nvidia)
company: Nvidia
role: Infrastructure Solutions Architect

=====================================================================
APPLY HERE (MANUAL):

    https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Infrastructure-Solutions-Architect_JR2019167/apply

=====================================================================

Packet contents:
  - JD.md                 (5124 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nvidia_JR2019167_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=2829;
then re-run render_xlsx.py.
