# Deliverability Report — Agency Cold Outreach (batches 1–4 + follow-ups)
**Date:** 2026-07-01 (~20:30 PT) · **Analyst:** making-money follow-up hardening pass
**Scope:** All cold sends batch1–batch4 (touch-1) + follow-ups (b1/b2 touch-2). Sender: cyshekari@gmail.com

---

## Headline numbers

| Metric | Value |
|---|---|
| Total UNIQUE recipients sent (batches 1–4) | **89** |
| Unique HARD bounces (address/domain doesn't exist or rejected) | **9** |
| POLICY / spam / blocklist rejections | **0** |
| **True hard-bounce rate** | **9 / 89 = 10.1%** |
| SMTP-time send failures (outbound rejected by Gmail) | **0 / 89** |
| Reputation verdict | **CLEAN — no degradation signal** |

> Per-batch recipient counts: batch1=15, batch2=27, batch3=2, batch4=45 → 89 unique.

---

## The 9 hard bounces (address | reason | batch)

All are recipient-side "this mailbox/address does not exist / rejected" — i.e. **bad list data**, not reputation problems.

| # | Address | Reason (class) | Batch |
|---|---|---|---|
| 1 | angela@pashallplus.com | address doesn't exist | batch4 |
| 2 | impallari@gmail.com | address doesn't exist | batch4 |
| 3 | info@advancedroofingtechnologies.com | address/domain doesn't exist | batch4 |
| 4 | info@chasenw.com | address doesn't exist | batch4 |
| 5 | info@highroadroofing.com | address doesn't exist | batch4 |
| 6 | jthroop@friedmanthroop.com | address doesn't exist | batch4 |
| 7 | info@allantelife.com | delivery failure (address not found) | batch2 |
| 8 | info@cwmalawfirm.com | delivery failure (address not found) | batch2 |
| 9 | info@jcooney.com | "address rejected / couldn't be found" | batch2 |

Split: **6 from batch4, 3 from batch2.** (batch1 and batch3 = zero bounces.)

**Live-scan note:** the fast IMAP scan re-confirms 3 of the 9 right now (allante, cwma, jcooney — still in the recent window). The other 6 (batch4, DSNs dated 06-30) have since been **auto-purged by Gmail from Spam**, which is exactly why the exclude list is *merge-mode and sticky* — once an address bounces it stays excluded forever even after the DSN disappears. All 9 are captured.

---

## Reputation verdict: CLEAN (no degradation)

Three independent signals confirm sender reputation is healthy:

1. **0 SMTP-time failures.** All 89 sends (and all follow-ups) were accepted by Gmail's outbound server at send time (`45 sent, 0 failed` on batch4, etc.). Bounces came back **asynchronously as recipient-side DSNs**, not as Gmail refusing to relay.
2. **0 policy/spam/blocklist rejections.** No DSN contains `spam`, `blocked`, `blacklist`, `reputation`, `550 5.7`, or `554 5.7`. Every failure is `5.1.x` "address/mailbox does not exist" or "address rejected / not found."
3. **Bounce cause = list quality, not domain health.** The bounces cluster on Hunter-guessed / role addresses that simply don't exist. That's a *prospecting-data* issue, fixable by tighter email verification pre-send — it does **not** indicate our domain is being throttled or filtered.

**Caveat / watch-item:** 10.1% is above the ideal <5% hard-bounce ceiling for cold sending. The cause is benign (bad addresses, not reputation), but continuing to send to unverifiable addresses *could* eventually draw ISP attention. **Recommendation:** run a syntax+MX+SMTP-probe verification on future batches before sending (batch4's 6/45 = 13% bounce rate was the main driver; batch1–3 combined were only 3/44 = 6.8%). This is a list-hygiene fix, not a reputation-repair.

> Separately: Gmail Spam also holds ~40 DSNs for addresses that are **NOT in batches 1–4** (e.g. info@aceplumbing.com, contact@brightsparkelectric.com, info@ridgelineeyecare.com — dated 06-19/06-20, before batch1). Those belong to an earlier/different outreach effort and are correctly **excluded from the 89-recipient denominator and the 10.1% rate.**

---

## All 9 bounces are excluded (sticky)

`followup_exclude.json` currently holds **9 bounced addresses = exactly the 9 above**, in both the `bounced` and `exclude` arrays. The follow-up sender skips any address in `exclude`, and the scan is merge-mode so these can never be dropped. **No future touch will hit any bounced address.** ✅

Verified: `exclude: 9 | bounced: 9 | replied: 0`.

---

## Machine-readable artifact
`agency/bounce_analysis.json` — programmatic dump (live-window classification; the sticky `followup_exclude.json` is the authoritative 9-address accumulator).
