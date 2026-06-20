"""
Rippling ATS filler — PARTIAL (BLOCKED by Cloudflare Turnstile).

Discovered 2026-05-24 via role-id 1243 (Daloopa, Product Manager).
Full form fill works; submit hangs on Cloudflare Turnstile invisible challenge.
Bot detection signal: JSHandle@node traces in Turnstile iframe console
(challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/...).
Sitekey observed: 0x4AAAAAACMregvPzfoTgN2k

STATUS: NOT VALIDATED. Same captcha class as Lever's visible hCaptcha — likely
unsolvable without 2captcha/anti-captcha integration or a real browser session.

What works:
1. Anonymous form (no account required).
2. URL pattern: https://ats.rippling.com/en-US/{slug}/jobs/{uuid}
3. Apply submit URL: https://ats.rippling.com/{slug}/jobs/{uuid}/apply?step=application
4. Resume upload via file input → auto-parses PDF and prefills name/email/phone/company/location/linkedin.
   - LinkedIn URL prefill can be malformed (missing /in/ path); always override.
5. Text inputs with stable IDs of pattern "field-N" (N varies per form).
   Discover via: snapshot, then look for <input id="field-{N}"> elements.
6. Combobox selects: click <button role=combobox id="field-N"> to open, then
   click <li role=option id="field-N-list-option-K"> (K=0,1,...) for the option.
   Options indexed by visible text (Yes/No, etc.).
7. Location typeahead: type into field, wait 1500ms, click first
   #field-{N}-list-option-0; hidden field stores Google Place ID.
8. Native setValue pattern (React-controlled inputs):
     setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
     setter.call(el, value)
     el.dispatchEvent(new Event('input', {bubbles:true}))
     el.dispatchEvent(new Event('change', {bubbles:true}))
     el.dispatchEvent(new Event('blur', {bubbles:true}))
9. SMS opt-in: native radios with name="sms_opt_in", values "true"/"false".
10. Essays: rendered as <input type="text"> (NOT textarea), but accept long values fine.
11. EEO: optional comboboxes; safe to leave at "Select..." default.
12. Submit button: <button> with innerText "Apply" (no specific id; find by text).

What blocks submission:
- Cloudflare Turnstile widget mounted in 1x1 iframe (display: none in DOM but active).
- Turnstile issues PAT (Private Access Token) challenge that returns 401 on automated browsers.
- The fetch hangs indefinitely; Apply button stays in spinner state.
- Daloopa observed value: data-sitekey="0x4AAAAAACMregvPzfoTgN2k".

To unblock (future work):
- Integrate 2captcha/CapSolver Turnstile solver → inject token via
  `window.turnstile.execute()` callback override OR set
  `window.cf-turnstile-response` hidden input value.
- OR use a real fingerprinted browser session via Browserbase/Anchor.
- OR ship STATUS.md=PREP-READY-MANUAL and let Cyrus click Apply by hand.

Discovered field map for Daloopa role 1243 (form layout will differ per company):
{
  "field-12": "first_name", "field-16": "last_name", "field-20": "email",
  "field-24": "pronouns_combobox", "field-31": "current_company",
  "field-35": "phone", "field-38": "phone_country_combobox",
  "field-46": "location_typeahead", "field-51": "location_place_id_hidden",
  "field-55": "linkedin", "field-63": "visa_now_combobox",
  "field-69": "visa_future_combobox", "field-75": "nyc_hybrid_combobox",
  "field-81/85/89/93/97": "essay_inputs", "field-101": "additional_info_optional",
  "field-105/111/118/124/130": "EEO_comboboxes",
  "sms_opt_in (radio name)": "SMS yes/no"
}
File inputs: 2 (resume idx 0, cover letter idx 1).
"""

# Stub adapter — extend when Turnstile is solvable.
def build_plan_partial(spec_path):
    raise NotImplementedError("Rippling ATS blocked by Cloudflare Turnstile. See _partial/rippling_filler.py docstring.")
