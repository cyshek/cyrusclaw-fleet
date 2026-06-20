# Captcha Solver Decision (research, 2026-05-13; revised evening for NopeCHA addition)

> **2026-05-27 UPDATE — SCAFFOLDING SHIPPED, AWAITING FUNDING DECISION.**
>
> The thin client (`role-discovery/capsolver_client.py`), runner helper
> (`role-discovery/captcha_presubmit.py`), and integration wiring into both
> `greenhouse_iframe_runner.py` and `ashby_filler.py` are in place. 36 unit
> tests cover the client, the helper, and the wiring. **All paths default-OFF.**
>
> Unlock procedure (Cyrus, when ready):
>
> ```bash
> # one-time: deposit ~$20 at https://capsolver.com
> export CAPSOLVER_API_KEY='<paste-key-here>'
> export ENABLE_CAPSOLVER=1
> # then run normally:
> cd projects/job-search/role-discovery
> .venv/bin/python inline_submit.py --role-id <strict-ashby-role>
> # or for the GH iframe path:
> .venv/bin/python greenhouse_iframe_runner.py --slug <packet-slug>
> ```
>
> Estimated cost to sweep the 53-row strict-Ashby cohort at $480-555K TC:
> ~$0.16 ($2.99 per 1000 reCAPTCHA v3 solves).
>
> Monitor first 5 solves: tail the runner's `report['captcha_presubmit']`
> field (logged + included in `applications/submitted/<slug>/report.json`).
> Look for `injected: true` and post-submit outcome != `CAPTCHA_GATE`.
> If `injected: true` AND post-submit still `CAPTCHA_GATE`, the tenant's
> min_score is higher than 0.7 — bump min_score and retry.
>
> Stop-loss kept at $15/mo as defined below.

**Problem:** Lever ships visible hCaptcha on every board sampled (Outreach, Spotify, Shield AI, Palantir). Headless auto-submit blocked. Ashby may be similar (Cohere). Greenhouse is fine — invisible reCAPTCHA v3 auto-passes.

**Goal:** Pick ONE captcha-solver to unblock Lever (and probably Ashby), keep monthly cost predictable, and define a stop-loss.

## TL;DR (revised 2026-05-13 evening)

- **Pipeline now supports NopeCHA (default) and CapSolver (fallback).** Switch via `CAPTCHA_VENDOR` env var.
- **NopeCHA free tier is NOT viable for this VM:** free tier excludes non-residential / datacenter IPs (per https://developers.nopecha.com/), and even if it worked, hCaptcha token costs 10 credits → only ~10 solves/day on free.
- **Recommended path:** subscribe to NopeCHA Basic (~$10/mo, ~500 hCaptcha/day) for predictable flat rate, OR deposit $20 in CapSolver (~$0.80/1k hCaptcha, no daily cap, no IP restriction). Either works; code supports both.
- **For now (no key):** Lever auto-submit stays blocked; runner returns ABORT-CAPTCHA-FAIL per role and continues batch.

---

## Service comparison

Per-1000 prices (pay-as-you-go) where the vendor publishes them. Pulled from each vendor's own pricing page today. hCaptcha rows are vendor-stated; for vendors that bury hCaptcha in a sub-page I used industry-standard rates that match their other categories.

| Service | hCaptcha /1k | reCAPTCHA v2 /1k | reCAPTCHA v3 /1k | Avg solve time | Model | Python SDK | Free trial |
|---|---|---|---|---|---|---|---|
| **CapSolver** | ~$0.80 | ~$0.80 | ~$0.80 | 5–15 s | AI-first | Yes (official) | Yes, small balance on signup |
| **2Captcha** | ~$2.99 | $1.00–2.99 | $1.45–2.99 | 10–30 s | AI + human fallback | Yes (official) | No (low min deposit ~$1) |
| **Anti-Captcha** | ~$2.00 | $0.95–2.00 | $1.00–2.00 | 5 s | 100% human | Yes (official) | No |
| **SolveCaptcha** | ~$1.00 | $0.55 | $0.80 | 2–3 s | AI + human | Yes | No |
| **DeathByCaptcha** | ~$1.39 | ~$1.39 | ~$2.89 | 7–16 s | Human-heavy | Yes (older) | No (15-cap free trial) |
| **NopeCHA** | flat-rate sub | flat-rate sub | flat-rate sub | 2–5 s | AI only (browser ext + API) | Yes | Yes (100/day free) |

**NopeCHA tiers (flat monthly, unlimited up to plan cap):** ~$10/mo (Basic, ~500/day), ~$25/mo (Pro, ~5k/day), $50+/mo (higher). Predictable cost — no surprises.

> Note on accuracy: independent reviews (sitescraper community, ScrapeOps benchmarks ~2024-25) consistently rank **CapSolver** highest for AI-solvable captchas (hCaptcha, Turnstile, reCAPTCHA v2/v3) on both speed and success rate (~95%+). 2Captcha and Anti-Captcha are reliable veterans but slower and pricier on hCaptcha because they're human-backed. NopeCHA is great when it works but has narrower hCaptcha coverage on enterprise variants.

## Integration with Playwright (token injection model)

All six work the same way for hCaptcha/reCAPTCHA:

1. Read `data-sitekey` + page URL from the form's `<iframe>` or hidden field.
2. POST to vendor API → get back a token (string).
3. Inject token into the page's `h-captcha-response` and `g-recaptcha-response` `<textarea>` elements via `page.evaluate(...)`.
4. Submit form. Done.

No iframe interaction, no clicking grid puzzles. CapSolver and 2Captcha both ship Playwright examples.

---

## Cost model for Cyrus's actual usage

**Volume:** 10-15 apps/day, ~5 days/week → ~50/wk → ~215/mo.

Hit rate by ATS (estimated from current pipeline):
- Greenhouse: 0% (invisible v3 auto-passes) — **no solver needed**
- Ashby: ~50% (some boards trigger visible challenges)
- Lever: ~100% (every board sampled has visible hCaptcha)
- Workday: ~80% (occasional Kasada/PerimeterX, rare hCaptcha)

**ATS mix in Cyrus's tracker today** (rough): Greenhouse ~50%, Lever ~25%, Ashby ~15%, Workday ~10%.

Captcha hits per month at 215 apps:
- Lever: 215 × 0.25 × 1.0 = ~54
- Ashby: 215 × 0.15 × 0.5 = ~16
- Workday: 215 × 0.10 × 0.8 = ~17
- **Total: ~87 captcha solves/month** (call it 100 to be safe)

| Volume | CapSolver $0.80/1k | 2Captcha $2.99/1k | NopeCHA Basic $10/mo |
|---|---|---|---|
| 100/mo (current pace) | **$0.08** | $0.30 | $10 (flat) |
| 300/mo (3x growth) | $0.24 | $0.90 | $10 (flat, under 500/day cap) |
| 1000/mo | $0.80 | $2.99 | $10–25 |
| **Annual at 300/mo** | **~$3** | ~$11 | ~$120 |

**Reality check:** at this volume, pay-as-you-go is essentially free. Even pessimistic 10x growth puts CapSolver at <$10/year.

---

## Recommendation (revised 2026-05-13 evening): **NopeCHA-first, CapSolver-fallback**

Why two vendors:

1. **NopeCHA is the cheapest at our volume IF stealth/account works.** ~$10/mo flat for ~500 hCaptcha/day, no per-solve metering anxiety. The Token API claims 15s avg solve.
2. **CapSolver is the safety net.** Per-solve $0.80/1k, works from datacenter IPs, no daily cap, well-documented. If NopeCHA throttles us or coverage drops, flip `CAPTCHA_VENDOR=capsolver` and keep going.
3. **Both share the same `CaptchaSolver` API.** Switching vendors is one env var — no code change in the filler or runner.

### Activation (whichever you choose first)

*NopeCHA path:*
1. Sign in at https://nopecha.com (Google or GitHub OAuth — no email/password).
2. Subscribe to a paid plan (free tier won't work from Azure datacenter IPs; see caveats above).
3. Get key from https://nopecha.com/manage → `echo '<key>' > projects/job-search/.nopecha-key && chmod 600 projects/job-search/.nopecha-key`.
4. Default vendor is `nopecha`; no env var needed.

*CapSolver path:*
1. Sign up at https://capsolver.com, deposit ~$20.
2. `echo '<key>' > projects/job-search/.capsolver-key && chmod 600 projects/job-search/.capsolver-key`.
3. `export CAPTCHA_VENDOR=capsolver` (or default to nopecha if both keys exist).

### Original recommendation: **CapSolver**, pay-as-you-go, $20 starter deposit

Three reasons:

1. **Best AI success rate on hCaptcha + Turnstile** (the two we actually need) per independent benchmarks; ~5-15s solves keeps the inline submit pipeline snappy.
2. **At Cyrus's volume, cost is rounding error** — $20 prepaid covers ~25,000 solves, i.e. years. No subscription drag.
3. **Token-injection works cleanly with Playwright/Chromium**, slots into the existing `lever_filler.py` plan as one extra step before form submit. No iframe scraping, no grid clicking.

### Stop-loss

**If monthly captcha spend exceeds $15** (~5,000 solves/mo, i.e. 100x expected), pause auto-submit on the offending ATS and fall back to manual queue for that surface. That's a signal something's broken — either hCaptcha success rate cratered (vendor issue, switch to 2Captcha/Anti-Captcha) or we're retrying captchas in a bad loop.

Also: **review monthly.** If hCaptcha disappears from Lever (they're slowly rolling out invisible hCaptcha v3, which would auto-pass like reCAPTCHA v3), drop the solver entirely.

---

## Solver-free alternatives (worth trying *before* paying)

1. **`playwright-stealth` + residential-ish browser fingerprint.** Many Lever boards drop the visible challenge if hCaptcha scores the session as "human." Cheap, free, worth 30 min of testing on Outreach. **Try this first.** If it knocks Lever hit-rate from ~100% to ~30%, captcha cost stays trivial.
2. **Manual-solve-once-per-session.** Open the canvas, Cyrus solves one Lever hCaptcha, the resulting `hcaptcha-cookie` (`hmt_*`) sometimes carries for the rest of the day on the same Lever subdomain. Fragile — Lever scopes cookies per-org — but free.
3. **Skip Lever entirely (short-term).** Greenhouse + Ashby are >50% of the pipeline already and submit cleanly. Drain those for 2-4 weeks while we evaluate stealth + CapSolver in parallel. **Lowest-risk path.**

### Suggested order of operations

1. **This week:** keep Lever in manual queue (it already is). Drain Greenhouse backlog with the working pipeline. Cost: $0.
2. **Next week:** try `playwright-stealth` against 2 Lever boards. Measure captcha hit rate. Cost: $0.
3. **If stealth doesn't kill the captcha:** sign up for CapSolver, deposit $20, wire it into `lever_filler.py` as a token-injection step. Total exposure: $20.
4. **Review after 30 days.** If <$1 spent, keep going. If >$15 spent, stop-loss kicks in.

---

*Compiled from vendor pricing pages 2026-05-13. Prices change; re-check before committing.*
