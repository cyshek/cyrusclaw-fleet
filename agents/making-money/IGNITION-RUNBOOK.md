# IGNITION RUNBOOK — the 15-minute handoff
_Last updated 2026-06-09. Owner action required. Everything below this is **already built**; this doc exists so you don't have to open three checklists and synthesize._

> **TL;DR for Cyrus:** Do **Step 1 + Step 2 + Step 3** below (≈15 min, ≈$17 total). Hand it back. I run the rest and get you a real "does it spread?" number in 2–4 weeks. That number decides whether we commit the real build.

---

## WHY this is the bottleneck (30-second version)
The whole mission rests on one question: **can a product spread itself** (so you, with no audience, reach $10k/mo without cold-selling or ad budgets)?

I built the tool to test it — **SiteLens**, a website auditor whose report is *shareable* (you run it → you send it to a site owner → they run their own → loop). It's built, tested, and the targeting (which sites to seed) is validated. **There is no more code that moves this forward.** Proving a loop *spreads* is impossible to fake in a sandbox — it needs a real public URL and a real first batch of sends. That's the only thing gating us, and it needs ~15 min of you.

---

## THE DECISION FIRST (so you're not just clicking blind)

**Fork you still owe me one answer on — pick A or B:**

- **(A) Barbell — MY RECOMMENDATION.** Fire **EXP-2 (SiteLens loop)** as the spine *first* (fastest path to a real spread number + cash), with the data-moat leg compounding in the background. Lowest cost to a decisive signal. **If you say nothing, I proceed on A.**
- **(B) All-in data-moat.** Skip the loop test, go straight at the slower/bigger "proprietary data" play. Higher ceiling, much slower to any proof, more $ before signal. Only pick this if you specifically want magnitude-over-speed and are fine waiting months for the first read.

**Which experiment to fire first, and why (if A):** EXP-2 (the loop) > EXP-1 (pSEO) > EXP-3 (Chrome). EXP-2 directly answers the thesis ("does it spread?"); the other two are cheaper corroborating probes that share the same domain, so **one $12 purchase unlocks all three.**

---

## THE 3 STEPS (do these, in order)

### ▶ STEP 1 — Buy ONE domain (~$12, ~5 min) — the single biggest unlock
A real domain makes the audit reports publicly shareable (the entire point) **and** unlocks EXP-1 at the same time.

**Pick one** (all three are DNS-free as of 2026-06-09, i.e. very likely registrable — descriptive/keyword domains, which double as an SEO asset):
1. **`linkpreviewcheck.com`** ← my pick (clear value-prop, "your shared link looks broken — check it" is the sharpest hook the tool produces)
2. `ogpreviewcheck.com`
3. `freesiteaudit.app`

**Where:** Cloudflare Registrar (at-cost, no markup, free SSL/DNS) → https://dash.cloudflare.com → *Domain Registration → Register Domains* → type the name → checkout. (Namecheap works too if you prefer.)

**Then tell me the exact domain you bought.** That one fact unblocks the most.

---

### ▶ STEP 2 — Free Google PageSpeed API key (~2 min, $0) — last 10% of "whoa"
Makes the reports show real Google performance scores (more credible = more shareable). Optional but cheap.

1. Go to https://console.cloud.google.com/apis/credentials (your Google account).
2. *Create credentials → API key.* Copy it.
3. (Optional) restrict it to "PageSpeed Insights API."
4. **Paste the key to me** (or drop it in `build/exp2-loop/.env` as `PSI_KEY=...` — I'll wire it).

> If you'd rather not, skip it — the tool already works keyless on raw-HTML signals. This just adds the Google score row.

---

### ▶ STEP 3 — Chrome dev account ($5 one-time, ~3 min) — ONLY if you want EXP-3 in parallel
Unlocks publishing the Chrome-extension probe (a second, cheap distribution test). Not required for the core thesis test.

1. https://chrome.google.com/webstore/devconsole → pay the one-time **$5** registration.
2. Tell me it's done; I package + submit the already-built extension.

> Skip this if you want to keep it to the single cleanest test. EXP-2 alone answers the thesis.

---

## WHAT I DO THE MOMENT YOU HAND BACK (same day)
1. **Deploy SiteLens** to the domain (Cloudflare Pages / a tiny host) with SSL — reports become real public links.
2. **Wire the PSI key** (if given) so reports show Google scores.
3. **Generate ~30 real SMB audits** from a candidate pool, ranked by my validated targeting harness (worst-SEO / broken-share-preview first = sharpest hook).
4. **Hand you a copy-paste send list** (site + personalized one-liner hook + report link). *This* is the only other ~30-min "scriptable human" ask: you send them (email/DM). I cannot send first-touch outreach for you — that's the one human gate.
5. **Measure real K-factor over 2–4 weeks** (decisive-or-silent: it refuses to declare PASS/FAIL on noise).
6. **Report the verdict + the single next move** (commit the real build / re-skin / pivot) — already coded as a one-command decision so it can't drift.

---

## WHAT "DONE" LOOKS LIKE
A real number: **K** (how many new people each sharer brings in). K ≥ ~0.4 sustained = the loop is real = we commit the build and scale it toward the $10k/mo target. K too low = I diagnose *which half* (reach vs conversion) and we re-skin or pivot — cheaply, because it's all built to be reused.

---

## SOURCE CHECKLISTS (detail, if you ever want it — you shouldn't need to)
- EXP-2 loop: `build/exp2-loop/IGNITION-CHECKLIST.md`
- EXP-1 pSEO: `build/exp1-pseo/CHECKLIST.md`
- EXP-3 Chrome: `build/exp3-chrome/CHECKLIST.md`

**Net:** the build is done. This is a ~$17, ~15-minute, mostly-just-clicking handoff. Do Step 1 (+optionally 2/3), tell me the domain, and I take it from there.
