# Cover answers — Mdcalc, Product Analyst (mdcalc-0ac0c07a-7963-4b68-8819-8f7f85503309)

## Full Name

Cyrus Shekari

## Describe a project where you owned a product or feature from problem definition through launch and post-launch measurement. What were you trying to improve, what did you build, and what decisions did you personally make?

At Microsoft, I owned the 0-to-1 build of Azure's Resilience Automation Platform from the ground up. The problem was clear but messy: the team was running resilience drills manually, the process didn't scale, and there was no structured way for engineering teams to self-serve or schedule their own tests. I started by defining the problem space - talking to engineering teams, mapping where toil was highest, and identifying that the biggest gap was the absence of any scheduling or workflow layer. From there I wrote the requirements, scoped the self-service scheduling workflows, and made the call to prioritize a phased delivery model rather than trying to ship everything at once.

The build decisions I owned directly included which workflows to automate first, how to instrument execution flows so we could measure activation and usage post-launch, and where to draw scope boundaries to ship fast without breaking existing drill operations. I also made the judgment call to invest early in a rack-level drill capability that hadn't existed before - that shipped in 4 months with a 94% recovery rate. Post-launch, I tracked the outcomes against the metrics I had defined upfront: operational toil reduction, drill volume, and business impact. The platform ultimately cut operational toil by 30%, scaled the program from 2 people to 45+ annual drills, and sustained $14M+ in documented business impact across enterprise customers including Databricks, Walmart, and SAP. The measurement loop wasn't an afterthought - I had instrumented the flows specifically so I could identify gaps after launch and drive the next round of iteration.
