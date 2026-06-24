# Cover answers — Heygen, Forward Deployed Engineer, Strategic Accounts (heygen-5113581007)

## Point us to one thing you've personally shipped to production that used LLMs, generative models, or real-time AI. A repo, a demo link, a blog post, a loom, or 2–3 sentences is all we need.

I built and shipped an internal AI agent for Azure resilience drill planning that used LLM prompt engineering and eval harnesses to restructure how program managers scoped and scheduled drills. It cut planning cycle time 39% and increased drill capacity 21%, and the prompt patterns and eval scaffolding got reused across follow-on partner engagements. Earlier at Microsoft I also shipped an LLM-powered semantic search over our internal docs with strict metadata standards and an eval signal, which cut lookup time 83% and became a reusable RAG pattern for adjacent platform teams.

## In the last 2 years, what's the largest enterprise deployment you personally owned end-to-end (scoping through production)? Please provide one sentence on the customer type, one on what you shipped, one on the outcome.

Customer type: Fortune 500 strategic Azure accounts including Databricks, Walmart, SAP, and NetApp, plus a sovereign-cloud enterprise tied to a $1.5B+ contract. What I shipped: Azure's first proactive resilience testing capability, delivered as a platformized production system with APIs, webhooks, and self-service scheduling that plugged into partner engineering stacks, plus a rack-level drill program I owned from discovery through rollout. Outcome: 45+ annual drills sustained, a 94% recovery rate, $14M+ in business impact, and critical hardware defects surfaced before they hit production.
