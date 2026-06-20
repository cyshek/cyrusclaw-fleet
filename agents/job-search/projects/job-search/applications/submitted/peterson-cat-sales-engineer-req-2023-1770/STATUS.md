STATUS: SUBMITTED
Submitted: 2026-05-26T17:41:29+00:00 (auto)
Driver: workday_playwright.py (chain_006)

role_id: 1269
ats: workday (tenant: petersonholding)
company: Peterson Cat
role: Sales Engineer (REQ-2023-1770)

Confirmation URL:
  https://petersonholding.wd1.myworkdayjobs.com/en-US/PetersonJobs/jobTasks/completed/application

Confirmation text excerpt:
  "Thank you for completing this task.
   Sales Engineer | REQ-2023-1770 | Being Reviewed | May 26, 2026"

Submitted by: cyshekari+petersonholding@gmail.com
Resume: Cyrus_Shekari_Resume_workday-petersonholding_Sales-Engineer-REQ-2023-1770_v2.pdf
Salary stated: 150000

Steps completed:
  applyManually → account-signed_in → iter1:info → iter2:exp → iter3:questions
  → iter4:voluntary → iter5:selfid → iter6:selfid → iter7:review → SUBMIT

Source-code changes shipped to land this (committed in chain_006):
  1. workday_playwright.fill_text — added JS native-setter fallback when click is intercepted
     (Peterson sticky footer was intercepting phone country code field clicks).
  2. workday_playwright.click_radio — label-click strategy (Workday reactive Yes/No widgets
     bind handler to <label> not <input>).
  3. workday_playwright.open_button_dropdown_by_aria — generic aria-label fallback for
     buttons with no stable id (Peterson State, Phone Device Type).
  4. fill_my_information source-fallback — opens "How Did You Hear About Us?" by aria-label
     when #source--source doesn't exist; picks LinkedIn-ish or first non-empty option.
  5. fill_application_questions — generic essay handlers (N/A for marked-yes follow-ups,
     reason-for-leaving, what-interests-you, qualifications, additional-info, cover-letter).
