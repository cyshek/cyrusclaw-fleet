PREP-READY-IFRAME-RUNNER — 2026-06-04T13:25:32+00:00

role_id: 2700
slug:    samsara-7187197
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-samsara-7187197.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/samsara-7187197/Cyrus_Shekari_Resume_samsara_7187197_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/samsara-7187197/cover_answers.md
wrapper: https://www.samsara.com/company/careers/roles/7187197?gh_jid=7187197

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug samsara-7187197

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
