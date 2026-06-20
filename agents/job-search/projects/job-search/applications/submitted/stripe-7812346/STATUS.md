PREP-READY-IFRAME-RUNNER — 2026-05-31T12:26:57+00:00

role_id: 879
slug:    stripe-7812346
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-stripe-7812346.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/stripe-7812346/Cyrus_Shekari_Resume_stripe_7812346_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/stripe-7812346/cover_answers.md
wrapper: https://stripe.com/jobs/search?gh_jid=7812346

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug stripe-7812346

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
