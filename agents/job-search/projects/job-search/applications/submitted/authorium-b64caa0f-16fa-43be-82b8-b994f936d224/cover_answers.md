# Cover answers — Authorium, Associate Solutions Engineer (authorium-b64caa0f-16fa-43be-82b8-b994f936d224)

## Full Name

Cyrus Shekari

## Describe a time when a customer asked you to configure a solution in a way that you knew was inefficient or unscalable. How did you guide them toward a better decision without damaging the relationship?

When I was building the internal Resilience Automation Platform at Microsoft, several partner service teams wanted us to keep running their recovery drills the way they always had, which meant a lot of manual, one-off configuration per team. It was familiar to them, but it didn't scale and it created a ton of operational toil. A few teams pushed back hard because they trusted the old process and didn't want to risk a failed drill.

Instead of telling them their approach was wrong, I co-led discovery sessions to understand what they actually cared about, which was reliability of the drill and not the specific mechanics. Once I framed the conversation around the business goal, I walked them through how a reusable, template-driven setup would give them the same outcome with less effort and fewer error points. I showed them as-built documentation and early results so it wasn't abstract.

That let me move the conversation from defending the old way to comparing outcomes. We transitioned execution to a scalable self-service model, cut operational toil by 30%, and the teams stayed bought in because they felt heard and saw the proof. Keeping it grounded in their goals instead of my preferences is what protected the relationship.

## Walk us through a specific complex workflow or process you owned from discovery to configuration. How did you document the logic, and how did you validate that it actually met the business need?

At Microsoft I owned the delivery of Azure's recovery validation program end to end. It started with discovery: I co-led sessions with 20+ partner service teams to capture requirements and action items, then translated those into standardized rack-level drill configurations and workflows. The conditional logic mattered a lot here, since a drill had to branch based on hardware state, recovery sequencing, and dependencies across data flows.

For documentation, I drafted design docs, workflow logic diagrams, and configuration notes, and I kept as-built records that reflected the final state of each environment. That made handoffs clean and gave QA something accurate to work from. I treated the documentation as part of the deliverable, not an afterthought.

Validation was where it got real. I executed disciplined QA and UAT practices to confirm the configurations matched the requirements, and I documented reproduction steps for the complex bugs we found. The drills themselves were the ultimate test of the business need, and the program sustained 45+ annual resilience drills, hit a 94% recovery rate within 4 months, and surfaced critical hardware defects before they could cause real outages. That outcome told me the workflow actually did what the business needed, not just what the spec said.

## Tell us about a time during a project delivery when you realized a deadline was at risk due to a technical blocker or a change in scope. How did you communicate this to stakeholders?

During one of the cross-org recovery executions I facilitated, I served as bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract. Partway in, we hit a sequencing dependency across data flows that wasn't going to resolve in time for the original window. That was a technical blocker with high visibility, since this was under executive attention.

My instinct was to surface it early rather than hope it would close on its own. I went back to the stakeholders quickly with a clear picture: what the blocker was, what it impacted, the sequencing risk it introduced, and the realistic options for the timeline. I kept it factual and tied each option to consequences so leadership could make a call instead of just hearing a problem.

Because I raised it proactively and brought the reproduction steps and the dependency map with me, the conversation stayed focused on the decision instead of blame. We adjusted the plan, kept the contract-critical test on track, and I documented the decisions so nothing got lost in the handoff. Surfacing blockers early and showing up with options instead of just bad news is how I keep stakeholders trusting the delivery.
