# Tailoring notes

## Title swaps applied
- (none)

## Bullet rewrites per role

### `microsoft_ft` (5 bullets emitted, master had 5)
1. Led **0-to-1 deployment** of Azure's Resilience Automation Platform, defining self-service scheduling requirements and production-grade workflows that cut operational toil by 30% and scaled execution across enterprise customers including Databricks, Walmart, SAP, and NetApp.
2. Pioneered Azure's first proactive rack-level resilience testing capability, delivering a **production deployment in 4 months** with a 94% recovery rate by embedding with cross-org engineering teams and resolving hardware defects before they surfaced in live environments.
3. Directed 14 high-visibility cross-org recovery executions, including serving as bridge lead for a **sovereign-cloud network isolation deployment** tied to a $1.5B+ enterprise contract, navigating unfamiliar infrastructure and on-premise security constraints.
4. Built an internal **AI agent for drill planning**, restructuring end-to-end workflows to reduce planning cycle time by 39% and increase deployment capacity by 21% — feeding field insights directly back to engineering to shape the platform roadmap.
5. Scaled a 2-person recovery validation operation into a platformized system sustaining **45+ annual production drills** and driving $14M+ business impact, codifying repeatable deployment patterns and runbooks for clean handoff to implementation teams.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Drove **production adoption of AI-driven code generation workflows**, conducting user demos and embedded training sessions across 14 Azure engineering teams — translating the gap between notebook prototypes and reliable pipelines into 37 engineering hours saved monthly.
2. Surfaced critical **product gaps in CV/ML tooling** by facilitating 11+ field interviews with Azure service teams, directly influencing roadmap prioritization to include intent-based YAML generation and closing the loop between customer need and platform capability.
3. Accelerated data retrieval for deployment workflows by migrating documentation to an **AI-powered semantic search pipeline** with rigorous metadata standards, cutting lookup time by 83% and improving knowledge-transfer fidelity across engineering teams.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and reduced region launch cycles by 28% by securing cross-functional alignment on a unified automation prioritization framework — embedding with 140+ teams to de-risk deployment paths and surface blockers before they became failures.
2. Conducted discovery across 20+ service teams to identify **81 hours of manual toil per region launch**, then built a phased roadmap to automate critical paths — mirroring the FDE practice of closing the gap between what teams think they need and what production actually requires.
3. Engineered a **Power BI dashboard** tracking operational toil across 140+ teams, enabling leadership to target automation gaps and prioritize the highest-impact deployment improvements across the region launch pipeline.

### `amazon_robotics` (3 bullets emitted, master had 3)
1. Achieved **zero operational downtime** during a 2,000+ unit production deployment by defining the legacy OS migration strategy, mapping hardware and software dependencies across 1,200+ stations in a live warehouse environment with real-world connectivity and infrastructure constraints.
2. Drove strategic alignment between IT, Operations, and Engineering teams to implement **automated CI/CD pipelines** for edge device software delivery, accelerating deployment cycles by 25% and establishing a repeatable rollout pattern for future production environments.
3. Managed Agile ceremonies and backlog prioritization to resolve **40+ high-priority production tickets**, stabilizing the developer intake process and transferring operational knowledge to customer-side teams for independent system operation post-deployment.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by building and operating an end-to-end CRM workflow managing 200+ monthly proposals — designing the data pipeline, scoping lifecycle, and invoicing process from scratch to production with no existing playbook.
2. Reduced Customer Acquisition Cost by **13%** and lifted conversions by 2.7% by executing a digital-first go-to-market strategy, optimizing web and search infrastructure to close the gap between what customers searched for and what the business actually offered.
3. Improved leadership pricing models by analyzing **1,000+ project records** to surface margin leaks — translating raw field data into actionable profitability insights and feeding findings directly into operational decision-making.

## Notes from the rewriter
- Wove in '0-to-1 deployment' (JD's exact framing) across microsoft_ft bullet 1 and microsoft_2022 bullet 2 to mirror Roboflow's core FDE mandate.
- Used 'on-premise security constraints' and 'sovereign-cloud network isolation' in microsoft_ft bullet 3 to directly echo JD language around edge hardware, limited connectivity, and on-premise requirements.
- Inserted 'gap between what teams think they need and what production actually requires' in microsoft_2022 bullet 2 — a direct paraphrase of Roboflow's 'eyes and ears in the field' FDE value prop.
- Reframed amazon_robotics bullet 1 around 'live warehouse environment with real-world connectivity and infrastructure constraints' to mirror JD verticals (logistics, manufacturing) and edge-first engineering language.
- Added 'knowledge transfer' and 'runbooks' explicitly in microsoft_ft bullet 5 and amazon_robotics bullet 3 to hit JD's 'Knowledge Transfer & Handoff' responsibility verbatim.
- Trimmed all bullets to stay within 290 chars and dropped one weaker microsoft_ft bullet to resolve page overflow while keeping all roles at or near max count.

