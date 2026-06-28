# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Product Manager**
- `microsoft_2023` → **Product Manager Intern**
- `microsoft_2022` → **Product Manager Intern**
- `amazon_robotics` → **Product Manager Intern**
- `pro_painters` → **Product Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (7 bullets emitted, master had 5)
1. Scaled Azure's **resilience automation platform** from a 2-person operation into a self-service orchestration system, standardizing agent-driven workflows to sustain 45+ annual drills and deliver **$14M+ impact** across Databricks, Walmart, SAP, and NetApp.
2. Led **0→1 development** of an internal Resilience Automation Platform, defining provisioning requirements and self-service scheduling capabilities that reduced operational toil by 30% and transitioned execution to a scalable, repeatable model.
3. Pioneered Azure's first proactive resilience testing capability — delivering a rack-level drill program in 4 months with a **94% recovery rate** — surfacing critical hardware defects and establishing a new continuous validation loop for enterprise infrastructure.
4. Directed 14 cross-org recovery executions under executive visibility, including serving as bridge lead for a **sovereign-cloud network isolation test** tied to a $1.5B+ enterprise contract, coordinating sandboxing and failover across distributed systems.
5. Built an **internal AI agent** for drill planning and restructured orchestration workflows, cutting planning cycle time by 39% and increasing drill capacity by 21% — directly expanding the team's ability to run parallel, autonomous task execution at scale.
6. Instrumented task completion rate, time-to-value, and cost-per-execution metrics across the resilience platform, building the **measurement layer** that guided roadmap investment decisions and surfaced where agent reliability gaps were highest.
7. Defined the agent artifact and review layer for post-drill analysis — standardizing logs, error traces, and recovery timelines so engineering leads could **verify outcomes in minutes** rather than reconstructing sessions from raw infrastructure telemetry.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Championed **AI-driven code generation** adoption across Azure, conducting user demos and structured training that drove utilization across 14 key engineering teams and saved 37 developer hours monthly — validating product-market fit for the agent-assisted workflow.
2. Shaped the product roadmap to include **intent-based YAML generation** by facilitating 11+ user interviews with Azure service teams, surfacing critical feature gaps and translating ambiguous developer needs into scoped, actionable requirements.
3. Improved developer trust in AI-assisted tooling by implementing rigorous metadata standards and migrating documentation to a **semantic search platform**, cutting information lookup time by 83% and reducing friction in the agent handoff experience.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and launched Azure regions 28% faster by securing cross-functional alignment on a unified automation prioritization framework — driving orchestration decisions across 140+ teams with incomplete and conflicting information.
2. Defined a product strategy to eliminate operational toil during region launches, conducting discovery with 20+ service teams to map **81 hours of manual effort per region** and building a roadmap to automate critical provisioning and deployment paths.
3. Instrumented a **Power BI observability dashboard** tracking automation gaps and toil distribution across 140+ teams, enabling leadership to allocate resources to high-impact paths and measure progress against the automation roadmap.

### `amazon_robotics` (3 bullets emitted, master had 3)
1. Achieved **zero operational downtime** during a 2,000+ unit pilot transition by defining the legacy OS migration strategy, mapping dependencies across 1,200+ stations, and designing the rollback and error-recovery model for the distributed robotics fleet.
2. Facilitated Agile ceremonies across sprint planning and retrospectives, **prioritizing the backlog** to resolve 40+ high-priority tickets and stabilize the developer intake process — keeping agent task queues unblocked during a high-stakes infrastructure migration.
3. Drove strategic alignment between IT, Operations, and Engineering to implement **automated CI/CD pipelines**, accelerating the software deployment cycle by 25% and establishing a repeatable, parallelized release model for fleet-wide software updates.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by redesigning the end-to-end task handoff workflow for 200+ monthly proposals — scoping requirements, reducing ambiguity at intake, and building a CRM process that let the sales team move on without tracking each job manually.
2. Reduced **Customer Acquisition Cost by 13%** and boosted conversion rate by 2.7% by executing a digital-first go-to-market strategy, optimizing the website funnel and Google Business profile to surface the right output at the right stage of the customer journey.
3. Improved leadership pricing decisions by conducting **financial analysis across 1,000+ project records**, identifying margin leaks and delivering a profitability model that gave decision-makers legible, fast-reviewable output rather than raw spreadsheet data.

## Notes from the rewriter
- 'agent orchestration' and 'provisioning' from the JD woven into microsoft_ft bullet#1 and bullet#4 — reframing Azure resilience platform as an orchestration/provisioning system.
- 'artifact and review layer' from the JD directly surfaced in microsoft_ft bullet#7 — logs, error traces, and recovery timelines mapped to Cursor's logs/video/preview artifact model.
- 'task handoff experience' from the JD injected into pro_painters bullet#1 — reframing CRM proposal workflow as a handoff-and-move-on loop matching Cursor's core UX problem.
- 'measurement layer' and 'task completion rate / time-to-value / cost-per-task' from the JD's instrumentation section used verbatim in microsoft_ft bullet#6.
- 'error recovery' and 'sandboxing' from the JD's orchestration model section woven into amazon_robotics bullet#1 to surface distributed systems fluency.
- 'developer trust' from the JD used in microsoft_2023 bullet#3 to frame the semantic search work as a trust and reliability outcome, not just a speed metric.

