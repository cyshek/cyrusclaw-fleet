PREP-READY-IFRAME-RUNNER — 2026-06-29T08:22:54+00:00

role_id: 916
slug:    wiz-4665622006
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-wiz-4665622006.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/wiz-4665622006/Cyrus_Shekari_Resume_wizinc_4665622006_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/wiz-4665622006/cover_answers.md
wrapper: https://www.wiz.io/careers/job/4665622006/:title?gh_jid=4665622006

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug wiz-4665622006

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
