PREP-READY-IFRAME-RUNNER — 2026-06-04T13:49:28+00:00

role_id: 2686
slug:    netskope-7786997
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-netskope-7786997.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/netskope-7786997/Cyrus_Shekari_Resume_netskope_7786997_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/netskope-7786997/cover_answers.md
wrapper: https://www.netskope.com/company/careers/open-positions/?gh_jid=7786997

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug netskope-7786997

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
