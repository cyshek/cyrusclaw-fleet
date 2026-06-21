# Cover answers — Restate, Forward Deployed Engineer (restate-ac039096-a44d-4ae6-9f57-50ab4b7d97d6)

## Full Name

Cyrus Shekari

## Tell us about a time you helped a customer  go from early POC to successful production. What were the hardest blockers, and what did you do to unblock them?

At Microsoft, I owned the end-to-end path from early concept to production for Azure's rack-level resilience drill program. It started as a novel capability with no existing playbook - we had a hypothesis that proactive hardware-level testing could surface defects before they caused customer outages, but nothing was standardized, no tooling existed, and no one had done it before at this scope inside Azure. My job was to take that early-stage idea and turn it into a repeatable, production-grade program in four months.

The hardest blockers were coordination complexity and undefined production-readiness criteria. We were touching infrastructure across multiple hardware teams, datacenter operations, and customer-facing service owners simultaneously, and everyone had a different mental model of what 'ready' meant. I resolved this by doing what amounted to structured discovery with each stakeholder group - mapping dependencies, surfacing conflicts early, and then defining a shared production-readiness checklist that all teams could sign off on before each drill executed. That shared definition was the unlock. Without it, every rollout would have stalled on ambiguity. We hit a 94% recovery rate on the first production run, and the reference implementation I built from that first drill became the reusable pattern for every subsequent one.

A second hard blocker was operational toil killing our ability to scale. Early on, everything was manual - scheduling, status tracking, escalation routing. I led the 0-to-1 build of an internal automation platform that codified the PoC-to-production workflow, reduced operational toil by 30%, and let us scale to 45+ drills annually without proportional headcount growth. The pattern I kept coming back to was: find the repeated manual step, turn it into a documented standard, then automate it. That loop is essentially what I'd be doing in this role at Restate - just applied to customer adoptions instead of internal infrastructure programs.
