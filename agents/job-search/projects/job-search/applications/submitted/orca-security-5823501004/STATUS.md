PREP-READY-IFRAME-RUNNER — 2026-05-31T12:24:10+00:00

role_id: 813
slug:    orca-security-5823501004
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-orca-security-5823501004.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/orca-security-5823501004/Cyrus_Shekari_Resume_orcasecurity_5823501004_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/orca-security-5823501004/cover_answers.md
wrapper: https://orca.security/about/careers/5823501004?gh_jid=5823501004

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug orca-security-5823501004

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
