# Company public-listings resolver (pattern doc)

When LinkedIn-only discovery surfaces a role (`source_key='linkedin:<jid>'`, no off-site ATS URL), the canonical apply URL still exists — we just have to find it. This is the pattern.

## When this happens

- **Anthropic** — promotes many roles directly through LinkedIn ads without a `boards.greenhouse.io` link on the post. Anthropic's careers site (`anthropic.com/jobs`) is the source of truth.
- **OpenAI** — same; LinkedIn-promoted roles often don't link out to Greenhouse from the post body.
- **Stripe** — LinkedIn posts link to `linkedin.com/jobs/view/...-stripe-<linkedin-jid>` only. Stripe's own listings live at `stripe.com/jobs/listing/...`, backed by a Greenhouse board.
- **Netflix** — Workday rebrand; LinkedIn posts often hide the Workday URL.
- **OpenAI / Anthropic / Stripe LinkedIn-only roles** also disproportionately appear with title-only signals in the LinkedIn feed, no location string, making naive title-matching tricky.

## The investigation pattern (run this for any new "LinkedIn-only" company)

1. **Find the public careers index.** Visit `<company>.com/jobs`, `/careers`, `/about/jobs`. Note the URL pattern of an individual listing.
2. **Identify the ATS.** View page source of an individual listing apply page. Look for:
   - `boards.greenhouse.io` / `job-boards.greenhouse.io` / `data-ghid=<id>` → Greenhouse
   - `jobs.lever.co/<slug>` / `data-lever-id` → Lever
   - `jobs.ashbyhq.com/<slug>` → Ashby
   - `myworkdayjobs.com/<tenant>` → Workday
   - `eightfold.ai`, `icims.com`, `taleo.net`, `smartrecruiters.com` → other ATSes
3. **Check for a public board JSON endpoint** — most ATSes expose one:
   - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` (no auth, returns all jobs with id, title, location, absolute_url; individual JD at `.../jobs/<id>`)
   - Lever: `https://api.lever.co/v0/postings/<slug>?mode=json` (returns all postings)
   - Ashby: `https://api.ashbyhq.com/posting-api/job-board/<slug>` (POST with empty body; returns all jobs)
   - Workday: `https://<host>/wday/cxs/<tenant>/<site>/jobs` (POST with search criteria; returns paged)
4. **Map ATS ids ↔ tracker rows.** Title is the strongest signal; location is the tie-breaker for multi-city listings. Watch for:
   - One ATS role posted to multiple LinkedIn JIDs (Stripe pattern — same role, different city → multiple LinkedIn JIDs). De-dupe the work.
   - Senior/staff/principal variants — title-substring match will collide. Use exact-normalized-title match plus title-similarity floor (~0.78).
5. **Bookkeep idempotently.** Backup tracker.db first. Update only URL columns (`jd_url`, `app_url`). Preserve the original LinkedIn URL in `agent_notes` so we can audit. Don't touch status/applied_by.
6. **Probe captcha behavior.** Before queueing submits, run a lightweight `probe_<company>_wrapper.py` (or the universal `captcha_probe.py`) to confirm whether the company's careers page wrapper provides a `validityToken`-bearing iframe (Databricks-style) or just thin chrome (Stripe-style). This dictates which runner to use.

## Per-company status

### ✅ Stripe — RESOLVED 2026-05-24

- **ATS:** Greenhouse, board slug `stripe`, ~500 active jobs.
- **Board JSON:** `https://boards-api.greenhouse.io/v1/boards/stripe/jobs` (no auth).
- **ID mapping:** Stripe surfaces the GH JID as `data-ghid="<id>"`, `?gh_jid=<id>`, and as the trailing number in `/jobs/listing/<slug>/<id>`. **Stripe ID == GH JID.**
- **Slug derivation:** title → lowercase → `&`→`and` → non-alnum→`-` → strip→trim. Matches Stripe's URLs.
- **Apply URL pattern:** `https://stripe.com/jobs/listing/<slug>/<gh_jid>/apply` (the only URL that mounts the GH iframe).
- **Captcha:** wrapper iframe src is the bare embed URL — **NO `validityToken`**. Submitting from the Stripe wrapper has no advantage over direct GH embed. **Needs reCAPTCHA Enterprise solver** to actually submit.
- **Resolver:** `role-discovery/stripe_public_listings.py`
- **Cache:** `applications/dryrun/_stripe-public-listings.json`

### 🟡 Anthropic — TODO

- **ATS:** Greenhouse (confirmed prior).
- **Board JSON:** `https://boards-api.greenhouse.io/v1/boards/anthropic/jobs` (untested).
- **Apply URL pattern:** Likely `anthropic.com/jobs/<gh_jid>` or `anthropic.com/jobs/listing/...`. Verify and parameterise.
- **TODO:** spawn the same resolver for the 10+ open Anthropic LinkedIn-only rows.

### 🟡 OpenAI — TODO

- **ATS:** OpenAI uses Ashby (`jobs.ashbyhq.com/openai`) plus an internal portal.
- **Board JSON:** `https://api.ashbyhq.com/posting-api/job-board/openai` (verify; Ashby allows public boards by default).
- **Apply URL pattern:** `openai.com/careers/<slug>` redirects to `jobs.ashbyhq.com/openai/<uuid>`. Tracker needs the uuid.
- **TODO:** confirm Ashby endpoint, write resolver, beware Ashby captcha (separate budget question — see CAPTCHA-SOLVER-DECISION.md).

### 🟡 Netflix — TODO

- **ATS:** Workday (`netflix.wd1.myworkdayjobs.com` or similar).
- **Board JSON:** `https://<host>/wday/cxs/<tenant>/<site>/jobs` (POST search). Cached `workday_dryrun.py` already does this.
- **Apply URL pattern:** Workday URL is the canonical link. LinkedIn typically doesn't leak it.
- **TODO:** write Netflix-specific tenant lookup (probe a known role's URL to learn the tenant) and resolver. Workday full-auto already works for several tenants — leverage that.

### 🟡 Databricks — partially-covered

- Already in the iframe-runner `companies.yaml` for the wrapper-URL workaround (validated 2026-05-24).
- **Open question:** how does LinkedIn-source discovery currently surface Databricks roles? Quick check needed to ensure resolver isn't needed.

### Other candidates to investigate

- **Apple** — careers site is custom; LinkedIn-only entries common. Internal portal needs login (effectively blocked).
- **Tesla** — Workday but with custom auth/captcha layer. Confirm tenant.
- **Coinbase** — Greenhouse (board slug `coinbase`). Should be easy.
- **Shopify** — Lever (`jobs.lever.co/shopify`).
- **Cloudflare** — Greenhouse (board slug `cloudflare`).
- **GitLab** — Greenhouse (board slug `gitlab`).

## Reusable bits

The Stripe resolver (`stripe_public_listings.py`) is the reference impl. Pieces that generalise:
- `fetch_*_listings()` — single GET to the ATS public board, cache to JSON
- `derive_slug(title)` — lowercase / replace `&` / non-alnum→`-`
- `title_similarity()` + `loc_overlap()` — fuzzy matcher with location tie-break
- `apply_matches()` — idempotent tracker mutation with auto-backup
- Promotion rule: single match if top candidate's normalized title exactly equals the row's normalized title (`title_score >= 0.999`).

For non-Greenhouse ATSes you only need to swap:
1. The fetch URL.
2. The shape of the per-job dict (key for id, title, location).
3. The apply-URL template (some companies have predictable wrappers, others go straight to the ATS).

## Generalisation TODOs

- [ ] Anthropic resolver — same Greenhouse pattern, swap board slug.
- [ ] OpenAI resolver — Ashby pattern (different ATS, different endpoint shape).
- [ ] Netflix resolver — Workday pattern (POST, paginated).
- [ ] Audit which other companies in `companies.yaml` have LinkedIn-only sourced rows in the tracker — those are the next candidates.
- [ ] Once 2-3 ATSes are covered, extract the shared bits into a `public_board_resolver.py` library so each new company is a 30-line config file, not a 250-line script.
