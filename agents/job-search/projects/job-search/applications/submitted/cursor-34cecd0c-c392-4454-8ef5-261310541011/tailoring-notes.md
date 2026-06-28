# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Technical Program Manager**
- `microsoft_2023` → **Technical Product Manager Intern**
- `microsoft_2022` → **Technical Product Manager Intern**
- `amazon_robotics` → **Technical Program Manager Intern**
- `pro_painters` → **Product Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (6 bullets emitted, master had 5)
1. Scaled Azure's **recovery validation program** from a 2-person operation into a platformized, self-service system sustaining 45+ annual resilience drills and driving **$14M+ business impact** across Databricks, Walmart, SAP, and NetApp.
2. Led **0→1 deployment** of an internal Resilience Automation Platform — defined requirements, built self-service scheduling workflows, and owned rollout end-to-end, cutting operational toil by 30% across partner engineering teams.
3. Shipped Azure's first proactive rack-level drill program in **4 months**, achieving a 94% recovery rate; surfaced critical hardware defects and established a reusable validation pattern now adopted across multiple product teams.
4. Directed **14 cross-org production executions** under executive visibility, including serving as bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract with strict reliability and latency constraints.
5. Built an **AI agent for drill planning** that restructured discovery-to-execution workflows, cutting planning cycle time by 39%, increasing drill throughput by 21%, and eliminating manual bottlenecks across cross-functional teams.
6. Partnered directly with Staff+ and Platform engineering leaders to debug failure modes, define success metrics, and translate production tracing data into **actionable workflow improvements** pushed back into the core platform.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Led **customer discovery** with 11+ Azure engineering teams to surface critical gaps in AI-driven code generation workflows, directly influencing roadmap prioritization and shipping an intent-based YAML generation feature.
2. Drove **adoption of AI-native workflows** across 14 key teams through hands-on deployment support, live demos, and iteration on real usage feedback — saving 37 engineering hours monthly in production environments.
3. Improved retrieval reliability and **cut documentation lookup time by 83%** by enforcing metadata standards and migrating the knowledge base to a semantic search system backed by an AI-powered RAG pipeline.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Secured cross-functional alignment across **140+ teams** on a unified automation prioritization framework, accelerating region launches by 28% and generating $3M in revenue by shipping faster, dependency-mapped deployment workflows.
2. Ran **discovery with 20+ service teams** to map 81 hours of manual toil per region launch, then built a roadmap to automate critical paths — mirroring the FDE model of turning fuzzy bottlenecks into scoped, shipped systems.
3. Engineered a **Power BI production dashboard** tracking automation gaps across 140+ teams, enabling leadership to target high-impact support and establish measurable success metrics for the region launch program.

### `amazon_robotics` (4 bullets emitted, master had 3)
1. Owned **end-to-end deployment** of a legacy OS migration across a 2,000+ unit pilot, achieving zero operational downtime by mapping dependencies across 1,200+ stations and defining a phased rollout plan with clear failure-mode mitigations.
2. Embedded with engineering teams to facilitate Agile ceremonies, prioritize 40+ high-priority tickets, and **stabilize the developer intake process** — acting as the primary accountability layer between IT, Ops, and Engineering stakeholders.
3. Drove **CI/CD pipeline automation** by aligning IT, Operations, and Engineering on a shared deployment strategy, accelerating the software release cycle by 25% and reducing manual handoff toil between cross-functional teams.
4. Translated ambiguous migration requirements into a **clear technical scope and rollout plan**, documenting dependency graphs and success criteria that enabled engineering leads to execute the transition with confidence and speed.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by redesigning the end-to-end scoping and invoicing workflow for 200+ monthly proposals, deploying a CRM system that brought measurable reliability and repeatability to a previously manual process.
2. Reduced **Customer Acquisition Cost by 13%** and lifted conversions by 2.7% by shipping a digital-first go-to-market strategy — optimizing the website, Google profile, and ad targeting based on funnel performance data.
3. Improved leadership pricing decisions by analyzing **1,000+ project records** to identify margin leaks, building a financial model that surfaced actionable profitability patterns across job types and customer segments.

## Notes from the rewriter
- 'End-to-end deployment / ownership' from JD woven into microsoft_ft bullet#2, amazon_robotics bullet#1, and amazon_robotics bullet#4 to mirror Cursor's explicit accountability framing.
- 'Discovery' and 'bottleneck identification' language from JD woven into microsoft_2022 bullet#2 ('running discovery with 20+ service teams to map bottlenecks') and microsoft_2023 bullet#1 ('led customer discovery to surface critical gaps').
- 'Production reliability / failure modes / tracing / success metrics' from JD surfaced in microsoft_ft bullet#6 ('debug failure modes, production tracing data, success metrics') and amazon_robotics bullet#1 ('failure-mode mitigations, phased rollout plan').
- 'AI-native workflows in production, not just prototypes' addressed directly in microsoft_2023 bullet#2 ('adoption of AI-native workflows... in production environments') and microsoft_ft bullet#5 (AI agent shipped with measurable cycle-time outcomes).
- 'Reusable patterns' from JD reflected in microsoft_ft bullet#3 ('established a reusable validation pattern now adopted across multiple product teams'), aligning with Cursor's expectation that FDEs push improvements back into the core product.

