PREP-READY-IFRAME-RUNNER — 2026-06-25T04:16:59+00:00

role_id: 3550
slug:    databricks-8595123002
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-databricks-8595123002.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/databricks-8595123002/Cyrus_Shekari_Resume_databricks_8595123002_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/databricks-8595123002/cover_answers.md
wrapper: https://databricks.com/company/careers/open-positions/job?gh_jid=8595123002

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug databricks-8595123002

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
