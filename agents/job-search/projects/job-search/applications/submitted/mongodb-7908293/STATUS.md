PREP-READY-IFRAME-RUNNER — 2026-06-02T09:03:50+00:00

role_id: 2234
slug:    mongodb-7908293
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-mongodb-7908293.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7908293/Cyrus_Shekari_Resume_mongodb_7908293_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7908293/cover_answers.md
wrapper: https://www.mongodb.com/careers/job/?gh_jid=7908293

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug mongodb-7908293

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
