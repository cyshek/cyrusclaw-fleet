PREP-READY-IFRAME-RUNNER — 2026-06-26T01:37:32+00:00

role_id: 3698
slug:    asana-7913978
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-asana-7913978.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/asana-7913978/Cyrus_Shekari_Resume_asana_7913978_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/asana-7913978/cover_answers.md
wrapper: https://www.asana.com/jobs/apply/7913978?gh_jid=7913978

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug asana-7913978

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
