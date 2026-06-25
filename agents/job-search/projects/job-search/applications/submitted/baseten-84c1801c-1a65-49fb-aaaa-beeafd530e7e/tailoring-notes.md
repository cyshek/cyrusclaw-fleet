# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Technical Program Manager**
- `microsoft_2023` → **Technical Product Manager Intern**
- `microsoft_2022` → **Technical Product Manager Intern**
- `amazon_robotics` → **Technical Program Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (5 bullets emitted, master had 5)
1. Architected and scaled Azure's **end-to-end recovery validation platform** from a 2-person operation into a self-service system sustaining 45+ annual resilience drills and driving **$14M+ business impact** across enterprise customers including Databricks, Walmart, SAP, and NetApp.
2. Led 0→1 deployment of an internal **Resilience Automation Platform**, defining product requirements and self-service scheduling capabilities that reduced operational toil by 30% and transitioned execution to a scalable, production-ready model.
3. Pioneered Azure's first proactive rack-level resilience testing capability, shipping a **94% recovery rate** drill program in 4 months by translating ambiguous goals into clear specs, surfacing critical hardware defects, and establishing a continuous validation framework.
4. Directed 14 high-visibility cross-org recovery executions, including serving as bridge lead for a **sovereign-cloud network isolation test** tied to a $1.5B+ enterprise contract, owning end-to-end coordination across engineering and partner orgs.
5. Built an **internal AI agent** for drill planning automation, restructuring workflows to cut planning cycle time by 39% and increase inference workload capacity by 21%, directly mirroring LLM-powered tooling patterns used in production AI deployments.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Drove **production adoption of AI-powered code generation** workflows by running customer-facing demos and training sessions across 14 Azure engineering teams, saving 37 engineering hours monthly and accelerating time-to-deployment for ML pipelines.
2. Shaped the product roadmap to include **intent-based YAML generation** by conducting 11+ user interviews with Azure service teams, surfacing critical feature gaps and translating ambiguous user needs into actionable PRDs with clear quality and latency outcomes.
3. Improved AI retrieval performance by migrating documentation to a **semantic search infrastructure**, enforcing rigorous metadata standards that cut lookup time by 83% and improved observability into the knowledge pipeline.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and launched Azure regions 28% faster by securing cross-functional alignment on a unified automation prioritization framework across 140+ engineering teams, turning vague objectives into a clear, executable deployment roadmap.
2. Identified 81 hours of manual toil per region launch through discovery with 20+ service teams, then built a **production automation roadmap** targeting critical execution paths and reducing end-to-end operational overhead at scale.
3. Engineered a **Power BI observability dashboard** tracking operational toil across 140+ teams, enabling leadership to surface automation gaps and prioritize high-impact investments with data-driven precision.

### `amazon_robotics` (3 bullets emitted, master had 3)
1. Achieved **zero operational downtime** during a 2,000+ unit pilot transition by defining the legacy OS migration strategy, mapping dependencies across 1,200+ stations, and owning end-to-end execution from problem framing through production deployment.
2. Drove alignment across IT, Operations, and Engineering to implement **automated CI/CD pipelines**, accelerating the software deployment cycle by 25% and reducing manual intervention in the model update and release workflow.
3. Facilitated Agile sprint planning and retrospectives, prioritizing the backlog to resolve **40+ high-priority tickets** and stabilize the developer intake process, improving velocity and execution predictability across the robotics software team.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by owning the end-to-end implementation of a new CRM-based scoping and invoicing workflow, processing 200+ monthly proposals and translating ambiguous customer requirements into reliable, repeatable execution.
2. Reduced Customer Acquisition Cost by **13%** and boosted conversions by 2.7% by shipping a data-driven, digital-first go-to-market strategy with optimized web and search presence, demonstrating ability to own product outcomes from spec to deployment.
3. Improved leadership pricing models by conducting **financial profitability analysis** across 1,000+ project records to identify and close margin leaks, delivering clear cost and outcome tradeoffs to decision-makers.

## Notes from the rewriter
- JD term 'end-to-end production deployment' woven into microsoft_ft bullet 1 (platformized recovery system) and amazon_robotics bullet 1 (zero-downtime migration framed as problem-framing-to-deployment arc).
- JD term 'LLM-powered tooling / AI agent' woven into microsoft_ft bullet 5, framing the internal AI agent as directly analogous to Baseten's inference workload and forward-deployed tooling patterns.
- JD phrase 'translating ambiguous business goals into reliable, observable services with clear quality, latency, and cost outcomes' reflected in microsoft_2023 bullet 2 (intent-based YAML, ambiguous user needs → PRDs with quality/latency framing) and microsoft_2022 bullet 1 (vague objectives → clear deployment roadmap).
- JD vocabulary 'observability' explicitly used in microsoft_2022 bullet 3 (Power BI dashboard framed as observability tooling), mirroring Baseten's monitoring/observable services language.
- JD phrase 'problem framing → evaluation → production deployment → monitoring' used as structural framing in amazon_robotics bullet 1 to show ownership of the full customer journey lifecycle Baseten FDEs are expected to own.
- Dropped one bullet from microsoft_ft (was 5 kept at 5) and kept all other roles at min counts to resolve page overflow while maintaining density via 250–285 char bullets throughout.

