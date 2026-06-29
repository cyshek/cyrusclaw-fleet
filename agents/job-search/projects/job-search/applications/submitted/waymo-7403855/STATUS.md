PREP-READY-IFRAME-RUNNER — 2026-06-29T08:04:09+00:00

role_id: 3374
slug:    waymo-7403855
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-waymo-7403855.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7403855/Cyrus_Shekari_Resume_waymo_7403855_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7403855/cover_answers.md
wrapper: https://careers.withwaymo.com/jobs?gh_jid=7403855

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug waymo-7403855

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
