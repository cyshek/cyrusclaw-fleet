# Cover answers — Lance, Product Manager (lance-294e2602-725c-4d84-a7a0-a1fc602acec8)

## Full Name

Cyrus Shekari

## Where are you currently located?

Kirkland, WA, in the Seattle area. I'm open to relocating to San Francisco for this role.

## When can you start?

Two weeks from an offer. I'd give my current team a standard two-week notice and then be ready to go.

## At Lance, our mission is to automate hotel operations. We believe this starts with our own work. Describe a manual, broken, or low-value process from a previous role that you found frustrating. Then, briefly outline the system or tool you would build to eliminate it entirely.

At Microsoft, recovery validation drills were run as a manual, person-dependent effort. Planning each drill meant chasing down dependencies across teams, hand-coordinating schedules, and rebuilding the same context every cycle. It didn't scale, it ate a huge amount of time, and the quality of any given drill depended on who happened to be running it. With 45+ drills a year on the line, that was a real bottleneck.

So I led the 0→1 build of an internal Resilience Automation Platform. I started with user research to understand where the actual toil lived, then built self-service scheduling and codified the planning workflow so teams could spin up drills without a coordinator in the loop. That cut operational toil 30% and moved us off the manual model. I also built an internal AI agent to restructure the planning steps, which cut planning cycle time 39% and grew drill capacity 21%.

For a hotel operations equivalent, I'd attack the repetitive coordination work the same way: map where staff are doing manual lookups and handoffs across systems, then build an agent layer that sits on top of the existing software, pulls the context automatically, and makes the routine decisions end-to-end. The pattern is the same one I've already shipped, surface the toil, codify the workflow, then hand the repetitive execution to an agent so people only touch the cases that genuinely need judgment.
