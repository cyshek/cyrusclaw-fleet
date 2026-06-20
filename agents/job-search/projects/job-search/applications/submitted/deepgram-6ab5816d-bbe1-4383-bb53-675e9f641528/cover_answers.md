# Cover answers — Deepgram, Solutions Engineer, Enterprise (deepgram-6ab5816d-bbe1-4383-bb53-675e9f641528)

## What excites you about Deepgram?

At Microsoft I've spent the last two years embedding with enterprise customers like Databricks, Walmart, and SAP to take ambitious Azure resilience deployments from scoping through go-live, including a sovereign-cloud network isolation test tied to a $1.5B+ contract that had to work flawlessly on day one. That work taught me that the hardest and most rewarding part of enterprise infrastructure is making it actually work in the customer's real environment, not just in a demo. The Solutions Engineer role at Deepgram is exactly that job, applied to a problem space (voice AI in live restaurant operations) where the stakes are immediate and measurable.

Deepgram specifically excites me because voice is the interface where latency, accuracy, and cost tradeoffs actually decide whether a product ships or dies, and you've built the foundation models and self-hosted options that let enterprises take it seriously. Restaurants are a brutal proving ground: noisy environments, POS integrations, menu edge cases, and fleets at scale. I want to be the person embedded with those customers, writing the code and playbooks that turn each deployment into leverage for the next one.

## If yes to question above, briefly describe one example.

The clearest example is the rack-level resilience drill I shipped at Azure in four months with a 94% recovery rate. I had to embed with hardware, networking, and service teams, debug actual production hardware defects in live environments, and adapt the validation framework to constraints nobody had documented. It became the new model for continuous validation across the fleet, and the patterns I codified got reused across 45+ annual drills. That loop, ship something real with a customer, then turn it into reusable infrastructure, is exactly what this role is asking for.

## Which sales methodologies (e.g., MEDDIC, Triangle, Solution Selling) have you worked with in technical pre-sales contexts?

My background is product and program management rather than formal pre-sales, so I haven't run a deal cycle under a named methodology like MEDDIC end to end. That said, I've done the underlying motions repeatedly: running technical discovery with 20+ Azure service teams to quantify 81 hours of manual toil per region launch, mapping decision criteria and champions across cross-org recovery executions, and translating customer pain into scoped technical commitments. I'm comfortable picking up MEDDIC or Solution Selling quickly and applying it rigorously, and I'd lean on the Deepgram sales team to learn the house standard fast.

## What tools or technologies have you used to demonstrate technical solutions to customers?

I've demoed and integrated technical solutions across a mix of API-driven platforms, internal tooling, and dashboards. At Microsoft I ran hands-on demos and integration support for an AI-driven code generation platform across 14 Azure service teams, walking engineers through APIs, YAML configuration, and migration paths until they were productive. I've used Power BI to build executive-facing dashboards that made operational data legible to non-technical stakeholders, and I regularly work in Slack, customer Git repos, and live debugging sessions to walk teams through API integrations and webhook flows.

For solutioning and prototyping I lean heavily on AI coding tools to spin up working integrations quickly, plus the usual stack of Postman, curl, and notebook environments for showing APIs end to end. The common thread: I'd rather show a customer working code in their own environment than walk them through a slide.

## If yes to above, which programming languages, and what was the most complex application or solution that you built?

I work primarily in Python and SQL, with regular use of YAML, JavaScript, and shell for integration and automation work, plus C++ and Java from my CS coursework at the University of Houston.

The most complex thing I've built is the internal Resilience Automation Platform at Azure, a 0→1 system where I defined the APIs, self-service workflows, and reference architectures that let service teams run resilience drills without manual coordination. It cut operational toil by 30% and became the substrate for 45+ annual drills across the fleet. The hard part wasn't any single component, it was making the platform flexible enough to handle wildly different customer service topologies (Databricks vs. SAP vs. sovereign cloud) while still codifying repeatable patterns. That's the same shape of problem as adapting Deepgram's platform to each restaurant brand's menu, POS, and ordering flow.

## What is the most impressive thing you've personally built or automated with AI? Describe exactly what you did, how it worked, and the measurable outcome

I built an internal AI agent for drill planning at Azure that restructured how my team scoped and sequenced resilience exercises. The agent used LLM-powered workflow automation to ingest drill requirements, pull from historical drill data and service dependency maps, and generate a structured plan (scope, participants, risk areas, runbook skeleton) that previously took a program manager days of meetings to assemble. I wired it into our existing planning tools so the output dropped directly into the workflows the team already used.

The measurable outcome: planning cycle time dropped 39% and we expanded drill capacity 21% with the same headcount. The bigger unlock was cultural, it proved to a traditionally process-heavy org that AI agents could replace coordination toil rather than just summarize meetings, and it became a reference point for other TPMs building their own agents. That experience of taking a real operational bottleneck, building an AI tool to kill it, and getting the team to adopt it is exactly the mindset I'd bring to scaling Deepgram deployments.
