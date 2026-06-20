# WWT — Consulting Systems Engineer (Seattle/Bellevue, WA) #26-0938 — SUBMITTED

- role_id: 2538
- company: World Wide Technology
- title: Consulting Systems Engineer (Seattle/Bellevue, WA), req #26-0938
- ats: ADP recruiting.adp.com SRCCAR (myjobs.adp.com CX front-end)
- submitted_on: 2026-06-10
- submitted_by: auto-subagent (adp-otp)
- confirmation_url: https://myjobs.adp.com/wwtexternalcareersite/cx/job-details?reqId=5001188060000
- confirmation_signal: job-details primary action button = "Applied" (SDF-BUTTON, non-actionable badge; no "Continue Application" affordance present). Persisted across navigation (job-details -> my-applications -> back). Pre-apply this button read "Apply".
- resume_attached: tailored SE resume prepared at applications/queued/World Wide Technology-2538/Cyrus_Shekari_Resume_World Wide Technology_2538_v2.pdf. NOTE: this was a `cx=continue_application` resume of a prior near-complete application record on this ADP candidate account; the Documents step was satisfied by the existing application record (no resume-required gate surfaced before ADP finalized to "Applied").

## OTP defeat (the headline)
- ADP email-OTP wall DEFEATED via Gmail IMAP on cyshekari@gmail.com.
- Tool: role-discovery/fetch_adp_code.py <since_epoch> --timeout 150 --poll 6  -> returned 6-digit code 932070, exit 0.
- Flow: Apply -> ADP auth ("Welcome! Let's find your dream job") -> entered cyshekari@gmail.com -> Continue triggered OTP send -> fetched code from inbox -> typed into Passcode -> ADP showed "Employer Privacy Policy" consent (Disagree/Agree) = OTP accepted -> Agree -> signed in as "Cyrus Shekari" -> continue_application.
- => the `adp-email-otp-required` block is DEBUNKED. Promote to MEMORY.md.

## Form steps completed
1. Contact Information: prefilled first=Cyrus / last=Shekari / email / phone +13468040227; filled address1=12420 NE 120th St #1437, city=Kirkland, state=WA (dijit value "WA" set via Dojo registry), zip=98034 (ZIP was the only required field). -> Next.
2. Data Protection Statement: ticked "Reviewed" / "accept" checkbox. -> Next.
3. Equal Employment Opportunity Information (voluntary, no required fields): was selecting decline-to-identify across eeoEthnicity/eeoGender/eeoVeteran(13=choose not to self-identify)/eeoDisability/_latino when the SRCCAR tab redirected/closed. On re-navigating to job-details the role already showed "Applied".
   - NOTE: EEO is voluntary; whether ADP recorded blanks or my decline picks, the application finalized to Applied.

## Answers given (factual + doctrine)
- Work auth: US citizen, authorized, no sponsorship needed. No security clearance. (Not re-prompted in this resumed flow.)
- Demographics: decline to self-identify (per personal-info.json default).
- Location/relocation: Kirkland WA (local to Seattle/Bellevue) -> no relocation knockout.

## ADP account
- Account ALREADY EXISTED for cyshekari@gmail.com (OTP-login only; no password-creation prompt). No .adp-creds.json needed/created for WWT.
