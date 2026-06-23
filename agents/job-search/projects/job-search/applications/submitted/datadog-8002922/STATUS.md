PREP-READY-IFRAME-RUNNER — 2026-06-23T07:55:57+00:00

role_id: 3124
slug:    datadog-8002922
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-datadog-8002922.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-8002922/Cyrus_Shekari_Resume_datadog_8002922_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-8002922/cover_answers.md
wrapper: https://careers.datadoghq.com/detail/8002922/?gh_jid=8002922

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug datadog-8002922

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
