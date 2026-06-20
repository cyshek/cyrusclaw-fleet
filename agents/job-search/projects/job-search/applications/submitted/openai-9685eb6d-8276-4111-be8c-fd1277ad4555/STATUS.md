BLOCKED — 2026-05-26T02:59:00+00:00 (V2 burndown re-attempt)

category: captcha-strict-ashby
role_id: 801
company: OpenAI
role: Technical Program Manager, Safety Systems Engineering
ats: ashby
apply_url: https://jobs.ashbyhq.com/openai/9685eb6d-8276-4111-be8c-fd1277ad4555
confirmation_url: (none — captcha-blocked, same as 2026-05-24)

## What happened (V2 fresh attempt)
Solo browser worker re-attempt per V2 burndown ("attempt every role"). Loaded the
Ashby form fresh (no leftover tabs/cookies from yesterday's attempt). All non-resume
fields filled green:
- Name: Cyrus Shekari
- Email: cyshekari@gmail.com
- Phone: 346-804-0227
- LinkedIn: https://linkedin.com/in/cyshekari
- Location: Kirkland, Washington, United States (typeahead option clicked)
- Start date: 06/08/2026 (react-datepicker, set via native value setter)
- Authorized to work: Yes
- Sponsorship needed: No
- US office 3d/week: Yes
- Arbitration ack: checked
- "I confirm I have read the above": checked
- EEO all 4 fields: Decline to self-identify

## Resume upload failure mode (new today)
Browser tool's `upload` action returned `{ok:true}` repeatedly but
`#_systemfield_resume.files.length` stayed 0. Tried:
1. `selector="#_systemfield_resume"` — ok:true, files=0
2. `selector="input[type=file]:nth-of-type(2)"` — ok:true, files=0
3. `inputRef="ax302"` (Resume Upload File button via aria snapshot) — error: "Node is not an HTMLInputElement" (Playwright resolved to the styled button, not the underlying input)
4. Force-visible the hidden input via CSS override, then upload again — ok:true, files=0
Yesterday's STATUS notes the working workaround was `inputRef` on the `e102`
"Upload File" button (role+name snapshot ref, not aria-ref); current snapshots
returned `e487` but `inputRef=e487` rejected as "not visible" even after scroll
+ override. Possible regression in the upload tool's chooser intercept for
Ashby's React-controlled file widget.

## Captcha context (unchanged from 2026-05-24)
Even if resume attaches, OpenAI Ashby uses reCAPTCHA Enterprise that spam-flags
all Azure datacenter IP submissions. Same pattern as roles 791/792/795/796/
797/798/799/931 (all today) and yesterday's two attempts on this exact role.
Tactical block reason: "fresh-attempt-flagged | needs CapSolver Enterprise".

## What unblocks this
1. Resume upload regression: investigate browser-tool `upload` with selector= on
   Ashby's `input[type=file]#_systemfield_resume` (was working 2026-05-24, file
   count=1 confirmed in yesterday's STATUS).
2. Captcha: residential proxy off Azure IP OR CapSolver reCAPTCHA Enterprise
   token integration. Without one of these, no strict-Ashby OpenAI/Cursor role
   can submit from this VM.

## Cost
~16 min browser time, no LLM credits beyond planning. Tracker row updated:
`agent_notes` appended with BLOCKED reason; `prep_status` left at `manual_ready`,
`applied_by` left NULL.
