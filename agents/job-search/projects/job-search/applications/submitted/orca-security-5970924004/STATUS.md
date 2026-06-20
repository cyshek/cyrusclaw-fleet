PREP-READY-IFRAME-RUNNER — 2026-05-31T12:22:42+00:00

role_id: 812
slug:    orca-security-5970924004
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-orca-security-5970924004.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/orca-security-5970924004/Cyrus_Shekari_Resume_orcasecurity_5970924004_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/orca-security-5970924004/cover_answers.md
wrapper: https://orca.security/about/careers/5970924004?gh_jid=5970924004

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug orca-security-5970924004

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
