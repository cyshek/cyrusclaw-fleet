# STATUS — adp-wfn Sager 2539 RE-SUBMIT — ✅ SUBMITTED (2026-06-10, subagent adp-sager-2539-submit)

## OUTCOME: SUBMITTED ✅
- Confirmation: "Application Submitted!" green banner + "Thank You! We have received your application." Form GONE. ADP BrightJump talent-pool page.
- URL: https://workforcenow.adp.com/mascsr/applicant/mdf/recruitment/postLogin.html?...&jobId=543016&requisitionId=9201264783565_1&OTP_login=true
- Evidence saved: applications/submitted/sager-electronics-2539/STATUS.md (+ screenshot captured).
- OTP defeated (code 914498) via _adp_wfn_runner.py phase otp.

## THE KEY UNLOCK (was the whole blocker): SELF-ATTEST needs a TYPED SIGNATURE, not just the checkbox.
The Self-Attest step has TWO required parts, and the signature field is HIDDEN until the checkbox is checked:
1. Checkbox "Yes, I agree to sign electronically." — visually-hidden input (x:-9999); but checking it REVEALS:
2. A required textbox "Please type your full name.*" — this is the e-signature. MUST contain "Cyrus Shekari".
Wizard stays invalid ("Self Attestation is required to proceed") until BOTH the checkbox is checked AND the signature text is set in REACT state. Setting DOM .value alone does NOT update React (input value-tracker mismatch); coordinate clicks on the hidden checkbox flip DOM .checked but React controlled state lags.

## RELIABLE METHOD (use this for phase_wizard self-attest):
Walk React fiber from the signature textbox / checkbox up to the `self-attestation-view` component (className 'self-attestation-view', ~depth 10-14). Its memoizedProps expose:
- checkBoxStatus = a=>{t({type:CHECK_BOX,param:a})}  -> call checkBoxStatus(true)
- onSignatureInput = a=>{t({type:SIGNATURE_VALUE,value:a})}  -> call onSignatureInput('Cyrus Shekari')
After both dispatches + ~700ms, verify on the wizard container (className 'c' near Submit btn, has submitApplication + isWizardValid): isWizardValid===true and the self-attestation-view 'signature' prop === 'Cyrus Shekari', reqAlert gone. THEN click the real Submit button (button:has-text('Submit')).
- The wizard container also exposes submitApplication=()=>{t(submitApplication)} but calling it directly BEFORE the signature was set did NOT submit (it re-validates). With signature set + isWizardValid true, the normal Submit-button click works.
- GOTCHA: checkbox element ids REGENERATE on every React re-render — never cache; re-query each time.
- GOTCHA: Submit-button click re-renders; before the signature was set, that re-render reset the checkbox to unchecked. Once signature text is in React state, attestation is stable.

## Earlier proven recipes (Personal Info / Resume / Questions / Self-ID) — see STATUS-adp-otp.md, all held.
- Self-ID also requires a separate "I have read the Voluntary Self-Identification of Disability Form" ack checkbox (visually-hidden; click label coords). Race/ethnicity decline checkbox is separate. Gender/Veteran/Disability "--Select One--" are NOT required.

## RECOMMENDATION: YES, land phase_wizard into _adp_wfn_runner.py — the full recipe is now reproducible end-to-end (Personal Info -> Resume -> Questions -> Self-ID -> Review -> Self-Attest w/ signature -> Submit). Parent to decide priority.
