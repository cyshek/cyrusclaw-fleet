PREP-READY-IFRAME-RUNNER — 2026-05-31T12:20:11+00:00

role_id: 623
slug:    datadog-7554877
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-datadog-7554877.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-7554877/Cyrus_Shekari_Resume_datadog_7554877_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-7554877/cover_answers.md
wrapper: https://careers.datadoghq.com/detail/7554877/?gh_jid=7554877

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug datadog-7554877

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
