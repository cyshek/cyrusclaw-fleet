# Cover answers — Deepgram, Forward Deployed Engineer, Deepgram for Restaurants (deepgram-a58e4a11-7f98-4686-98e8-2612b52d7bbd)

## Full Name

Cyrus Shekari

## What excites you about Deepgram?

My work at Microsoft has been fundamentally about taking complex technical systems and making them work reliably at enterprise scale - building the playbooks, reference architectures, and tooling that turn one-off deployments into repeatable, scalable programs. I led the 0 to 1 build of an internal Resilience Automation Platform, served as the embedded technical partner on a sovereign-cloud test tied to a $1.5B+ contract, and translated live production observations into product requirements that shaped the platform roadmap. That loop of deploying, observing, codifying, and feeding back is exactly what this role is asking for.

What draws me specifically to Deepgram is the bet you are making on voice as a native infrastructure layer, not a feature bolted onto something else. The restaurant vertical is a genuinely hard deployment environment - noisy, high-throughput, latency-sensitive, deeply integrated with POS and ordering systems - and the Forward Deployed Engineer model means the work is real-world, not theoretical. I want to be in the room where the deployment either works or it does not, own that outcome, and build the patterns that make the next one faster. Deepgram processing over 50,000 years of audio and sitting at the center of the emerging voice AI economy is exactly the kind of technical foundation I want to be building on.

## If yes to question above, briefly describe one example.

At Microsoft, I served as the bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract. I was the embedded technical partner between the customer's engineering team and Microsoft's internal teams, coordinating a live production drill that required precise sequencing across multiple organizations and zero margin for error. The deployment worked, the customer's confidence in the platform increased, and the pattern I helped establish became a reference for future sovereign-cloud engagements. That combination of high-stakes live deployment, cross-org trust-building, and codifying what worked for reuse is the exact motion I am looking to bring to Deepgram's restaurant deployments.

## Which sales methodologies (e.g., MEDDIC, Triangle, Solution Selling) have you worked with in technical pre-sales contexts?

My exposure to formal sales methodologies has been adjacent rather than direct. At Microsoft, I facilitated technical discovery sessions with enterprise customers and prospects - mapping their operational pain points, surfacing integration requirements, and building the technical case for platform capabilities. That work has strong overlap with MEDDIC-style discovery, particularly around identifying metrics, understanding the economic buyer's concerns, and mapping decision criteria during scoping conversations.

I have not held a dedicated pre-sales title, but I regularly operated in that zone - especially during the scoping phase of new enterprise deployments where I was translating customer requirements into architectures and building the credibility needed to move deals forward technically. I am familiar with Solution Selling framing from working alongside account teams on complex enterprise engagements and am confident I can get up to speed quickly on whatever methodology Deepgram's sales team uses.

## What tools or technologies have you used to demonstrate technical solutions to customers?

At Microsoft, I used Azure portal walkthroughs, live drill simulations, and Power BI deployment dashboards to give customers and executive stakeholders real-time visibility into operational outcomes. I built a Power BI dashboard tracking toil across 140+ teams that became a key artifact in both internal reviews and customer-facing conversations about automation progress and go-live timelines.

Beyond dashboards, I ran hands-on demos and integration sessions when I championed AI-driven code generation adoption across 14 Azure service teams - those sessions were essentially live technical demonstrations designed to build confidence and drive behavior change in engineering teams. I also used structured documentation, reference architectures, and playbooks as demonstration artifacts during discovery and solutioning phases, helping customer engineering teams visualize how a deployment would actually work before a line of integration code was written.

## If yes to above, which programming languages, and what was the most complex application or solution that you built?

I work primarily in Python, with exposure to SQL, YAML, and scripting for automation and data workflows. The most complex thing I built is the internal AI agent for drill planning at Microsoft. The problem it solved was a planning cycle that was manual, fragmented, and bottlenecked on a small team - each resilience drill required significant coordination overhead to schedule, configure, and validate before execution.

I built an agent that restructured the planning workflow end to end, pulling in relevant operational context, generating drill configurations, and surfacing scheduling recommendations based on historical patterns and customer constraints. It was not a simple prompt wrapper - it required designing the right data inputs, building reliable output structures the downstream process could actually consume, and iterating on failure modes until the outputs were trustworthy enough to act on. The result was a 39% reduction in planning cycle time and a 21% increase in deployment capacity. That project taught me a lot about where AI tooling actually earns trust in an operational context versus where it creates new failure modes if you are not careful.

## What is the most impressive thing you've personally built or automated with AI? Describe exactly what you did, how it worked, and the measurable outcome

The most impactful AI build I have done is the drill planning agent at Microsoft. The context: I was running Azure's resilience drill program, which had scaled to 45+ annual drills across enterprise customers including Databricks, Walmart, SAP, and NetApp. Planning each drill was heavily manual - pulling together customer environment context, configuring test parameters, coordinating scheduling windows, and validating readiness criteria. The process was a bottleneck that limited how many drills we could run and how fast we could move.

I built an internal AI agent that automated the core planning cycle. It ingested operational data about customer environments and historical drill records, used that context to generate structured drill configurations and scheduling recommendations, and surfaced decision points for human review rather than burying the operator in raw output. The architecture was designed around the failure modes I had seen in earlier automation attempts - places where unchecked AI output would have created downstream coordination problems - so I built explicit validation checkpoints and structured outputs the rest of the workflow could consume reliably.

The measurable outcome was a 39% reduction in planning cycle time and a 21% increase in deployment capacity. Those numbers translated directly into more drills executed per quarter, faster customer response times, and more headroom for the team to focus on the higher-judgment parts of the work. It also became the model for how I think about AI tooling in operational contexts - the goal is not to automate everything, it is to automate the right things and make the human decision points faster and better-informed.
