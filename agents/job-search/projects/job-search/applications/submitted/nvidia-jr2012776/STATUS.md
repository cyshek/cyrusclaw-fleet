STATUS: PREP-READY-MANUAL
Generated: 2026-06-28T08:15:59+00:00

role_id: 1577
ats: workday (tenant: nvidia)
company: NVIDIA
role: Solutions Architect, Infrastructure

=====================================================================
APPLY HERE (MANUAL):

    https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-WA-Redmond/Solutions-Architect--Infrastructure_JR2012776/apply

=====================================================================

Packet contents:
  - JD.md                 (4941 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nvidia_JR2012776_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=1577;
then re-run render_xlsx.py.
