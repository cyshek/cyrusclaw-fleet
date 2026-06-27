# Cover answers — Cursor, Product Manager, Agent Harness (cursor-69abc2ba-2823-40c3-9b86-94ab63859649)

## Full Name

Cyrus Shekari

## Please write a short note on a project you're proud of:

At Microsoft, I built an internal AI agent to automate drill planning workflows for Azure's resilience program. The agent used LLM-powered task decomposition to break complex drill plans into structured execution steps, cutting planning cycle time by 39% and increasing overall drill capacity by 21%. What made it hard was that the failure modes were non-obvious - the agent would loop on ambiguous inputs or take unproductive paths when task dependencies weren't clearly defined. I spent a lot of time reading execution traces, identifying where things broke down, and translating those patterns into concrete changes to the decomposition logic and retry behavior.

I'm proud of it because it wasn't just a demo - it ran on real workloads with real stakes. And the process of defining evaluation criteria, analyzing trace failures, and iterating on the harness is exactly the kind of work I find most interesting. Shipping a capable agent is one thing; building the framework that makes it reliably useful is a different and harder problem, and that's the one I want to keep working on.
