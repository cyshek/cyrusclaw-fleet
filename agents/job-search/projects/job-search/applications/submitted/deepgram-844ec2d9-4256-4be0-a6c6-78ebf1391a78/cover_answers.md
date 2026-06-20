# Cover answers — Deepgram, Solutions Architect (EST or PST) (deepgram-844ec2d9-4256-4be0-a6c6-78ebf1391a78)

## Full Name

Cyrus Shekari

## What excites you about Deepgram?

At Microsoft, I spent the last year building out Azure's post-sales customer engagement model, scaling it from a 2-person operation into a platformized system and shipping an internal AI agent that cut planning cycle time by 39%. That work sits right at the intersection of customer-facing technical problem-solving and building scalable infrastructure to multiply what a small team can do, which maps directly to how Deepgram describes the Solutions Architect role. The combination of owning complex customer engagements while simultaneously engineering repeatable solutions is exactly the kind of work I find most engaging.

Deepgram's specific technical bet is what makes this compelling beyond just the role shape. Voice AI is at an inflection point, and Deepgram is positioned as the foundational layer for that entire ecosystem, with real-time STT, TTS, and production-grade voice agents already powering 1,300+ organizations. The chance to work at the technical interface with developers and enterprises who are building on that stack, while contributing to the support infrastructure that makes the platform stickier and more scalable, is a genuinely interesting problem. The AI-first operating culture and the expectation to actively build with these tools rather than just talk about them is a strong signal that this is a team I'd fit in with quickly.

## What percentage of your time in your current/previous role involves directly interacting with customers to solve technical challenges?

In my current role at Microsoft, I'd estimate roughly 50-60% of my time involves direct customer engagement. I own post-sales technical execution for enterprise customers including Databricks, Walmart, SAP, and NetApp, which means I'm regularly on the hook for coordinating resilience drills, troubleshooting production-environment issues, and serving as the technical bridge lead during high-stakes recovery executions. One example is a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract where I coordinated directly across engineering and infrastructure teams with the customer under executive visibility.

The remaining time is split between building internal tooling to scale that engagement model and analyzing failure patterns to surface product improvement opportunities, which I'd characterize as customer-adjacent work that still feeds back into the customer experience. So while the direct interaction number sits around 50-60%, the broader customer-impact scope is closer to 80-90% of what I own on any given week.

## What approaches have you used to translate customer needs into technical solutions?

My most consistent approach is starting with structured discovery before jumping to solutions. At Microsoft, I conducted resilience planning sessions with enterprise customers to surface what they actually needed from availability testing, then translated those requirements into product specifications for our internal Resilience Automation Platform, including self-service scheduling capabilities that reduced operational toil by 30%. The key was separating what customers said they wanted from what the underlying problem actually was.

During my 2023 internship, I ran 11+ user interviews with Azure service teams to identify critical feature gaps in a developer tooling product. Rather than taking requests at face value, I mapped them to patterns, prioritized by impact, and secured stakeholder buy-in to ship intent-based YAML generation as a high-value self-service capability. That same pattern-to-prioritization approach carried into Amazon Robotics, where I mapped dependencies across 1,200+ stations during a legacy OS migration and translated operational constraints into a phased execution strategy that hit zero downtime.

The common thread across all of these is treating the customer interaction as a discovery process first, then building the technical solution around what the data and conversations actually reveal rather than what the first ask sounds like.

## What tools or methods have you used to scale your technical expertise across multiple customer engagements?

The biggest lever I've used is documentation and tooling that lets customers self-serve before they need to escalate. At Microsoft, I restructured our internal knowledge base with rigorous metadata standards and migrated it to an AI-powered semantic search tool, which reduced lookup time by 83% and let support teams resolve issues faster without pulling in senior engineers every time. That same principle applies to customer-facing resources, not just internal ones.

On the automation side, I built an internal AI agent for drill planning that cut planning cycle time by 39% and increased drill capacity by 21%. The goal was to codify the expertise that previously lived in one or two people's heads into a repeatable system that any team member could run. I also built a Power BI dashboard during my 2022 internship to surface toil patterns across 140+ teams, which gave leadership the visibility to target automation investments rather than making ad hoc decisions.

More broadly, I think about scalability as a forcing function when designing any customer-facing process. If solving a problem requires me to be in the room every time, that's a design flaw, not a solution. The goal is always to solve it once in a way that the next ten customers benefit from without additional marginal effort.

## What is the most impressive thing you've personally built or automated with AI? Describe exactly what you did, how it worked, and the measurable outcome

The most impactful thing I've built is an internal AI agent for resilience drill planning at Microsoft. The problem was that our drill planning process required significant manual coordination, pulling in information from multiple sources, resolving scheduling conflicts, and producing execution briefs that took hours per engagement. As we scaled from a small operation to 45+ annual drills, that overhead was becoming a ceiling on how much the team could actually execute.

I built the agent to ingest drill parameters, historical execution data, and infrastructure dependency information, then generate structured planning artifacts and flag potential conflicts automatically. The underlying approach combined LLM-based reasoning for the synthesis and recommendation layer with structured data lookups against our internal systems. I defined the architecture, wrote the integration logic connecting the agent to our data sources, and iterated on the prompt and workflow design based on output quality against real past engagements.

The measurable outcome was a 39% reduction in planning cycle time and a 21% increase in drill capacity, meaning the same team could execute meaningfully more engagements without adding headcount. Beyond the numbers, it shifted how the team operated. Senior engineers stopped getting pulled into routine planning tasks and could focus on the higher-complexity execution and customer engagement work. That shift from manual to scalable is the part I'm most proud of, because the artifact that matters isn't the agent itself but the capacity it unlocked.
