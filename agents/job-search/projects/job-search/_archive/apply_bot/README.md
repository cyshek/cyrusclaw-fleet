# Apply Bot

Playwright-based auto-apply harness. Currently supports Greenhouse (covers
Anthropic, Scale AI, OpenAI, Stripe, Databricks, and ~70 of your 264 queued roles).

## How Greenhouse submission works (important!)

Greenhouse uses **reCAPTCHA Enterprise v3 (invisible/score-based)** on the submit
endpoint. Headless and even real-Chrome+stealth requests get scored as bots and
hit `HTTP 428 captcha-failed`. **However**, Greenhouse has a built-in fallback:
when reCAPTCHA fails, it sends an 8-character security code by email and shows
an OTP input on the page. The bot detects this UI and prompts you for the code.

So the typical live submit flow is:

1. Bot fills 18/18 fields and clicks Submit.
2. Greenhouse rejects with captcha-failed and emails an 8-char code to your
   personal Gmail (the `email` from `assets/personal-info.json`).
3. You read the email, paste the code into the bot's prompt — bot enters it and
   re-clicks Submit. Application accepted.

If you don't want the OTP step, use `--prep` mode: the bot fills the form in a
visible browser and waits for you to click Submit yourself (your real-human
mouse activity gives reCAPTCHA a high enough score to skip the OTP entirely).

## Quick start

**Dry-run a single role** (opens browser, fills form, screenshots, does NOT submit):
```powershell
cd C:\OpenClaw\apply_bot
python apply.py --url "<greenhouse-apply-url>" --company "<co>" --role "<role>"
```

**Dry-run top N from your ranked list:**
```powershell
python apply.py --top 5
```

**Live mode** (submits, then prompts you for the 8-char OTP from your email):
```powershell
python apply.py --url "..." --company "..." --role "..." --live
```

**Live mode with pre-supplied OTP** (if you already have the code):
```powershell
python apply.py --url "..." --live --otp ABCD1234
```

**Prep mode** (fill form, leave browser open for you to click Submit yourself —
no OTP needed because real human activity defeats reCAPTCHA):
```powershell
python apply.py --url "..." --prep
```

**Live mode with Gmail auto-OTP** (fully unattended — bot fetches the code from your inbox):
```powershell
python apply.py --url "..." --live --gmail-imap
```
Requires one-time setup of `assets\.gmail_credentials` — see "Fully unattended" section below.

**Headless** (no visible browser window): add `--headless` to dry-run or live
modes (NOT compatible with `--prep`).

## Fully unattended (Gmail auto-OTP) setup

To eliminate the manual OTP-paste step:

1. Enable 2FA on `cyshekari@gmail.com` if not already.
2. Generate a Google **App Password** at https://myaccount.google.com/apppasswords
   (select "Mail" / "Windows Computer"). You'll get a 16-char code.
3. Create `C:\OpenClaw\apply_bot\assets\.gmail_credentials` with two lines:
   ```
   cyshekari@gmail.com
   xxxxxxxxxxxxxxxx
   ```
   (this file is gitignored).
4. Test once: `python apply.py --url "..." --live --gmail-imap`. The bot will
   submit, wait up to 90s polling Gmail IMAP, find the Greenhouse OTP, paste it,
   and re-submit. End result: hands-free.

You can also batch this: `python apply.py --top 20 --live --gmail-imap` will
walk down your top-20 ranked roles, submitting each one without intervention.

## Output

Each run creates a folder `runs/<timestamp>-<company>-<role>/` containing:
- `01-landed.png` — initial JD page
- `02-form.png` — the application form before fill
- `03-filled.png` — the form after fill (review this before going live!)
- `04-after-submit.png` — only in live mode
- `05-otp-prompt.png` — only when reCAPTCHA failed and OTP UI appeared
- `06-after-otp-submit.png` — only after OTP code submitted
- `result.json` — every field attempted (selector, label, value, success/error)

## What it fills automatically

From `assets/personal-info.json`:
- Name, email, phone, country
- Resume upload (`assets/Cyrus_Shekari_Resume.pdf`)
- LinkedIn / website (when the form has that field)
- Work authorization: yes
- Visa sponsorship: no
- Non-compete / restrictive agreement: no
- Security clearance: no
- AI-policy / privacy / terms-acknowledgement: yes
- Gender / Race / Veteran / Disability: decline to self-identify
  (with fuzzy fallbacks: "I do not want to answer", "Prefer not to say", etc.)

## Form-handling features

- **Formik-safe typing**: clicks → fill("") → press_sequentially → Tab. This
  triggers React's synthetic onChange so Formik's controlled state actually
  registers the value (regular `.fill()` looks correct in DOM but fails Formik
  validation).
- **React-Select dropdowns**: types into the input, clicks the first matching
  `div[class*='option']`, falls back to Enter. Detects "no options" message and
  cycles through fallback strings (e.g., for the "Decline" wording variations).
- **Custom yes/no questions**: 11+ keyword regexes covering sponsorship, work
  authorization, relocation, in-person work, non-compete agreements, security
  clearance, AI/privacy policy acknowledgement, prior-applicant questions, etc.
- **Validation guard**: refuses to submit if any required essay/textarea field
  is still blank, listing them so you can extend the rule set.

## Workflow

1. **Always dry-run first** for a new company. Open `03-filled.png` and verify.
2. If it looks right, re-run with `--live` (then enter OTP) OR `--prep` (then
   click Submit yourself).
3. Mark the row as `submitted` in your tracker.

## Diagnostic tools

- `python diag_dropdowns.py <url>` — opens form, lists every react-select option
  text per dropdown. Run this before fielding a new ATS tenant so you know what
  answer strings to type.
- `python verify.py <url> <co> <role>` — fills then reads back visible
  `.select__single-value` text per dropdown. Use to confirm dropdowns took
  before going live.
- `python submit_debug.py` — Scale AI specific. Captures network responses
  during submit (this is how we discovered the captcha-failed 428).
- `python probe_captcha.py` — lists all captcha widgets on a page (sitekey,
  type, sitescript URLs). Run on any new tenant.

## Limitations

- Only Greenhouse adapter built (Ashby, Lever, Workday: TODO).
- Doesn't handle multi-page application flows yet (most Greenhouse apps are
  single-page).
- Doesn't auto-write cover letters (your policy: skip unless required).
- Free-text "Why are you interested?" questions: TODO (currently left blank).
- OTP must be entered manually (we don't have access to your Gmail).
- `APPLY_OTP_NONINTERACTIVE=1` env var: skips the OTP prompt and exits with
  `otp_pending` status in result.json (used for batch / autopilot runs).

