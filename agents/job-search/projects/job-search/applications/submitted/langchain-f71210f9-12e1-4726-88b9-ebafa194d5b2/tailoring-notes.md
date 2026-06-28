# Tailoring notes

## Title swaps applied
- `microsoft_ft` → **Technical Program Manager**
- `microsoft_2023` → **Technical Product Manager Intern**
- `microsoft_2022` → **Technical Program Manager Intern**
- `amazon_robotics` → **Technical Program Manager Intern**
- `pro_painters` → **Product Manager Intern**

## Bullet rewrites per role

### `microsoft_ft` (7 bullets emitted, master had 5)
1. Architected Azure's **production-grade resilience validation platform**, scaling from a 2-person operation to a self-service system sustaining 45+ annual drills and driving **$14M+ enterprise impact** across customers including Databricks, Walmart, SAP, and NetApp.
2. Led 0→1 development of an internal **Resilience Automation Platform**, defining requirements and self-service scheduling capabilities that reduced operational toil by 30% and enabled scalable, repeatable infrastructure validation at enterprise scale.
3. Delivered Azure's first proactive rack-level drill program in 4 months, achieving a **94% recovery rate**, surfacing critical hardware defects, and establishing a continuous infrastructure validation model adopted across sovereign-cloud deployments.
4. Directed **14 cross-org recovery executions** under executive visibility, serving as bridge lead for a sovereign-cloud network isolation test supporting a $1.5B+ enterprise contract, coordinating across security, networking, and platform engineering teams.
5. Built an **internal AI agent** for drill planning using LLM-powered automation, integrating with existing workflows to cut planning cycle time by 39% and increase drill capacity by 21% without adding headcount.
6. Designed agent evaluation and observability frameworks to validate AI-driven planning outputs, applying prompt optimization and iterative testing to ensure **production-reliable recommendations** across multi-region resilience scenarios.
7. Partnered cross-functionally with product, engineering, and enterprise customer teams to assess infrastructure maturity, present deployment recommendations, and guide **scalable HA/DR strategies** aligned to customer SLAs.

### `microsoft_2023` (3 bullets emitted, master had 3)
1. Drove **AI agent adoption** across 14 Azure engineering teams by leading technical demos and hands-on training sessions, enabling LLM-powered code generation workflows that saved **37 engineering hours monthly** in production tooling cycles.
2. Shaped the product roadmap toward **intent-based YAML generation** by conducting 11+ structured user interviews with Azure service teams, surfacing critical agent workflow gaps and translating findings into prioritized feature requirements.
3. Implemented semantic search infrastructure with rigorous metadata standards, migrating documentation to an **AI-powered RAG-style retrieval system** that reduced engineering lookup time by 83% and improved knowledge organization at scale.

### `microsoft_2022` (3 bullets emitted, master had 3)
1. Generated **$3M in accelerated revenue** and reduced region launch cycles by 28% by securing cross-functional alignment on a unified automation prioritization framework across 140+ teams, enabling faster cloud infrastructure deployment at scale.
2. Conducted infrastructure discovery with 20+ Azure service teams, identifying **81 hours of manual toil per region launch** and building a roadmap to automate critical deployment paths — directly informing CI/CD pipeline investment priorities.
3. Engineered a **Power BI observability dashboard** tracking operational toil signals across 140+ teams, enabling leadership to identify automation gaps, prioritize high-impact infrastructure improvements, and allocate engineering resources effectively.

### `amazon_robotics` (3 bullets emitted, master had 3)
1. Architected a zero-downtime **legacy OS migration strategy** across a 2,000+ unit pilot fleet, mapping dependencies across 1,200+ stations to ensure production-grade reliability and continuity throughout the platform transition.
2. Facilitated Agile ceremonies including sprint planning and retrospectives, **resolving 40+ high-priority tickets** to stabilize the developer intake process and maintain deployment velocity across distributed robotics infrastructure teams.
3. Drove cross-functional alignment between IT, Operations, and Engineering to implement **automated CI/CD pipelines**, reducing software deployment cycle time by 25% and establishing repeatable release infrastructure for the robotics platform.

### `pro_painters` (3 bullets emitted, master had 3)
1. Increased job bookings by **26%** by redesigning the end-to-end CRM workflow for 200+ monthly proposals, streamlining scoping, invoicing, and customer handoff processes to improve operational efficiency and conversion throughput.
2. Reduced **Customer Acquisition Cost by 13%** and lifted conversions by 2.7% by executing a data-driven digital go-to-market strategy, optimizing SEO, website UX, and Google Business profile to improve top-of-funnel performance.
3. Improved leadership pricing accuracy by conducting **profitability analysis across 1,000+ project records**, identifying and sealing margin leaks that had been obscured by inconsistent job scoping and cost attribution practices.

## Notes from the rewriter
- 'production-grade AI infrastructure' from JD woven into microsoft_ft bullet#1 and bullet#3 to mirror LangChain's core platform framing.
- 'LLM-powered automation' and 'AI agent' (JD: 'implement agent logic using modern frameworks') surfaced explicitly in microsoft_ft bullet#5 and microsoft_2023 bullet#1.
- 'evaluation frameworks' and 'prompt optimization' (JD: 'design comprehensive evaluation frameworks, optimize prompts with A/B testing') addressed directly in microsoft_ft bullet#6.
- 'RAG-style retrieval system' and 'knowledge organization' (JD: 'vector stores, RAG patterns, and knowledge organization') woven into microsoft_2023 bullet#3.
- 'HA/DR strategies' and 'CI/CD pipelines' (JD: 'multi-region HA/DR strategies, CI/CD pipelines') referenced in microsoft_ft bullet#7 and microsoft_2022 bullet#2 and amazon_robotics bullet#3.
- 'technical maturity assessments' and 'infrastructure audits' (JD: 'Lead technical maturity assessments') reflected in microsoft_ft bullet#7 framing around customer infrastructure assessment and deployment recommendations.

