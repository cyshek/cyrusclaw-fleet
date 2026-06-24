PREP-READY-IFRAME-RUNNER — 2026-05-26T18:15:46+00:00

role_id: 1352
slug:    pinterest-7901910
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-pinterest-7901910.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/pinterest-7901910/Cyrus_Shekari_Resume_pinterest_7901910_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/pinterest-7901910/cover_answers.md
wrapper: https://www.pinterestcareers.com/jobs/?gh_jid=7901910

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug pinterest-7901910

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
