PREP-READY-IFRAME-RUNNER — 2026-06-29T08:03:05+00:00

role_id: 2849
slug:    fanduel-7951178
plan:    /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-fanduel-7951178.json
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/fanduel-7951178/Cyrus_Shekari_Resume_fanduel_7951178_v2.pdf
cover:   /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/fanduel-7951178/cover_answers.md
wrapper: https://www.fanduel.careers/open-positions?gh_jid=7951178

Calling agent / cron: do NOT execute the browser plan with the
generic browser tool — the canonical /embed/job_app URL is
reCAPTCHA-Enterprise gated. Instead run:

    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug fanduel-7951178

and overwrite this STATUS.md with the runner's outcome block
(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).
