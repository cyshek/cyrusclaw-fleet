# Cover answers — Cursor, Forward Deployed Engineer (cursor-34cecd0c-c392-4454-8ef5-261310541011)

## Tell us about a time you convinced a technical audience to adopt a new solution or tool. What was the resistance and how did you handle it?

During my 2023 internship at Microsoft, I was tasked with driving adoption of an AI-driven code generation tool across 14 Azure service teams. The resistance was real: senior engineers were skeptical that an LLM could generate YAML pipelines that met their service's specific compliance and reliability bar, and a few had already tried earlier generations of codegen tools that produced unusable output.

Instead of pushing harder on demos, I ran 11+ discovery interviews to understand the exact friction points, the YAML patterns they actually wrote, the edge cases that broke prior tools, and where they didn't trust the output. That gave me concrete evidence to take back to the product team, and I scoped intent-based YAML generation into the roadmap with a prompt-iteration plan tied to the failure modes engineers had flagged. Once engineers saw their own pain points reflected in the v2, adoption picked up and the workflow ended up saving 37 engineering hours monthly.

The lesson I carried forward: technical audiences don't adopt tools because of polish, they adopt them when you've clearly heard their objections and shipped against them. I used the same playbook later at Microsoft when rolling out the Resilience Automation Platform to partner teams.
