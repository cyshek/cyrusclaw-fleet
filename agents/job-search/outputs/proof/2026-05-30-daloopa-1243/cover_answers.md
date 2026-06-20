# Cover answers — Daloopa, Product Manager (daloopa-49ac87b7)

## Describe a product or major feature you were responsible for bringing into the world. Start with the situation as it existed before your work began, and end with what changed after.

When I joined Azure's resilience org, validation drills were a manual, 2-person operation. Each drill took weeks to plan, execution was bespoke, and there was no scalable way to offer this as a repeatable service to enterprise customers like Databricks, Walmart, SAP, and NetApp. There was no product, just a tribal process with no telemetry, no self-service, and no roadmap.

I owned the end-to-end transition into a productized B2B platform. I authored PRDs for a Resilience Automation Platform, defined self-service workflows, and partnered with engineering to shift execution to an API-driven model. I also shipped Azure's first proactive resilience testing product in 4 months, delivering a 94% recovery rate at rack-level scale.

After the work, we sustained 45+ annual drills, drove $14M+ in measurable business impact, and cut operational toil by 30%. The team went from firefighting bespoke requests to running a differentiated product that enterprise customers actively requested by name.

## What happened after this shipped? Describe one concrete change you made in response to usage, feedback, or results.

Once the platform was live and running drills at scale, telemetry and customer feedback showed planning was still the bottleneck. Drill coordinators were spending disproportionate time on scoping, dependency mapping, and scheduling, even though execution itself had been automated. Customers loved the outcomes but pushed back on the lead time.

In response, I architected an AI agent for drill planning using LLM-powered automation layered on top of a rules-based workflow engine. It ingested customer intent, mapped it against service dependencies, and generated a draft plan a human could review and approve. Planning cycle time dropped 39% and drill capacity lifted 21%, which directly translated into more revenue-tied executions per quarter without adding headcount.

## Describe a moment where product design or engineering disagreed with your direction. What was at stake, and how did it get resolved?

On the AI planning agent, I pushed for a hybrid LLM + rules-based system. Engineering initially wanted a pure rules engine, arguing it was more deterministic, easier to debug, and lower risk for executions tied to enterprise contracts. Their concern was legitimate: a hallucinated drill plan touching a customer like SAP or Walmart would be a serious incident.

What was at stake was both speed and trust. A pure rules engine would have taken much longer to cover the long tail of customer intents, and we'd lose the planning-time wins customers were asking for. I worked with engineering to scope the LLM strictly to intent parsing and draft generation, while the rules layer governed anything that touched real infrastructure. We added human approval gates and telemetry on every agent decision.

That compromise got us the 39% cycle time reduction without compromising determinism where it mattered. Engineering ended up co-owning the design, and we shipped with both teams confident in the guardrails.

## Describe a product call you made that you're still confident was the right one, even though it was unpopular or risky at the time.

Early in the productization of the resilience platform, leadership wanted to keep prioritizing white-glove drill executions because they were the visible revenue driver. I made the call to invest a meaningful chunk of engineering capacity into the self-service, API-driven workflows instead, even though it meant slower short-term drill throughput and pushback from stakeholders who measured success in drill count.

The risk was real. If self-service adoption didn't materialize, I'd have spent quarters on infrastructure with no top-line story. But I was convinced the manual model couldn't scale to the demand we were seeing, and that productizing was the only way to sustain $14M+ in impact without scaling headcount linearly.

That bet is what enabled the 30% reduction in operational toil and the eventual 45+ annual drill cadence. Without the self-service foundation, the AI planning agent wouldn't have had anything to plug into. I'd make the same call again.

## Describe a time a GTM request put pressure on your roadmap. What did you do next?

During the sovereign-cloud network isolation launch tied to a $1.5B+ enterprise contract, the GTM and field teams pushed hard for customer-specific drill scenarios that weren't on the roadmap. The contract timeline was non-negotiable and the asks would have consumed most of a quarter's engineering capacity.

I did two things. First, I sat in on customer calls myself to separate true blockers from nice-to-haves, and got to a much smaller set of requirements that actually gated the contract. Second, I reframed the remaining asks as reusable platform capabilities rather than one-off customizations, so the work fed the broader roadmap instead of forking it.

We shipped the launch on time, the contract closed, and the capabilities we built carried forward into later executions across other enterprise customers. That experience reinforced for me that GTM pressure is usually a signal worth decoding, not just absorbing.

## Any additional information you'd like to share?

Daloopa's problem space resonates with me directly. At Microsoft I've been building AI agents that turn messy, manual analyst-style work into clean, auditable, productized workflows, which is essentially what Scout is doing for fundamental research. I've also spent time as a trader and in the Trading Enthusiast Club in undergrad, so the analyst workflow isn't abstract to me. I'd be excited to bring the 0→1 productization and AI agent experience to a team that's redefining how investment research gets done.
