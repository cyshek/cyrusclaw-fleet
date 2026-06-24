# Cover answers — Claim-Health, Forward Deployed Engineer (claim-health-c9512763-dcae-40ed-a929-37d16d915ed0)

## Full Name

Cyrus Shekari

## Describe a system or product you owned end-to-end. What problem did it solve, and what tradeoffs did you make?

At Microsoft, I owned the 0-to-1 build of Azure's Resilience Automation Platform. The problem was straightforward but messy in practice: Azure's recovery validation program was a 2-person manual operation trying to support 45+ annual resilience drills across enterprise customers like Databricks, Walmart, and SAP. Every drill required significant hand-holding - scheduling was ad hoc, workflow steps were undocumented, and there was no self-service path for engineering teams. The whole thing didn't scale.

I defined the requirements, drove the workflow orchestration design, and worked directly with engineering teams to ship self-service scheduling and execution primitives. The result was a 30% reduction in operational toil and a system that could sustain drill volume without headcount growth. I also built an internal AI agent that automated scheduling logic and cut planning cycle time by 39% - that one was more tactical but had immediate leverage.

The main tradeoff I made was prioritizing durable abstractions over fast patches. There was pressure early on to just add more manual process and people to cover demand. I pushed instead to slow down for one sprint, standardize the workflow primitives properly, and build something that generalized. That decision cost time upfront but meant the platform could absorb new drill types without rework. The other tradeoff was scope - I deliberately kept the self-service interface narrow at launch rather than building for every edge case. That kept the initial deployment clean and let us learn from real usage before extending.

## What excites you about building foundational systems at an early-stage company like Claim Health?

The work I've done at Microsoft - building workflow orchestration systems, embedding with operational teams to find bottlenecks, turning manual processes into scalable platforms - maps almost exactly to what the Forward Deployed Engineer role describes. I spent the last year inside Azure's resilience operations, watching where real workflows broke under load, and then building the automation layer to fix them at the root rather than patching symptoms. That feedback loop between operational reality and software design is where I do my best work, and it sounds like that's exactly how Claim Health is structured.

What specifically draws me to Claim Health is the problem itself. Post-acute care is an operationally intense environment running on fragmented, manual infrastructure - that's a genuinely hard systems problem, and the stakes are real. Revenue cycles and patient access aren't abstract. I want to work on a platform where correctness and reliability matter because the underlying workflows actually matter. Early-stage also means the abstractions I help design now become core to how the product evolves - that kind of ownership over product direction, not just execution, is what I'm looking for in this next role.

## Describe a messy or ambiguous problem you enjoyed working on. Why?

The one that comes to mind is when I was asked to build Azure's first proactive resilience testing capability. There was no playbook - leadership wanted a rack-level drill program but hadn't defined what success looked like, what the failure modes were, or how it would fit into existing operations. I had four months, a loose mandate, and a lot of engineering stakeholders who were skeptical it was worth doing.

What made it enjoyable was that the ambiguity forced me to go find the structure myself. I embedded with the operations and infrastructure teams, mapped the dependency graph for how rack-level failures actually propagated, and worked backwards from what a 'successful' drill would need to prove. By the time I had a concrete proposal, I had also built enough credibility with the skeptics that execution went smoothly. We delivered at a 94% recovery rate and surfaced real hardware defects that wouldn't have been caught otherwise.

I gravitate toward problems like this because the interesting work is usually in the diagnosis phase - figuring out what the actual problem is before jumping to solutions. In this case, the ambiguity wasn't a blocker, it was the signal that nobody had done the structural thinking yet. That's the part I find genuinely engaging.

## Anything else we should know about you?

I graduated in December 2024 with a CS degree from University of Houston, so I'm early in my career by years-on-paper but have been working in technical program and product roles since 2021 across Microsoft, Amazon Robotics, and a small business where I rebuilt their operational workflows from scratch. The range of those environments - a 2-person painting company to a sovereign-cloud infrastructure program at Microsoft - has given me a decent instinct for where complexity actually lives versus where it just looks complex on the surface.

I'm fully open to relocating to New York and can start within two weeks of an offer. I'd rather move fast on something I'm genuinely excited about than wait around.
