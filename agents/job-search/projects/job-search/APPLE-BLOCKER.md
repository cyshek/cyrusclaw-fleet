# APPLE-BLOCKER.md — Apple jobs portal is SSO-walled at the apply step

**Date:** 2026-05-27
**Author:** apple-driver-spike subagent
**Verdict:** **GENUINELY BLOCKED** — needs Apple ID auth cookie injection (no free path around it).
**Confidence:** HIGH — verified on 3/10 stranded roles (covering both HRDWR + SFTWR teams); identical SSO redirect on all three; only one apply CTA per JD.

## TL;DR

Every Apple JD on `jobs.apple.com/en-us/details/<reqid>/<slug>` is publicly readable, but the **only** "Submit Resume" link points at `https://jobs.apple.com/app/en-us/apply/<reqid>`, which 302-redirects to an Apple ID OAuth signin (`idmsa.apple.com/IDMSWebAuth/signin?appIdKey=967e0c9e…&path=/app/en-us/apply/<reqid>`). No guest-apply path exists, no recruiter email is published in the JD, no Easy-Apply-style external fallback. This is the **"SSO-as-captcha"** class already enumerated in the captcha registry (MEMORY.md L110-L125, HANDOFF.md captcha table row 6). It is **not** a missing-driver problem — there is nothing for a custom driver to fill until an authenticated Apple ID session exists.

## Evidence

### 1. JD page is anonymous-readable; apply step is not
Three URLs walked (browser profile=openclaw, no Apple ID cookie):

| id | role | JD URL | Apply CTA → |
|---|---|---|---|
| 1637 | Hardware EPM | `…/details/200663959-0836/hardware-epm-engineering-program-manager?team=HRDWR` | `…/app/en-us/apply/200663959-0836` → 302 → `idmsa.apple.com/IDMSWebAuth/signin?appIdKey=967e0c9e…&path=%2Fapp%2Fen-us%2Fapply%2F200663959-0836` |
| 83   | TPM Services Pricing | `…/details/200660835-0836/technical-product-manager-services-pricing-platform?team=SFTWR` | `…/app/en-us/apply/200660835-0836` → same `idmsa.apple.com/IDMSWebAuth/signin?appIdKey=967e0c9e…&path=%2Fapp%2Fen-us%2Fapply%2F200660835-0836` |
| 1634 | EPM iCloud Mail | `…/details/200664688-3543/engineering-program-manager-icloud-mail-apple-services-engineering?team=SFTWR` | `…/app/en-us/apply/200664688-3543` → same idmsa URL pattern |

### 2. The SSO is OAuth-style, not a checkbox
Inside the `idmsa.apple.com` page sits an iframe at:

```
https://idmsa.apple.com/appleauth/auth/authorize/signin
  ?frame_id=daw-<uuid>
  &language=US-EN
  &skVersion=7
  &client_id=967e0c9eb29cb96878a15488726dd401bae3c121c2b0b124d9e6eb537387d235   ← shared across all Apple jobs apply pages
  &redirect_uri=https://idmsa.apple.com
  &response_type=code
  &response_mode=web_message
  &state=daw-<uuid>
  &authVersion=latest
```

Form has `Email or Phone Number` + `Password` text inputs, plus hidden `grantCode`, `requestUri`, `scnt`, `appIdKey`, `path`, `rv`, `iframeId`, `rememberMe` fields. The `scnt` token + the `daw-` frame id are server-issued per-request — i.e. CSRF-style, regenerated every load. After credential submission Apple routes through SMS/email 2FA on any unfamiliar device (this is the normal Apple ID consumer flow).

### 3. Only one apply link per JD; no published recruiter email
DOM scan of the JD page (role 83) for any `apply|submit|resume|refer` link or `…@apple.com` mailto:

```json
{
  "applyLinks": [
    {"text": "Submit Resume", "href": "https://jobs.apple.com/app/en-us/apply/200660835-0836"},
    {"text": "Submit Resume", "href": "https://jobs.apple.com/app/en-us/apply/200660835-0836"}
  ],
  "emails": []
}
```

(The two entries are top-of-page + bottom-of-page copies of the same button.)

### 4. Even *creating* an Apple ID is itself friction-walled
The "Create Your Apple Account" link goes to `account.apple.com/account?appId=4753&returnUrl=…` which is the standard consumer Apple ID provisioning: name + DOB + email + phone, with SMS verification on the phone, then password complexity, then 2FA enrollment. There is no "headless" or "developer-only" variant.

## Why this is NOT a "missing custom driver" problem

The original blocked-note (`unsupported-ats: ValueError: role id=X has unsupported ATS URL`) is technically correct — `inline_submit.detect_ats()` returns `unknown` for `jobs.apple.com` URLs — but writing an `apple_filler.py` analog to `greenhouse_filler.py` / `ashby_filler.py` would not help, because:

1. The apply page DOM does not exist until the user is authenticated. There are no fields to fill.
2. The auth wall is full Apple ID (OAuth code grant with 2FA on unfamiliar device), not a one-time checkbox or invisible reCAPTCHA score that CapSolver could relay.
3. There is no "apply with resume" mailto / external form / Workday-fallback / Greenhouse-back-end that bypasses jobs.apple.com.

## Screenshots

Captured live in the apple-driver-spike subagent transcript (browser tool, profile=openclaw, 2026-05-27 ~19:21-19:25 UTC). Not persisted to disk because the inline transcript carries the evidence; re-capturable any time via `browser.screenshot` on:

- `https://jobs.apple.com/app/en-us/apply/200664688-3543` — redirects to Apple ID sign-in iframe (the SSO wall).
- `https://jobs.apple.com/en-us/details/200660835-0836/technical-product-manager-services-pricing-platform?team=SFTWR` — JD page with single "Submit Resume" CTA.

## What would unblock this (infra ask)

Analogous to the LinkedIn-authed-resolver escalation (`projects/job-search/ESCALATE-linkedin-authed-resolver.md`), unblock requires **Apple ID session-cookie provisioning** on the OpenClaw browser:

1. Cyrus signs into `jobs.apple.com` in a real browser on a trusted device (one-time SMS 2FA challenge).
2. The session cookies (`myacinfo`, `aasp`, `dssid2`, `idmsa`-domain auth tokens) are exported and injected into the OpenClaw user-data-dir for the `openclaw` profile (or a new `apple` profile).
3. Cookies refreshed periodically (Apple ID sessions typically last weeks-to-months idle, but get invalidated on Apple device password changes or trust-this-device re-prompts).

Then a driver becomes worth writing: it would land on `…/app/en-us/apply/<reqid>` with cookies attached, the iframe would be skipped, and the actual application form (resume upload + work-history + EEOC) would render. Driver shape would mirror `workday_playwright.py` (multi-step JS-rendered SPA with section-by-section navigation) more than the JSON-spec-based Greenhouse/Ashby fillers.

**Estimated effort once cookies are provisioned:** ~1 day (mirror `workday_playwright.py` structure; Apple uses its own SPA framework, not Workday's, so each field selector needs first-hit discovery).

**Estimated effort without cookies:** infinite — there is nothing to drive.

## Decision

**Recommendation:** keep the 10 Apple roles open in the tracker (do NOT skip-flip them), but mark them with `APPLE-DIAGNOSED` agent_notes so future audits don't re-spawn this spike. Revisit only when/if Apple ID cookie injection is provisioned (low priority — $TC band of EPM/PM roles vs. effort + Apple's notoriously slow recruiter response makes this a poor ROI vs. the 184 already-open queue).

## Cross-reference

- Captcha registry — class 6 "SSO-as-captcha" (MEMORY.md L110-L125).
- HANDOFF.md "Open questions for Cyrus" already had: "Apple custom-ATS driver: build vs defer? (recommendation: defer.)" — **this spike confirms defer.**
- LinkedIn-authed-resolver escalation (`projects/job-search/ESCALATE-linkedin-authed-resolver.md`) — same shape of blocker, same shape of unblock (cookie provisioning).
