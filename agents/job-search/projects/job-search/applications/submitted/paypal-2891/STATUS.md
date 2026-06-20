# PayPal 2891 - Product Manager 2, Technical

## Submission Status: SUBMITTED

- **submitted_by**: auto
- **submitted_on**: 2026-06-14
- **confirmation_text**: "application submitted" (confirmation matched)
- **confirmation_url**: https://wd1.myworkdaysite.com/recruiting/paypal/jobs/job/San-Jose-California-United-States-of-America/Product-Manager-2---Technical_R0136890/apply
- **resume_attached**: Cyrus_Shekari_Resume_workday-paypal_R0136890_v2.pdf
- **account**: cyshekari+wd-paypal-202606140319@gmail.com (fresh-account mode, signin_fresh)

## Fixes Applied (2026-06-14)

This role was previously blocked at the Voluntary Disclosures step. The following fixes were applied to `_workday_runner.py`:

1. **PayPal voluntary disclosure button selectors**: Buttons for `personalInfoUS--veteranStatus` and `personalInfoUS--gender` use `data-automation-id` not element `id`. Added `button[data-automation-id='<bid>']` fallback selector.

2. **Ethnicity checkbox commit**: PayPal uses UUID-id checkboxes not linked via `for=` attribute. Changed from label click → JS `el.checked=true + change event` (doesn't update React state) to: JS proximity scan to find decline checkbox ID, then **Playwright `check(force=True)`** (properly triggers React synthetic events).

3. **Terms & Conditions checkbox**: Added multi-method approach (label click → `check(force=True)` → JS change event → find-by-text label → force click).

4. **NOADVANCE-DIAG JS syntax**: Fixed missing closing `}` in JS arrow function.

## Flow

My Information → My Experience (resume uploaded, WE date-repaired) → Application Questions → Voluntary Disclosures (ethnicity decline + T&C + gender/veteran) → Self Identify (disability) → Review → SUBMITTED
