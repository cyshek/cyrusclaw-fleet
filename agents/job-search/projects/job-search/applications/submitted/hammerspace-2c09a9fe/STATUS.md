PREP-READY-RIPPLING-RUNNER — 2026-05-30T18:39:51+00:00

role_id: 1614
ats:     rippling (board: hammerspace)
company: Hammerspace
role:    Forward Deployed Engineer
slug:    hammerspace-2c09a9fe
pdf:     /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/hammerspace-2c09a9fe/Cyrus_Shekari_Resume_rippling-hammerspace_2c09a9fe_v2.pdf
cover:   NOT GENERATED
apply:   https://ats.rippling.com/hammerspace/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc

Calling agent / cron: do NOT execute via the generic browser tool.
Rippling submits via a direct-API flow (S3 presigned upload + Cloudflare
Turnstile solve + POST /apply). Invoke the runner CLI:

    .venv/bin/python role-discovery/rippling_filler.py \
        --slug hammerspace --job-id 2c09a9fe-fedd-472a-9198-f2f6001934bc \
        --resume /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/hammerspace-2c09a9fe/Cyrus_Shekari_Resume_rippling-hammerspace_2c09a9fe_v2.pdf \
        --answers <answers.json> \
        --out /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/hammerspace-2c09a9fe/submit_artifacts.json \
        --dry-run   # remove for real submit

<answers.json> must contain the standard 9-field basicQuestions schema
(first_name, last_name, email, current_company, location, linkedin_link,
phone_number, plus optional cover-letter freeform). See
rippling_filler.py header + applications/_rippling-smoke-2026-05-30.json
for the verified shape.

On success overwrite this STATUS.md with the SubmitArtifacts outcome
and stamp tracker.db (applied_by='rippling-runner', applied_on=<date>,
prep_status='submitted').
