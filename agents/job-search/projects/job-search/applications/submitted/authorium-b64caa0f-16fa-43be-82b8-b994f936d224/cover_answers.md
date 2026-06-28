# Cover answers — Authorium, Associate Solutions Engineer (authorium-b64caa0f-16fa-43be-82b8-b994f936d224)

## Full Name

Cyrus Shekari

## Describe a time when a customer asked you to configure a solution in a way that you knew was inefficient or unscalable. How did you guide them toward a better decision without damaging the relationship?

At Microsoft, stakeholders across our Azure resilience program initially wanted each of the 45+ annual drills to be planned and scheduled manually, with custom one-off documentation for every engagement. It made sense from their perspective - they wanted full control and visibility into each event. But I could see that approach would break down fast as we scaled, and it was already creating inconsistency across drill records.

Rather than pushing back directly, I started by validating what they cared about most: visibility, accuracy, and control. Then I showed them how a standardized workflow configuration and shared playbook structure could actually give them more of those things, not less. I built out a working prototype of the standardized model and walked them through a side-by-side comparison - what the manual approach looked like at 10 drills versus 45. Once they saw the operational math, the conversation shifted from 'why change' to 'how do we get there.'

The outcome was the 0-to-1 Resilience Automation Platform I ended up owning end-to-end. It reduced operational toil by 30% and transitioned the program to a repeatable, scalable model. The key was framing the better design in terms of their goals, not mine - and giving them something concrete to react to rather than just a recommendation on paper.

## Walk us through a specific complex workflow or process you owned from discovery to configuration. How did you document the logic, and how did you validate that it actually met the business need?

The clearest example is Azure's rack-level drill program, which I built from scratch in four months. Discovery started with structured sessions across infrastructure, operations, and engineering teams to understand what a successful recovery actually looked like at the rack level - what signals indicated pass or fail, what dependencies existed between hardware and software layers, and what had never been formally tested before. I documented each of those requirements explicitly, mapping the conditional logic of how a drill would execute: if a rack is isolated, then recovery triggers in this sequence, else escalation follows this path.

From there I translated that logic into workflow configurations and execution playbooks, making sure every step had a defined owner, a validation checkpoint, and a documented expected outcome. I maintained an as-built record throughout so that any deviation from the original design was captured and explained, not just patched over.

Validation came through disciplined QA execution. I ran UAT scripts against each configuration before any live drill, documented reproduction steps for anything that didn't behave as expected, and tracked defect resolution before sign-off. The final program achieved a 94% recovery rate across launch and surfaced critical hardware defects before they reached customers. That outcome was the confirmation the configuration actually met the business need - not just that it worked in a test environment, but that it held up under real conditions with real stakes.

## Tell us about a time during a project delivery when you realized a deadline was at risk due to a technical blocker or a change in scope. How did you communicate this to stakeholders?

During a sovereign-cloud network isolation test tied to a large enterprise contract at Microsoft, we hit a technical blocker mid-execution: a dependency on a third-party network configuration that hadn't been validated for our isolation scenario. The timeline was tight and the executive visibility on this one was high, so I knew the worst thing I could do was wait and see if it resolved itself.

I surfaced the blocker the same day I identified it - first to my immediate lead with a clear description of the issue, what I had already tried, and my best estimate of the blast radius if it didn't resolve within 24 hours. Then I helped prepare a concise stakeholder update that framed the situation honestly: here is what we know, here is what we are doing to resolve it, and here are the two most likely outcomes with their timeline implications. I avoided vague language like 'we might be delayed' and instead gave them a decision point - if we can't validate the dependency by a specific date, we need to evaluate a scope adjustment.

The blocker was resolved within the window, and the execution stayed on schedule. But the stakeholders told me afterward that the early, structured communication was what kept their confidence intact. That stuck with me - when a deadline is at risk, people need clarity and options, not reassurance.
