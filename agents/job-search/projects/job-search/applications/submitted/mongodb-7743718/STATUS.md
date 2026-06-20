PREP-READY-IFRAME-RUNNER — 2026-05-31T12:29:44+00:00

role_id: 953
slug:    mongodb-7743718
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-mongodb-7743718.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7743718/Cyrus_Shekari_Resume_mongodb_7743718_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mongodb-7743718/cover_answers.md
wrapper: https://www.mongodb.com/careers/job/?gh_jid=7743718

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug mongodb-7743718

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
