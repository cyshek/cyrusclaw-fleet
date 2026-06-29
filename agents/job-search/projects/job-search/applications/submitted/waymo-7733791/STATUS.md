PREP-READY-IFRAME-RUNNER — 2026-06-29T08:04:16+00:00

role_id: 3375
slug:    waymo-7733791
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-waymo-7733791.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7733791/Cyrus_Shekari_Resume_waymo_7733791_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-7733791/cover_answers.md
wrapper: https://careers.withwaymo.com/jobs?gh_jid=7733791

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug waymo-7733791

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
