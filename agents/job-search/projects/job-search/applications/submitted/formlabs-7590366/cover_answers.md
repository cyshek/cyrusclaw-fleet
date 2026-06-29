# Cover answers — Formlabs, Solutions Architect - Digital Systems (formlabs-7590366)

## Please describe your most complex project.

The most complex project I've worked on was the sovereign-cloud network isolation test at Microsoft, tied to a $1.5B+ enterprise contract. The core challenge wasn't just technical, it was orchestrating 14 cross-org recovery executions across globally distributed systems under direct executive visibility, where failure wasn't really an option.

On the technical side, I had to map integration dependencies across multiple enterprise platforms and define a sequencing architecture that could handle network isolation without cascading failures across the distributed environment. That meant working through every failure mode in advance, establishing clear recovery checkpoints, and building coordination patterns that 14 different teams could actually execute reliably under pressure. At the same time, I was managing stakeholder communication across organizations that had different priorities, timelines, and definitions of success.

What made it genuinely complex, beyond the scale, was the constraint that we couldn't rehearse the full scenario end-to-end before the real execution. That forced me to invest heavily in the architecture upfront, making hard trade-off calls on isolation boundaries and recovery sequencing early, then holding those decisions even as teams pushed back. That experience shaped how I think about integration governance now: get the architectural decisions right early, document the reasoning clearly, and give teams enough structure that execution can succeed even when things don't go exactly as planned.
