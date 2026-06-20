# Rogo — Product Manager | Enterprise (role 1393)

**Status:** SUBMITTED ✅ 2026-05-26 (chain_003)
**Confirmation:** "Success" heading + "Your application was successfully submitted. We'll contact you if there are next steps."

## Notes
- Ashby tenant, same strict-cluster reCAPTCHA sitekey (`6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`) as Blaxel/Mercor/OpenAI/Cursor.
- HOWEVER: submit was NOT blocked. Spam-flag is per-context, not strict per-sitekey.
- Filled 12/12 plan + 2 comboboxes manually:
  - "How did you hear about this role?" combobox → Job Board (was in plan but as text field, not combobox)
  - "Location" typeahead → Kirkland, Washington, United States (skipped by plan as unknown _ashby_type=Location)
- 2 Y/N radio groups (Yes for legally authorized, No for require sponsorship) — clicked via label scrollIntoView + clickCoords (matches chain_002 pattern).
- Essay (Why Rogo) used plan-generated text verbatim.

## Open Ashby driver gap (TODO chain_004 or later)
- **Ashby `_ashby_type=Location` typeahead** missing from plan emitter. Pattern: needs to emit a combobox-typeahead action that types city, waits for `[role=option]` to populate, picks the matching US option.
- **Ashby `MultiValueSelect` rendered as combobox-typeahead** (how-did-you-hear) — plan emits as text field but page is combobox.
