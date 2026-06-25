# Application Status: Blaxel (YC X25) — Forward Deployed Engineer (FDE)

## SUBMITTED

- **role_id:** 1325
- **slug:** blaxel-yc-x25-4acea42a-589d-42b1-949e-d4ec4b8907a2
- **url:** https://jobs.ashbyhq.com/blaxel/4acea42a-589d-42b1-949e-d4ec4b8907a2
- **submitted_by:** auto (_ashby_runner.py)
- **submitted_on:** 2026-06-24
- **ats:** ashby
- **confirmation:** "Your application was successfully submitted. We'll contact you if there are next steps."
- **classify:** submitted
- **exit_code:** 0
- **resume:** Cyrus_Shekari_Resume_ashby-blaxel_4acea42a_v2.pdf

## Notes
- Form had 3 radio fields (work-auth Yes, visa No, SF office Yes) using yesno_button widget
- Required fix: added `chain_last_ms_yesno_fallback` to `_ashby_runner.py` — after
  `_pw_click_radio_option` fails for yesno_button fields (no labeled-radio structure),
  fallback uses real Playwright `.click()` on the matching `<button>` inside `div[class*=_yesno_]`
  as the absolute last operation before submit
