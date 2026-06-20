PREP-READY-IFRAME-RUNNER — 2026-05-31T12:30:40+00:00

role_id: 958
slug:    abnormal-security-7728984003
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-abnormal-security-7728984003.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/abnormal-security-7728984003/Cyrus_Shekari_Resume_abnormalsecurity_7728984003_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/abnormal-security-7728984003/cover_answers.md
wrapper: https://abnormal.ai/careers/jobs/7728984003?gh_jid=7728984003

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug abnormal-security-7728984003

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
