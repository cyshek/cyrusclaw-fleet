# Uber 158015 — Program Manager, AV Operational Safety (row 1883)

**STATUS: SUBMITTED** ✅
**Submitted:** 2026-06-08 (America/Los_Angeles) by job-search agent (subagent last-mile finisher)
**Apply URL:** https://www.uber.com/careers/apply/form/158015
**Account:** cyshekari+wd-uber-202606081753@gmail.com (role-discovery/.uber-creds.json)

## Confirmation evidence (DEFINITIVE — server-side success token)
- **GraphQL POST `https://www.uber.com/careers/apply/graphql` returned 200 with:**
  `{"data":{"submitApplication":"NysPhHBXE83Up4i9JpP3saDtS3EiOhokLSxHbUWb8A8="}}`
  (a real submitApplication token — the authoritative backend success signal)
- URL changed to `https://www.uber.com/careers/apply/success`
- Success-page DOM (form GONE):
  > Program Manager, AV Operational Safety
  > Chicago, USA
  > **Application submitted**
  > Thanks for your application! We will reach out if you're a fit for our needs.

## Form contents submitted
- Basic: Cyrus Shekari, mobile 346-804-0227, US
- Resume: Cyrus_Shekari_Resume_uber_158015_v2.pdf ("File successfully uploaded")
- Experience: Microsoft — Technical Program Manager (current, from 03/2024)
- Education: University of Houston, BS Computer Science, 08/2021–12/2024
- Screening (truthful): driver/partner=No, open-to-other-roles=Yes, reside-in-US=Yes,
  Uber subsidiary employee=No, legal right to work=Yes, require sponsorship=No
- Demographics (voluntary): Prefer not to say; veteran=I prefer not to say
- Arbitration: Yes, I agree
- zipCode 98033, disabilityAccomodation=No

## ROOT-CAUSE LESSON (critical for future Uber applies)
Submit kept failing with graphql `SessionTokenInvalid{"session token provided does not
match with database"}` — which the React UI mistranslated as generic "Oops! Something
went wrong" and "Missing required fields". The form's session token is bound to a FRESH
page load + sign-in; a tab that has been heavily manipulated / re-navigated across many
scripts carries a STALE token the backend rejects. FIX that worked: close the stale form
tab, open a NEW tab, sign in fresh, fill the ENTIRE form, and submit in ONE continuous
flow (minimal round-trips). Also note: re-uploading the resume WIPES the education section
and regenerates 4 junk parser experience blocks (empty required dates) — must remove junk
blocks down to 1 and re-fill education AFTER every upload.
