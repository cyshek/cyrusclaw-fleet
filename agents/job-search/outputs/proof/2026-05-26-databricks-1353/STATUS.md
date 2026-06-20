PREP-READY-IFRAME-RUNNER — 2026-05-26T18:25:01+00:00

role_id: 1353
slug:    databricks-8419271002
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-databricks-8419271002.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/databricks-8419271002/Cyrus_Shekari_Resume_databricks_8419271002_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/databricks-8419271002/cover_answers.md
wrapper: https://databricks.com/company/careers/open-positions/job?gh_jid=8419271002

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug databricks-8419271002

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
