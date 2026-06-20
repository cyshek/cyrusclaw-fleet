PREP-READY-IFRAME-RUNNER — 2026-05-26T18:22:26+00:00

role_id: 1366
slug:    elastic-7939709
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-elastic-7939709.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/elastic-7939709/Cyrus_Shekari_Resume_elastic_7939709_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/elastic-7939709/cover_answers.md
wrapper: https://jobs.elastic.co/jobs?gh_jid=7939709&gh_jid=7939709

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug elastic-7939709

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
