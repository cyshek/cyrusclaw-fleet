# Cover answers — Smartcatplatforminc, Forward Deployed Engineer (smartcat-5841901004)

## What is the most innovative AI-first solution you delivered to a client? What impact did it have?

At Microsoft, I designed and shipped an internal AI agent with prompt-engineered planning workflows that automated the most manual parts of Azure's resilience drill execution. The agent ingested customer environment context, generated drill plans, and orchestrated handoffs that previously required a senior engineer to scope by hand. It cut cycle time by 39% and grew our drill capacity by 21%, which directly translated into more enterprise customers (Databricks, Walmart, SAP, NetApp) getting validated resilience coverage without us linearly scaling headcount.

The broader impact was that it changed how the team operated. We went from a 2-person team running a handful of drills to 45+ annual customer drills, and the LLM-powered automation became embedded in the customer-facing delivery motion rather than sitting as an internal tool. It also surfaced patterns in customer environments we hadn't seen before, which fed back into roadmap priorities for the Resilience Automation Platform.

## What has been the most challenging pre-sales technical demo / Proof of Concept that you delivered? What made it challenging and what was the result?

The hardest technical proof I led was Azure's first proactive rack-level resilience drill, tied to a sovereign-cloud network isolation go-live attached to a $1.5B+ enterprise contract. The challenge was that no one had run a destructive test at that blast radius against production infrastructure before, so I had to earn trust from skeptical engineering partners, customer executives, and internal risk reviewers in parallel, while the technical design itself was still being validated.

I shipped the rack-level drill program in 4 months and we hit a 94% recovery rate on the first execution. It surfaced critical defects that would have otherwise hit the customer in production, and gave the account team the technical proof they needed to close the go-live milestone. It also became the template for 14 cross-org executions I bridged under executive visibility.

The lesson I took into every demo after that: pre-sales technical credibility isn't about a polished slide, it's about being the person in the room who can answer the uncomfortable failure-mode question honestly and still land the outcome.
