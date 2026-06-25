PREP-READY-IFRAME-RUNNER — 2026-06-25T04:54:38+00:00

role_id: 3628
slug:    esri-5151688007
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-esri-5151688007.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/esri-5151688007/Cyrus_Shekari_Resume_esri_5151688007_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/esri-5151688007/cover_answers.md
wrapper: https://www.esri.com/careers/5151688007?gh_jid=5151688007

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug esri-5151688007

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
