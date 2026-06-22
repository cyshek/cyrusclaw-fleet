# Cover answers — Tenexlabs, Forward Deployed Engineer (tenex-2a359a2a-d5ed-48e8-96b8-b93826110ee9)

## Full Name

Cyrus Shekari

## What did you study in college?

Bachelor of Science in Computer Science with a minor in Mathematics from the University of Houston. Coursework covered data structures, algorithms, databases, artificial intelligence, and machine learning. Graduated with a 3.8 GPA and was inducted into Phi Beta Kappa.

## What specifically interests you about joining Tenex at this stage? What's driving your interest in making a move right now?

At Microsoft I've spent the last two years doing work that maps closely to what Tenex describes as forward deployment - embedding in client engagements, owning architecture and outcome end-to-end, and building AI systems that had to run in production without hand-holding. I led the 0-to-1 build of a resilience automation platform, served as bridge lead on a $1.5B+ sovereign-cloud engagement with 14 cross-org recovery executions under executive visibility, and built an internal AI agent for drill planning that cut cycle time by 39% and compounded across every subsequent engagement. Those are the kinds of problems and stakes I want more of, not less.

What draws me to Tenex specifically is the model: elite teams embedded directly into Fortune 500 operations, with formal partnerships at Anthropic and OpenAI and a mandate to ship AI systems that actually change how businesses run. That's meaningfully different from being a downstream integrator or a consulting firm that delivers a deck. The uncapped throughput model also signals something real about how the firm thinks about engineering output - I want to be in an environment where the work I ship is measured and rewarded directly, not averaged into a team score. The timing is right because the problems Tenex is taking on are the most interesting ones in the industry right now, and I want to be building at that frontier while it's still being defined.

## Tell us about a technical decision you got meaningfully wrong. What did it cost (time, money, downtime) and what do you do differently now? Give us a number if you can.

When I built the initial version of the internal AI agent for drill planning at Microsoft, I designed it as a tightly coupled workflow where the planning logic, the scheduling triggers, and the output formatting were all bundled into a single pipeline. My reasoning at the time was speed - I wanted to ship fast and the integration points felt stable enough. They weren't. When upstream data schemas shifted during a platform migration, the whole pipeline broke, and we lost roughly three weeks of iteration time rebuilding what should have been modular components. That's time that came directly out of the 39% cycle-time improvement I eventually documented - the real number would have been higher if we hadn't burned those weeks on rework.

What I do differently now is enforce clear separation between the data ingestion layer, the reasoning/orchestration layer, and the output layer from the start, even when it feels like overhead on a fast-moving build. I also build explicit schema contracts at integration boundaries and write tests against those contracts before I wire up the components. The extra day upfront has paid back multiples every time a downstream dependency has changed since - which, in enterprise codebases, is always.

## What's a widely accepted engineering practice, tool, or trend you think is overrated? What do you do instead?

Comprehensive pre-production documentation for AI agent systems. There's a common instinct, especially in enterprise environments, to spec out the full agent architecture, write detailed design docs, and get alignment before writing a line of code. In theory that's responsible engineering. In practice, for agentic systems specifically, the design doc is almost always wrong by the time you run the first real workflow against production data - the edge cases you couldn't anticipate from a whiteboard dominate the actual behavior.

What I do instead is ship a minimal but genuinely production-wired prototype as fast as possible, then document what I learn from running it. Not a demo, not a sandbox - something that touches real data and real integrations, even if it's limited in scope. The friction that surfaces in the first week of real operation tells you more about the architecture you actually need than any amount of upfront design. I still write design docs, but I treat them as living artifacts that trail the build rather than constrain it. The resilience automation platform I built at Microsoft went through three significant architectural changes in the first six weeks precisely because real usage exposed things no spec would have predicted.

## What's something you understand unreasonably well  (Postgres internals, a niche protocol, vim, anything) and what's one non-obvious thing about it that most engineers get wrong?

Azure's resilience and fault injection model - specifically how rack-level and fault domain isolation actually behaves versus how it's documented and how most teams reason about it. I spent months running and iterating on proactive rack-level resilience tests, including the first of that type shipped in Azure's enterprise deployment history, and the gap between the theoretical blast radius and the real blast radius under load is consistently surprising.

The non-obvious thing most engineers get wrong is assuming that fault domain separation at the infrastructure layer gives you recovery isolation at the application layer. It often doesn't. When we ran our first rack-level tests, workloads that were nominally spread across fault domains still exhibited cascading recovery failures because the application-level coordination logic - health checks, leader election, connection pool reinitialization - had implicit timing dependencies that only surfaced under real partition conditions. The 94% recovery rate we eventually achieved required fixing things above the infrastructure layer that most teams never instrument because they trust the platform abstraction to handle it. The platform handles the hardware. The application logic is still yours.

## Link something you've built that you're proud of (repo, PR, demo, launch, blog post). In 3–4 sentences, what would you change about it today?

The most concrete public artifact I can point to is my GitHub at github.com/cyshek, though the most significant production work I've shipped - the resilience automation platform, the AI drill-planning agent, the rack-level testing capability - lives inside Microsoft's internal systems and isn't publicly shareable. The internal AI agent for drill planning is probably what I'm most proud of in terms of real-world impact: it cut planning cycle time by 39%, increased drill capacity by 21%, and those gains compounded across every client engagement that came after. If I were rebuilding it today, I'd decouple the orchestration layer from the scheduling logic much earlier, invest in better observability from day one rather than retrofitting it, and design the human-review checkpoints as first-class components rather than adding them as guardrails after the fact. The core workflow held up, but the architecture made iteration slower than it needed to be.
