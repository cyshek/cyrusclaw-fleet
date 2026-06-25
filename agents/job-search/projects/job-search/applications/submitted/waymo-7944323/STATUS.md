PREP-READY-IFRAME-RUNNER — 2026-06-25T03:15:33+00:00

role_id: 3620
slug:    waymo-7944323
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-waymo-7944323.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7944323/Cyrus_Shekari_Resume_waymo_7944323_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7944323/cover_answers.md
wrapper: https://careers.withwaymo.com/jobs?gh_jid=7944323

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug waymo-7944323

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
