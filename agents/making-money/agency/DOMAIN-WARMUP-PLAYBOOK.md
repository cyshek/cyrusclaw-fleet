# DOMAIN + GOOGLE WORKSPACE WARM-UP PLAYBOOK
**Owner:** making-money (agency outreach) · **Drafted:** 2026-06-30 · **Status:** READY TO EXECUTE on approval

> **Why this exists:** GlockApps (2026-06-30) proved cold sends from `cyshekari@gmail.com` land
> **75% in SPAM** (Gmail/Yahoo/AOL all folder it), 25% inbox (Outlook only), 0% Promotions. The
> root cause is structural — a **consumer @gmail.com cold-emailing strangers = interpersonal-spam**
> classification that body tweaks cannot fix. The fix is a **custom domain on Google Workspace,
> authenticated and warmed**. This playbook is the exact path from "domain purchased" to "warm and
> inboxing" so that when Cyrus approves, we send within hours and reach healthy volume on schedule.

---

## TL;DR — the numbers

| Item | Value |
|---|---|
| Domain registration | **~$12–15/yr** (Cloudflare/Namecheap; .com) |
| Google Workspace Business Starter | **$7/user/mo** ($3.50/mo first 3 months promo; ~16% off on annual) — **1 user is enough** |
| **Total cost** | **~$7/mo + ~$14 one-time** (≈ **$98 year one**, or ~$56 year one with the 3-mo promo) |
| Time: purchase → authenticated + first send | **2–4 hours** (mostly DNS propagation wait) |
| Time: first send → healthy cold volume (30–40/day) | **~14–21 days** of warm-up |
| Time: → full target volume (treat ≤50/day as the ceiling per inbox anyway) | **~21–28 days** |
| Expected inbox lift | **~25% → 70%+** once warmed (industry benchmark for authenticated, warmed custom domains) |

**Bottom line:** Cyrus says yes at noon → domain authenticated and a first warm-up email sending by
late afternoon → the held **batch 5 (30 records)** can begin its real send inside the warm-up ramp,
and we're at full cold-outreach volume in ~3 weeks instead of blind-spamming the gmail.com sender today.

---

## CRITICAL DECISION: send from a SEPARATE domain, not Cyrus's primary

**Do NOT cold-email from a domain Cyrus uses (or will use) for anything he cares about.** Cold
outreach carries spam-complaint risk; if reputation tanks, it should never poison his real mail.

**Recommended setup:**
- **Buy a dedicated outreach domain** — a clean, business-credible .com (e.g. `getspeedtolead.com`,
  `replyspeed.io`, `[brand]hq.com`). Short, pronounceable, not obviously throwaway, no hyphens/numbers.
- Put the mailbox on it: `cyrus@<domain>` (a real human first name inboxes better than `hello@`/`team@`).
- **Optional but ideal (advanced):** send from a **subdomain** like `outreach.<domain>` or
  `mail.<domain>` so the root domain's reputation stays pristine for any future real use. For a
  single-domain single-mailbox start this is optional — root-domain sending is fine at our volume.
  Decision: **start root-domain** for simplicity; only split to a subdomain if we ever scale past
  one mailbox.

**The 3 candidate names to register (Cyrus picks one at purchase):**
1. `getspeedtolead.com` — describes the offer (speed-to-lead is our core pitch)
2. `replyspeed.io` — short, brandable, SaaS-flavored
3. `leadrescue.co` — benefit-oriented, memorable

*(Any available clean .com works. .com > .co > .io for cold-email trust. Avoid brand-new gTLDs like
.xyz/.online — they carry spam baggage.)*

---

## PHASE 1 — Purchase + provision (≈30 min of active work)

**Cyrus does (needs his card + login — these are the (a) credential / (b) money steps I can't do):**
1. **Register the domain** at Cloudflare Registrar (at-cost, ~$10–11/yr, free DNS, no upsell games)
   or Namecheap. *Cloudflare preferred* — cleanest DNS UI and we'll be adding TXT/CNAME records.
2. **Sign up for Google Workspace** Business Starter (1 user) at workspace.google.com → use the
   domain from step 1 → create the mailbox `cyrus@<domain>`. Pick a strong password.
3. **Hand me:** the domain name, confirmation Workspace is active, and either (a) DNS access so I can
   verify records, or (b) be available for ~10 min to paste the DNS records I generate.

**I do (the moment the domain + Workspace exist):**
4. Generate the **exact DNS records** to paste (verification TXT, MX, SPF, DKIM, DMARC) — see Phase 2.
5. Stage the warm-up schedule + repoint the batch-5 sender to the new `From:` address.

> **Why Cyrus must do 1–2 personally:** domain registration and the Workspace subscription are a
> money commitment + an account login/2FA only he can complete. Everything after (DNS values,
> authentication verification, warm-up automation, send scheduling) is mine.

---

## PHASE 2 — Authenticate the domain (the deliverability foundation)

All four records must be live **before any send**. Authentication is *non-negotiable* — it's what
separates "real business" from "spammer" in Gmail/Yahoo/Microsoft's 2024+ bulk-sender rules.

### 2a. Domain verification + MX (turns on the mailbox)
- Workspace gives a **TXT verification record** (or a CNAME) at signup — add it; click Verify.
- **MX records** (route mail to Google). Modern Workspace uses a single MX:
  ```
  Host: @    Type: MX    Priority: 1    Value: smtp.google.com.
  ```
  *(Older multi-record Google MX set also works if the console shows it; use whatever the Admin
  console's "Activate Gmail" step prints.)*

### 2b. SPF (authorize Google to send for the domain) — **confirmed current syntax**
```
Host: @    Type: TXT    Value: v=spf1 include:_spf.google.com ~all
```
*(Source: Google Admin SPF docs, fetched 2026-06-30. Exactly one SPF TXT record on the domain — never
two. `~all` = softfail, Google-recommended.)*

### 2c. DKIM (cryptographically sign every message) — **must be turned on manually**
- Admin console → **Apps → Google Workspace → Gmail → Authenticate email**.
- Generate a **2048-bit key** for the domain → Google prints a TXT record with host
  `google._domainkey` → add it to DNS → return to console → **Start authentication**.
- ⚠️ DKIM is **OFF by default** on new Workspace domains. Skipping this is the #1 silent
  deliverability killer. Verify it shows "Authenticating email" (green) before sending.

### 2d. DMARC (tells receivers what to do + gives us reporting) — **start at p=none, then ramp**
```
Host: _dmarc    Type: TXT
Value: v=DMARC1; p=none; rua=mailto:dmarc@<domain>; adkim=s; aspf=s; pct=100
```
- **Start `p=none`** (monitor-only) so nothing legit gets blocked while SPF/DKIM settle.
- After ~1 week of clean DKIM/SPF alignment in the `rua` reports → move to **`p=quarantine`**, then
  optionally `p=reject`. (Gmail/Yahoo bulk rules require *at least* `p=none` to exist; stricter is better.)
- `rua=mailto:dmarc@<domain>` lands aggregate reports in the same mailbox so I can monitor alignment.

### 2e. Verify everything before sending
I'll confirm with `dig` from the VM (these are read-only DNS lookups, run on approval):
```bash
dig +short TXT <domain>                 # expect the v=spf1 line
dig +short MX <domain>                   # expect smtp.google.com / google MX
dig +short TXT google._domainkey.<domain># expect the DKIM v=DKIM1 key
dig +short TXT _dmarc.<domain>           # expect v=DMARC1; p=none...
```
Then send ONE message through the new mailbox to a GlockApps seed → confirm SPF/DKIM/DMARC all
**pass** + check the new inbox %. **Do not start warm-up volume until this single test passes.**

> **DNS propagation note:** Cloudflare/Namecheap TXT+MX usually go live in **minutes to ~1 hour**
> (TTL 300–3600s). Worst case 24–48h, but at modern registrars sub-hour is typical. This is the
> only real "wait" in the whole process.

---

## PHASE 3 — Warm-up ramp (14–21 days to healthy)

A brand-new domain with zero sending history must **earn** reputation. Blasting 30 cold emails on
day 1 from a cold domain re-creates the spam problem on new infrastructure. The ramp:

### The mechanics that matter (more than the exact daily count)
1. **Engagement is the currency.** Early sends should generate **opens + replies** from real humans
   so Gmail learns "people want mail from this sender." Two ways to manufacture early engagement:
   - **Self/friendly seeding:** Cyrus emails 5–10 friends/colleagues from the new address asking them
     to **reply** (a reply is the strongest possible positive signal) and, if it's in spam, mark
     **"Not spam" + move to Primary**. ~3–5/day for the first 3–4 days. *(Cyrus's optional 5-min help.)*
   - **A warm-up service (recommended, ~$0–30/mo):** Mailwarm/Warmup Inbox/Instantly/TrulyInbox
     auto-exchange warm-up mail across a network of real inboxes (auto-open, auto-reply, auto-rescue
     from spam). Hands-off, and the single biggest accelerant. **Flag for Cyrus as an optional add-on
     — most cold-email tools (Instantly ~$30/mo) bundle warm-up + sending + inbox rotation.**
2. **Gradual volume increase.** Never more than ~roughly double per few days.
3. **Spread sends across the day**, not in a burst (the sender already spaces 6s; keep daily chunks
   small and ideally drip over hours).
4. **Keep the batch-5 format** that's already staged: plain text, **zero links** on first touch,
   real-name personalization, 90–104 words. That format is correct — it just needed a real domain.

### The ramp schedule (single mailbox)
| Days | Daily volume | What we send | Notes |
|---|---|---|---|
| **1–3** | 3–5 | warm-up/friendly seeds only (asking for replies) | NO cold prospects yet. Build first reputation. |
| **4–7** | 8–12 | warm-up + first **real cold** prospects from batch 5 | Start the held batch 5 here, in small daily chunks. |
| **8–14** | 15–25 | cold prospects (batch 5 → batch 4 re-touch) | Watch bounces + spam-complaint signals daily. |
| **15–21** | 25–40 | full cold cadence | Treat **~40–50/day as the steady ceiling** per single inbox. |
| **22+** | 40–50 (cap) | steady-state outreach + follow-up orchestrator | Add a 2nd mailbox/domain only if we need >50/day. |

**Healthy = ready for full volume when, after ~day 14–21:**
- A fresh GlockApps re-test shows **inbox ≥70% / spam ≤20%**, AND
- Real-prospect bounce rate stays **<3%**, AND
- DMARC `rua` reports show **100% SPF+DKIM alignment**, AND
- Zero spam-complaint spikes.

### Guardrails (auto-pause triggers)
- **Bounce rate >5%** in any day → pause, scrub list, investigate (we already validate addresses, so
  this should stay low — batch 5 pre-flight showed 0 malformed).
- **Spam complaints climb** (visible if we add Google Postmaster Tools — free, recommended: add the
  domain to postmaster.google.com for reputation dashboards) → pause + revert to warm-up-only for 3 days.
- Never exceed the day's scheduled ceiling even if tempted.

---

## PHASE 4 — Cut the held batches over to the new sender

Once the single GlockApps test passes (end of Phase 2) and we hit the day-4 ramp step:
1. **Repoint the sender:** change `From:` in the batch sender from `cyshekari@gmail.com` to
   `cyrus@<domain>`, and swap SMTP creds to the new Workspace mailbox (app password / OAuth).
   - Concretely: edit the SMTP block in `send_batch5.py` (and the follow-up orchestrator's send path)
     to the new host/user/app-password. One-line change set; I'll stage it pre-approval so it's ready.
2. **Begin batch 5** in the small daily chunks the ramp allows (not all 30 at once on day 4 — drip
   ~8–12/day rising with the ramp). The follow-up orchestrator (`516bf53f`) keeps doing touch-2/3.
3. **Keep cyshekari@gmail.com OUT of cold sending permanently.** Optionally use it only as a
   warm-up *recipient* or for genuinely warm 1:1 replies. Its reputation is already singed.
4. **Re-run GlockApps** at day ~14 to confirm the lift and decide on `p=quarantine` for DMARC.

---

## What I can do autonomously the instant the domain exists
- Generate + hand over every exact DNS record (verification, MX, SPF, DKIM, DMARC).
- `dig`-verify propagation + send the single authentication test to GlockApps.
- Repoint `send_batch5.py` + the follow-up orchestrator to the new `From:`/SMTP (staged now).
- Build + run the warm-up drip scheduler (daily small-chunk cron) and the day-14 re-test.
- Monitor bounces/alignment and ramp the schedule.

## What still needs Cyrus (and only Cyrus)
- **(money + login)** Register the domain + start the Workspace subscription + create the mailbox.
- **(optional, 5 min)** Send a handful of friendly warm-up seeds asking friends to reply, days 1–3.
- **(optional spend)** Approve a warm-up/sending tool (e.g. Instantly ~$30/mo) if we want the
  hands-off accelerant + inbox rotation. Not required — manual seeding + careful ramp also works.

---

## Risks / honest caveats
- **Warm-up can't be fully skipped.** Even a perfectly authenticated domain that blasts 30 cold
  emails on day 1 will get filtered. The 14–21 day ramp is the cost of doing this right; there's no
  legitimate same-day shortcut to healthy cold volume on brand-new infrastructure.
- **70%+ is a benchmark, not a guarantee.** Inbox rate depends on list quality, complaint rate, and
  ongoing engagement. Our lists are decent (validated, personalized); if recipients never engage,
  reputation plateaus. Replies are the lever.
- **One mailbox caps ~40–50 cold/day.** To scale outreach materially we'd add mailboxes/domains
  (each ~$7/mo). That's a later decision once we prove the first domain converts.
- **A warm-up tool is the single biggest accelerant** and de-risks the ramp, but it's an added
  ~$30/mo — staged as optional, Cyrus's call.
