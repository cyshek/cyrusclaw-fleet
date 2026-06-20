SUBMITTED — 2026-05-25T03:53:00+00:00

role_id: 671
company: Harvey
role: Innovation Product Manager
ats: ashby
apply_url: https://jobs.ashbyhq.com/harvey/e5272fbe-4431-4841-bf00-b9f59812b82a/application
job_url:   https://jobs.ashbyhq.com/harvey/e5272fbe-4431-4841-bf00-b9f59812b82a
est_tc: 360000 (posted band $178.5K-$241.5K + equity + bonus)

confirmation: "Your application was successfully submitted. We'll contact you if there are next steps."
confirmation_url: https://jobs.ashbyhq.com/harvey/e5272fbe-4431-4841-bf00-b9f59812b82a/application (in-place success panel; URL unchanged)

resume: Cyrus_Shekari_Resume_ashby-harvey_e5272fbe_v2.pdf (1 page)
location: New York City, New York, United States
phone: 346-804-0227
email: cyshekari@gmail.com
linkedin: https://linkedin.com/in/cyshekari

Quality gate audit:
- US-auth (Yes/No button widget): Yes — clickCoords on visible button (Snowflake 870 rule)
- Sponsorship (radio): No, I do not require sponsorship
- Hybrid office 3d/wk (radio): Yes, based in this location
- Current employer: Microsoft
- School: University of Houston
- Pronouns: Decline to answer
- AI-disclosure asked? No
- Resume 1 page: yes
- Demographics: only Pronouns field present (declined)

Tenant captcha config: PERMISSIVE (invisible reCAPTCHA v3, site key 6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y).
No visible challenge. Same family as Snowflake 870 — Harvey is now a known-good Ashby tenant.

Pipeline notes (for future Ashby runs):
1. **React-state desync on text fields** — Ashby validates against React internal state, not DOM .value. First submit failed with "Missing entry for required field: Legal First and Last Name" etc despite all DOM values being populated via JS native value setter. Fix: clear via JS, then re-type via CDP `act:type` (real keystrokes). After that, validation passed.
   - Same pattern as Stripe Formik issue (MEMORY 2026-05-24).
   - Ashby's Location combobox (role=combobox with autocomplete dropdown) DID accept native value setter + option mousedown/mouseup/click — state-aware on the option click. So combobox path is fine; only plain text inputs need CDP keystrokes.
2. **Yes/No button widget for US-auth** — confirmed Snowflake 870 rule: clickCoords on the visible button (after scrollIntoView), not evaluate-click. JS click() on the underlying checkbox left React state unset and yielded "_active_" CSS but no form-state update.
3. **Radio groups (sponsorship + hybrid)** — `input.click()` via JS evaluate ALSO failed to update React state (checked the DOM, but Ashby validator reported "Missing entry"). Fix: clickCoords on the `<label>` element (scrollIntoView+coords). Same lesson as Yes/No buttons — Ashby React form is hostile to synthetic events; needs real Playwright/CDP clicks.
4. **Resume upload** — `browser.upload selector="#_systemfield_resume"` returned ok:true but did NOT actually set files (page has 2 file inputs; selector match was ambiguous or hit the wrong one). Fix: snapshot the resume container with selector `[class*=_container_1fd3o]:first-of-type` to get the button ref (e2 = "Upload File"), then `browser.upload ref=e2 paths=[...]`. That set files=1 on `#_systemfield_resume`. Visible filename appeared in body.

Action items for inline_submit / ashby_filler:
- Plan should emit CDP `act:type` clear+type for text fields (not just JS native value setter).
- Plan should emit clickCoords on radio LABEL elements (with scrollIntoView before measuring), not `input.click()`.
- Plan should emit ref-based upload via the visible "Upload File" button, not selector against the hidden input.
- These 3 changes would have made Harvey a one-shot submit.

submitted_by: auto (job-search subagent, role 671)
