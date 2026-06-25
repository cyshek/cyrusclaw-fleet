PREP-READY-IFRAME-RUNNER — 2026-06-25T05:10:56+00:00

role_id: 3562
slug:    okta-7727835
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-okta-7727835.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/okta-7727835/Cyrus_Shekari_Resume_okta_7727835_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/okta-7727835/cover_answers.md
wrapper: https://www.okta.com/company/careers/opportunity/7727835?gh_jid=7727835

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug okta-7727835

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
