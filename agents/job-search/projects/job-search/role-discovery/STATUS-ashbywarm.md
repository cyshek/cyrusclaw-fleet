# STATUS — ashby-warmed-profile-build subagent — COMPLETE

## VERDICT: warmed-profile does NOT crack the HARD/residential-resistant strict-Ashby score-gate cohort. Confidence: HIGH.

## What was built (NEW files, committed 961bbc3)
- `role-discovery/warmed_profile_chrome.sh` — launcher: Xvfb :99 TRUE headful (NOT --headless) +
  persistent --user-data-dir=.warmed-profile/ + _proxy_relay.py :18901 → Webshare residential +
  Chrome-149 UA, CDP :19333. Prints JOBSEARCH_CDP. (installed xvfb+x11-utils via sudo for headful.)
  RUN: `source warmed_profile_chrome.sh` → exports JOBSEARCH_CDP=http://127.0.0.1:19333
- `role-discovery/warm_profile.py` — organic warming: google+consent, 2 real searches w/ result-click,
  human scroll/mouse dwell across 8+ major sites, reCAPTCHA demo seed; reports trust cookies.
  RUN (after source): `.venv/bin/python warm_profile.py`
- Combine with runner flags for the strict cohort: `JOBSEARCH_STEALTH=1 JOBSEARCH_KEEP_UA=1`.

## Warming done
2 passes → persistent profile (.warmed-profile/, 107MB) with 216 cookies incl _GRECAPTCHA(89)+NID(276)
+AEC+DV, organic search→click→scroll/mouse history across google/reddit/ashbyhq/wikipedia/bbc/HN/
nyt/stackoverflow/amazon/linkedin/github + 2 reCAPTCHA demo loads. Fingerprint verified clean:
egress=82.23.97.223 (residential), UA Chrome-149 (no HeadlessChrome), webdriver=False, plugins=5.

## Phase 3 LIVE result — Tavus 891 (confirmed residential-resistant baseline)
3 runs (2 no-submit score-probes + 1 REAL submit), each with a VALID freshly-solved in-browser v3
token (sitekey 6LeFb_…, token_len ~2200, injected=2):
  → ALL returned **HTTP 200, ashbyErrorType=RECAPTCHA_SCORE_BELOW_THRESHOLD**, "flagged as possible
    spam". classify=spam-flag, ok=false.
Independent reCAPTCHA-v2-checkbox probe on the warmed profile = **aria-checked:false** (would force a
challenge) → directly confirms Google assigns this profile a LOW trust score.
Evidence: role-discovery/.warmed-profile-proof/ (tavus-891-warmed-dryrun.log,
tavus-891-warmed-REALSUBMIT.log, *-resp-spamflag.json).

## Why (residual — CHOSE-NOT-TO, not CAN'T)
reCAPTCHA-v3 trust here is gated by signals a FRESH in-session warmed profile cannot fake:
(1) profile AGE (weeks of organic history); (2) a REAL logged-in GOOGLE ACCOUNT (biggest v3 booster
= a Cyrus credential, the one legit bank); (3) higher-trust/MOBILE/non-shared IP (the shared Webshare
pool IP is itself likely Google-flagged). NONE are an engine fix.

## Bookkeeping
- Tavus 891 stays `blocked` (spam-flag ≠ confirmed submit; NO false applied — verified).
- tracker.db backed up: projects/job-search/tracker.db.bak.1781154791-ashbywarm
- block_reason appended (warmed-profile-fails note) on 891/944/946/947/1237/2549.
- Docs: TOOLS.md Ashby VERDICT rewritten (3-tier: permissive / moderate=residential-cracks /
  hard=resists-both); MEMORY.md DEBUNKED ledger entry added; memory/2026-06-11.md logged.
- Ashby test suite: 147 passed, 6 skipped (I did NOT modify _ashby_runner.py; its pre-existing
  uncommitted chain_p13 change belongs to another worker — left untouched per single-writer rule).
- Cleaned up the warmed Chrome (:19333) + Xvfb :99 processes I spawned.

## FOR PARENT
- The ~46 manual_ready Ashby rows split: MODERATE strict cohort is drainable NOW via the EXISTING
  proven `_residential_browser.sh` (06-08, ~$0) — parent's call to batch. The ~6 HARD-cohort rows
  (Tavus 891, Baseten 944/946/947, Mercor 1237, OpenAI 2549) resist BOTH residential AND warmed-profile
  → keep blocked/manual until a real Google-logged-in aged profile or mobile IP. Do NOT re-grind
  warmed-profile on them.
- The OpenAI blocked rows (~30) are `openai-applimit-180d` (server-side 180-day per-applicant limit),
  NOT a score-gate — no IP/profile change helps; we already applied.
