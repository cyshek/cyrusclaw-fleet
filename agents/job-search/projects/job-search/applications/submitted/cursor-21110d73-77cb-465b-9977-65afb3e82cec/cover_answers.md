# Cover answers — Cursor, Product Manager, Cloud Agents (cursor-21110d73-77cb-465b-9977-65afb3e82cec)

## Please write a short note on a project you're proud of:

At Microsoft, I built an AI agent for drill planning on top of LLM workflows and Copilot Studio that restructured how our team scoped and executed resilience drills. The planning loop had been the bottleneck for years, so I rewrote it end-to-end: how a planner describes intent, how much context the agent receives, how ambiguity gets resolved, and how the output gets reviewed. Cycle time dropped 39% and drill capacity went up 21%, all under executive review on infra work where mistakes are expensive.

The part I'm proudest of is that it actually got trusted. Engineers on high-stakes recovery executions started relying on agent-authored plans instead of treating them as a curiosity, which is the hardest threshold to cross with AI tooling. To get there I spent a lot of time on the legibility layer, what artifacts the agent produced, how reviewers could verify work without reconstructing the session, and where humans needed to stay in the loop. That trust then unlocked the broader platform play: 45+ annual drills, $14M+ in business impact, and a continuous validation model that customers like Databricks and SAP now depend on.

It's the closest analog I have to what Cloud Agents is building, agents running autonomously on infra work, returning artifacts a human can review in minutes, and earning enough trust that people hand off real tasks and move on.
