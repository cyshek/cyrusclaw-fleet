# Email Deliverability / Inbox Placement Diagnostic

**Date:** 2026-06-30  
**Tool:** mail-tester.com  
**Test address:** test-8kilyl428@srv1.mail-tester.com  
**Result URL:** https://mail-tester.com/test-8kilyl428  
**From:** cyshekari@gmail.com  
**Subject tested:** "3 reviews for Simons Hall Johnston?"  
**Body:** Representative cold email from batch4_payload.json (first record)

---

## Score: 10 / 10 ✅ "Wow! Perfect, you can send"

---

## Flagged Issues (verbatim from mail-tester)

### ✅ SpamAssassin likes you
- No SpamAssassin rules triggered. Score: clean.

### ✅ You're properly authenticated
- SPF: pass (Gmail's infrastructure handles this automatically)
- DKIM: pass (Gmail signs outbound mail)
- Note: "Check DMARC policy state" link shown — DMARC for gmail.com is maintained by Google; no personal action needed.

### ⚠️ Your message could be improved (orange — advisory only, did NOT reduce score)
- **"There is no html version of your message."** — Plain-text only email. This is advisory; plain-text cold emails are often *better* for deliverability.
- **"You have no images in your message."** ✅ — Good for cold email; images trigger promotional classification.
- **"Your content is safe."** ✅ — No spam-flagged keywords.
- **"We checked if you used a URL shortener system."** ✅ — No URL shorteners used (cal.com direct link is fine).
- **"Your message does not contain a List-Unsubscribe header."** ⚠️ (amber) — Advisory for bulk/newsletter senders. Cold 1:1 email does NOT require this header; absence is expected and acceptable.

### ✅ You're not blocklisted
- Gmail's sending IP is not on any major blocklist.

---

## Interpretation

**• Deliverability is NOT the cause of 0 replies — the email is technically perfect.**  
  Authentication (SPF/DKIM), reputation, content, and blacklist checks all pass with a perfect 10/10. There is no spam-scoring problem. These emails are not landing in spam due to technical issues. Gmail's infrastructure handles everything correctly.

**• The 0-reply problem is almost certainly Gmail's Promotions tab or prospect-side behavior, not spam foldering.**  
  mail-tester.com only tests spam-filter compatibility (SpamAssassin/technical checks). It does NOT test whether Gmail's machine-learning classifier routes email to "Promotions" vs "Primary." Cold outreach from a free @gmail.com account with a booking link (cal.com) is a classic pattern that Gmail classifies as Promotions — recipients may never see it in their Primary inbox even though it's not in spam.

**• Top 2 fixes to pursue:**
  1. **Send from a custom domain (e.g. cyrus@[yourdomain].com via Google Workspace or similar).**  
     Gmail-to-Gmail emails, especially cold outreach, are heavily Promotions-tab-classified by Google's ML. A custom domain + properly configured DKIM/SPF/DMARC signals "business email" rather than "promotional blast from a free Gmail." This is the highest-leverage single change.
  2. **Use an inbox-placement test (not just spam-score test) to confirm Promotions vs Primary routing.**  
     Tools like GlockApps, Litmus, or the "Run inbox placement test" button on the mail-tester result page (links to easydmarc.com) test actual Gmail Primary vs Promotions placement. That will confirm/deny the Promotions hypothesis before spending money on a domain.

---

## Raw Result URL
https://mail-tester.com/test-8kilyl428

(Result expires in ~7 days per mail-tester standard policy.)
