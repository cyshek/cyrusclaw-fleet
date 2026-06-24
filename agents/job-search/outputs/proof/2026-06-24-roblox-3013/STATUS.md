PREP-READY-IFRAME-RUNNER — 2026-06-21T01:29:48+00:00

role_id: 2222
slug:    roblox-7895212
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-roblox-7895212.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/roblox-7895212/Cyrus_Shekari_Resume_roblox_7895212_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/roblox-7895212/cover_answers.md
wrapper: https://careers.roblox.com/jobs/7895212?gh_jid=7895212

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug roblox-7895212

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
