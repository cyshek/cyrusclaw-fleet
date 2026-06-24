PREP-READY-IFRAME-RUNNER — 2026-06-24T04:37:14+00:00

role_id: 3105
slug:    brex-8443298002
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-brex-8443298002.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/brex-8443298002/Cyrus_Shekari_Resume_brex_8443298002_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/brex-8443298002/cover_answers.md
wrapper: https://www.brex.com/careers/8443298002?gh_jid=8443298002

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug brex-8443298002

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
