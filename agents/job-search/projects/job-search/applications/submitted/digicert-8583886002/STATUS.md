PREP-READY-IFRAME-RUNNER — 2026-06-23T08:00:35+00:00

role_id: 3322
slug:    digicert-8583886002
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-digicert-8583886002.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/digicert-8583886002/Cyrus_Shekari_Resume_digicert_8583886002_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/digicert-8583886002/cover_answers.md
wrapper: https://www.digicert.com/careers/?gh_jid=8583886002

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug digicert-8583886002

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
