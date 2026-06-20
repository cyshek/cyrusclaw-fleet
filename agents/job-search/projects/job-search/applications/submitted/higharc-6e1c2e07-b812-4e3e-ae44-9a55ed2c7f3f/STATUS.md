# 1112 Higharc — Solutions Engineer

OUTCOME: SUBMITTED ✅ (real server FormSubmitSuccess)
Date: 2026-06-11
submitted_by: auto-residential
resume_attached: yes (Cyrus_Shekari_Resume_ashby-higharc_6e1c2e07_v2.pdf)

## Evidence (FormSubmitSuccess POST + confirmation route)
Residential egress: Webshare 82.23.97.223 (verified NOT Azure).
Submit POST captured:
  SUBMIT-RESP status=200 body={"data":{"submitApplicationFormAction":
  {"__typename":"SingleFormSubmitResult","messages":null,
  "applicationFormResult":{"__typename":"FormSubmitSuccess","_":null}}}}
Confirmation page text:
  "Application Success — Thank you for applying to Higharc! We've received your
   application ... we'll be reviewing it carefully ..."

This is a genuine server FormSubmitSuccess, NOT a text-match. classify:"submitted".

## chain_p14 location fix — VALIDATED LIVE
There was an EARLY FormRender error "Missing entry for required field: Where are
you currently located" (the known chain_p11/p14 autofill-clobber double-POST
pattern), but the clobber-guard + last-ms trusted-keystroke Location commit won:
the FOLLOWING submit POST returned a clean FormSubmitSuccess. So the broadened
geo-combobox locator + region ladder shipped in chain_p14 (commit 7d84e9f) WORKS
on this multi-value-single-select Location tenant. (final-clobber-guard logged
location_ok=False as a warning, but the trusted-keystroke + server FormSubmitSuccess
prove Location was accepted.)

Log: /tmp/ashby-1112.log
