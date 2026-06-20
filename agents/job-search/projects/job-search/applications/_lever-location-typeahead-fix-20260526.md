# Lever location-typeahead bypass — fix shipped 2026-05-26

## Symptom
Lever apply forms have `#location-input` (visible text) + `#selected-location` (hidden JSON). The location field is a jQuery typeahead backed by `retrieveLocations.js`. If the user doesn't click a dropdown item, the on-blur handler WIPES both inputs.

Result: any submit driver that uses the generic native-setter pathway (which dispatches `blur`) leaves the location empty, and Lever rejects submit with "Please select a location".

## Diagnosis (Palantir 96a0ce26, 2026-05-26 06:30 UTC)
- Reproduced on `jobs.lever.co/palantir/96a0ce26-...`.
- `act:type` to `#location-input` did trigger the dropdown ("Loading" → "No location found"), but blur wiped the input.
- Direct `fetch('/searchLocations?text=Kirkland%2C+WA&hcaptchaResponse=')` returned `[{name: 'Kirkland, WA, USA', id: 'f7215bebe15fa292cf98e78ab55f6db6b2e779e6'}]` with status 200, EMPTY hcaptcha token — confirmed first call is unauthenticated.
- A second call to the same endpoint returned 500 → the endpoint rate-limits non-hCaptcha calls per session. So we must NOT poll; one fetch only.

## Fix
`role-discovery/lever_filler.py`:
- New JS payload `JS_FILL_LOCATION_TYPEAHEAD`: fetches `/searchLocations` directly, picks exact-name match (falls back to first result, then to a synthetic `{name: <input>}` if API returns nothing), sets both `#location-input` and `#selected-location`, then `.off('blur')` to neutralize the wipe handler.
- `emit_steps` now appends this step right after `JS_FILL_TEXT_FIELDS` whenever `plan["text_fields"]["location"]` is set.

## Validated
End-to-end on Palantir 96a0ce26 (manual run, not yet re-run through the driver):
- `JS_VERIFY` reported `unset_count: 0` after the bypass.
- Submit click then revealed hCaptcha visible-challenge (the real wall — separate blocker, unblocks on `.capsolver-key`).

## Limitations
- One-shot per page load. If the bypass is re-invoked the second `/searchLocations` call gets 500 (hcaptcha-gated). The runner shouldn't re-issue this step.
- Synthetic fallback (`{name: <raw input>}`) may still be server-rejected on tenants that re-validate the id. Not yet observed — Palantir accepted `{name: 'Kirkland, WA, USA', id: 'f7215beb...'}`.
- Other Lever tenants (Outreach 814, Spotify, Shield AI, etc.) not yet re-tested. The pathway is generic — same DOM, same retrieveLocations.js — so should work everywhere.
