PREP-READY-IFRAME-RUNNER — 2026-06-21T10:37:30+00:00

role_id: 2749
slug:    pubmatic-5177499008
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-pubmatic-5177499008.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/pubmatic-5177499008/Cyrus_Shekari_Resume_pubmatic_5177499008_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/pubmatic-5177499008/cover_answers.md
wrapper: https://pubmatic.com/job/?gh_jid=5177499008

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug pubmatic-5177499008

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
