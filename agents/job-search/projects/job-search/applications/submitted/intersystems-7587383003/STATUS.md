PREP-READY-IFRAME-RUNNER — 2026-06-30T03:21:39+00:00

role_id: 3454
slug:    intersystems-7587383003
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-intersystems-7587383003.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/intersystems-7587383003/Cyrus_Shekari_Resume_intersystems_7587383003_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/intersystems-7587383003/cover_answers.md
wrapper: https://www.intersystems.com/careers/careers-search/?gh_jid=7587383003

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug intersystems-7587383003

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
