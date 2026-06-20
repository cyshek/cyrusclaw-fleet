# Cover answers — Anara, Technical Product Manager (anara-f69dcabe-1f30-46ce-8407-ba03f55f2ced)

## Full Name

Cyrus Shekari

## Write a short note on a project you’re most proud of

The project I'm proudest of is the rack-level resilience drill program I built and shipped at Microsoft. Azure had no proactive way to test recovery at the hardware level, so I went from idea to production in 4 months, owning discovery, requirements, and the rollout. We hit a 94% recovery rate, surfaced critical hardware defects that would have caused real outages, and set a new continuous-validation standard the org now runs against. It started as a gap I noticed and turned into a capability that didn't exist before.

What made it satisfying was that none of it was theoretical. I did the discovery through partner interviews and workflow debugging, sat with the engineering team to figure out what was actually feasible, then made the calls on scope so we could ship fast instead of designing forever. The first version was scrappy, and we tightened it as real drills exposed where the friction was. That loop of build, learn from real usage, and cut the friction is how I like to work.

The part I keep coming back to is that it shifted how people operated. Recovery validation went from a manual, 2-person effort into a platformized system sustaining 45+ drills a year, and the impact landed on real R&D teams like Databricks, Walmart, SAP, and NetApp. Building something technical that genuinely changes how a serious group of people does their work is exactly the kind of problem I want to keep chasing.
