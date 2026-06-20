# STATUS — Nordstrom 2049 fresh-account Workday submit

- Role: 2049 Nordstrom Product Manager 2 — Experimentation, Observability & Platform Infrastructure (Hybrid - Seattle)
- URL: https://nordstrom.wd501.myworkdayjobs.com/nordstrom_careers/job/Seattle-WA/Product-Manager-2---Experimentation--Observability---Platform-Infrastructure--Hybrid---Seattle-_R-837009
- Tenant: nordstrom (no fresh_alias yet → will MINT, mode=create_fresh)

## DB safety (done)
- backup: tracker.db.bak.nord2049-1780981686
- integrity BEFORE: ok
- row 2049 pre-state: status='blocked', block_reason='workday-profile-prefill-uncommittable', applied_by='', applied_on='', prep_status=''

## Plan
1. inline_submit.py --role-id 2049 → PREP-ONLY (tailors resume, builds dryrun spec). [IN PROGRESS]
2. _workday_runner.py --url <url> --tenant nordstrom --role-id 2049 --resume <tailored pdf> --dryrun  → sanity review
3. _workday_runner.py (same, no --dryrun) → real submit
4. On exit 0 + real confirmation → write applications/submitted/<slug>/STATUS.md, UPDATE roles (re-verify still blocked first), render_xlsx.py

## Phase: DRYRUN running
- PREP done (137.6s). Tailored PDF: applications/submitted/nordstrom-product-manager-2-experimentation-observ/Cyrus_Shekari_Resume_workday-nordstrom_Product-Manager-2-Experimentation-Observ_v2.pdf
- prep flipped prep_status='manual_ready' (NOT applied — row still status='blocked')
- slug = nordstrom-product-manager-2-experimentation-observ
- dryrun cmd: _workday_runner.py --url <url> --tenant nordstrom --role-id 2049 --resume <pdf> --source LinkedIn --dryrun
