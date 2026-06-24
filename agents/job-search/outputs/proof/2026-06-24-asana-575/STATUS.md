SUBMITTED — 2026-05-25T17:14:00+00:00

role_id: 1542
slug:    asana-7913978
ats:     greenhouse_iframe (asana.com → job-boards.greenhouse.io/embed/job_app)
wrapper: https://www.asana.com/jobs/apply/7913978?gh_jid=7913978
embed:   https://job-boards.greenhouse.io/embed/job_app?for=asana&token=7913978

Final URL after submit: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=asana&token=7913978

Outcome reported by runner: TIMEOUT (legacy detector only matched body text;
the new template at /embed/job_app/confirmation has no "thank you" copy on
first paint). Treated as SUBMITTED because:
  1. URL transitioned to .../job_app/confirmation (canonical GH success path).
  2. fieldErrs was empty — no validation rejection.
  3. grecaptcha-error was empty — no captcha gate.
  4. Email verification interstitial (8x security-input-N boxes) fired AFTER
     the first submit click, runner auto-pulled the code from Gmail
     (`XBaGqE81`) and resubmitted successfully — the verification flow only
     fires server-side AFTER a real submission, so this is definitive
     evidence the form was accepted on the second click.

Pipeline tweaks landed in this run (kept):
- `adapters/greenhouse_iframe.py` HOST_TO_GH_SLUG: added `asana.com → asana`.
- `greenhouse_dryrun.py` LABEL_RULES: added Asana-specific rules
  ("otherwise engaged" → worked_at_company_before; "please list the u.s.
  government entity" / "list the u.s. government entity" / "type 'n/a.'" /
  "type 'n/a'" → literal_na) + new `literal_na` resolver returning "N/A".
- `greenhouse_filler.py` DEMO_LABEL_RE: added `\bsex\b` so "Please identify
  your sex" routes to the demographic decline path (was previously falling
  into the multi_checkboxes branch and trying to tick a US/USA option).
- `greenhouse_iframe_runner.py` outcome detector: also match
  `/job_app/confirmation` in `location.href` (was body-text only).

Confirmation post-flight: Asana confirmation emails / login-link may follow
in cyshekari@gmail.com inbox.
