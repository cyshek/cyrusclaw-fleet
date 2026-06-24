# Cover answers — Cursor, Product Manager, Agent Harness (cursor-69abc2ba-2823-40c3-9b86-94ab63859649)

## Please write a short note on a project you're proud of:

At Microsoft, I built an internal AI agent for Azure drill planning that I'm genuinely proud of. The planning process was painful: engineers had to gather scope, dependencies, blast radius, and stakeholder context across dozens of teams before a single drill could run. I designed an agent that decomposed planning into tool-augmented subtasks, pulled context from our internal systems, and produced a draft plan a human could steer and edit, with guardrails on what the agent was allowed to autonomously decide versus surface for review.

The hard part wasn't wiring up the tools, it was figuring out where the agent should stop. Early versions over-reached and produced confident but wrong dependency maps, so I spent a lot of time reading traces, classifying failure modes, and tightening the harness around the steps where the model was unreliable. I also built a lightweight eval set from past drills so we could measure whether changes actually improved plan quality instead of just feeling better.

The result was a 39% cut in planning cycle time and a 21% increase in drill capacity, but the part I care about more is that it changed how the team thought about agent work generally: as something you measure, constrain, and iterate on, not something you ship once and hope.
