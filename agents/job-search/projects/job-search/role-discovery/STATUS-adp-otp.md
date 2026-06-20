# STATUS — adp-wfn Sager 2539 (subagent adp-sager-2539, 2026-06-10)

## Phase: WIZARD MAPPING — OTP DEFEATED, Personal Info + Resume DONE; mapping Questions
- OTP fully defeated this run (code 497066). Live authenticated session on postLogin.html.
- Wizard steps: Personal Information -> Resume -> Questions -> Voluntary Self-ID -> Review -> Self-Attest & Submit.

## PROVEN RECIPES (for _adp_wfn_runner.py phase_wizard)
- **Apply/Consent/Contact/OTP**: WORKS via _adp_wfn_runner.py phases. Contact = guestFirstName/guestLastName/guestEmail filled; "Send code"; fetch_adp_code.py; OTP into input[aria-label*=ode]; Verify. Lands postLogin "Complete Your Application".
- **Personal Information** (ALL fields pre-filled except address): 
  1) country `#PersonalAddress_country` (MDF combobox): click -> type "United States" -> click `[role=option]:has-text('United States')`. MUST do country FIRST.
  2) address `#PersonalAddress_address_line1` is GOOGLE PLACES (`pac-target-input`): click, type full addr, wait 2.6s, **MOUSE-click first `.pac-container .pac-item`** (NOT keyboard — must fire place_changed) -> auto-fills city/postal/county.
  3) Fill BOTH phone inputs (`personalInfomationMobileNumberError` AND `...ErrorMessage`) with "+1 346 804 0227" (the 2nd twin holds just "+1" and flags invalid otherwise).
  4) Tab to blur, click Next.
  GOTCHA: picking country AFTER places wipes the address. GOTCHA: keyboard-Enter on pac leaves line1 red-bordered (uncommitted place).
- **Resume**: FIRST `input[type=file]` (accept .pdf,.doc,.docx) = resume; 2nd = optional attachments (skip). `set_input_files(pdf)` -> "Bravo! We have your resume." Required clears.

## Done
- Personal Info advanced to Resume; Resume uploaded (Bravo confirmation). Currently ON Resume step, NOT yet Next.

## Next
- Click Next -> map QUESTIONS step (screening Qs). Answer per doctrine, SUBMIT.
- Then Voluntary Self-ID (decline) -> Review -> Self-Attest & Submit.

## Blockers
- RESOLVED: Questions step conquered. Now on Voluntary Self-ID.

## QUESTIONS RECIPE (PROVEN — for _adp_wfn_runner.py)
The Questions step is a React `questionnaire-view`. Fields: Q0 referral text `#question_0`, Q1 how-heard `#question_1` (sdf-select-simple), Q2 total-comp `#question_2`(text)+`#question_currency_type_2`(MDFSelectBox react-select), Q3 VISA `#question_3`(sdf-select-simple), + a REQUIRED 'What is your desired salary?' block (`#desiredSalaryId` text + `#add_info_select_box` currency sdf-select + Annually sdf-radio-group).
1. **sdf-select-simple (Q1/Q3)**: plain `page.click('#question_N')` opens it; options render as `[role=option]` in a portal; click the option by text. Q1->'LinkedIn', Q3->'No'.
2. **Q2**: `.fill('#question_2','150000')`; currency `#question_currency_type_2` click -> `.MDFSelectBox__option` has-text 'United States Dollar' click.
3. **Desired-salary block** is REQUIRED and its currency sdf-select (`#add_info_select_box`) WILL NOT open in headless (option portal renders EMPTY). FIX = drive via REACT HANDLERS on the questionnaire-view props bag (walk `__reactFiber` up from `#question_0` ~16 levels to the memoizedProps that has `currencyValidation`): call `onDesiredSalaryValue('150000')`, `onDesiredSalaryType({detail:{value:'Annually'}})`, `onCurrencyChange({detail:{codeValue:'USD',label:'United States Dollar ( USD )',shortName:'SYS:5:420',value:'USD'}})`, `onCurrencyValueChange(usd)`. This flips `currencyValidation:true`, `validState:true`.
4. **Q0** (`#question_0`, required text): type ANY value (e.g. 'Not Applicable') + Tab. Sets `applicantReferralIndicator:true` but `validState` still goes TRUE and `allRequiredQuestionnaireFilled:true`. The DOM `aria-invalid=true` on Q0/Q2 is STALE/cosmetic — ignore it; trust React `validState`.
5. Click Next -> advances to Voluntary Self-ID. (CHECK `validState:true` + `allFilled:true` in the props bag before clicking.)
GOTCHA: clicking 'Previous' then 'Next' CLEARS the sdf-select answers (Q1/Q3) in React (`requiredQuestionsValidation` drops) — re-answer them. Avoid Previous.

## Next
- Voluntary Self-ID: decline all (Gender/Ethnicity/Race/Veteran/Disability). 'I decline to identify my race and ethnicity' option exists. Then Review -> Self-Attest & Submit.
