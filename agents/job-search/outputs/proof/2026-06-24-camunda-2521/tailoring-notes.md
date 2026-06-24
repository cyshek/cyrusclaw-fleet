# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Technical Program Manager**
- `microsoft_2023` → **Technical Product Manager Intern**
- `microsoft_2022` → **Technical Program Manager Intern**
- `amazon_robotics` → **Technical Program Manager Intern**
- `pro_painters` → **Product Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (7 bullets emitted, master had 5)
1. Scaled Azure's **end-to-end** recovery validation program from a 2-person operation into a platformized system, standardizing deployment workflows to sustain 45+ annual resilience drills across enterprise customers including Databricks, Walmart, and SAP.
2. Led **0→1 development** of an internal Resilience Automation Platform, defining self-service scheduling requirements and governance guardrails that reduced operational toil by 30% and enabled scalable, repeatable production deployments.
3. Pioneered Azure's first proactive resilience testing capability, delivering a **rack-level drill program** in 4 months with a 94% recovery rate — surfacing critical hardware defects and establishing a continuous validation playbook adopted org-wide.
4. Directed **14 cross-org** production executions under executive visibility, including serving as bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract requiring strict governance and auditability.
5. Built an **internal AI agent** for drill planning using prompt engineering and LLM-powered automation, cutting planning cycle time by 39% and increasing drill capacity by 21% — directly feeding the pattern back into platform tooling.
6. Drove organisational adoption of new resilience workflows by aligning engineering, architecture, and business stakeholders — translating technical deployment outcomes into executive-visible fitness metrics customers could act on independently.
7. Authored the **deployment playbook** for resilience drill execution, documenting what good looks like across integration patterns, failure modes, and handoff criteria so each successive deployment was faster and required less intervention.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Championed **production adoption** of AI-driven code generation workflows, conducting user demos and hands-on training that drove utilization across 14 Azure service teams and saved 37 engineering hours monthly in real deployed environments.
2. Shaped the product roadmap to include **intent-based YAML generation** by facilitating 11+ structured discovery interviews with Azure service teams, surfacing critical workflow gaps and translating business-language needs into executable feature requirements.
3. Improved **agentic retrieval accuracy** by implementing metadata standards and migrating documentation to an AI-powered semantic search tool, reducing lookup time by 83% and demonstrating production-grade context management for LLM-integrated workflows.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and launched Azure regions 28% faster by securing cross-functional alignment on a unified automation prioritization framework spanning 140+ teams — turning ambiguous multi-org priorities into an executable deployment roadmap.
2. Mobilized a product strategy to eliminate **manual toil** during region launches, conducting discovery with 20+ service teams to surface 81 hours of manual effort per region and building the automation roadmap targeting the highest-impact integration paths.
3. Engineered a **Power BI dashboard** to track and visualize operational toil across 140+ teams, enabling leadership to identify automation gaps, prioritize high-impact support, and measure deployment efficiency improvements over successive launch cycles.

### `amazon_robotics` (3 bullets emitted, master had 3)
1. Achieved **zero operational downtime** across a 2,000+ unit pilot by owning the legacy OS migration strategy end-to-end — mapping dependencies across 1,200+ stations and documenting a repeatable deployment playbook for handoff to the standing ops team.
2. Facilitated Agile ceremonies including sprint planning and retrospectives, prioritizing the backlog to resolve **40+ high-priority integration failures** and stabilize the developer intake process for a distributed robotics production environment.
3. Drove cross-functional alignment across IT, Operations, and Engineering to implement **automated CI/CD pipelines**, accelerating the software deployment cycle by 25% and establishing a scalable, auditable release pattern across the warehouse fleet.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by optimizing end-to-end operations and managing scoping, proposal generation, and invoicing for 200+ monthly engagements — deploying a structured CRM workflow that turned a manual process into a repeatable, scalable system.
2. Reduced **Customer Acquisition Cost by 13%** and boosted conversions by 2.7% by executing a digital-first go-to-market strategy, optimizing the website and Google Business profile to improve lead quality and lower the cost per closed booking.
3. Improved leadership pricing models by conducting **financial profitability analysis** across 1,000+ project records, identifying margin leaks and delivering data-driven recommendations that directly informed strategic pricing decisions for the following season.

## Notes from the rewriter
- 'Deployment playbook' (JD: 'Build the playbook') woven into microsoft_ft bullet#7 and amazon_robotics bullet#1 to mirror Camunda's explicit ask for playbook-builders.
- 'Organisational adoption' (JD: 'Drive organisational adoption') used verbatim in microsoft_ft bullet#6, framing stakeholder alignment work in Camunda's own language.
- 'Governance and auditability' (JD: 'built-in governance, auditability') surfaced in microsoft_ft bullet#4 (sovereign-cloud contract context) and skills_priority to signal enterprise production credibility.
- 'Intent-based / business-language to executable' framing (JD: 'business processes described in natural language, generated as executable BPMN workflows') used in microsoft_2023 bullet#2 to mirror ProcessOS's core value proposition.
- 'Production AI agent' and 'prompt engineering' (JD: 'practical AI experience... prompt engineering, agent testing') explicitly named in microsoft_ft bullet#5 to surface hands-on agentic experience in a verifiable production context.
- 'Handoff' language (JD: 'Hand off deliberately... leave each customer team trained, independent') mirrored in microsoft_ft bullet#7 and amazon_robotics bullet#1 to show Cyrus already operates this way natively.

