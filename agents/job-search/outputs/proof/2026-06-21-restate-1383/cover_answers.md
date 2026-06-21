# Cover answers — Restate, Solutions Engineer (restate-c9419551-7f51-4691-8ba9-d80a27f1e284)

## Full Name

Cyrus Shekari

## Tell us about a time you helped a customer  go from early POC to successful production. What were the hardest blockers, and what did you do to unblock them?

At Microsoft I drove technical adoption of Azure's recovery validation platform from PoC to production for enterprise customers like Databricks, Walmart, SAP, and NetApp. The early PoCs proved the validation logic worked, but "it works in a demo" is a long way from "it runs safely in production against a customer's critical workloads." My job was to close that gap and standardize production-ready workflows that now sustain 45+ annual resilience drills and drove $14M+ in business impact.

The hardest blockers were rarely the core capability. They showed up at the edges: Kubernetes and cloud setup that differed per customer, observability gaps where a failed drill gave us no signal on why it failed, and networking and security constraints. The toughest single case was a sovereign-cloud network isolation and security test tied to a $1.5B+ Tier-1 enterprise contract, where strict networking and compliance rules meant the standard rollout path didn't apply at all. I served as bridge lead there, working hands-on with partner engineers to map the isolation requirements, get the right observability in place, and define a deployment pattern that satisfied the constraints without weakening the test.

The way I unblocked things was to stop treating each customer escalation as a one-off. I owned post-deployment escalation and on-call response, so I partnered directly with partner engineers on the Kubernetes, observability, and cloud setup that kept tripping people up, then fed the recurring friction back into the product. That became a 0-to-1 internal Resilience Automation Platform with self-service deployment patterns that cut operational toil 30% and let engineers adopt the workflow without hand-holding. The lesson I carry into a role like this one: the path from PoC to production is mostly about turning repeated, painful blockers into reusable known-good patterns so the next customer never hits them.
