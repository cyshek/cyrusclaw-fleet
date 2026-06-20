# Cover answers — Clipboard, Tooling Program Manager (clipboard-80f1fd1c-7b09-4d6e-9a0b-e234fc9672b8)

## Full Name

Cyrus Shekari

## Describe something you built from scratch. Go five levels deep — what it was, why you built it, what the architecture looked like, what broke, and what you'd do differently.

At Microsoft I built Azure's internal Resilience Automation Platform from 0 to 1, taking it through discovery, scoping, build, and launch. The why: our resilience validation work was a manual, 2-person operation that couldn't scale. We were running drills by hand, and the operational toil meant we capped out well below the demand we were seeing across enterprise customers. I built it to turn that bespoke, person-dependent process into self-service tooling the whole team could run.

The architecture was a self-service platform layer sitting on top of our drill execution workflows, with an AI agent handling the planning side. I anchored the design from first principles around workflows, dependencies, and tradeoffs rather than features: standardized the drill workflows so they could be templated, built the automation to drive execution, and layered in an AI agent that restructured how planning happened. The outcome was a 30% reduction in operational toil, a 39% cut in planning cycle time, and a 21% increase in drill capacity, which let us sustain 45+ annual drills.

What broke: early on I underestimated how much the planning workflow itself, not just the execution, was the bottleneck. The first cut automated execution but left planning manual, so we just moved the constraint. That's what pushed me to build the AI agent and restructure planning, which is where the real cycle-time gains came from. What I'd do differently: instrument the toil measurement up front. We eventually built a Power BI dashboard to quantify toil across teams, and if I'd had that signal from day one I'd have attacked the planning bottleneck first instead of discovering it mid-build. The lesson stuck with me. Measure where the time actually goes before you decide what to automate.

## Describe your experience building & scaling Technical Operations teams and/or 10’xing technical delivery for an operational domain.

My core experience here is scaling Azure's resilience validation portfolio from a 2-person operation into a platformized program. That meant defining the quarterly roadmap, standardizing the workflows, and building the tooling that let a small team sustain 45+ annual drills and drive $14M+ in business impact. The leverage came from systems, not headcount: I pioneered Azure's first proactive resilience testing capability in 4 months with a 94% recovery rate, and used AI-driven automation to cut planning cycle time by 39% and increase capacity by 21%. That's the closest thing I have to 10x'ing delivery for an operational domain, multiplying what a small team could execute by replacing manual effort with self-service tooling.

The operational realities ran through everything. I directed 14 recovery executions under executive visibility and served as bridge lead on a sovereign-cloud isolation test tied to a $1.5B+ contract, which meant navigating Ops, Engineering, and Product and resolving friction directly rather than escalating. As an intern I also drove tooling adoption across 14 teams and built a Power BI dashboard tracking operational toil across 140+ teams, so I've worked the discovery and prioritization side of operations at scale too.

On the team side, I've partnered directly with Operations leadership to set efficiency targets and mentored junior contributors to raise the team's delivery velocity and ownership. I'm honest that I've been a senior IC and mentor rather than a formal people manager, which is exactly why a role with a path to management interests me. I've already been holding the execution bar and developing people informally, and I want to do that with real ownership.

## If you selected "other", please tell us how you heard about the position.

I found the role through Clipboard's public job listing on Ashby.
