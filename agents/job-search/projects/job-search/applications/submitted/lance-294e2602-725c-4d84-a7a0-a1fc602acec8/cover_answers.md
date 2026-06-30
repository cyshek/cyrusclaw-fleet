# Cover answers — Lance, Product Manager (lance-294e2602-725c-4d84-a7a0-a1fc602acec8)

## Full Name

Cyrus Shekari

## Where are you currently located?

Kirkland, WA (Seattle metro). I'm open to relocating to San Francisco for the right role.

## When can you start?

Two weeks from offer acceptance.

## At Lance, our mission is to automate hotel operations. We believe this starts with our own work. Describe a manual, broken, or low-value process from a previous role that you found frustrating. Then, briefly outline the system or tool you would build to eliminate it entirely.

At Microsoft, scheduling and coordinating recovery drills was almost entirely manual. Every cycle meant tracking down engineers across multiple teams, wrangling calendar availability, filling out the same planning documents by hand, and chasing down status updates via email and Teams threads. The whole process was fragile, person-dependent, and ate up a disproportionate share of the team's time before a single drill actually ran. It was the kind of low-value coordination work that obscured the high-value resilience engineering underneath it.

I built the foundation of what became our internal Resilience Automation Platform to address exactly this. The core idea was a self-service scheduling layer where teams could register drill parameters, dependencies, and availability constraints themselves, rather than routing everything through a central coordinator. Automated conflict detection, pre-populated templates, and status dashboards replaced the manual back-and-forth. The result was a 30% reduction in operational toil and a 21% increase in drill capacity without adding headcount.

The system I'd build to eliminate it entirely would go further: a workflow engine that ingests team availability via calendar APIs, auto-generates scheduling options, routes approvals programmatically, and surfaces a live status board that updates without anyone manually touching it. The coordinator role shifts from logistics manager to exception handler, which is where human judgment actually adds value. That same philosophy maps directly to what Lance is doing for hotel ops, replacing reactive, manual coordination loops with systems that just run.
