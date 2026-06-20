SUBMITTED — 2026-05-25T00:55 UTC

role_id: 1233
company: Comet
role: Product Manager - Opik
location: East Coast USA
est_tc: (not on Levels)
fit: ?
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=comet&token=7503269003
confirmation_text: greenhouse confirmation page reached (conf=true, fieldErrs=[], grecapErr empty)
verification_code_used: sHErYUOn
submitted_by: auto (job-search single-role worker, role 1233)
resume_attached: Cyrus_Shekari_Resume_comet_7503269003_v2.pdf
tracker_db_backup: tracker.db.bak.20260524-role1233

Notes:
- NEW iframe-wrapper host: `comet.com` → GH slug `comet`. Added to `adapters/greenhouse_iframe.HOST_TO_GH_SLUG` (permanent pipeline fix).
- Wrapper-iframe lookup failed (comet's careers page does NOT embed a `#grnhse_iframe`; it loads `go.comet.ml` Marketo form instead). Runner fell back to direct embed URL (`job-boards.greenhouse.io/embed/job_app?for=comet&token=7503269003`) and the form submitted successfully — recaptcha was invisible/no validity-token required for this tenant.
- 16/16 fields filled cleanly after 3 LABEL_RULES additions (permanent pipeline fixes in `greenhouse_dryrun.py` LABEL_RULES):
    1. `"do you have N+ years" / "N+ years of product"` → `answer_yes` (placed BEFORE `years of product management` so PM yes/no doesn't fall through to numeric resolver). Was causing `filled_needs_review` with value="2" against [Yes,No] options.
    2. `"proven experience shipping" / "shipping high-quality products" / "planning to launch to maintenance"` → `answer_yes`. Was a hard blocker.
- Application questions on Comet form: LinkedIn URL, city+state, sponsorship (No), 2+yr PM XP (Yes), years-as-SWE (text→"2"), PM-in-devtools (Yes), AI-agents-XP (Yes), proven-shipping (Yes). No AI-disclosure question, no US-auth question, no travel%, no school, no demographics asked on this tenant.
- Single email verification code (`sHErYUOn`) fetched via gmail_imap.wait_for_verification_code, one-shot fill of #security-input-0..7, click "Submit application" → confirmation page.
- Resume upload: `verify_resume` reported `filename_visible=true` (Filestack committed), even though `click_attach` reported "no #resume input and no filename in body" mid-step — committed before that check ran. Same Filestack quirk as Guidewheel.
