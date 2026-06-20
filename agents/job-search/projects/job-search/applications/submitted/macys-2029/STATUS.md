SUBMITTED — 2026-06-10 (Oracle Cloud HCM / CX guest apply, hourly-grind worker)

role_id: 2029
company: Macy's
role: Product Manager (New York, NY) — $121,440–$202,320
app_url: https://ebwh.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/86418
ats: oracle-cloud-hcm-cx (CX_1001)

CONFIRMATION:
- After Submit, redirected to /my-profile showing:
  "Thank you for submitting your job application."
  ACTIVE JOB APPLICATIONS → "Product Manager, New York, NY"
  Status: "Under Consideration" · "Macy's 86418 Applied on 06/10/2026"
- Only outstanding item is an OPTIONAL WOTC tax-credit form (not required for consideration).

resume_attached: yes — Cyrus_Shekari_Resume_Macys_2029macys_pm.pdf (family=pm, tailored)
cover_letter: not required (optional input, skipped)

WHAT I ANSWERED (best-judgment + factual):
- Age: "I am at least 18 years of age"
- Legally authorized to work in US: YES (factual)
- Require sponsorship now/future: NO (factual)
- Gender (EEO, required LOV): "Not Specified" (decline-to-self-identify per personal-info default)
- Ethnicity/race: left blank (voluntary)
- SSN (optional): skipped
- Address: 12420 NE 120th St #1437, Kirkland WA 98034 → ZIP LOV resolved "98034, Juanita, King, WA" (Oracle dependent dropdown auto-filled city/county/state)
- E-Signature Full Name: Cyrus Shekari
- Communication opt-ins: left at defaults

KEY LEARNING (DEBUNKED): The old block_reason "need-runner-oracle-emailOTP" was WRONG for this
tenant. Macy's CX_1001 guest apply does NOT require email-OTP verification and does NOT require an
account — entering the email + clicking Next goes STRAIGHT to the full single-page application form.
No _oracle_runner.py needed for this tenant class.

ORACLE CX RUNNER RECIPE (proven here, for future Oracle CX rows):
1. Click "Apply Now" → email auth screen → type email, privacy checkbox pre-checked → click "Next".
2. Lands on full single-page form (step 1 of 4, but step 1 IS the whole core form).
3. Plain text inputs (firstName/lastName/phone/fullName) commit fine via native value-setter + input/change.
4. Address + Gender are Oracle LOV comboboxes that IGNORE native value-setter (show value but aria-invalid stays true).
   MUST: real-type (Playwright type slowly) into the combobox → it exposes a listbox item with id
   "<fieldId>-listitem-0" (aria-activedescendant confirms) → click that listitem via mousedown+mouseup+click.
   ZIP LOV is the driver: selecting the ZIP listitem auto-populates city/county/state (all become aria-invalid=false).
5. Yes/No/age "questions" are <button>s (not radios) — click the right one scoped to its question container.
6. Resume: standard <input type=file id="attachment-upload-2">; browser.upload element="input#attachment-upload-2"
   (file must live under /home/azureuser/.openclaw/media/inbound/).
7. Hidden "oda-work-summary-text-area" reports aria-required but is invisible (Oracle Digital Assistant) — NOT a real blocker.
8. Two Submit buttons: click button.apply-flow-pagination__submit-button (the real one); fixer button flips to
   submit-mode (errorCount===0) once all LOVs validate.
9. Confirm ONLY on redirect to /my-profile + "Thank you for submitting" + role under ACTIVE JOB APPLICATIONS + "Applied on <date>".
