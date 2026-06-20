SUBMITTED — 2026-05-26T18:51:00+00:00

role_id: 1004
ats: ashby
company: AVIDA
role: Associate Product Manager
url: https://jobs.ashbyhq.com/avida/0b436257-9455-4e8f-a414-2b2b0425e85a/application
est_tc: $0 (unrated)
fit_score: -

confirmation_url: https://jobs.ashbyhq.com/avida/0b436257-9455-4e8f-a414-2b2b0425e85a/application
confirmation_text: "Success — Your application was successfully submitted. We'll contact you if there are next steps."
submitted_by: agent (subagent chain_006 worker)
resume_attached: Cyrus_Shekari_Resume_ashby-avida_0b436257_v2.pdf (uploaded via ref e11 — `#_systemfield_resume` direct upload silently no-op'd, ref of visible "Upload File" button worked)

## Form fill summary
- Name/email/phone: act:type direct selectors
- Resume: browser.upload ref=e11 (visible Upload File button), verified files.length=1
- Worked at sub-100 pre-IPO startup (optional): skipped (No is correct, but optional + Yes/No widget is button-pair — left blank since not required)
- Timezone "Which timezone do you live in?" (REQUIRED): Pacific Time Zone (PST): UTC-8. — clickCoords (406,299) on label, React state confirmed (input.checked=true)

## Driver upgrade shipped
- `ashby_dryrun.py`: added `_r_us_timezone` resolver + LABEL_RULES entries for "which timezone do you live in" / "what time zone are you in" / etc. Resolver picks the "Pacific" option (Cyrus is Kirkland WA), falls back to PST/UTC-8 substring, then to Eastern, then to first option, then to free-text. Tested working on AVIDA form (8-option list).
- Bug found + fixed: initial version used `(field, info)` signature but Ashby resolvers use `(personal, field)` and options come from `f.get('values')` not `f.get('options')`. Fixed inline before commit.

## Permissive-Ashby tenant validated
AVIDA is a permissive Ashby tenant — invisible reCAPTCHA v3 not deployed (or score-passable). Successful clean submit confirms not all Ashby = strict-Ashby cluster.
