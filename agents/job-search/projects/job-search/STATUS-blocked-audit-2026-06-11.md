# STATUS: blocked-section-audit 2026-06-11

phase: BUCKET-1 done (population), found 4 phantom-blocked
done:
- population counts captured
- blocked=98, manual_ready=29, manual-apply=146 (status), submitted=30
- 4 phantom-blocked CONFIRMED: 944/946/947/1237 — disk STATUS.md=SUBMITTED(residential FormSubmitSuccess 2026-06-08) AND db response_status=submitted-residential, but status=blocked/applied_by=null. STALE ashby-score label. FIX: set applied.
next: backup db, correct the 4, continue bucket re-derivation
blockers: none

## blocked block_reason families (98 total)
- openai-applimit-180d: 33  -> TIME (cooldown ~late Nov)
- lever-hcaptcha: 15        -> CREDENTIAL/vendor (hCaptcha-Enterprise, no vendor)
- eightfold-resumewall: 12  -> CODE/PROXY (Filestack upload OR residential)
- linkedin: 8               -> PROXY (li_at burns on shared IP)
- ashby-hard-score: 8       -> 4 are PHANTOM(submitted); rest HARD score (credential: aged Google login)
- proxy-ip-walled: 7        -> PROXY (DataDome/Akamai IP-bound)
- need-runner-misc: 4       -> CODE (per-ATS runner builds)
- icims: 3                  -> mixed (hcaptcha/sso/req)
- workday-we-wall: 2        -> CODE (WE-persist-across-nav)
- hcaptcha-need-key: 2      -> CREDENTIAL (vendor)
- closed-expired: 2         -> CLOSED (legit)
- senior-out-of-scope: 1    -> legit skip
- gh-embed-bounce: 1        -> CODE (Stripe hosted flow)

## manual-apply status families (146)
- linkedin: 64 + 12 (linkedin-2026-06-09): 76 -> PROXY
- google-sso: 61            -> CYRUS-SIDE (Google handles himself)
- tiktok-otp: 2, blocklist: 2, snap/ripple/apple/icims/closed: ~5

## Corrections applied
- 944/946/947/1237 -> applied/auto/2026-06-08 (phantom-blocked, residential FormSubmitSuccess). DONE. blocked 98->94.

## Validations (sampled)
- 2547 Synectics: HTTP 500 -> dead/expired. CONFIRMED closed-expired (legit).
- 2123 Quuppa: LinkedIn-only apply URL, lever board no longer lists SE -> closed-dead-req (legit).
- 2527 Snowflake: role='Senior Technical Program Manager' -> senior-title gate, legit out-of-scope.
- 2612 Stripe gh-embed: prior report already re-ran on current _gh_submit engine -> still uncertain, Stripe-hosted custom flow off standard embed. CODE wall (not phantom).
- 12 Netflix eightfold rows: all RESUMEWALL (Filestack dropzone rejects set_input_files) + invisible reCAPTCHA. CODE(Filestack build) OR PROXY(residential).

## Genuinely auto-appliable NOW (hand to browser worker)
- NONE found beyond the 4 already-corrected phantoms. Every remaining blocked row is a real wall (settled-unwinnable OR needs a multi-hour build OR proxy/credential).

## Proxy price-out (DONE)
- 7 DataDome/Akamai = clean proxy wins (guaranteed)
- 12 Netflix eightfold = PARTIAL (proxy fixes reCAPTCHA, Filestack upload still needs code build)
- 86 LinkedIn-class: 60 no-external-apply (DEAD even w/proxy, LinkedIn IS apply host), 24 stranded/auth (proxy+li_at MIGHT resolve a fraction)
- 4 ashby-HARD: residential PROVEN insufficient, needs aged Google login (credential) NOT proxy
- REC: ~7 guaranteed, ~15-30 plausible w/ proxy+code+li_at. Hold proxy purchase until Cyrus provides li_at, then buy both for the ~500-row LinkedIn cohort. Vendor: residential ~$15-50/mo or mobile 4G/5G ~$30-90/mo.

## PHASE: COMPLETE
- Report: BLOCKED-REPORT-2026-06-11.md
- 4 phantoms corrected (944/946/947/1237), backup taken, verified disk+db both directions
- blocked 98->94, applied 542->546
- Pipeline bug flagged to parent: residential-drain submitter sets response_status+STATUS.md but NOT status/applied_by -> strands its own wins
- NO code touched, NO browser used, NO blanket git-add


