# Netflix 2853 — Product Manager, Ads Platform - Ads Reporting

- **Status:** SUBMITTED ✅
- **Submitted:** 2026-06-20
- **By:** auto (_eightfold_runner.py)
- **ATS:** Eightfold (explore.jobs.netflix.net)
- **enc_id:** 9L5PoEOBZ
- **Confirmation:** Submit API HTTP 201, {"status":201, "data":{"success":true, "profile":{"encId":"9L5PoEOBZ","fullname":"Cyrus Shekari"}}}
- **Resume attached:** Cyrus_Shekari_Resume.pdf (base resume, 122687 bytes; upload via in-browser fetch -> encId)
- **Unblock:** Prior "eightfold-RESUMEWALL / needs residential IP" was WRONG. Resume upload works via in-browser FormData fetch. Real blocker was the self-ID checkbox-group React commit (genderIdentity/raceEthnicity/sexualOrientation). FIX: Playwright .check() on the 'I choose not to disclose' checkbox INPUT by id (label.click() left React uncommitted -> SPA silently blocked submit POST). After fix: submit POST fires, 201 success.
