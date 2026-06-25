# AGENCY-PLAN.md — The Operating Plan

_Owner: making-money agent. Cyrus does sales calls + approvals; agent does everything else._
_Created 2026-06-24. This is the live playbook — update as we learn._

## The one-line pitch
We make sure local service businesses **never lose another lead and automatically collect 5-star reviews** — by replying to every inbound inquiry in under 60 seconds and following up until they book, fully automated.

## Why this offer (decided 2026-06-24)
- **Speed-to-lead is the highest-ROI, easiest-to-explain automation.** Harvard study: contacting a lead within 5 min vs 30 min = 100x more likely to connect; 78% of customers buy from whoever responds first. Most local businesses take HOURS or never reply. That gap = lost money the owner can feel.
- **Review generation** bolts on for free (same tool, after-job trigger) and visibly raises Google rating → more inbound. Easy upsell, sticky.
- Clear ROI = clear close. "You're missing ~X leads/month worth ~$Y. We fix that for $Z." That math sells itself on a call.

## ICP (who we target)
Owner-operated local service SMBs, ~$1M–$10M revenue, 1–3 locations:
- Med spas / aesthetics
- Dental / orthodontics
- Personal-injury & family law firms
- Home services: HVAC, roofing, plumbing, solar

Signal of a hot prospect: contact form with no instant auto-reply, "we'll respond within 24–48h" language, weak/low Google review count, no online booking, runs paid ads (so they're already paying for leads they then drop).

## The offer & pricing (anchor — adjust per call)
- **Setup / build:** $1,500–$3,000 one-time (speed-to-lead responder + review-request flow, wired to their forms/CRM/phone).
- **Monthly retainer:** $500–$1,000/mo (hosting, monitoring, tweaks, monthly report).
- **Land first 1–2 clients at a discount / pilot** ($750 setup) to get case studies. Document results obsessively ($ recovered, response time before/after, reviews gained).
- Math to the goal: 8–10 retainers @ ~$750/mo avg = ~$6–7.5K/mo recurring + setup fees on top. That's the $5–15K/mo target with a manageable client count.

## Sales motion (Cyrus's part is small + scripted)
1. Agent sources prospects + writes a personalized cold email/Loom-style pitch referencing their specific gap.
2. Agent sends outreach (standing approval for sending exists; med via Cyrus's Gmail).
3. Interested reply → agent books a 15-min call on Cyrus's calendar + preps a one-page brief + a LIVE demo wired to that prospect's own site.
4. Cyrus runs the call (script + objection-handling cheatsheet provided by agent). Closes.
5. Agent delivers the build, onboards, monitors.

## Delivery stack ($0 to start)
- **n8n** self-hosted on this VM (Docker) — the workflow engine.
- **OpenAI API** — the responder's brain (drafts the instant reply, qualifies, books).
- Twilio (SMS) / email / webhook into their existing form — wired per client.
- One reusable TEMPLATE workflow → each new client is a fast re-skin, not a rebuild.

## What's built / status
- [x] Pitch deck (live: http://40.65.93.84:8080/agency-pitch.html) — generic, reusable, self-healing.
- [ ] Prospect list (50+ with personalization hooks) — IN PROGRESS (subagent 2026-06-24).
- [ ] Working demo automation (speed-to-lead responder) — NEXT.
- [ ] Cold outreach templates (email + follow-up) tuned to the gap.
- [ ] Sales-call script + objection cheatsheet for Cyrus.
- [ ] n8n self-hosted + the template workflow.

## Agent's standing job (so Cyrus doesn't have to manage me)
Build the foundation, source + warm prospects, draft all outreach, prep every call, deliver every build. Surface to Cyrus ONLY: (a) a call to run, (b) a credential/login, (c) a spend approval, (d) a genuine fork in strategy.

## Open questions for Cyrus (non-blocking)
- "Replace the job eventually" vs "need out soon-ish"? (sets aggressiveness)
- OK to open a VM port for n8n? (defaulting yes — reversible)
- OK to spend pennies on OpenAI API for demos? (assuming yes under $0-50 leash)
- Agency name (still "Automate." placeholder) — fine to pick something + grab a cheap domain when first client is close?
