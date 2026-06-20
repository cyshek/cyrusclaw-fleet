STATUS: PREP-READY-MANUAL
Generated: 2026-05-17T05:41:18+00:00

role_id: 763
ats: workday (tenant: nvidia)
company: Nvidia
role: Software Program Manager, New Product Introduction

=====================================================================
APPLY HERE (MANUAL):

    https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Software-Program-Manager--New-Product-Introduction_JR2014827-1/apply

=====================================================================

Packet contents:
  - JD.md                 (3446 chars of JD body)
  - Cyrus_Shekari_Resume_workday-nvidia_JR2014827-1_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (NOT GENERATED — RuntimeError: cover_answer_generator failed (rc=1): Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 513, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 508, in main
    result = run(args.slug, args.max_retries)
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 447, in run
    dryrun_path = resolve_dryrun_path(slug)
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 167, in resolve_dryrun_path
    raise FileNotFoundError(
FileNotFoundError: dryrun ambiguous for slug nvidia-jr2014827-1: ['workday-intel-JR0283865-1.json', 'workday-nvidia-JR2014827-1.json', 'workday-adobe-R165611-1.json']
)
  - meta.json, prefill.json

Workday auto-submit is not implemented (per-tenant variability + MFA +
account creation makes it not worth building for the current role count).
Open the apply URL above, create/sign into the Workday account, paste
answers from cover_answers.md, attach the tailored PDF, submit.

Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',
applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id=763;
then re-run render_xlsx.py.
