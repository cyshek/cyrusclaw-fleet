PREP-READY-IFRAME-RUNNER — 2026-05-31T12:03:54+00:00

role_id: 602
slug:    coreweave-4671723006
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-coreweave-4671723006.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/coreweave-4671723006/Cyrus_Shekari_Resume_coreweave_4671723006_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/coreweave-4671723006/cover_answers.md
wrapper: https://coreweave.com/careers/job?4671723006&board=coreweave&gh_jid=4671723006

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug coreweave-4671723006

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
