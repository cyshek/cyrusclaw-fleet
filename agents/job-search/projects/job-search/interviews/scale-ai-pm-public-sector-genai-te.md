# Scale AI — PM, Public Sector GenAI Test & Evaluation (T&E)

**Role:** Product Manager, Public Sector GenAI Test & Evaluation (T&E) (req 4687591005)
**Location:** SF / St. Louis / NYC / DC
**Applied:** 2026-05-13
**Apply URL:** https://job-boards.greenhouse.io/scaleai/jobs/4687591005
**Comp band (per JD):** $205.6K–$257K (SF/NYC/Seattle) / $184.8K–$231K (DC/CO/TX/HI) / $154.4K–$193K (St. Louis) — plus equity + benefits

> 📅 **Add interview date/time + format/interviewer name here when you have them.**

---

## What this role actually is

T&E = Test & Evaluation. Translation: you own the **tech stack that proves Scale's agentic AI works well enough to deploy in government contexts**. Continuous measurement, hillclimbing infra for ML teams, surfacing performance to stakeholders. This is essentially "platform PM for the eval layer of Scale's Public Sector business."

Key signals from the JD:
- "Traversing multiple engineering orgs" → coordination-heavy across Infra / ML Research / Product
- "Unscripted, high-stakes" → DoD/IC customers, hard SLAs
- "Read code, participate in technical design reviews" → expect technical depth questions
- They want **two specific examples of "inherited a failing project → shipped to prod"** — prepare these.
- They explicitly call out **Linear** for weekly delivery reporting. Mention it if you have used it.

## Company snapshot

- **Mission:** Reliable AI for the world's most important decisions
- **Public Sector team:** dedicated unit working with DoD, IC, civilian agencies
- **Named customers:** Meta, Cisco, DLA Piper, Mayo Clinic, Time Inc., Government of Qatar, US Army, US Air Force
- **CEO:** Alexandr Wang (until 2025 — confirm current; he moved to Meta as Chief AI Officer late 2025). **Current CEO situation:** verify before interview — leadership changed recently.
- **Notable recent moves:** Meta took a ~$14B stake in Scale in 2025 and hired Alexandr Wang. This will likely come up — have a thoughtful take that doesn't badmouth either side.
- **Defense Llama** + **Donovan** are Scale's known public-sector AI products
- **Levels.fyi TC reference:** Scale PM TC is roughly $300–400K all-in at mid/senior levels (check `tracker.roles.est_tc` for 838)

## Likely interview questions

### Technical / Role-specific (most likely focus)
1. **"How would you design an evaluation system for a multi-step agentic workflow?"** — be ready: golden datasets vs synthetic, online vs offline eval, human-in-the-loop scoring, regression detection, slice-level metrics, agreement w/ human labelers
2. **"You inherit our T&E pipeline. ML teams say cycles are too slow. How do you diagnose?"** — instrument first (where's the time going? data prep / inference / scoring / reporting), interview the ML leads, look for the long-pole step, propose 1 quick win + 1 structural fix
3. **"How do you balance evaluation rigor with shipping velocity?"** — tiered eval (smoke before merge, full nightly, certification before deploy), risk-based gating, fast paths for low-risk changes
4. **"How would you measure 'is this agent good enough for DoD'?"** — task success rate on representative scenarios, failure-mode taxonomy, safety/refusal behavior, robustness to adversarial inputs, hallucination rate on factual queries
5. **"Walk me through a recent technical roadmap you owned."** — pick something cross-org with measurable outcome

### Behavioral (T&E PM specifically)
1. **"Two examples of inheriting a stalled project and shipping it."** ⭐ they literally ask for this — drill two STAR stories. Lead with "stalled because [X]" → "first 2 weeks I did [diagnostic]" → "the unlock was [Y]" → "shipped [date], impact [metric]".
2. **"Time you aligned three engineering orgs."** — Infra + ML Research + Product is the JD-named triple. Pick a story w/ clear org boundaries.
3. **"Vague problem → measurable roadmap."** — e.g. "improve X" became "ship Y by Q3 measured by Z."
4. **"Disagreement with eng leadership"** — show you can push back with data, not ego.
5. **"How do you report to executives?"** — weekly Linear status, blockers up, no surprises, ruthless prioritization.

### Public Sector / domain
1. **"Why public sector AI?"** — be specific: high-stakes decisions, accountability matters more than consumer AI, eval rigor is non-negotiable
2. **"Familiarity with DoD acquisition / ATO / cleared environments?"** — be honest. If no clearance: emphasize you're clearance-eligible (US citizen) and willing to start the process.
3. **"What's the difference between evaluating a chatbot vs an agent?"** — agents have multi-step trajectories, tool use, state, side effects. Eval is path-dependent. Need trajectory-level metrics not just final-answer metrics.

### Why-Scale / fit
1. **"Why Scale?"** — Data + eval moat for AI is the deepest moat in the industry. Public Sector is where AI matters most.
2. **"Why now?"** — agentic systems just crossed the threshold where eval can't be human-bottlenecked anymore. This is when this role gets built.
3. **"Where else are you interviewing?"** — mention Cresta + 1–2 others. Don't oversell.

## Smart questions to ASK

- "How does this T&E platform serve Defense Llama / Donovan / other public-sector products?"
- "What's the current ratio of human eval vs automated eval, and where do you want it in 6 months?"
- "Who would I be partnering with most — ML Research, Infra, or specific PMs?"
- "What does 'good' look like 6 months in?"
- "Public Sector vs Commercial T&E — same stack or forked? What's the strategy?"
- "How is the Meta investment changing day-to-day priorities, if at all?"
- "What's the clearance path support look like for someone who'd need to get sponsored?"

## Things to study / refresh before the call

- [ ] Skim a recent paper on LLM/agent evaluation (HELM, AgentBench, BFCL, or similar). 30 min.
- [ ] Read Scale's blog posts on Defense Llama + Donovan if any are public. 15 min.
- [ ] Refresh on **Linear** workflow if you haven't used it lately.
- [ ] Have two "inherited stalled project → shipped" stories drilled cold.
- [ ] Have one "aligned 3 eng orgs" story drilled cold.
- [ ] Salary range to ask for: anchor near top of band ($230K+ for DC, $250K+ for SF/NYC). Defer if recruiter — "would love to learn more first."
- [ ] Confirm: do you currently hold any clearance? If not, be ready to answer "willing to get one."

## Tonal notes

- Scale is engineering-led and direct. Don't fluff.
- The role description is unusually specific ("at least two instances", "at least three distinct engineering organizations") — they will probe for these exact numbers. Be precise.
- If they ask about agentic eval and you don't know a term → say so and ask. Bluffing reads worse than learning fast.

## Logistics

- [ ] Confirm interviewer name + role
- [ ] Quiet space, good lighting, stable internet
- [ ] Resume PDF open (`scale-ai-4687591005/Cyrus_Shekari_Resume_*.pdf`)
- [ ] JD open, this prep doc open in another window
- [ ] Water, notepad

---

_Last updated: 2026-05-19. Add notes after the call._
