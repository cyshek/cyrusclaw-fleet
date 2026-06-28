STATUS: PREP-READY-MANUAL
Generated: 2026-06-28T08:15:58+00:00

role_id: 1182
ats: workday (tenant: nvidia)
company: NVIDIA
role: Solutions Architect – OEM AI

=====================================================================
APPLY HERE (MANUAL):

    https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Solutions-Architect---OEM-AI_JR2016349/apply

=====================================================================

Packet contents:
  - JD.md                 (4870 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nvidia_JR2016349_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (answers for open-text/essay questions — copy-paste as needed)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=1182;
then re-run render_xlsx.py.
