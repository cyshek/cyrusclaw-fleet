# STATUS — Workday WE-cohort batch (generalize the cross-nav WE fix)

Subagent: workday-we-cohort-batch. Started 2026-06-10 23:30 PDT.
Fix under test: commits b12fc52 (`harden_my_experience_before_next` + WE block-count plateau + multi-source committed-date read) + b5d4d54 (Self-Identify disability loop). Proof template: Nvidia 2829 SUBMITTED.

Baseline: Workday suite = 121 passed (re-confirmed at start).
Sole browser worker (honored). Concurrent ENGINE-ONLY worker editing _ashby_runner.py — will NOT touch browser.

## Cohort (serial, in order)
1. Gates Foundation 2542 — Sr Technical PM — tenant gatesfoundation wd1
   URL: https://gatesfoundation.wd1.myworkdayjobs.com/Gates/job/Seattle-WA/Senior-Technical-Program-Manager_B021600
2. Boeing 2546 — Project Management Specialist — tenant boeing wd1
   URL: https://boeing.wd1.myworkdayjobs.com/EXTERNAL_CAREERS/job/USA---Everett-WA/Project-Management-Specialist_JR2026510327-2
3. PayPal 2891 — Product Manager 2, Technical — tenant paypal wd1
   URL: https://paypal.wd1.myworkdayjobs.com/jobs/job/San-Jose-California-United-States-of-America/Product-Manager-2---Technical_R0136890

Resume: projects/job-search/resume/Cyrus_Shekari_Resume.pdf

## Progress
- [x] **Gates 2542: SUBMITTED ✅** dryrun EXIT 0 → real submit EXIT 0 (`confirmation matched: thank you for applying`) → idempotent re-check EXIT 7 ALREADY_APPLIED (server proof) → bookkeeping DONE (DB backup tracker.db.bak.20260611-064059-wecohort, STATUS.md, roles set applied). WE fix GENERALIZED to 2nd tenant. harden plateaued clean total=6 empty=0.
- [x] **Boeing 2546: BLOCKED** (banked) — dryrun EXIT 5. NOT WE-count (harden plateaued clean) and NOT pollution (reproduced on a TRULY FRESH minted account). My required-upload fix DID clear Boeing's "Upload a file required" error, but a DEEPER hidden My-Experience blocker remains: Next clicks but RETURNS to My-Experience every visit → loop-cap. Root gap = `click_next()` swallows post-Next `page_errors()`, so a non-aria-required/Formik field or a Select-One listbox isn't surfaced. block_reason=`workday-myexperience-next-noadvance`. Engine fix committed **730c499** (upload-required re-upload, suite 122 green).
- [~] PayPal 2891: dryrun #1 EXIT 5 (polluted alias, same no-advance pattern, NO upload error). Re-testing on TRUE-fresh account to disambiguate hidden-blocker vs pollution (/tmp/paypal2891-dryrun2-truefresh.log).
- [ ] render_xlsx.py ONCE at end

## Engine edit (committed 730c499 — only my hunks)
- `_workday_runner.py` handle_experience: required-upload-on-revisit re-upload (Boeing-class), exempt from _MAX_RESUME_UPLOADS, bounded by _MAX_REQ_REUPLOADS=4.
- `test_workday_upload_reverify.py`: +Boeing scenario, updated eval seqs. Workday suite 122 passed.
- [ ] Boeing 2546: dryrun → submit → bookkeeping
- [ ] PayPal 2891: dryrun → submit → bookkeeping
- [ ] render_xlsx.py ONCE at end

(updated after each role)
