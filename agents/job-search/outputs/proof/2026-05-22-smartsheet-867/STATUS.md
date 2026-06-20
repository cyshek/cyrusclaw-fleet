# STATUS: SUBMITTED

- Role ID: 1368
- Company: Smartsheet
- Title: Product Manager II - Growth (Remote Eligible)
- ATS: greenhouse (new job-boards form)
- Submitted: 2026-05-25T16:08 UTC
- Confirmation URL: https://job-boards.greenhouse.io/smartsheet/jobs/7951915/confirmation
- Confirmation text: "Thank you for your interest in Smartsheet! Your application has been received."

## Notes for next time (job-boards.greenhouse.io)

This is the NEW Greenhouse form variant (job-boards.greenhouse.io), not the legacy boards.greenhouse.io. Key differences from the existing inline_submit plan template:

1. **No "Apply" button click needed** — form is rendered immediately on page load.
2. **Comboboxes are downshift-style `<input role="combobox">`** (not the legacy react-select with `.select__control`). Opening the listbox requires a *real* `browser.act:click` via ref (synthetic mousedown/mouseup/click events do NOT open it). After the listbox is open, options appear at `[id^="react-select-<id>-option"]` and synthetic clicks work fine on them.
3. **File upload requires `browser:upload` with `ref` of the visible Attach button** (e.g. `ref=e15`), NOT the hidden `input#resume` selector. Uploading by selector returns `ok:true` but `files.length` stays 0. After successful upload, the file input is removed from the DOM and a `.file-upload__filename` div shows the attached file name.
4. **Phone (intl-tel-input v18)**: flag selector is now `.iti__selected-country` (button), opens a dialog (not popover), country items have `role=option` and ids like `iti-0__item-us`. Click pattern still works.
5. **Country combobox**: same downshift behavior — real click opens listbox, then synthetic click on `react-select-country-option-0` selects.
6. **Demographic decline label**: Smartsheet uses plain apostrophe `"I don't wish to answer"` (not curly `'`). Need to include both variants in the decline-labels list.
7. **Privacy notice option**: "Yes" doesn't exist; option text is "I acknowledge receipt of the Applicant Privacy Notice." — needs_review_dropdowns label mismatch.
8. **Email verification (8-char code)**: After clicking Submit, an inline 8-char code prompt appears (8 separate `<input id="security-input-{0..7}">` fields). Fetched via `fetch_company_code.py smartsheet`. Re-submit succeeds → `/confirmation` URL.
9. **reCAPTCHA Enterprise v3 (invisible, badge-only)** — passed without intervention. Site key: `6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0`.
10. **Location field**: Google Places–style remote search via react-select. Needs *real* typing (`browser.act:type` with `slowly:true`) — synthetic value-set returns "0 results available".
