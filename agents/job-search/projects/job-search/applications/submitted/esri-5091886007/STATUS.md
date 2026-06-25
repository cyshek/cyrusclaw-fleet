PREP-READY-IFRAME-RUNNER — 2026-06-25T04:50:10+00:00

role_id: 3627
slug:    esri-5091886007
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-esri-5091886007.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/esri-5091886007/Cyrus_Shekari_Resume_esri_5091886007_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/esri-5091886007/cover_answers.md
wrapper: https://www.esri.com/careers/5091886007?gh_jid=5091886007

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug esri-5091886007

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
