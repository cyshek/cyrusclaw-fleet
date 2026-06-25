PREP-READY-IFRAME-RUNNER — 2026-06-25T03:11:07+00:00

role_id: 3619
slug:    waymo-8027001
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-waymo-8027001.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-8027001/Cyrus_Shekari_Resume_waymo_8027001_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/waymo-8027001/cover_answers.md
wrapper: https://careers.withwaymo.com/jobs?gh_jid=8027001

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug waymo-8027001

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
