PREP-READY-IFRAME-RUNNER — 2026-06-25T03:51:26+00:00

role_id: 3609
slug:    cato-networks-4903797101
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-cato-networks-4903797101.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/cato-networks-4903797101/Cyrus_Shekari_Resume_catonetworks_4903797101_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/cato-networks-4903797101/cover_answers.md
wrapper: https://www.catonetworks.com/careers/careers-post/4903797101?gh_jid=4903797101

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug cato-networks-4903797101

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
