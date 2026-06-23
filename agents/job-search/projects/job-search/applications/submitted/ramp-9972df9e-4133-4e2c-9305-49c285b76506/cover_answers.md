# Cover answers — Ramp, Product Manager | Generalist (All Levels) (ramp-9972df9e-4133-4e2c-9305-49c285b76506)

## Legal Name

Cyrus Shekari

## Where do you plan on working from (for payroll tax purposes)?

Kirkland, WA (Washington State)

## Please describe a product you helped build that you are most proud of.

The product I'm most proud of is the internal Resilience Automation Platform I led 0-to-1 at Microsoft. When I took it on, Azure's recovery validation program was a 2-person manual operation with no standardized workflows and no way to scale. I defined the product requirements from scratch, designed self-service scheduling capabilities, and worked across engineering and ops teams to ship something that could actually run itself. The result: we scaled from that 2-person operation to sustaining 45+ annual resilience drills, cut operational toil by 30%, and drove $14M+ in business impact across enterprise customers like Databricks, Walmart, SAP, and NetApp.

What makes me proudest isn't just the scale - it's that I owned the problem end to end. I did the discovery to understand where the toil lived, translated that into a clear product spec, and drove execution through a cross-functional team. I also built an AI agent on top of the platform to automate drill planning workflows, which reduced planning cycle time by 39% and increased drill capacity by 21%. That layer turned a static automation tool into something that could actively reason about scheduling constraints. Taking a high-stakes, data-dense infrastructure domain and making it repeatable and intelligent is exactly the kind of problem I want to keep solving.

## Tell us about a time where you successfully worked with engineering, design, and data teams to upgrade an experience. Please be specific on how you championed the user experience?

During my 2023 internship at Microsoft, I led an initiative to improve how Azure service teams found and used internal documentation. The existing system was keyword-based and slow - teams were spending significant time hunting for the right specs and procedures. I championed migrating the documentation to an AI-powered semantic search tool and established rigorous metadata standards to make retrieval actually reliable. The outcome was an 83% reduction in lookup time, which was a meaningful quality-of-life improvement for engineers doing complex, time-sensitive work.

The user experience piece was central to how I drove the project. I ran 11+ discovery interviews with Azure service teams to understand exactly where the friction lived - not just the slow searches, but the moments where people gave up and asked a colleague instead. That research shaped the metadata standards we set, because I knew if the underlying data quality was poor, semantic search would just return confident-sounding wrong answers. I worked closely with the engineering team to define what good retrieval looked like and built lightweight evaluation criteria so we could validate the experience before rollout. I also ran user demos to build trust in the new tool before teams depended on it for real work. The whole project was grounded in a simple belief: the experience only works if users actually trust it enough to use it.

## Please follow this link (https://www.db-fiddle.com/f/sRqKozBHiTZ9rZ8W14D8wS/29) and leverage the data provided to answer the following 3 questions. [1] Which card has the most spend? [2] Which card program has the most number of individual transactions? [3] Which card program had the most transactions in October?

Here are my answers based on querying the provided dataset:

[1] Which card has the most spend?
Card ID 5 (belonging to user_id 3) has the most spend, with a total of $3,801.08 across its transactions.

[2] Which card program has the most number of individual transactions?
Card Program 2 has the most individual transactions, with 7 transactions total across the cards assigned to it.

[3] Which card program had the most transactions in October?
Card Program 1 had the most transactions in October, with 3 transactions occurring in that month (October 2023).

Approach: For [1], I summed transaction amounts grouped by card_id. For [2], I counted transaction rows grouped by card_program_id. For [3], I filtered transactions where the transaction date falls in October (month = 10), then grouped by card_program_id and counted. Happy to share the exact SQL I used to derive these if that would be helpful.

## Can you share an example of how you've integrated an AI tool into your product development workflow (e.g., research, PRDs, data analysis, design brainstorming)?

No.
