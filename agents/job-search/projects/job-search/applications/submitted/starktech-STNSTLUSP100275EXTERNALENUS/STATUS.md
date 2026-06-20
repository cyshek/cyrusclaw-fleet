SUBMITTED — 2026-06-10 (hourly grind)

Company: Stark Tech
Role: Sales Engineer - HVAC (P-100275)
ATS: Phenom (careers.starktech.com)
apply_url: https://careers.starktech.com/us/en/apply?jobSeqNo=STNSTLUSP100275EXTERNALENUS
confirmation_url: https://careers.starktech.com/us/en/applythankyou?status=success&jobSeqNo=STNSTLUSP100275EXTERNALENUS&jobApplicationId=6a29e96f27fa0fcbb58ff435
confirmation_text: "Cyrus, you have successfully applied for: Sales Engineer - HVAC"
jobApplicationId: 6a29e96f27fa0fcbb58ff435
submitted_by: _phenom_runner.py (manual completion via browser tool after root-cause diagnosis)
resume_attached: Cyrus_Shekari_Resume.pdf

Answers to custom questions:
- Highest education: Bachelor of Science
- Currently working at most recent job: Yes
- Compensation expectations: $130,000 - $160,000
- Authorized to work in US: Yes
- Require sponsorship: No
- Background check: Yes
- Know Stark Tech employees: No
- Disability status: I do not want to answer

RUNNER BUG DIAGNOSED AND FIXED (2026-06-10):
1. alert("resume uploaded successfully") fires during upload; Playwright page.on("dialog") accepts it but the browser CDP session exit leaves an unaccepted dialog that blocks all subsequent clicks on the tab.
2. _phenom_runner.py click_next() was clicking a "Review" nav breadcrumb button instead of the "Next" submission button (same text match, wrong button).
3. Country/State comboboxes were not committing to React state via JS native-value-setter (need Playwright select_option or browser tool select instead).
FIX: alerts.clear() + window.alert=()=>{} suppression added. click_next should use EXACT text "Next" not /review/i. select_option via Playwright needed for country/state.
