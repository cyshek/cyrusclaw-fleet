# App-Wedge Candidates — Demand-Mining Report
_Subagent for `making-money`. Date: 2026-06-07. Goal: 3 evidence-backed micro-app candidates + ranked #1 for a fully-AI-run micro-business whose owner has NO audience. Ranking axis: where real, searchable, PAYING demand already lives AND a distribution path that does not depend on an audience we lack._

---

## 0. Method, honesty notes, and what was blocked

**This VM's datacenter IP is heavily bot-walled.** Concretely:
- `web_search` tool is **non-functional** (SearXNG base URL not configured — returns hard error).
- Google, Bing, and DuckDuckGo raw-HTML search all return empty/JS-challenge shells from this IP. So I could **not** pull live search-volume numbers or Reddit threads directly.
- **Reddit is hard-blocked** (HTTP 403 "request blocked due to a network policy"). So r/shopify / r/SaaS quotes are unavailable — I flag every place that would normally lean on them.
- **G2 / Capterra** are JS+anti-bot walled (403 "enable JS and disable ad blocker"). Could not mine those review bodies.

**What DID work (and carried the whole report):**
1. **Shopify App Store individual app pages + review pages via `curl`** — raw HTML contains the *actual 1-star review text* (grep on `tw-break-words` paragraphs), the rating distribution (`X% of ratings are N stars`), pricing, and the "what merchants think" AI summary. This is the core evidence engine and it is high-quality, first-party data.
2. **Shopify `sitemap_apps_en.xml`** = **21,301 app slugs** (saved to `research/slugs.txt`). This is the *entire* English app catalog, keyword-greppable, so I can measure how crowded any niche is and find every competitor by name.
3. **Chrome Web Store `/search/<keyword>` and `/category/...` pages via the `web_fetch` tool** (NOT curl) — render to ranked result lists with star ratings and publisher domains. Good for mapping competitive intensity.

**Honest limitation:** Chrome Web Store **detail** pages return 0 bytes to `curl` and timed out in the headless browser, so I could **not** capture exact install/user counts for Chrome incumbents. I therefore characterize Chrome competition by **star rating + "Featured" badge + whether the publisher is a funded SaaS** (a strong proxy), and I say so wherever it matters. Treat Chrome-side "scale" claims as directional, not precise.

**Where demand evidence is weak, I say so explicitly.** I did not manufacture confidence.

---

## 1. The single most important pattern I found

Across the **largest, most-reviewed** Shopify apps, the dominant 1-star theme is not "missing feature" — it is **"this app silently changed/broke my store and then I couldn't undo it, and support vanished."** This appeared *unprompted* in the lowest reviews of category leaders:

- **PageFly (Landing Page Builder, 5,684 reviews, 94% 5★ — i.e. a beloved app still bleeding this complaint):**
  > "PageFly's free version corrupted my entire store without warning. After a theme update, PageFly made 100+ unauthorized changes to my store (confirmed by Shopify support). My product descriptions disappeared and were replaced with garbage text... they 'don't have access'... If something breaks, they disappear."
  (https://apps.shopify.com/pagefly/reviews?ratings%5B%5D=1)

- **Shogun (Landing Page Builder, 1,938 reviews):**
  > "Embedded codes on my entire website and my website is down for the whole day already." / "Near impossible to remove their code from your site if you don't want to use it." / "the app installed various code to my theme without me using the app... some of my pages have been completely removed of text."
  (https://apps.shopify.com/shogun/reviews?ratings%5B%5D=1)

- **SearchPie SEO (2,322 reviews, 4.9★):**
  > "Using the app default fixes suggested damaged my SEO score by their own scorecard. Changes can't be undone and support team not helpful at all." / "once you stop using the app all the work you put into the meta titles and descriptions disappear... I had to spend two weeks updating all of my info again."
  (https://apps.shopify.com/seo-booster/reviews?ratings%5B%5D=1)

- **Wholesale Pricing Discount B2B (545 reviews):**
  > "They broke my chekout button. Had custom code to add shipping insurance and signature options at checkout = Now broken." / "I explicitly told the dev team to not break my site... [they] never reached out during implementation."
  (https://apps.shopify.com/wholesale-pricing-discount/reviews?ratings%5B%5D=1)

**Why this matters for us:** it is a *meta-pain* with built-in **recurring-revenue logic** (continuous protection = a monthly insurance subscription, not a one-and-done utility), it is **horizontal** (every merchant who installs apps is exposed), and the search intent is real and growing ("shopify backup", "undo shopify theme change", "what did this app change"). It also directly informs Candidate A below.

---

## 2. Candidate A — **"App Guardian": Shopify theme/app change-monitor + one-click rollback** ⭐ (RECOMMENDED #1)

**The exact narrow pain (one sentence):** Shopify merchants install apps that silently inject/modify theme code and occasionally corrupt their storefront, with no visibility into *what changed* and no easy *undo* — so they want a watchdog that snapshots every change and rolls it back in one click.

**Platform: Shopify App Store** (marketplace-native). This is correct because (a) the buyer intent lives exactly here — merchants search the Shopify store for "backup", "restore", "theme history"; (b) Shopify's Admin API + Asset API + theme versioning give us the exact hooks to diff and restore theme assets; (c) the marketplace ships the buyers, which is the whole point for an audience-less owner.

**Evidence of demand:**
- The four category-leader 1-star quotes in §1 are the demand — destructive changes + no undo is the recurring grievance of the *biggest* apps.
- The backup sub-category already exists and people pay monthly for it (proves willingness to pay for "insurance"): `backup-master` (123 reviews, 98% 5★, https://apps.shopify.com/backup-master), `avada-backups-restore` (https://apps.shopify.com/avada-backups-restore), plus 18+ backup/restore slugs in `slugs.txt` (`akadenia-backup`, `easy-backup-restore`, `recover-backups-data-restore`, `ordersafe-auto-backup`, `sbit-store-backup-restore`, `content-history-restore-pro`...). A populated-but-not-dominated category = proven demand, room to differentiate.
- The market leader (Rewind, an established paid backup vendor — its slug 404'd in my probes but it is the known incumbent at enterprise pricing) validates that backup/restore is a real, monetized, recurring category.

**Competitive landscape + weaknesses to exploit:**
- Existing backup apps mostly do **blind full-store snapshots** — they back everything up but **don't tell you WHICH app changed WHAT**, and restore is all-or-nothing. The unmet need in the 1-star quotes is *attribution + surgical undo* ("I want to see the 100 changes PageFly made and revert just those"). That is the wedge: **change-attribution + granular rollback + alerting**, not just bulk backup.
- Backup incumbents are mid-size (BackupMaster ~123 reviews), i.e. **no untouchable 10k-review gorilla owns "theme change history + undo."** The framing is open.
- Weakness we avoid: generic backup apps read as boring/optional. We reframe as an **active guardian** ("get alerted the instant an app rewrites your theme; undo it before customers notice") which is more urgent and more clearly worth a recurring fee.

**Why an AI-agent team can build + operate this:** It is **read-mostly + diff + store-and-restore** — no checkout/payments surface (the dangerous part of Shopify). Tech is well-trodden: poll/subscribe to theme asset changes via Admin API, store versioned snapshots in cheap object storage, compute diffs, expose a restore endpoint. **Support load is low and automatable** because the product is mostly autonomous (it watches and alerts); most tickets are "restore this for me," which is a button. No human-in-the-loop content moderation, no fragile third-party scraping.

**Monetization:** **$9–$19/month** tiered by store size / snapshot frequency / retention. People pay recurring because it is **insurance** — value is *continuous* (every new app install is a new risk) and the cost of one corrupted storefront (lost sales + hours of rebuild, per the quotes) dwarfs the fee. This is the cleanest recurring logic in the whole report: you cannot "use it once and uninstall" — uninstalling removes the protection.

**Rough build estimate:** **~2–4 weeks** to a credible v1 (theme-asset watcher + snapshot + diff viewer + one-click restore + email/Slack alert). Main technical risk: **Shopify API coverage** — Asset API gives theme files cleanly, but capturing *all* app side-effects (metafields, script tags, checkout extensions) is broader; v1 should scope to **theme files + key metafields** (the exact thing the quotes complain about) and expand. Secondary risk: storage cost at scale (mitigated by dedup/diff-only storage).

**Moat / why we don't just get cloned:** Thin but real. (1) **Data/history lock-in** — the longer a merchant runs it, the deeper their change-history and the higher their switching cost. (2) **Trust + review moat** — backup/safety is a trust purchase; early 5★ reviews + "X stores protected, Y restores performed" compounds and is hard for a clone to match cold. (3) **Attribution dataset** — as we observe which apps make which changes across many stores, we can build an "app behavior" knowledge base (e.g. "PageFly typically touches these 14 assets") that a fresh cloner lacks.

---

## 3. Candidate B — **Preorder / partial-payment with reconciled second-charge billing**

**The exact narrow pain (one sentence):** Merchants running preorders/deposits get the first payment fine, then the **second/balance charge breaks** (failed captures, billing mistakes, oversells, money stuck in limbo) with no recovery path, leaving thousands of dollars unbillable.

**Platform: Shopify App Store** (marketplace-native; this is inherently a Shopify-checkout problem).

**Evidence of demand (strong, specific):**
- **STOQ / Preorder (3,218 reviews):**
  > "The app works fine for collecting the first payment, but once you get into post-preorder issues (remaining balance collection, billing mistakes, payment corrections), there is no real support or solution... nearly $2,000 is in limbo with no way to properly charge customers... My honest advice: skip partial payment apps entirely and use Shopify's native system."
  (https://apps.shopify.com/back-in-stock-restock-alerts/reviews?ratings%5B%5D=1)
- **Deposit & Partial Payment ("Depo"), 88 one-star reviews, 11% of all ratings are 1★** (high for this store):
  > "This app has so many issues it is virtually unusable." / "they charged us when we didnt even use the app" / "no support from app developer..no email reply nothing...fake 5 star reviews."
  (https://apps.shopify.com/deposits-split-payments/reviews?ratings%5B%5D=1)
- **Early Bird (Preorder & Restock), 70 one-star reviews:**
  > "It will let the customer purchase into zero and negative amounts... if a product has an inventory of 1 it will allow the customer to purchase 4... The customer is left unaware that 3 items are not in stock, and we the merchants are stuck dealing with this." (oversell bug)
  (https://apps.shopify.com/early-bird-pre-order-manager/reviews?ratings%5B%5D=1)
- **Niche density (proof of paying market):** 58 preorder/deposit slugs in `slugs.txt`; leaders are large (`advanced-pre-order-pro` 3,218 reviews at $6.99/mo, `early-bird-pre-order-manager`). Real money flows here.

**Competitive landscape + weaknesses:** Many apps, but they **uniformly fail at the hard part: the second charge and reconciliation.** That is the moat the incumbents have NOT crossed — the entire category's 1-star reviews converge on it. A product that nails **reliable balance-capture + clear oversell guards + self-serve correction of billing mistakes** would directly target the exact complaint.

**Why an AI-agent team can build + operate:** Build is well-defined (preorder UI + deposit + scheduled balance capture). **BUT this is the riskiest candidate** because it **touches money and Shopify's payment APIs are deliberately restrictive** — capturing a delayed second payment reliably is exactly why incumbents fail (Shopify's payment hold/capture windows, vaulting limits, and the fact that you often *cannot* re-charge a stored card without Shopify Subscriptions APIs). Support load is **higher** (money disputes = anxious, urgent tickets), which cuts against "low human babysitting."

**Monetization:** **$19–$49/month** (merchants running preorders are revenue-motivated and will pay for reliability). Recurring logic is solid — it is core checkout infrastructure they run continuously.

**Rough build estimate:** **3–6 weeks**, and the main technical risk is the **single biggest risk in this report**: Shopify's payment/capture API may make "reliable automatic second charge" genuinely hard or partially impossible — the same wall the incumbents hit. **Must be de-risked with a payments spike before committing.**

**Moat:** If (big if) we solve reconciled second-charge billing where others can't, that *is* the moat — it's the unsolved technical problem of the category. Thin otherwise.

---

## 4. Candidate C — **Etsy seller research/profit Chrome extension (narrow, e.g. true-profit + fee/ads reconciliation)**

**The exact narrow pain (one sentence):** Etsy sellers can't easily see their **true per-order profit** after Etsy's stack of fees (listing, transaction, payment processing, offsite-ads 15%, regulatory) and ad spend, so they fly blind on which products/keywords actually make money.

**Platform: Chrome Web Store extension** (marketplace-native, audience-free distribution). Correct because Etsy seller tools are overwhelmingly distributed as Chrome extensions that overlay etsy.com, and sellers actively **search the Chrome store** for "etsy" tools.

**Evidence of demand:**
- The Chrome store "etsy" search shows a **populated, paying ecosystem**: `EverBee` (4.7, Featured), `Alura` (4.3, Featured), `EHunt/EtsyHunt` (4.1), plus thin/mediocre tools: **`ProfitTree – Etsy Seller Assistant` (4.0)**, `Etsy - Sold out` (3.0), `Etsy Price Tracker` (4.4). (https://chromewebstore.google.com/search/etsy)
- Mediocre ratings on the **profit-specific** incumbent (ProfitTree 4.0) + the existence of multiple thin export-only utilities suggests the "true-profit, done well" slot is **not** locked down the way research/SEO (EverBee) is.

**Competitive landscape + weaknesses:** EverBee/Alura own *product research & SEO* and are strong (4.7/4.3) — do **not** fight them there. The opening is the **profit/financial-reconciliation** sub-slot (ProfitTree 4.0 is beatable), which is also stickier than research (you check profit continuously, not once). **Honest caveat:** I could not pull exact install counts (Chrome detail pages blocked), and Reddit/forum demand quotes were unreachable, so this candidate's demand evidence is **moderate, not strong** — it rests on incumbent ratings + ecosystem density, not on captured "I wish this existed" quotes.

**Why an AI-agent team can build + operate:** Etsy has an open-ish seller API + the extension can parse the seller dashboard DOM; profit math is deterministic. Low support load (analytics overlay). Buildable.

**Big honest risk on monetization:** **Etsy sellers skew hobbyist and cheap.** The audience's willingness to pay recurring is the weakest of the three candidates. Realistic price **$5–$12/month**, and churn risk is high (seasonal sellers). Recurring logic exists (ongoing fee/ads reconciliation each month) but is softer than Candidate A's insurance logic.

**Rough build estimate:** **1–3 weeks** (DOM overlay + fee model + simple dashboard). Main technical risk: **Etsy DOM/API changes** breaking the overlay (ongoing maintenance tax), and Etsy ToS limits on automated access.

**Moat:** Thinnest of the three. Some via accumulated historical profit data per seller (switching cost) and the fee-model accuracy, but a determined cloner can replicate. Etsy-platform-dependency is also a single-point-of-failure risk.

---

## 5. Niches I examined and DOWN-RANKED (so we don't waste cycles)

- **AI alt-text / image-SEO (Shopify):** 64 near-duplicate slugs (`ai-alt-text-generator`, `-1`, `-3`...) but **tiny per-app review counts** (AltKing `alt-text-automator-by-starapps` = 80 reviews). Cheap to build = **commoditized, near-zero moat, low per-app paying demand.** Pass.
- **GMC / Google Shopping feed (Shopify):** real recurring pain, BUT dominated by a **beloved gorilla** — Simprosys (`google-shopping-feed`) ~**1,032 reviews at 97% 5★**, cheap ($4.99–$17.99/mo). Hard to dislodge a loved, cheap incumbent. Pass for now.
- **SEO suites (Shopify):** SearchPie 2,322 reviews — shark tank of funded incumbents. The *complaints* (price, lock-in, destructive fixes) are useful intel (they feed Candidate A) but the head-on category is a bad entry. Pass.
- **Profit analytics (Shopify):** 105 slugs — extremely crowded (BeProfit, TrueProfit, etc.). Pass on Shopify; the *Etsy* profit slot (Candidate C) is far less contested.
- **Dropshipping research (Chrome):** strong incumbents (Koala 4.7, Dropship.io 4.6, Dropified 4.8). Crowded & mature. Pass.
- **Amazon seller tools (Chrome):** heavyweight funded incumbents (Helium10, SellerApp, SellerSprite). Capital-intensive arena; the only weak rating was Helium10's *review-request* helper (3.4), too narrow. Pass.
- **LinkedIn email finder (Chrome):** total **bloodbath** — every result 4.2–5.0, backed by funded SaaS (Apollo, GetProspect, Wiza, SignalHire). Pass hard.

---

## 6. On the widened aperture (web/mobile/desktop)

Per the scope update, I tested whether a **non-marketplace** shape beats marketplace-native here. **It does not, for an audience-less owner**, because:
- A **pure web app has ZERO built-in traffic** — we'd be buying ads or grinding SEO from zero with no audience, which is the exact constraint the strategy was built to avoid.
- **iOS/Android** discovery is ASO-pay-to-play + a 30% cut, and none of the validated pains above are mobile-native.
- Every validated pain I found **lives inside a host platform** (a Shopify store, an Etsy dashboard) where a marketplace/extension overlay is the *natural* delivery vehicle AND the *distribution* vehicle simultaneously. That is the rare case where product shape and distribution are the same decision — which is exactly what an audience-less owner wants.

So all three finalists are marketplace-native by evidence, not by constraint. (Candidate A could later add a thin web dashboard, but acquisition stays via the Shopify store.)

---

## 7. RANKED RECOMMENDATION

1. **⭐ Candidate A — Shopify "App Guardian" (theme/app change-monitor + one-click rollback).** Best blend of: evidence (the loudest, most cross-cutting 1-star pain across the *biggest* apps), **cleanest recurring/insurance logic** (can't use-once-and-quit), **lowest build risk** (read+diff+restore, NO payment surface), **lowest/automatable support load**, marketplace-native distribution, and a populated-but-not-dominated backup category proving willingness to pay. **$9–$19/mo, ~2–4 weeks.**
2. **Candidate B — Reconciled preorder/partial-payment.** Sharpest, most specific demand evidence (money literally stuck in limbo, 11% 1★), strong price power ($19–$49/mo) — but **highest technical risk** (Shopify payment-capture wall is why incumbents fail) and higher support load. Ranked #2 only because the very thing that makes it a great wedge (hard billing) may be the thing that blocks us. **Requires a payments feasibility spike before commit.**
3. **Candidate C — Etsy profit Chrome extension.** Good audience-free distribution and beatable profit-incumbent (ProfitTree 4.0), fastest to build (1–3 wks) — but **weakest demand evidence** (no captured forum quotes; rests on incumbent ratings) and **weakest payer** (cheap hobbyist sellers, $5–$12/mo, churn risk).

---

## 8. Single strongest piece of evidence for the #1 pick
A **beloved, 5,684-review, 94%-5★ category leader (PageFly)** still carries fresh 1-star reviews like: _"PageFly's free version corrupted my entire store without warning... made 100+ unauthorized changes (confirmed by Shopify support)... My product descriptions disappeared and were replaced with garbage text... If something breaks, they disappear."_ (https://apps.shopify.com/pagefly/reviews?ratings%5B%5D=1). When even the *best-loved* apps in the store routinely destroy storefronts with no undo, a vendor-neutral **"watch every change + one-click rollback"** guardian sells itself on the exact fear merchants are already voicing — and it's an insurance product they pay for every month they keep installing apps (i.e. forever).

## 9. Build artifacts for the team
- `research/slugs.txt` — all 21,301 Shopify app slugs (keyword-greppable competitor index).
- Reusable recon recipe (since search tools are IP-blocked): `curl -A '<desktop UA>' 'https://apps.shopify.com/<slug>/reviews?ratings%5B%5D=1&sort_by=newest'` then grep `tw-break-words` paragraphs for real 1-star text; rating distribution via `grep 'of ratings are'`. Chrome competitive map via the `web_fetch` tool on `https://chromewebstore.google.com/search/<keyword>`.
- Next step if A is chosen: a 1-day spike to confirm Shopify Asset API + theme-version webhooks cover the change-capture + restore loop end-to-end.