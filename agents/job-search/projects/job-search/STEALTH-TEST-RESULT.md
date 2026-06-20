# Stealth vs Lever hCaptcha — Test Result (2026-05-13)

**Question:** Does `playwright-stealth` (or modern equivalent) make Lever's visible-challenge hCaptcha go away?

**Answer: NO. Stealth makes zero observable difference.** We need a CAPTCHA solver service.

## Setup

- **Library:** `tf-playwright-stealth==1.2.0` (the actively maintained fork of the abandoned `playwright-stealth`; transplanted from `puppeteer-extra-plugin-stealth`; published Jun 2025).
- **Browser:** Playwright 1.59.0 Chromium (chromium-headless-shell 1217), default UA overridden to a regular desktop Chrome 131 string.
- **Mode:** Headless only. Headed launches errored out (no X display on the VM); but the headless case is the operationally relevant one anyway — that's what our submit pipeline runs.
- **Test scripts:** `role-discovery/test_lever_captcha.py` (page-load probe) and `role-discovery/test_lever_submit.py` (post-submit-click probe). Both write JSON results to the same dir.

## Sites tested

All 3 from `tracker.db`:
- Outreach: `https://jobs.lever.co/outreach/810b13b3-8338-44fd-99dd-94d24cfe078c/apply`
- Spotify:  `https://jobs.lever.co/spotify/a4a933ce-ab44-4a13-b8ca-8575c97ea40a/apply`
- Palantir: `https://jobs.lever.co/palantir/96a0ce26-cf84-4fa8-934b-acc4363620b2/apply`

All 3 use the **same hCaptcha sitekey** `e33f87f8-88ec-4e1a-9a13-df9bbb1d8120` — i.e. Lever ships a single shared hCaptcha integration across customer boards.

## Findings

### Page-load (no submit click yet)
On all 3 sites, with and without stealth, hCaptcha is mounted but invisible — only two `hcaptcha-enclave.html` iframes (the worker sandboxes) are present, the container div has `height:0`, and no checkbox/challenge iframe is rendered. **This was a red herring** — Lever uses hCaptcha's "invisible" deployment pattern where the challenge only fires at submit time.

### Post-submit-click (the real test)
After filling the form with junk data and clicking the visible "Submit application" button:

| Site     | No stealth                 | With stealth (`stealth_async`) |
|----------|----------------------------|--------------------------------|
| Outreach | enclave 1366×900 **visible** ✅ | enclave 1366×900 **visible** ✅ |
| Spotify  | enclave 1366×900 **visible** ✅ | enclave 1366×900 **visible** ✅ |
| Palantir | enclave 1366×900 **visible** ✅ | enclave 1366×900 **visible** ✅ |

✅ = visible challenge overlay appeared. The `hcaptcha-enclave` iframe expanding to full viewport (1366×900) is hCaptcha's signature for "showing the user the image-grid challenge."

**Result: 0 of 3 sites bypassed.** Stealth produced byte-identical detection behavior to vanilla Playwright. hCaptcha's risk score for our headless Chromium is the same either way — it always escalates to a visible challenge on submit.

### Bonus gotcha (worth keeping)
First test run's submit "didn't trigger" the challenge because `button[type='submit']` matched a hidden helper element first: `<button type="submit" class="hidden" id="hcaptchaSubmitBtn">`. Lever injects this for hCaptcha's internal flow — it is **not** the user-facing submit. **Future filler code must select the visible "Submit application" button explicitly** (e.g. `button:has-text('Submit application'):visible`), not just `button[type=submit]`. This is now baked into `lever_filler.py`'s requirements regardless of solver path.

## Verdict

**Stealth does not solve this.** hCaptcha's bot detection here is not based on `navigator.webdriver` or the trivial fingerprint surface that stealth patches — it's risk-scoring the entire session (TLS, IP reputation, behavioral signals, residential vs. datacenter IP, etc.) and our Azure VM + clean Chromium profile fails that score regardless of fingerprint paint.

**Recommendation:** Proceed with the captcha-solver decision per `CAPTCHA-SOLVER-DECISION.md`. The stealth-first hypothesis is now disproved on three independent Lever boards.

## Artifacts
- `role-discovery/test_lever_captcha.py` — page-load probe
- `role-discovery/test_lever_submit.py` — submit-time probe
- `role-discovery/test_lever_captcha_results.json` — page-load raw data
- `role-discovery/test_lever_submit_results.json` — submit-time raw data
- `role-discovery/submit_probe_*.png` — post-submit screenshots
