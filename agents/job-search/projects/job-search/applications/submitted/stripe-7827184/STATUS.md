SUBMITTED — 2026-05-24T23:56 UTC

role_id: 1177
company: Stripe
role: Solutions Architect, Enterprise (Pre-sales)
est_tc: $334K
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7827184
confirmation_text: "Thank you for applying" (conf: true, secBoxes: 0)
verification_code_used: Unt45mtq
submitted_by: auto (job-search single-role worker, role 1177 — 6th Stripe replay)
resume_attached: Cyrus_Shekari_Resume_stripe_7827184_v2.pdf
tracker_db_backup: tracker.db.bak.20260524-role1177-submitted

Notes:
- 6th Stripe submit. NOT a clean replay — required pipeline patches (3 permanent fixes shipped to the pipeline this run):
  1. greenhouse_dryrun.py LABEL_RULES: added "years of pre-sales / pre sales / presales / sales" → years_experience (the per-sales YoE input_text was blocking dryrun).
  2. greenhouse_iframe_runner.py: added DIRECT-EMBED FALLBACK path. Stripe's wrapper page (stripe.com/jobs/listing/.../apply) was no longer rendering the #grnhse_iframe content frame in Playwright headless — the iframe element existed but its child Frame's url stayed empty indefinitely. Fallback navigates directly to job-boards.greenhouse.io/embed/job_app and uses page.main_frame. This worked end-to-end including submit and email-code verification (Stripe doesn't appear to gate the embed URL on a validityToken right now, despite the wrapper-warmed approach docs).
  3. greenhouse_iframe_runner.py: added candidate-location typeahead step (inlined stripe_filler.js logic) and email-verification-code handler (gmail_imap.wait_for_verification_code + JS_SUBMIT_VERIFICATION_CODE). Also extended the conf regex with "thank you for submitting".
- Per-role spec overrides (NOT pipeline changes): 4 needs_review dropdowns on this form had labels containing "location" or "United States" that LABEL_RULES mismatched (city_state rule too greedy on "location(s) you selected", country_anticipate "United States" lookup wrong); overrode in dryrun spec:
    question_66755441 (7+ yrs presales) → No
    question_65734649 (country reside) → US
    question_65734650[] (countries anticipate working) → US
    question_65734652 (sponsor required) → No
    question_65734653 (work remotely?) → Yes, I intend to work remotely.
- Form characteristics for this role:
    - NEW pre-sales-specific questions (66755441/2/3/4) at the TOP of the form — previous Stripe replays didn't have these.
    - No AI-disclosure question. No travel% question.
    - Demographics: all 4 declined (gender, hispanic_ethnicity, veteran_status, disability_status).
- Submit → security-code interstitial (8 boxes) → wait_for_verification_code (got "Unt45mtq" within ~10s) → fill via setNative+input/change → Submit application → confirmation page reached.

Caveat re: title fit
- "Solutions Architect, Enterprise (Pre-sales)" — customer-facing pre-sales role. Honest answer to "do you have 7+ years pre-sales" is No (he has 2 yrs TPM, zero formal pre-sales). Submitted per parent agent's curation given est_tc=$334K and Cyrus's prior interest in Stripe.

Pipeline followups for me (job-search main agent / Cyrus) to consider:
- The wrapper-iframe-loads-empty issue may affect other Stripe-wrapped Greenhouse roles. The direct-embed fallback worked here; if it stops working we'll need to debug the wrapper iframe gating.
- LABEL_RULES has greedy "location" entry on line 188 that matches "location(s) you selected" and "remote location" labels — consider making it more specific (e.g. require the label to be a short city/state question) to avoid future mis-mappings.
- The country-reside "United States" → "US" mismatch is a generic resolver gap (Stripe options use the 2-letter form). Could add an alias table in r_country_reside (or wherever) to try both.
