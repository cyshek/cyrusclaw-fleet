PREP-READY-IFRAME-RUNNER — 2026-06-04T14:31:11+00:00

role_id: 2766
slug:    actively-ai-5051155008
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-actively-ai-5051155008.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/actively-ai-5051155008/Cyrus_Shekari_Resume_activelyai_5051155008_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/actively-ai-5051155008/cover_answers.md
wrapper: http://www.actively.ai/careers?gh_jid=5051155008

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug actively-ai-5051155008

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
