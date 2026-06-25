# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Technical Program Manager**
- `microsoft_2023` → **Technical Product Manager Intern**
- `microsoft_2022` → **Technical Program Manager Intern**
- `amazon_robotics` → **Technical Program Manager Intern**
- `pro_painters` → **Product Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (5 bullets emitted, master had 5)
1. Scaled Azure's **recovery validation program** from a 2-person operation into a platformized system, standardizing cloud deployment workflows to sustain 45+ annual resilience drills across enterprise customers including Databricks, Walmart, SAP, and NetApp.
2. Led **0→1 development** of an internal Resilience Automation Platform, defining self-service scheduling requirements and infrastructure automation capabilities that reduced operational toil by 30% and transitioned execution to a scalable, repeatable model.
3. Pioneered Azure's first **proactive resilience testing** capability, delivering a rack-level drill program in 4 months with a 94% recovery rate, surfacing critical hardware defects and establishing a new continuous validation model for platform administration.
4. Directed **14 cross-org recovery executions** under executive visibility, including serving as bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract requiring strict security and compliance adherence.
5. Built an internal **AI agent** to automate drill planning workflows, reducing planning cycle time by 39% and increasing drill capacity by 21%, establishing a reusable automation framework adopted across platform and infrastructure teams.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Championed adoption of **AI-driven code generation** workflows, conducting technical demos and training sessions that drove utilization across 14 Azure service teams and saved 37 engineering hours monthly on cloud platform operations.
2. Influenced the product roadmap to include **intent-based YAML generation** by facilitating 11+ user interviews with Azure service teams to surface critical infrastructure automation gaps and unmet platform administration needs.
3. Improved **data retrieval and observability** by implementing rigorous metadata standards and migrating documentation to an AI-powered semantic search tool, reducing lookup time by 83% across distributed engineering teams.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and launched Azure regions 28% faster by driving cross-functional alignment on a unified automation prioritization framework spanning 140+ teams across cloud infrastructure and platform operations.
2. Defined a platform strategy to reduce operational toil during region launches, conducting discovery with 20+ service teams to identify **81 hours of manual effort** per region and building a roadmap to automate critical deployment paths.
3. Engineered a **Power BI observability dashboard** to track infrastructure toil and automation gaps across 140+ teams, enabling leadership to prioritize high-impact platform investments and accelerate cloud deployment timelines.

### `amazon_robotics` (4 bullets emitted, master had 3)
1. Achieved **zero operational downtime** during a 2,000+ unit pilot transition by defining the legacy OS migration strategy, mapping dependencies across 1,200+ stations, and aligning IT, Operations, and Engineering on a phased deployment plan.
2. Facilitated Agile ceremonies including sprint planning and retrospectives, prioritizing the backlog to resolve **40+ high-priority tickets** and stabilize the developer intake process across distributed platform and infrastructure teams.
3. Drove strategic alignment across IT, Operations, and Engineering to implement **automated CI/CD pipelines**, accelerating the software deployment cycle by 25% and reducing manual overhead in production environment management.
4. Documented infrastructure migration runbooks and deployment dependencies, creating reusable **technical architecture artifacts** that reduced onboarding time for new engineers and improved cross-team execution consistency.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by optimizing end-to-end scoping and invoicing operations for 200+ monthly proposals, implementing a structured CRM process that improved pipeline visibility and reduced manual overhead.
2. Reduced **Customer Acquisition Cost by 13%** and boosted conversions by 2.7% by executing a digital-first go-to-market strategy, optimizing web presence and Google profile to improve qualified inbound lead volume.
3. Improved leadership **pricing and profitability models** by conducting financial analysis across 1,000+ project records to identify margin leaks and surface data-driven recommendations for cost optimization.

## Notes from the rewriter
- 'platform administration' and 'observability' (from JD domain: Platform Administration) woven into microsoft_ft bullet#3 and microsoft_2022 bullet#3 referencing logging/monitoring/audit parallels via Power BI dashboard and drill program.
- 'infrastructure automation' and 'deployment workflows' (from JD domain: InfraOps/Terraform) surfaced in microsoft_ft bullet#2 (Resilience Automation Platform self-service scheduling) and microsoft_2022 bullet#2 (automating critical deployment paths).
- 'network isolation' and 'security and compliance' (from JD: Security & Identity / Networking & Deployments) explicitly referenced in microsoft_ft bullet#4 describing the sovereign-cloud network isolation test tied to a major enterprise contract.
- 'cloud deployment' and 'distributed architectures' (from JD requirements) mirrored in microsoft_2022 bullet#1 (Azure region launches, 140+ teams) and amazon_robotics bullet#3 (CI/CD pipelines, production environment management).
- 'technical architecture artifacts' and 'custom architectures' (from JD: assist SAs with custom architectures) surfaced in amazon_robotics bullet#4 to demonstrate Cyrus's ability to produce reusable deployment documentation for enterprise-scale environments.

