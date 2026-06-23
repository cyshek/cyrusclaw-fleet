# Cover answers — Fluidstack, Product Manager, Data Centers and Tooling (fluidstack-49b1ab6b-d27d-4002-9dbd-89938df3d5ce)

## Full Name

Cyrus Shekari

## Tell us about something you've built/done that you think is genuinely cool, big or small, work or personal.

At Microsoft, I built Azure's first rack-level proactive validation program from scratch. The idea came from noticing that our reactive incident response model meant we were always catching hardware failures after they'd already caused customer impact. I defined the requirements for continuous infrastructure monitoring at the rack level, worked with engineering to surface defect signals early, and operationalized a workflow that could act on those signals before outages occurred. Within four months, we hit a 94% recovery rate on identified defects, and the program became a model for how Azure approaches proactive hardware reliability.

What I find genuinely cool about it is that it's one of those rare products where the value is invisible when it's working - customers never see the outage that didn't happen. Designing for that kind of negative outcome, and then figuring out how to measure success when success is absence of failure, was a real product challenge. Building the MTTR dashboards and uptime SLA tracking on top of it so leadership could actually quantify the business impact made it feel complete. It's the kind of infrastructure-layer work that doesn't get a lot of fanfare but quietly keeps things running at scale.
