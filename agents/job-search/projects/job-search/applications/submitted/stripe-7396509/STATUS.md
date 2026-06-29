PREP-READY-IFRAME-RUNNER — 2026-06-29T08:22:48+00:00

role_id: 884
slug:    stripe-7396509
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-stripe-7396509.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/stripe-7396509/Cyrus_Shekari_Resume_stripe_7396509_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/stripe-7396509/cover_answers.md
wrapper: https://stripe.com/jobs/search?gh_jid=7396509

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug stripe-7396509

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
