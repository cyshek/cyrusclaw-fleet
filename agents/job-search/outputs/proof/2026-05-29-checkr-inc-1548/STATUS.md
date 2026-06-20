# Checkr Solutions Engineer — SUBMITTED chain_015 2026-05-29

- Role id: 1548
- ATS: greenhouse (job-boards.greenhouse.io/checkr/jobs/7848516)
- Confirmation URL: https://job-boards.greenhouse.io/checkr/jobs/7848516/confirmation
- Confirmation page title: "Thank you for applying"
- Body excerpt: "Thank you for applying to Checkr! We make it a point to review every candidate in the process. Should your background and experience meet the requirements of one of our job openings, we will contact you to request additional information within 5 calendar days. Best, Checkr Team"
- Security code email subject: "Security code for your application to Checkr" from Greenhouse <no-reply@us.greenhouse-mail.io>
- Code used: umbqcOBB
- Resume PDF: Cyrus_Shekari_Resume_checkr_7848516_v2.pdf (uploaded via CDP DOM.setFileInputFiles into #resume)

## Inline patches required (NOT in inline-plan)
1. `#candidate-location` react-select typeahead — required, missing from `text_fields` (was emitted as `location` but selector is `candidate-location`).
2. `#country` react-select typeahead — required, missing from `country_dropdowns` (empty).

Both filled inline by the worker. Now ported into `greenhouse_filler.py` (chain_015 post-port).
