# Custom ATS Scout — 2026-05-13

**Author:** scout-custom-ats subagent  
**Scope:** "other" host bucket in tracker.db (non-Greenhouse / non-Lever / non-Ashby branded careers sites)  
**Method:** tracker.db → web_fetch shell pages → boards-api.greenhouse.io probe → live browser snapshot of iframe DOMs (Stripe, Datadog, Databricks)

---

## TL;DR — One-line answer

> **All 13 hosts are Greenhouse boards in disguise.** Every single sampled apply form is the standard `https://job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<jid>` iframe. **Our existing `greenhouse_filler.py` already drives that exact form.** The work to "support" these hosts is 90% adapter shim, 10% iframe-context plumbing in the browser-driving layer. There is no "Workday/Lever-class" deep work hiding here.

---

## Evidence

### 1. Every URL in tracker.db carries `gh_jid=…`

```
tracker.db roles WHERE host in {datadog, databricks, stripe, coreweave, abnormal, dropbox,
elastic, okta, salesloft, pinterest, mongodb, orcasecurity, lyft (careerpuck)}
  → 100% have gh_jid query param
```

### 2. boards-api.greenhouse.io accepts every slug

| Host                      | GH slug            | jobs in API |
|---------------------------|--------------------|-------------|
| careers.datadoghq.com     | `datadog`          | 410         |
| databricks.com            | `databricks`       | 814         |
| stripe.com                | `stripe`           | 486         |
| coreweave.com             | `coreweave`        | 250         |
| abnormal.ai               | `abnormalsecurity` | 86          |
| jobs.dropbox.com          | `dropbox`          | 72          |
| jobs.elastic.co           | `elastic`          | 149         |
| www.okta.com              | `okta`             | 377         |
| www.salesloft.com         | `salesloft`        | 28          |
| www.pinterestcareers.com  | `pinterest`        | 159         |
| www.mongodb.com           | `mongodb`          | 414         |
| orca.security             | `orcasecurity`     | 17          |
| app.careerpuck.com (Lyft) | `lyft`             | 132         |

### 3. Standard Greenhouse hosted JD URLs **redirect to the company-branded site**

`https://job-boards.greenhouse.io/<slug>/jobs/<jid>` → 302 → company URL. Greenhouse has set the company page as the canonical board UI for these tenants. The hosted JD is gone, but the **apply form** remains hosted at Greenhouse.

### 4. Apply form is the standard `/embed/job_app` iframe (every host)

Confirmed by direct fetch — every host returns the standard "Apply for this job" form, including the "Autofill with MyGreenhouse" button, react-select dropdowns, Filestack-style attach buttons, and invisible reCAPTCHA Enterprise:

| Host         | embed URL response | "Apply for this job" string | reCAPTCHA |
|--------------|--------------------|------------------------------|-----------|
| datadog      | 200, 75 KB         | ✅                            | invisible v3-style enterprise |
| databricks   | 200, 87 KB         | ✅                            | invisible |
| stripe       | 200, 118 KB        | ✅                            | invisible |
| coreweave    | 200, 70 KB         | ✅ (lazy-load)                | invisible |
| abnormalsec  | 200, 81 KB         | ✅                            | invisible |
| dropbox      | 200, 129 KB        | ✅                            | invisible |
| elastic      | 200, 79 KB         | ✅                            | invisible |
| okta         | 200, 88 KB         | ✅                            | invisible |
| salesloft    | 200, 32 KB         | ✅                            | invisible |
| pinterest    | 200, 77 KB         | ✅                            | invisible |
| mongodb      | 200, 68 KB         | ✅                            | invisible |
| orcasecurity | 200, 37 KB         | ✅                            | invisible |
| lyft         | 200, 93 KB         | ✅                            | invisible |

### 5. Live browser snapshots (Stripe, Datadog, Databricks)

Each company page injects an iframe with a `validityToken` parameter:

```
Stripe:     https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7815794
Datadog:    https://job-boards.greenhouse.io/embed/job_app?for=datadog&validityToken=N2Sf...&token=7683226
Databricks: https://job-boards.greenhouse.io/embed/job_app?for=databricks&validityToken=OmxI...&token=8335860002
```

Inside the iframe: identical DOM to the Notion/Anthropic forms `greenhouse_filler.py` already submits — same field labels, same react-select widgets, same "Resume/CV*" Attach button, same Linkedin Profile field, same demographic block at the bottom.

Stripe uniquely also includes:
- Native first-party file picker ("Dropbox" button + "Enter manually") — same Greenhouse widget, no Stripe customization.
- Inline "Locate me" geolocation button on Location field — also standard Greenhouse.

The `validityToken` is a Greenhouse-issued CSRF/origin nonce. It is regenerated on every company-page render and is required for the hidden POST. We do **not** need to mint it; we just need to grab it from the iframe `src` after the page loads, which our browser-driver already does whenever it picks an iframe by selector.

---

## Per-host rundown

### Tier 1 — already works with zero new code (just JD-fetch shim + iframe context switch)

| Host | Open roles | ATS engine | Auth/SSO wall | Captcha | Adapter effort |
|---|---|---|---|---|---|
| Datadog | 6 | Greenhouse `/embed/job_app` (iframe in `careers.datadoghq.com`) | none | invisible reCAPTCHA Enterprise | **small** |
| Databricks | 5 | Greenhouse `/embed/job_app` (iframe in `databricks.com`) | none | invisible reCAPTCHA Enterprise | **small** |
| Stripe | 5 | Greenhouse `/embed/job_app` (iframe in `stripe.com`) | none | invisible reCAPTCHA Enterprise | **small** |
| CoreWeave | 4 | Greenhouse `/embed/job_app` (iframe in `coreweave.com`) | none | invisible reCAPTCHA Enterprise | **small** |
| Abnormal Security | 2 | Greenhouse `/embed/job_app` (iframe in `abnormal.ai`) | none | invisible reCAPTCHA Enterprise | **small** |

### Tier 2 — same pattern, 1-3 roles each

| Host | Open roles | Notes | Effort |
|---|---|---|---|
| Dropbox (`jobs.dropbox.com`) | 1 | 403 on direct fetch (Cloudflare bot block), but iframe still serves. Will need browser path, no curl path. | small |
| Elastic (`jobs.elastic.co`) | 1 | Standard pattern. | small |
| Okta (`www.okta.com`) | 1 | Standard pattern. | small |
| Salesloft (`www.salesloft.com`) | 1 | Generic "Future Sales Engineer Opportunities" req — low value. | small |
| Pinterest (`www.pinterestcareers.com`) | 3 | Bot-blocks plain fetch. Browser path works. | small |
| MongoDB (`www.mongodb.com`) | 3 | Standard pattern. | small |
| Orca Security (`orca.security`) | 3 | Standard pattern; page literally has `#apply-form` anchor that scrolls to embedded GH iframe. | small |
| Lyft via CareerPuck (`app.careerpuck.com`) | 8 | CareerPuck is a third-party careers-page service that wraps Greenhouse embed. Same iframe still applies. | small |

---

## What "small" actually means

**No new filler.** Reuse `greenhouse_filler.py` and `greenhouse_dryrun.py` unchanged. The dryrun spec comes from the same `boards-api.greenhouse.io/v1/boards/<slug>/jobs/<jid>?questions=true` endpoint we already use.

The only real changes:

1. **`detect_ats()` extension** — recognize these hosts and map them to `("greenhouse", slug, jid)`. The `gh_jid` in URL gives us `jid`. The `slug` is one of 13 known constants (table above). New helper: `RESOLVE_HOST_TO_GREENHOUSE_SLUG = {"careers.datadoghq.com": "datadog", ...}`.
2. **`inline_submit.py` packet prep** — use the resolved slug+jid to call the boards-api JSON for JD + dryrun. Already does this for native Greenhouse; just route through the new resolver. **Probably <30 lines of Python.**
3. **Browser plan execution** — instead of navigating to `https://job-boards.greenhouse.io/<slug>/jobs/<jid>` and filling that page, navigate to `app_url` (the company page) and switch the active context to the first `<iframe>` whose `src` contains `job-boards.greenhouse.io/embed/job_app`. After context switch, the existing step plan works as-is.
   - This is the only piece that touches the browser-driver code path. If our `greenhouse_filler.py` step plan doesn't currently support iframe-scoped refs, we need a small wrapper that captures `iframe.contentDocument` or uses the browser tool's iframe-ref support.
4. **Confirmation detection** — same as standard Greenhouse ("Application submitted." text in iframe). No change.

**Total estimated effort:** half a day for one engineer / one focused subagent. ~8 lines of host→slug mapping per company, plus the iframe context wrapper.

### Captcha note

Every form uses **invisible reCAPTCHA Enterprise**, identical to standard Greenhouse boards (Notion, Anthropic, Sierra, Vercel, etc.) that we already submit successfully. **No new captcha defenses.** No hCaptcha, no Cloudflare Turnstile, no visible challenges observed on any of the 13 hosts.

---

## Build-next ranking by ROI

ROI = (open roles unlocked) / (effort). Since every adapter is "small" and all share one shim, the practical play is to ship **one PR that handles all 13 hosts at once**.

| Rank | Action | Roles unlocked | Effort | Why |
|---|---|---|---|---|
| **1** | Single "GH-iframe" shim covering the 13 hosts above | **47** open roles | small (single half-day) | One change, clears the entire "other" bucket. |
| 2 | (n/a — there is no tier 2; everything in this scout is the same shape) | – | – | – |

If we want to stage it for safety, suggested order (by open-role count and brand fit):

1. Datadog (6) — clean, no anti-bot.
2. Databricks (5) — clean.
3. Stripe (5) — clean.
4. CoreWeave (4) — clean.
5. Lyft via CareerPuck (8 if status-bucket recheck includes them) — clean.
6. MongoDB / Pinterest / Orca / Okta / Dropbox / Elastic / Abnormal / Salesloft — incremental once the wrapper is proven.

---

## Things this scout did NOT check

- **Did not test a real submit.** Read-only by mandate. We are inferring "no new captcha" from form HTML / iframe inspection. The first live submit on Stripe will tell us if there's a tenant-specific extra field.
- **Did not check Apple** (per task constraint — separate path).
- **Did not check LinkedIn** (per task constraint — not an ATS).
- **Did not test the iframe-context support in our current browser tool plan executor.** That's the one engineering risk; if iframe ref-passing isn't supported, we need to add it. It's a known-good pattern in Playwright/CDP, so unlikely to be blocked.
- **CareerPuck (Lyft):** confirmed via boards-api that the GH slug `lyft` returns 132 jobs. The CareerPuck shell at `app.careerpuck.com` returns a 2.6 KB SPA shell. Did not snapshot the iframe live — strong inference only. Worth a 2-minute live check before going to prod.
- **Dropbox & Pinterest** return HTTP 403 to plain Python `urllib` (Cloudflare). Browser path will still work; but this means our `web_fetch` helper for JD prep must use the `boards-api.greenhouse.io` JSON, not the careers page.

---

## Appendix — sample apply iframe URLs

```
Stripe:
  https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7815794
Datadog (with validityToken from a fresh page render):
  https://job-boards.greenhouse.io/embed/job_app?for=datadog&validityToken=<ephemeral>&token=7683226
Databricks (with validityToken):
  https://job-boards.greenhouse.io/embed/job_app?for=databricks&validityToken=<ephemeral>&token=8335860002
```

Direct-fetch (no validityToken) also returns the form for several tenants — Greenhouse only enforces the token at submit-time on tenants that opted in. The browser path picks up the token automatically by reading the iframe `src` post-render, so we don't need per-tenant logic.
