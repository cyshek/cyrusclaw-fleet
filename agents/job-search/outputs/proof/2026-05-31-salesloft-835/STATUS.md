PREP-READY-IFRAME-RUNNER — 2026-05-31T12:24:58+00:00

role_id: 835
slug:    salesloft-6674655
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-salesloft-6674655.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/salesloft-6674655/Cyrus_Shekari_Resume_salesloft_6674655_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/salesloft-6674655/cover_answers.md
wrapper: https://www.salesloft.com/company/careers?gh_jid=6674655

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug salesloft-6674655

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
