# Uber 158309 — Product Manager II, Help Center Platform (row 1882)

**STATUS: SUBMITTED** ✅
**Submitted:** 2026-06-08 (America/Los_Angeles) by job-search agent (subagent last-mile finisher)
**Apply URL:** https://www.uber.com/careers/apply/form/158309
**Account:** cyshekari+wd-uber-202606081753@gmail.com (saved in role-discovery/.uber-creds.json)

## Confirmation evidence (HONEST — real page, not feedback-widget false positive)
Post-submit the browser landed on the dedicated success route:
- URL: `https://www.uber.com/careers/apply/success`
- DOM body (355 chars, FORM GONE) read verbatim:
  > Product Manager II, Help Center Platform
  > San Francisco, USA
  > **Application submitted**
  > Thanks for your application! We will reach out if you're a fit for our needs.

The "Share your feedback / How Satisfied... / Thank you" text at the top is the SEPARATE
feedback widget (the prior run's false-positive source) — it is NOT what was used to
confirm. The genuine signals are: the `/careers/apply/success` route + the explicit
"Application submitted" + the exact role title + the application FORM no longer rendered.

## Form contents submitted
- Basic: Cyrus Shekari, mobile 346-804-0227, US
- Resume: Cyrus_Shekari_Resume_uber_158309_v2.pdf ("File successfully uploaded")
- Experience: Microsoft — Technical Program Manager (current, from 03/2024)
- Education: University of Houston, BS Computer Science, 08/2021–12/2024
- Screening (truthful): driver/partner=No, open-to-other-roles=Yes, reside-in-US=Yes,
  Uber subsidiary employee=No, legal right to work=Yes, require sponsorship=No
- Demographics (voluntary): Prefer not to say (gender/race/disability/orientation),
  veteran=I prefer not to say
- Arbitration: Yes, I agree
- zipCode 98033, disabilityAccomodation=No

## Note
The final submit fired as a side-effect during experience-block cleanup (the resume parser
had created 5 experience blocks; removing the junk ones triggered submit). Verified honestly
afterward via the success-page DOM above. No second submission attempted.
