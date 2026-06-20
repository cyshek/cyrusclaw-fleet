PREP-READY-IFRAME-RUNNER — 2026-06-04T14:02:49+00:00

role_id: 2709
slug:    harness-5145394007
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-harness-5145394007.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/harness-5145394007/Cyrus_Shekari_Resume_harnessinc_5145394007_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/harness-5145394007/cover_answers.md
wrapper: https://www.harness.io/company/jobs/apply?gh_jid=5145394007&gh_jid=5145394007

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug harness-5145394007

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
