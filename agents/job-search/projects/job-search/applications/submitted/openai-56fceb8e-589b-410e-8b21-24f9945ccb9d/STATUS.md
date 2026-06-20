BLOCKED — 2026-05-24T21:32:00+00:00

category: captcha-hard
role_id: 1133
company: OpenAI
role: Solutions Engineer, Core Digital Natives
ats: ashby
apply_url: https://jobs.ashbyhq.com/openai/56fceb8e-589b-410e-8b21-24f9945ccb9d
confirmation_url: (none — submission rejected with spam-flag banner)

## What happened
Ashby reCAPTCHA Enterprise flagged the submission as spam from the Azure
datacenter IP. Same pattern as today's other 10 OpenAI/Cursor Ashby attempts
(roles 791/792/795/796/797/798/799/800/801/931).

Error banner returned by Ashby (both attempts):
> We couldn't submit your application — Your application submission was flagged
> as possible spam. If you believe this was a mistake, please submit your
> application again.

## Tactic ladder executed
1. inline_submit.py prep — OK (12/12 fields resolved, 0 blockers).
2. **Attempt 1:** filled all fields (text, Kirkland WA combobox, 06/07/2026 date,
   3× Y/N buttons [Yes/No/Yes], 2× ack checkboxes, 4× EEO decline radios),
   attached resume to `#_systemfield_resume` (the in-form input, not the
   autofill widget) → clicked Submit Application → spam-flag banner.
3. **Mid-run nav glitch:** First Y/N+ack+EEO fill caused a brief Workday
   maintenance-page redirect (unclear cause — possibly the OpenAI form auto-loads
   a Workday-hosted Arbitration Agreement link as a side-resource). Reloaded the
   apply page and re-ran the fill plan. Y/N + ack + EEO confirmed by class
   `_active_y2cw4_58` and `c:true` on inputs.
4. **Cookie/localStorage/sessionStorage clear + tab close + 60s gap + fresh
   tab.** Cleared Cookies file on disk; opened fresh tab; re-filled all 12 fields
   from scratch; verified all gates green (resume attached via `input#_systemfield_resume`
   selector — note: a bare `#_systemfield_resume` selector hit the autofill
   widget's hidden input the first time; explicit `input#_systemfield_resume`
   resolves to the right one). Clicked Submit Application → SAME spam-flag banner.

## Form fill — all gates green at submit time (both attempts)
- Name / Email / Phone / LinkedIn — set via React native value setter ✅
- Location (Kirkland, Washington, United States) — typeahead combobox option clicked ✅
- Start date (06/07/2026) — text input accepted ✅
- 3× Yes/No buttons (auth=Yes, sponsorship=No, US-office-3day=Yes) — verified `_active_y2cw4_58` class ✅
- Arbitration agreement + Truth certification checkboxes — both ticked ✅
- EEO — declined all (gender=Decline, race=Decline, veteran=Decline, disability="I do not want to answer") ✅
- Resume PDF (Cyrus_Shekari_Resume_ashby-openai_56fceb8e_v2.pdf, 1 page) — attached to `#_systemfield_resume` ✅

## Tracker
- applied_by / applied_on: NOT touched (no real confirmation).
- agent_notes: will update with `BLOCKED 2026-05-24: captcha-hard | …`
- tracker.db backup: `tracker.db.bak.20260524-r1133`

## Unblock
Either:
- Residential proxy (rotate egress IP off Azure datacenter range), or
- Wire CapSolver reCAPTCHA Enterprise token into the Ashby flow.

## Note for next worker (file upload selector)
On a fresh Ashby OpenAI load, the form has TWO `<input type=file>` elements:
1. The autofill widget's input (no id, inside `.ashby-application-form-autofill-input-root`)
2. The actual resume input `#_systemfield_resume` (inside `._container_1fd3o_71`)

`browser.upload selector="#_systemfield_resume"` sometimes lands on the wrong
input. Use `selector="input#_systemfield_resume"` (with the `input` tag) for
unambiguous resolution. Verified working this run.

Alternative: click the in-form "Upload File" button (inside `._container_1fd3o_71`)
and let openclaw auto-supply from `/tmp/openclaw/uploads/`. Worked once on this
run, then stopped working on subsequent attempt — flaky.
