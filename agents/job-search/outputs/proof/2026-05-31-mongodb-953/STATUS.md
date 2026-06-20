PREP-READY-IFRAME-RUNNER — 2026-05-31T12:21:39+00:00

role_id: 752
slug:    mongodb-7793281
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-mongodb-7793281.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7793281/Cyrus_Shekari_Resume_mongodb_7793281_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7793281/cover_answers.md
wrapper: https://www.mongodb.com/careers/job/?gh_jid=7793281

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug mongodb-7793281

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
