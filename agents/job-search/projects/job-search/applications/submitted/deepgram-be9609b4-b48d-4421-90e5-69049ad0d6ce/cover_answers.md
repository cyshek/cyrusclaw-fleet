# Cover answers — Deepgram, Solutions Architect (San Francisco, CA) (deepgram-be9609b4-b48d-4421-90e5-69049ad0d6ce)

## What excites you about Deepgram?

At Microsoft I've spent the last two years owning post-deployment technical engagements for enterprise Azure customers like Databricks, SAP, and Walmart, and the work I'm proudest of is the stuff that turns repeated customer pain into platformed solutions, like the Resilience Automation Platform I led 0→1 that cut operational toil 30%, or the LLM-powered drill planning agent that grew capacity 21% while freeing engineers for higher-leverage work. The Applied Engineering role reads like exactly that pattern at a faster clip: own the customer, resolve the hard technical issues, then build the automation so the next ten customers don't need to file the same ticket.

Voice is also the AI surface I'm most excited about right now. The latency, accuracy, and cost tradeoffs in real-time STT and voice agents are genuinely hard, and Deepgram is the rare company shipping voice-native foundation models that customers like Twilio and Vapi are betting production traffic on. Being in San Francisco close to those developers, helping them get to production and feeding the patterns back to product, is the kind of seat I want next.

## What approaches have you used to translate customer needs into technical solutions?

My default is to start with structured discovery, then quantify the pain before I propose anything. During my 2022 Microsoft internship I ran sessions with 20+ Azure service teams to measure manual toil per region launch, landed on 81 hours, and used that number to build a prioritized automation roadmap that ultimately accelerated region launches 28% and unlocked $3M in revenue. The discipline is the same whether the customer is internal or external: get the real data, rank by leverage, then ship the smallest thing that moves it.

For external customers, I do the same on escalations. As technical escalation lead on 14 cross-org recovery executions, including a sovereign-cloud network isolation test tied to a $1.5B+ contract with strict latency and isolation requirements, my job was to translate ambiguous customer constraints into a concrete test plan and acceptance criteria the engineering team could execute against. I also intern-tested this from the product side, conducting 11+ structured interviews with Azure service teams to translate qualitative pain into prioritized intent-based YAML generation features for the roadmap.

The last piece is closing the loop. I partner with product and engineering to convert recurring support patterns into roadmap items and self-service tooling so the fix scales past the one customer who reported it.

## What tools or methods have you used to scale your technical expertise across multiple customer engagements?

The biggest lever has been productizing the work. At Microsoft I took resilience validation from a 2-person manual operation and led the 0→1 build of an internal Resilience Automation Platform, authoring the PRDs, APIs, and self-service scheduling workflows in Python so customers could drive their own drills. That shift sustained 45+ annual drills and drove $14M+ in business impact without scaling headcount linearly, because the platform absorbed the repetitive parts of every engagement.

Documentation and search are the second lever. During my 2023 internship I migrated internal docs to an AI-powered semantic search experience with enforced metadata standards, cutting customer lookup time 83% and measurably reducing inbound questions on common configuration issues. Pairing good self-service content with a search layer that actually finds it deflects the long tail of repeat questions.

Third is automation around my own workflow. I built an internal AI agent for drill planning using LLM-powered automation and RAG over historical telemetry, which cut planning cycle time 39%. The pattern I keep coming back to: handle the customer well once, then encode the reasoning into a tool, a doc, or an agent so the next engagement starts at a higher floor.

## What is the most impressive thing you've personally built or automated with AI? Describe exactly what you did, how it worked, and the measurable outcome

The drill planning AI agent I built at Microsoft. Planning a resilience drill at Azure scale meant pulling together historical telemetry, prior drill outcomes, service dependencies, and runbook context, then drafting a plan a TPM could review. It was the most repetitive, judgment-heavy part of my week, and it was the bottleneck on how many drills the team could run.

I built an agent that ran RAG over our historical drill telemetry and post-mortems, plus structured service metadata, and used an LLM to draft the initial plan: scope, blast radius, dependencies to coordinate with, recovery validation steps, and a risk summary. I wired it into our existing scheduling workflow so a TPM could accept, edit, or reject sections rather than starting from a blank doc. The grounding in real telemetry was what made the output trustworthy enough to actually use, versus generic LLM suggestions that hallucinate dependencies.

Outcome: planning cycle time dropped 39% and total drill capacity grew 21%, which let the team take on more customer-driven validations and freed senior engineers to focus on pre-sales design work and harder escalations. It's the project that most convinced me that the highest-leverage AI work right now is wrapping models around real operational data, not building from scratch.
