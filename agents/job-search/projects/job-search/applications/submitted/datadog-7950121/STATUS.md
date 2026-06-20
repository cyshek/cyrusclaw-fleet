PREP-READY-IFRAME-RUNNER — 2026-06-02T03:49:48+00:00

role_id: 1945
slug:    datadog-7950121
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-datadog-7950121.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-7950121/Cyrus_Shekari_Resume_datadog_7950121_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/datadog-7950121/cover_answers.md
wrapper: https://careers.datadoghq.com/detail/7950121/?gh_jid=7950121

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug datadog-7950121

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
