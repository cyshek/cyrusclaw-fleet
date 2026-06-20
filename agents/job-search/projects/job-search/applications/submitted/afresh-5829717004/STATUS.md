SUBMITTED — 2026-05-25T01:41 UTC

role_id: 994
company: Afresh
role: Product Manager
location: San Francisco, CA
fit: 92 (llm)
yoe: 3
est_tc: $0 (not on Levels)
confirmation_url: https://job-boards.greenhouse.io/afresh/jobs/5829717004/confirmation
confirmation_text: "Thank you for your interest in Afresh! We have received your application..." (title="Thank you for applying")
verification_code_used: m1VwV7PA
submitted_by: auto (job-search subagent, role 994)
resume_attached: Cyrus_Shekari_Resume_afresh_5829717004_v2.pdf
tracker_db_backup: tracker.db.bak.20260524-r994

Notes:
- Native Greenhouse board (job-boards.greenhouse.io/afresh/...). No iframe wrapper needed (HOST_TO_GH_SLUG entry NOT added — runner used direct embed/native fallback like Axon 1056).
- Two permanent LABEL_RULES additions to `greenhouse_dryrun.py` (apply to any future tenant phrasing the same way):
    1. "able to work on-site" → `ack_in_office` (placed BEFORE "willing to work from the office"; covers "Are you able to work on-site in <city>?" phrasings).
    2. "created roadmaps" + "products through from concept to launch" → `answer_yes` (placed near "shipping high-quality products"; covers PM-experience yes/no screeners about roadmaps/concept-to-launch).
- 19-field form, 15 filled / 4 declined-demographics / 0 blockers after the two LABEL_RULES additions.
- Required fields the dryrun didn't pre-spec but the live form demanded: address country (turned out to be the phone-iti country dropdown — id=`country`, label "Country*" — auto-set to United States/+1 by the phone iti step), `school--0`, `degree--0`. Filled inline:
    - school--0: "University of Houston" (per personal-info.json + brief). Required typing the full string to trigger the async-search react-select (typing first 6 chars was insufficient — the menu returned alphabetical "Aalborg…Aalto…" instead of filtered results).
    - degree--0: "Bachelor's Degree" (matched by startsWith).
- Gates per brief: AI=No → no AI-usage question on this form; the form's gen-coding-tools question is a skill-have-you-done (Yes is correct given Cyrus's PM exp). US-auth=Yes ✓. Sponsorship=No ✓. Demographics declined (gender/hispanic/veteran/disability). School=Univ of Houston ✓. Travel=100% → no travel% question; on-site SF = Yes (per brief 100% travel willingness).
- Disability_status required `I do not want to answer` — not in the standard declines list. Picked via fallback regex `/decline|prefer not|don'?t wish|do not wish|not to identify|not to disclose/i`. (Note: "I do not want to answer" should be added to the explicit declines list in `greenhouse_filler.py` JS_DECLINE_DEMOGRAPHICS — currently only matched by the fallback regex. Future improvement; not blocking now.)
- First Submit click required scrolling button into viewport and using clickCoords (not synthetic dispatchEvent click) because the React submit handler needs a trusted-coordinate click event. Synthetic .click() opened the email-verification step but the submit-with-code step required a coords click too.
- Email verification: single 8-char code (m1VwV7PA) fetched via gmail_imap.wait_for_verification_code (38-second wait), one-shot fill of #security-input-0..7, clickCoords on Submit → /confirmation.
- Resume upload: Filestack committed cleanly on first Attach click (filename visible in body, #resume input swapped out).
- Cost: 1 LLM resume tailoring pass + 1 cover-answers pass + 1 email-verification IMAP fetch. ~10 min end-to-end (incl. dryrun rebuild after 2 LABEL_RULES added).
