# Cover answers — Ramp, Product Manager | Agentic CX (ramp-a3afd259-ba6b-4eb0-a1b6-05d01dddacd8)

## Legal Name

Cyrus Shekari

## Where do you plan on working from (for payroll tax purposes)?

Kirkland, WA (open to relocating to New York for the role)

## The role requires deep hands-on experience building with AI. Describe a project where you leveraged core LLM concepts (e.g., prompting, fine-tuning, embeddings, retrieval) and translate them into a reliable, user-facing product. What was the greatest technical challenge you faced, and how did you resolve it?

No.

## Walk us through a time you "vibe-coded a prototype before lunch and wrote the rollout plan after." Describe a messy operational problem you turned into an elegant automated system using AI, detailing the full journey from prototype to scaled production.

At Microsoft, the resilience testing operation was genuinely messy: 45+ annual drills coordinated across dozens of teams, tracked through a patchwork of spreadsheets, manual handoffs, and ad-hoc Slack threads. There was no single source of truth, scheduling conflicts were constant, and planning cycles dragged on far longer than they needed to. I started by roughing out a prototype of what an automated scheduling and workflow system could look like, mapping the core inputs (team availability, dependency chains, recovery validation checkpoints) into a lightweight working model before getting into any formal spec work. The goal was to get something tangible in front of stakeholders fast, so I could pressure-test the logic and surface the edge cases that never show up in a whiteboard diagram.

The hardest part of the transition to production was not the tooling, it was the data reliability problem underneath. Drill metadata was inconsistent across teams, which meant any automated system would inherit the chaos if I did not fix the inputs first. I implemented standardized metadata schemas and migrated the underlying documentation to a semantic search setup, which cut lookup time by 83% and brought retrieval accuracy to a level where the AI agent could actually be trusted to surface the right context at the right step. Once the data foundation was solid, the agent layer could do real work. The end result was a Resilience Automation Platform that reduced operational toil by 30%, cut planning cycle time by 39%, and scaled a 2-person manual operation into a platformized system that drove measurable business impact across enterprise customers including Databricks, Walmart, SAP, and NetApp. The rollout required a lot of internal enablement work, running training sessions and change management across CX, engineering, and go-to-market teams, which honestly ended up being as important as the build itself.
