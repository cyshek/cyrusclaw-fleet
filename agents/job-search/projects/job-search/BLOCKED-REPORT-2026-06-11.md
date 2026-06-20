# BLOCKED-SECTION AUDIT — 2026-06-11

_Refresh/correction of `BLOCKED-REPORT-2026-06-10.md`. PROBE+AUDIT only — no live submits. Re-derived every bucket from EVIDENCE (disk STATUS.md + db `response_status` + sampled dryrun/HTTP), per the "block_reason strings lie" rule._

---

## HEADLINE NUMBERS

| Metric | Count |
|---|---|
| `status='blocked'` (after corrections) | **94** (was 98) |
| `prep_status='manual_ready'`, unapplied | 29 |
| `status='manual-apply'` | 146 |
| Phantom-blocked recovered this run | **4** (944, 946, 947, 1237) |
| Genuinely auto-appliable NOW (new) | **0** |

---

## ✅ PHANTOM-BLOCKED — RECOVERED (4 rows, corrected in DB)

`tracker.db.bak` taken before the write.

| id | company | role | evidence |
|---|---|---|---|
| 944 | Baseten | Solution Architect (AI/LLM Inference) | disk `STATUS: SUBMITTED (residential)` + `FormSubmitSuccess token` (2026-06-08) AND db `response_status=submitted-residential` |
| 946 | Baseten | AI Solutions Engineer | same |
| 947 | Baseten | Solution Architect | same |
| 1237 | Mercor | Research Program Manager | same |

**Root cause of the mislabel:** these were submitted in the **2026-06-08 residential-egress drain** (`FormSubmitSuccess` confirmed, `response_status` stamped), but the OLD `status='blocked'` / `block_reason='ashby-score-gate-warmed-profile-required'` from the failed pre-drain attempt was never cleared. Both disk and the `response_status` column agreed they were applied; only `status`/`applied_by` lagged. **Corrected → `status='applied', applied_by='auto', applied_on='2026-06-08'`** with an audit note appended to `agent_notes`.

> **Pipeline note for parent:** the residential-drain submitter writes `STATUS.md` + sets `response_status='submitted-residential'` but did NOT flip `status`/`applied_by`. That's a recurring mislabel SOURCE — any future residential-drain run will re-strand its wins the same way. The drain submit path should set `status='applied', applied_by='auto'` on a `FormSubmitSuccess`, same as the standard submit-bookkeeping step. Flagged, not fixed here.

---

## 🟢 GENUINELY AUTO-APPLIABLE NOW: none

Beyond the 4 phantoms, **every remaining blocked row is a real wall** — verified by sampling. There is no "prepped-READY mislabeled as blocked" cohort left and no shipped-fix-already-covers-it row sitting un-retried. (The shipped GH `needs_review`/education/location and Ashby `final_clobber_guard` fixes have already been consumed by earlier workers; what remains are walls those fixes don't touch.)

---

## 🔵 BLOCKER FAMILIES (the 94 blocked, plain English)

| Family | Count | Why it's stuck | Lever |
|---|---|---|---|
| **OpenAI 180-day app limit** | 33 | OpenAI Ashby board enforces a 180-day per-applicant cap; Cyrus hit it. Policy, not tech. | **TIME** — re-attemptable ~late Nov 2026 |
| **Lever / iCIMS hCaptcha-Enterprise** | 18 | CapSolver does NOT support hCaptcha on our account (VERIFIED); Lever uses hCaptcha-Enterprise rqdata, not token-defeatable. | **CREDENTIAL** — needs an hCaptcha-capable vendor (e.g. 2Captcha/NopeCHA hCaptcha-Enterprise tier) |
| **Netflix Eightfold resume-wall** | 12 | `explore.jobs.netflix.net` Eightfold form fills clean but resume is HARD-required and its Filestack/react-dropzone rejects `set_input_files` + file_chooser + synthetic-drop (files stays 0). Plus invisible reCAPTCHA-v3. | **CODE** (Filestack-API upload, ~3hr build) — proxy only helps the reCAPTCHA layer, not the upload |
| **LinkedIn-class** | 8 (blocked) | LinkedIn is the apply host or off-site URL unresolved from this datacenter IP; li_at burns on the shared Webshare IP. | **PROXY + CREDENTIAL** (see proxy section — mostly dead even with proxy) |
| **DataDome / Akamai IP-bound** | 7 | SmartRecruiters one-click (NYC cohort `cityjobs.nyc.gov`) + Ashby/Lever rows where the challenge is bound to THIS Azure datacenter IP; a token from another IP won't validate. | **PROXY** — cleanest pure-proxy win |
| **Ashby HARD score-gate** | 4 | Tavus 891, Deepgram 970/971, OpenAI 2549. Submit POST returns `RECAPTCHA_SCORE_BELOW_THRESHOLD` even through VERIFIED residential egress AND a warmed persistent profile (both DISPROVEN, 2026-06-09/10). Form fills clean; the wall is reCAPTCHA-v3 trust requiring profile AGE + a real logged-in Google account. | **CREDENTIAL** (a real aged Google login = a Cyrus credential) — NOT engine, NOT residential proxy |
| **`need-runner-*` ATS builds** | 4 | Paylocity (1254), Jobvite (1290), Oracle/custom (2033 Morgan Stanley), SuccessFactors (2280 A.O.Smith) — each needs a per-ATS upload/account runner not yet built. | **CODE** (multi-hour per ATS) |
| **Workday WE-persist-across-nav** | 2 | Boeing 2546, PayPal 2891. Filled work-experience block is empty again on the Next-nav revisit (values don't persist across navigation) → EXIT-5 loop. | **CODE** (per-field blur+verify-persisted, or React-store write; multi-hour) |
| **iCIMS misc** | 3 | AMD 1478 (internal SSO portal), Joby 2351 (hCaptcha no vendor), RealPage 2479 (req unresolved). | mixed CREDENTIAL/CODE |
| **gh-embed Stripe hosted flow** | 1 | Stripe 2612 — custom Stripe-hosted flow off the standard GH embed; re-run on current engine still uncertain, no `/confirmation`. | **CODE** |
| **Closed / expired** (legit) | 2 | Synectics 2547 (HTTP 500, dead), Quuppa 2123 (LinkedIn-only, SE role gone from lever). | none — genuinely closed |
| **Senior, out-of-scope** (legit) | 1 | Snowflake 2527 = "Senior Technical Program Manager" → senior-title gate. | none — correct skip |

**Settled-unwinnable share:** OpenAI(33) + hCaptcha(18+3) + Ashby-HARD(4) + closed/senior(3) = **~61 of 94** are walls we've already PROVEN (DEBUNKED ledger) we cannot crack with code/engine alone. The rest are CODE builds (Filestack 12, need-runner 4, Workday 2, Stripe 1 = 19) or PROXY (7 + LinkedIn).

---

## 🌐 PROXY PRICE-OUT (spans Cyrus's Request 1)

**Question:** how many rows would a dedicated non-shared residential/mobile proxy plausibly unlock?

Honest breakdown — a proxy alone is NOT the silver bullet the row counts suggest:

| Cohort | Rows | Does a residential/mobile proxy unlock it? |
|---|---|---|
| DataDome/Akamai IP-bound | **7** | **YES** — these are purely IP-reputation walls. Clean win. |
| Netflix Eightfold | 12 | **PARTIAL** — fixes the invisible reCAPTCHA layer, but the Filestack upload still needs a code build. Proxy alone ≠ submit. |
| LinkedIn `no-external-apply` | 60 | **NO** — LinkedIn IS the apply host (on-platform Easy Apply); no off-site form exists to automate even with a perfect IP. |
| LinkedIn `stranded/auth` | 24 | **MAYBE** — proxy + a fresh `li_at` cookie MIGHT resolve the off-site ATS URL, but each then needs its underlying ATS to be automatable. Optimistically a fraction land. |
| Ashby HARD-score | 4 | **NO** — residential egress already DISPROVEN (still `SCORE_BELOW_THRESHOLD`); needs an aged real-Google-login profile, not an IP. |

**Realistic proxy unlock:** **~7 clean wins immediately** (DataDome/Akamai), **+ up to ~12 more** if paired with the Filestack build (Netflix) and **a speculative slice of the 24 LinkedIn-stranded** if also paired with a Cyrus `li_at`. So: **7 guaranteed, ~15–30 plausible with proxy+code+li_at combined.** The headline "86 LinkedIn rows" is misleading — 60 of those are dead regardless of IP.

**Vendor/cost rec (for Cyrus's spend call — NOT purchased):**
- **Mobile/residential rotating IP** — e.g. a small residential plan (Webshare residential, Bright Data, or IPRoyal) at roughly **~$15–50/mo** for a few GB, OR a single dedicated **mobile (4G/5G) proxy ~$30–90/mo** (mobile IPs carry the highest reCAPTCHA-v3 trust and best DataDome pass-rate).
- **Best ROI framing:** a proxy's *guaranteed* return here is small (~7 rows). Its real value is **enabling the LinkedIn off-site resolver** (the long-promised highest-leverage unblock) — but ONLY in combination with a `li_at` cookie from Cyrus, and even then the upside is the ~24 stranded rows minus whatever ATSes are themselves blocked. **I would NOT buy a proxy purely for the 94-row blocked tab; buy it if/when Cyrus also provides `li_at`** so the proxy+cookie pair can be validated against the full ~500-row LinkedIn-stranded spreadsheet cohort (Request 1 territory), not just these 24.

---

## 📌 ANSWER TO CYRUS (2 paragraphs)

**What we recovered:** I re-derived every blocked row from disk + DB evidence (not the lying `block_reason` labels) and found **4 rows that were actually already submitted** — Baseten ×3 (944/946/947) and Mercor (1237) — landed in the June 8 residential-egress drain with confirmed `FormSubmitSuccess`, but their stale "ashby-score blocked" tag was never cleared. I corrected those to **applied** (backup taken first). That drops the real blocked count from 98 to **94**. Beyond those phantoms, there is **no other low-hanging fruit** — no prepped-but-mislabeled rows, nothing the already-shipped GH/Ashby fixes would now land. I also caught a recurring pipeline bug: the residential-drain submitter writes the success file but forgets to flip `status`/`applied_by`, so it will keep stranding its own wins — worth a one-line fix in that submit path.

**What's left and why:** the 94 break into three honest groups. **~61 are settled-unwinnable by code** — OpenAI's 180-day cooldown (33, frees up ~late Nov), Lever/iCIMS hCaptcha-Enterprise (21, no vendor supports it on our account), the Ashby HARD-score four (residential AND warmed-profile both already disproven — these need a real aged Google login, i.e. you), and a few genuinely-closed/too-senior reqs. **~19 are multi-hour code builds** we've deliberately parked (Netflix's 12 Filestack-upload rows, 4 niche-ATS runners, 2 Workday work-history-persistence rows, Stripe's custom flow). **The remaining handful is proxy territory.** The single spend that unlocks the biggest chunk is a **residential/mobile proxy (~$15–90/mo)** — but candidly its *guaranteed* yield on this tab is only ~7 DataDome/Akamai rows; its real payoff is unlocking the **LinkedIn off-site resolver**, and that only works if you also hand me a fresh `li_at` cookie. So my recommendation: hold the proxy purchase until you're ready to also provide `li_at`, then buy both together so we can attack the full ~500-row LinkedIn cohort, not just these few. Everything else is correctly blocked.
