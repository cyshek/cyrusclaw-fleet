SUBMITTED — 2026-05-26T18:58:00+00:00

role_id: 1184
ats: ashby (permissive)
company: Orb
role: Solutions Architect- San Francisco HQ (HQ-SF, Hybrid)
url: https://jobs.ashbyhq.com/orb/3dfabceb-5b4f-457d-9691-233e6b01ac29/application
est_tc: $200-275K OTE (per posting)

confirmation_url: same
confirmation_text: "Success — Your application was submitted. We'll reach out soon with next steps!"
submitted_by: agent (subagent chain_006 worker)
resume: uploaded via ref e20 (visible "Upload File" button) — verified files.length=1

## Form fill summary
- Name/email/phone/LinkedIn: act:type direct selectors (4 fields)
- Location (required combobox): act:type "Kirkland" → selected "Kirkland, Washington, United States" from listbox (Ashby location typeahead)
- 3-day office Yes/No (REQ): clickCoords on Yes button (Ashby button-pair widget) → _active_y2cw4_58 class set
- Work auth (REQ): radio "Can work for any employer" — clickCoords on label
- Sponsorship Yes/No (REQ): clickCoords on No → _active_ class set
- Preferred Pronouns (REQ checkbox group): "Prefer not to answer" — clickCoords on label
- Source (REQ checkbox group): "Online job board (LinkedIn, Indeed)" — clickCoords
- EEOC gender/race/veteran (REQ): "Decline to self-identify" / "I decline to self-identify for protected veteran status" — clickCoords on each
- Voluntary demographics (age, gender, neurodiversity, race, sexual orientation, etc.): LEFT BLANK per personal-info.json optional_field_policy=skip_unless_required

## Driver upgrade shipped
- `role-discovery/greenhouse_dryrun.py` `r_work_authorized`: added "Can work for any employer" / "Can work for current employer" / "Seeking work authorization" option family. Picks "any employer" when authorized=yes. Generic to Orb-family Ashby tenants; would also catch any GH role using the same option labels.

## Required-but-not-in-plan field
- Location (combobox at top of Ashby form, `Start typing...` placeholder, listbox-based typeahead). Plan emitter didn't surface this as a required field. Worth adding to ashby_dryrun to detect `LocationComponent` widget and emit a city-typeahead step. TODO for future Ashby crawler upgrade.
