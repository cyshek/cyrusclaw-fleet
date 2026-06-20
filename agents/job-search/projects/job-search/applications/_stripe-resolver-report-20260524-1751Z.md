# Stripe public-listings resolver — report

**Stamp:** 20260524-1751Z
**Subagent:** isolated, ~45min phase-1 + ~30min phase-2, **Phase 3 intentionally skipped (see decision below)**
**Tracker rows touched:** 8 of 10 open Stripe rows (URLs upgraded from LinkedIn → Stripe canonical).

## Headline findings

1. **Stripe has a fully public Greenhouse board.** `https://boards-api.greenhouse.io/v1/boards/stripe/jobs` returns 496 active roles (as of fetch). No auth, no scraping. The GH `id` field is the same number Stripe surfaces as `data-ghid` / `?gh_jid=` in its own URLs. **We never needed to scrape `stripe.com/jobs/search`** — the GH API is the canonical source of truth.
2. **Stripe's `stripe.com/jobs/listing/<slug>/<gh_jid>/apply` wrapper does NOT carry a `validityToken`.** The iframe src it ships is the bare `https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=<id>` — byte-for-byte identical to the URL we'd hit directly. Unlike Databricks, **Stripe's wrapper offers no fresh-context advantage** for the reCAPTCHA Enterprise gate. (Probed via Playwright on gh_jid 7176530 and 7607761; both confirmed.)
3. **Initial-render state on the form is clean** for both wrapper and direct embed: no `.grecaptcha-error`, no recaptcha/hcaptcha iframes, submit button enabled. The captcha gate has historically fired only on submit-click — that hasn't changed.

## Matches (8/10 resolved cleanly)

| Tracker id | LinkedIn title (loc) | → Stripe role (loc) | gh_jid | Apply URL |
|---|---|---|---|---|
| 1019 | Product Manager, Startup Products (SF) | Product Manager, Startup Products (NYC/Chi/SEA/SF) | 7901987 | https://stripe.com/jobs/listing/product-manager-startup-products/7901987/apply |
| 1049 | Product Manager, Payments (SEA) | Product Manager, Payments (SF/NY/SEA/Remote-US) | 7176530 | https://stripe.com/jobs/listing/product-manager-payments/7176530/apply |
| 1055 | Product Manager, Commerce Systems (SEA) | Product Manager, Commerce Systems (SF/SEA/NYC/US-Remote) | 7561551 | https://stripe.com/jobs/listing/product-manager-commerce-systems/7561551/apply |
| 1171 | Partner Solutions Architect - AWS (NY) | Partner Solutions Architect - AWS (NY) | 7607761 | https://stripe.com/jobs/listing/partner-solutions-architect-aws/7607761/apply |
| 1175 | Specialist Solutions Architect, Payments (SF) | Specialist Solutions Architect, Payments (NY/SF/Chi) | 7377591 | https://stripe.com/jobs/listing/specialist-solutions-architect-payments/7377591/apply |
| 1177 | Solutions Architect, Enterprise (Pre-sales) (SF) | Solutions Architect, Enterprise (Pre-sales) (Chi/NYC/US-Remote) | 7827184 | https://stripe.com/jobs/listing/solutions-architect-enterprise-pre-sales/7827184/apply |
| 1180 | Specialist Solutions Architect, Money Management (SF) | Specialist Solutions Architect, Money Management (NY/SF/Remote) | 7380371 | https://stripe.com/jobs/listing/specialist-solutions-architect-money-management/7380371/apply |
| 1249 | Product Manager, Startup Products (SEA) | (same as 1019: Stripe posts once across cities) | 7901987 | https://stripe.com/jobs/listing/product-manager-startup-products/7901987/apply |

**Two LinkedIn rows map to the SAME Stripe role** (1019 and 1249 → gh_jid 7901987). This is expected — Stripe posts a single multi-city role; LinkedIn duplicates by city. Both updated; submitting one closes both.

## Unmatched (2/10)

| Tracker id | LinkedIn title (loc) | Why |
|---|---|---|
| 1080 | Technical Program Manager, Payments Experiences (SF) | No matching role on Stripe's GH board today. Closest hits: "Engineering Manager, LATAM Payments Experiences", "Global Payments Experiences Engineering Manager" (both EM, not TPM). Either delisted or rebranded since LinkedIn scrape. |
| 1263 | Technical Program Manager, Payments Experiences (SEA) | Same as 1080 — same LinkedIn-side title, just a different LinkedIn JID for the SEA office. Same resolution. |

**Recommendation:** flip both to `status='closed'` with flag `not-on-stripe-board` since the role no longer exists. Not done here — left to Cyrus / next sweep.

## Tracker mutations

- Backed up to `tracker.db.bak.20260524-stripe-resolver` (946,176 bytes).
- For the 8 resolved rows: updated `jd_url` → listing-detail URL, `app_url` → apply URL. Preserved the LinkedIn URL in `agent_notes` as `linkedin_url_pre_stripe_resolver=<url>` (idempotent — only appended if not already present).
- **Did NOT touch:** `status`, `applied_by`, `applied_on`, `prep_status`, `flags`. Only the two URL columns.

## Captcha probe (Phase 2)

Probed gh_jid 7176530 (PM Payments) and 7607761 (Partner SA AWS) on both URL shapes:

| Shape | URL | iframe src | `validityToken`? | initial `.grecaptcha-error`? | submit button | Result |
|---|---|---|---|---|---|---|
| Stripe wrapper | `stripe.com/jobs/listing/<slug>/<jid>/apply` | `job-boards.greenhouse.io/embed/job_app?for=stripe&token=<jid>` | **NO** | (frame detach race; not testable) | n/a | Iframe src is bare |
| Direct embed | `job-boards.greenhouse.io/embed/job_app?for=stripe&token=<jid>` | (self) | n/a | **NO** | enabled | Form loads cleanly |

Compare to Databricks (validated 2026-05-24 per BACKLOG.md): wrapper iframe carried `validityToken=...`, which let post-submit reCAPTCHA Enterprise pass. **Stripe does not do this** — Stripe's wrapper is just a thin chrome over the direct embed, so it gains nothing.

Probe artifacts:
- `/tmp/stripe_probe_7176530.json` (PM Payments)
- `/tmp/stripe_probe_7607761.json` (Partner SA AWS)
- New script: `role-discovery/probe_stripe_wrapper.py` (lightweight, no-packet captcha-presence probe)

## Phase 3 (submit attempts) — INTENTIONALLY SKIPPED

**Decision:** spend zero LLM credits on Stripe submits in this run.

**Reasoning:**
1. The brief framed Phase 3 around "wrapper-URL workaround validated on Databricks. Stripe may benefit if it carries a fresh-context iframe with a server-issued validityToken. **Unverified — your job to test.**" → Phase 2 verified: **Stripe wrapper does NOT carry validityToken**, so the workaround does not apply.
2. The historical failure mode is well-documented across 4+ prior attempts (role 877 2026-05-22, role 1019 2026-05-23, plus the 2026-05-16 batch — all in MEMORY.md and BACKLOG.md "Stripe / Greenhouse-iframe v2"): post-submit `.grecaptcha-error` AND the Formik "LinkedIn Profile required" sticky-validation issue. Neither has a fix without reCAPTCHA Enterprise solver budget.
3. Each Stripe submit attempt costs ~$0.50 (LLM resume tailoring + cover-answer generation) before we even hit the submit failure. Burning $1.50 to re-confirm a documented failure mode is wasteful when budget approval for the solver would unblock all 7 unique Stripe roles at once.
4. The brief itself authorised stopping early: *"On any major uncertainty: write to ESCALATE-STRIPE.md, skip to the next phase, do not block."* This is not uncertainty so much as "experiment design says we'd be confirming a known result at a cost".

**What unblocks Stripe submits:**
- Cyrus approves a paid solver subscription that supports reCAPTCHA Enterprise (CapSolver: ~$0.005/solve; NopeCHA: ~$25/mo Pro plan). See `CAPTCHA-SOLVER-DECISION.md`. Once funded, all 7 unique Stripe roles + Datadog + Scale AI become submittable simultaneously.
- AND a separate fix for the Formik LinkedIn-required gate (separate from captcha — see MEMORY.md 2026-05-22 entry; fiber-walk diagnosis was correct).

**Prep artifacts left for Cyrus / future me:** the 8 resolved rows are now ready for `inline_submit.py --role-id <id>` once the captcha solver is funded. The pipeline auto-detects iframe-Greenhouse from the URL pattern and routes through `greenhouse_iframe_runner.py`.

## Deliverables checklist

- [x] `role-discovery/stripe_public_listings.py` — resolver (NEW)
- [x] `role-discovery/probe_stripe_wrapper.py` — captcha-presence probe (NEW, lightweight, no-packet)
- [x] `applications/dryrun/_stripe-public-listings.json` — 496-listing cache (NEW, idempotent)
- [x] `tracker.db.bak.20260524-stripe-resolver` — backup
- [x] 8 tracker rows: jd_url + app_url updated, LinkedIn URL preserved in agent_notes
- [x] This report: `applications/_stripe-resolver-report-20260524-1751Z.md`
- [x] `projects/job-search/COMPANY-PUBLIC-LISTINGS-RESOLVER.md` — generalised pattern (NEW)
- [x] `BACKLOG.md` updated — Stripe P0 status revised
- [x] `MEMORY.md` updated — 2026-05-24 entry

## Generalisation pointer

The Stripe technique generalises: **before scraping a careers HTML page, check whether the company has a public Greenhouse/Lever/Ashby/etc. board JSON endpoint.** Most enterprise career sites are just branded chrome over an ATS that exposes a stable public API. See `COMPANY-PUBLIC-LISTINGS-RESOLVER.md`.
