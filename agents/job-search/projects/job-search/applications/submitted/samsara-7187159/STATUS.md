PREP-READY-IFRAME-RUNNER — 2026-06-04T13:32:04+00:00

role_id: 2702
slug:    samsara-7187159
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-samsara-7187159.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/samsara-7187159/Cyrus_Shekari_Resume_samsara_7187159_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/samsara-7187159/cover_answers.md
wrapper: https://www.samsara.com/company/careers/roles/7187159?gh_jid=7187159

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug samsara-7187159

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
