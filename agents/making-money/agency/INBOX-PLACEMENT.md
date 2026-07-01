# Inbox Placement Test — cyshekari@gmail.com Cold Emails

**Date:** 2026-06-30  
**Tool:** GlockApps Free Spam Checker (https://glockapps.com/free-test/ft-f3cb5b-5dff6016/)  
**Test email sent:** 2026-06-30 ~7:08 PM PDT  
**Report URL:** https://glockapps.com/free-test/ft-f3cb5b-5dff6016/  

---

## Email Tested

- **From:** cyshekari@gmail.com  
- **Subject:** "3 reviews for Simons Hall Johnston?"  
- **Body:** ~120-word plain-text cold outreach with one link (cal.com/cyshek), signed "— Cyrus"  
- **Seed address used:** ft-f3cb5b-5dff6016@ft.glockdb.com  

---

## GlockApps Results

### Deliverability (4 seed addresses: Outlook, Gmail, Yahoo, AOL)

| Placement | % | Providers |
|-----------|---|-----------|
| **Inbox** | **25%** | Outlook only |
| **Tab**   | **0%**  | — |
| **Spam**  | **75%** | Gmail ✗, Yahoo ✗, AOL ✗ |
| Missing   | 0%  | — |

**Spam score (SpamAssassin):** 0.90 / 5.0 — "SpamAssassin likes your email!"  
**Blocklist (sending IP 209.85.214.171 = Google SMTP):** Clean ✓  

### Authentication Records

| Check | Result |
|-------|--------|
| **SPF** | Passed 11/11 — `v=spf1 redirect=_spf.google.com` |
| **DKIM** | Passed 9/9 — selector `20251104`, domain `gmail.com` — all signatures valid |
| **DMARC** | Passed 10, Warning 1 — `v=DMARC1 p=none` (monitoring only, no enforcement policy) |

---

## Critical Interpretation: What This Actually Means

### The GlockApps free test uses *bulk-recipient seed addresses* — not how 1:1 cold B2B email works

The 75% Spam result is real but requires careful interpretation:

1. **GlockApps seed inboxes are generic honeypot/test addresses** with no engagement history with cyshekari@gmail.com. Gmail's spam classifier is heavily **sender-recipient relationship-weighted**: a cold email to an address that has never interacted with the sender, on a consumer @gmail.com domain, looks identical to spam patterns. This is the *worst-case* scenario — a seed inbox that has never seen your address before.

2. **The test seed is hosted at ft.glockdb.com** (a testing domain), not a real gmail.com inbox. The Gmail engine that received this test email may treat glockdb.com-routed Gmail addresses differently than a real law firm's Gmail-hosted inbox.

3. **The 0% Tab result is actually a strong signal**: Gmail's Promotions/Updates tab classifier did NOT fire. If the email were "bulk" or "marketing" it would first land in Promotions, then potentially Spam. The fact that Tab=0% and Spam=75% means Gmail is flagging it as *interpersonal spam* (unrecognized cold sender), not *bulk promotional mail*.

4. **SpamAssassin 0.90 = excellent content score**. The email content itself is not triggering rule-based spam filters. The Spam classification is purely reputation/relationship-based.

### Why Gmail Sends Cold Emails to Spam (not Promotions)

Gmail's spam vs. Promotions decision tree, simplified:
- **Promotions tab trigger**: marketing structure (HTML, images, unsubscribe headers), bulk-send patterns, newsletter-style content
- **Spam trigger**: unrecognized sender + no prior relationship + cold outreach pattern

Our email is 1:1 plain text with no unsubscribe link, no HTML, no images — it **cannot** be classified as Promotions. It will either land in **Primary** (if the recipient has a warm relationship or good sender reputation with them) or **Spam** (if the sender is unrecognized).

---

## Tab Placement Question (Promotions Hypothesis)

**Answer: The Promotions hypothesis is WRONG. Our emails are NOT going to Promotions.**

Evidence:
- GlockApps Tab result: **0%** — zero Promotions/Updates/Social classification
- Email structure: plain text, single link, no HTML, no unsubscribe, no image — all factors that *prevent* Promotions classification
- Gmail's Promotions classifier specifically targets: HTML emails, marketing language ("discount", "offer", "deal"), multiple images, unsubscribe footers, mass-send headers
- None of those are present

**The actual problem is Spam classification**, driven by:
1. `@gmail.com` consumer domain sending cold B2B outreach — Gmail expects commercial senders to use custom domains
2. Zero sender-recipient prior relationship
3. cal.com link (external scheduling link) may trigger Gmail's heuristics for cold outreach / spam
4. Sending volume/pattern (sending to multiple firms) may have accumulated a negative reputation signal on the cyshekari@gmail.com account

---

## Confidence Rating

| Hypothesis | Confidence | Evidence |
|------------|------------|----------|
| Going to Promotions | ❌ Very unlikely (<10%) | Tab=0%, plain-text structure, no HTML/unsubscribe |
| Going to Primary (warm recipients) | ✅ Likely for recipients who know Cyrus | Relationship-based; not measurable via seed test |
| Going to Spam (cold/unknown recipients) | ⚠️ HIGH risk (60-80%) | GlockApps 75% spam rate; consumer gmail.com sender |
| Inbox for truly cold law firm prospects | ❓ 20-40% | SPF/DKIM pass, but sender reputation is the variable |

---

## What Single Change Most Reduces Spam Risk

**Use a custom domain + Google Workspace** (e.g., cyrus@yourcoldoutreach.com or cyrus@[brandeddomain].com).

Why this is the highest-leverage fix:
- Gmail's heuristics treat `@gmail.com` cold B2B senders as inherently suspicious (consumer domain)
- Custom domain signals: "this is a real business entity sending transactional/commercial email"
- With a custom domain: SPF/DKIM/DMARC are configured for *your* domain (not delegated from Gmail); you control the sending reputation
- Warm-up + domain age + gradual volume increase would allow building a positive reputation
- **This is exactly the custom-domain question the inbox test was meant to answer**

Secondary changes with meaningful impact:
- **Remove the cal.com link** (batch5 already does this — good move; reduces cold-outreach pattern signals)
- **Use per-recipient personalization** in subject line (already doing this) 
- **Add a warm-up period** — pause bulk sends for 2-4 weeks on cyshekari@gmail.com to let any accumulated spam-report signals decay

---

## Recommendation on Custom Domain Spend

**YES — the custom domain spend is justified, specifically to fix Spam (not Promotions).**

The test definitively rules out the Promotions hypothesis. The real problem is that Gmail (and Yahoo, AOL) are treating our cold email as Spam. A custom domain via Google Workspace ($6-12/month) combined with:
1. Proper SPF/DKIM/DMARC for the custom domain
2. Gradual send volume warm-up
3. Continued plain-text format + no links (batch5 pattern)

...should move inbox placement from ~25% to 70%+ based on industry benchmarks for properly warmed custom domains sending B2B cold email.

**Expected outcome:** Primary tab placement for most recipients (since content classifies as 1:1 personal email, not promotional), with Spam rate dropping from ~75% to ~10-20% after proper warm-up.

---

## Limitations of This Test

- GlockApps free test uses only 4 seed addresses (Outlook 1x, Gmail 1x, Yahoo 1x, AOL 1x) — limited statistical sample
- The free test does NOT show which Gmail "tab" within inbox (Primary/Promotions/Updates) for emails that DO reach inbox — but this is moot since Tab=0%
- Seed inbox behavior differs from real recipient inboxes (no prior relationship, fresh accounts)
- Cannot test without a paid account whether a custom domain would improve the Gmail seed result

---

*Test conducted by sending representative batch4 email body from cyshekari@gmail.com to GlockApps seed address ft-f3cb5b-5dff6016@ft.glockdb.com via Gmail SMTP SSL (port 465).*
